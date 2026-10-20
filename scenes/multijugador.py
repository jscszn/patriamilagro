"""Escenas del modo multijugador local (cliente-servidor con sockets, 2 a 4 jugadores).

SalaScene        crear una partida (arranca el servidor en este equipo) o unirse a una por IP;
                 en la sala cada jugador elige su ROL y marca LISTO.
PartidaRedScene  dibuja la fase que diga el servidor: informe, nivel, votación, resultado y final.

El cliente no decide nada: envía botones, votos y "listo", y dibuja la instantánea que le
llega. Las reglas están en net/sesion.py.
"""
from __future__ import annotations

import getpass

import pygame

import input_manager as im
import settings
from audio import gestor as audio
from core.decision_tree import CAPTURAR, EXTRADITAR, LIBERAR
from core.game_state import EstadoJuego
from core.decision_tree import CATEGORIAS
from core.mapa import NOMBRE_RUTA, Mapa
from net import sesion as ss
from net.cliente import Cliente
from net.protocolo import PUERTO, ip_local
from net.servidor import Servidor
from render.grafo_visual import dibujar_mapa
from render.hud import dibujar_barras_opinion
from render.texto import dibujar_parrafo, dibujar_texto
from render.ui import ListaOpciones, dibujar_marco
from scenes.base import Scene
from scenes.level import LevelScene

C = settings.COLORES
ROLES = settings.ROLES
DECISIONES = [(CAPTURAR, "CAPTURAR"), (EXTRADITAR, "EXTRADITAR"), (LIBERAR, "DEJAR LIBRE")]
SELLOS = {CAPTURAR: "¡CAPTURADO!", EXTRADITAR: "¡EXTRADITADO!", LIBERAR: "LIBERADO..."}
ACCIONES_DE_JUEGO = (im.IZQUIERDA, im.DERECHA, im.ARRIBA, im.ABAJO, im.SALTAR, im.DISPARAR)


def _fila_jugadores(sup, jugadores, y: int, id_local: int, marca: str = "listo") -> None:
    """Una casilla por jugador con su número, rol y una marca (listo / ya votó)."""
    ancho = 240 // max(1, len(jugadores))
    for i, j in enumerate(jugadores):
        x = 8 + i * ancho
        color = ROLES[j["rol"]]["color"] if j["conectado"] else C["gris_oscuro"]
        dibujar_texto(sup, f"{j['id']}P {ROLES[j['rol']]['nombre'][:7]}", (x, y), color, sombra=False)
        hecho = j.get(marca)
        pygame.draw.rect(sup, C["verde"] if hecho else C["gris_oscuro"], (x, y + 10, ancho - 6, 3))
        if j["id"] == id_local:
            pygame.draw.rect(sup, C["blanco"], (x - 2, y - 2, ancho - 2, 17), 1)


# =============================================================================
# Sala: crear, unirse y elegir rol
# =============================================================================
class SalaScene(Scene):
    def __init__(self, juego, aviso: str = "", **datos):
        super().__init__(juego, **datos)
        self.aviso = aviso
        self.tiempo = 0.0
        self.ip = "127.0.0.1"
        self.menu = ListaOpciones(["CREAR PARTIDA", "UNIRSE A UNA PARTIDA", "VOLVER"])
        self.acciones_sala = ListaOpciones(["LISTO", "SALIR"])
        self.ip_local = ip_local()
        # Si se vuelve de una partida con la conexión viva, se entra directo a la sala
        self.modo = "sala" if juego.cliente is not None and juego.cliente.conectado else "menu"
        audio.musica("menu")

    @property
    def cliente(self) -> Cliente:
        return self.juego.cliente

    # --- Conexión ------------------------------------------------------------------------------
    def _crear(self) -> None:
        try:
            self.juego.servidor = Servidor(PUERTO)
        except OSError:
            self.aviso = f"EL PUERTO {PUERTO} ESTÁ OCUPADO: ¿YA HAY UN SERVIDOR?"
            return
        self.juego.servidor.sesion.en_arena = self.juego.arena
        self.juego.servidor.iniciar_en_hilo()
        self._unirse("127.0.0.1")

    def _unirse(self, direccion: str) -> None:
        self.juego.cliente = Cliente()
        if self.juego.cliente.conectar(direccion, getpass.getuser()):
            self.modo, self.aviso = "sala", ""
        else:
            self.aviso = self.juego.cliente.error
            self.juego.cerrar_red()
            self.modo = "menu"

    def _salir(self, aviso: str = "") -> None:
        self.juego.cerrar_red()
        self.modo, self.aviso = "menu", aviso

    # --- Lógica --------------------------------------------------------------------------------
    def handle_events(self, eventos):
        if self.modo != "ip":
            return
        for e in eventos:                                  # se escribe la IP con el teclado
            if e.type != pygame.KEYDOWN:
                continue
            if e.key == pygame.K_BACKSPACE:
                self.ip = self.ip[:-1]
            elif e.key in (pygame.K_RETURN, pygame.K_KP_ENTER) and self.ip:
                self._unirse(self.ip)
            elif e.key == pygame.K_ESCAPE:
                self.modo = "menu"
            elif e.unicode and e.unicode in "0123456789." and len(self.ip) < 15:
                self.ip += e.unicode

    def update(self, dt, acciones):
        self.tiempo += dt
        entrada = acciones[settings.JUGADOR_LOCAL]
        if self.modo == "menu":
            if entrada.pulso(im.CANCELAR):
                self.juego.escenas.cambiar("menu")
            elif self.menu.update(dt, entrada):
                if self.menu.seleccion == "CREAR PARTIDA":
                    self._crear()
                elif self.menu.seleccion == "UNIRSE A UNA PARTIDA":
                    self.modo, self.aviso = "ip", ""
                else:
                    self.juego.escenas.cambiar("menu")
        elif self.modo == "sala":                          # en modo "ip" todo llega por handle_events
            self._actualizar_sala(dt, entrada)

    def _actualizar_sala(self, dt: float, entrada) -> None:
        c = self.cliente
        c.actualizar()
        if c.error or not c.conectado:
            self._salir(c.error or "SE PERDIÓ LA CONEXIÓN")
            return
        if c.estado is None or c.id is None:
            return
        if c.estado["fase"] != ss.SALA:                    # el anfitrión empezó la partida
            self.juego.escenas.cambiar("partida_red")
            return
        yo = next((j for j in c.estado["jugadores"] if j["id"] == c.id), None)
        if yo is None:
            return
        soy_anfitrion = c.estado["anfitrion"] == c.id
        self.acciones_sala.opciones = ["NO ESTOY LISTO" if yo["listo"] else "LISTO"] + \
            (["EMPEZAR PARTIDA"] if soy_anfitrion else []) + ["SALIR"]
        self.acciones_sala.indice = min(self.acciones_sala.indice, len(self.acciones_sala.opciones) - 1)
        if not yo["listo"]:                                # izquierda/derecha: cambiar de rol
            paso = int(entrada.pulso(im.DERECHA)) - int(entrada.pulso(im.IZQUIERDA))
            if paso:
                orden = settings.ORDEN_ROLES
                libres = [r for r in orden if r == yo["rol"] or r not in {j["rol"] for j in c.estado["jugadores"]}]
                c.enviar("rol", rol=libres[(libres.index(yo["rol"]) + paso) % len(libres)])
                audio.efecto("mover")
        if self.acciones_sala.update(dt, entrada):
            eleccion = self.acciones_sala.seleccion
            if eleccion == "SALIR":
                self._salir()
            elif eleccion == "EMPEZAR PARTIDA":
                c.enviar("empezar")
            else:
                c.enviar("listo", listo=not yo["listo"])

    # --- Dibujo --------------------------------------------------------------------------------
    def draw(self, sup):
        sup.fill((8, 8, 32))
        dibujar_texto(sup, "MULTIJUGADOR", (128, 8), C["amarillo"], 2, centrado=True)
        if self.modo == "menu":
            dibujar_parrafo(sup, "De 2 a 4 jugadores en la misma red. Uno CREA la partida y los demás se UNEN "
                                 "escribiendo su dirección IP.", (20, 36), 216, C["blanco"])
            self.menu.draw(sup, 128, 92)
            dibujar_texto(sup, f"TU IP: {self.ip_local}   PUERTO: {PUERTO}", (128, 150), C["cian"], centrado=True)
        elif self.modo == "ip":
            dibujar_texto(sup, "IP DEL ANFITRIÓN", (128, 60), C["blanco"], centrado=True)
            caja = pygame.Rect(48, 78, 160, 20)
            dibujar_marco(sup, caja)
            cursor = "_" if int(self.tiempo * 2) % 2 == 0 else " "
            dibujar_texto(sup, self.ip + cursor, (128, 84), C["amarillo"], centrado=True)
            dibujar_texto(sup, "NÚMEROS Y PUNTO: ESCRIBIR", (128, 112), C["gris"], centrado=True)
            dibujar_texto(sup, "ENTER: CONECTAR   ESC: VOLVER", (128, 124), C["gris"], centrado=True)
        else:
            self._dibujar_sala(sup)
        if self.aviso:
            dibujar_parrafo(sup, self.aviso, (12, 196), 232, C["rojo"])

    def _dibujar_sala(self, sup):
        c = self.cliente
        if c is None or c.estado is None or c.id is None:
            dibujar_texto(sup, "CONECTANDO...", (128, 100), C["blanco"], centrado=True)
            return
        e = c.estado
        dibujar_texto(sup, f"SALA EN {self.ip_local}" if self.juego.servidor else "CONECTADO A LA SALA",
                      (128, 30), C["cian"], centrado=True)
        for i, j in enumerate(e["jugadores"]):
            y = 44 + i * 26
            rol = ROLES[j["rol"]]
            caja = pygame.Rect(8, y, 240, 24)
            dibujar_marco(sup, caja, fondo=(20, 20, 50) if j["id"] == c.id else (0, 0, 40),
                          borde=rol["color"] if j["id"] == c.id else C["gris"])
            anfitrion = " (ANFITRIÓN)" if j["id"] == e["anfitrion"] else ""
            dibujar_texto(sup, f"{j['id']}P {j['nombre']}{anfitrion}", (14, y + 2), C["blanco"])
            dibujar_texto(sup, "LISTO" if j["listo"] else "ELIGIENDO", (242, y + 2),
                          C["verde"] if j["listo"] else C["gris"], derecha=True)
            flechas = "< " + rol["nombre"] + " >" if j["id"] == c.id and not j["listo"] else rol["nombre"]
            dibujar_texto(sup, flechas, (14, y + 12), rol["color"])
            dibujar_texto(sup, f"{rol['salud']} CORAZONES  VOTO X{rol['voto']}", (242, y + 12), C["gris"],
                          derecha=True, sombra=False)
        yo = next((j for j in e["jugadores"] if j["id"] == c.id), None)
        if yo is not None:
            dibujar_parrafo(sup, ROLES[yo["rol"]]["habilidad"].upper(), (12, 150), 232, ROLES[yo["rol"]]["color"],
                            interlineado=0)
        self.acciones_sala.draw(sup, 128, 172, separacion=11)
        faltan = max(0, e["minimo"] - len(e["jugadores"]))
        if faltan:
            dibujar_texto(sup, f"FALTAN {faltan} JUGADORES", (128, 208), C["naranja"], centrado=True)
        elif e.get("aviso"):
            dibujar_texto(sup, e["aviso"][:40], (128, 208), C["naranja"], centrado=True)


# =============================================================================
# Nivel dibujado a partir de las instantáneas del servidor
# =============================================================================
class VistaNivel(LevelScene):
    """La misma escena de nivel, pero su estado NO se simula aquí: llega del servidor."""

    def __init__(self, juego, mundo: dict, id_local: int):
        Scene.__init__(self, juego)
        self._id_local = id_local
        self.numero = mundo["numero_nivel"]
        self.partida = None
        self.inicio = {}
        self.estado = EstadoJuego.from_dict(mundo)
        self.preparar_vista(self.numero)

    @property
    def id_local(self) -> int:
        return self._id_local

    def aplicar(self, mundo: dict, eventos: list, dt: float) -> None:
        self.estado = EstadoJuego.from_dict(mundo)
        self.tiempo += dt
        for evento in eventos:
            self._procesar_evento(evento)
        self._actualizar_tutorial(dt)
        self._actualizar_efectos(dt)


# =============================================================================
# Partida en red: una pantalla por fase
# =============================================================================
class PartidaRedScene(Scene):
    def __init__(self, juego, **datos):
        super().__init__(juego, **datos)
        self.cliente: Cliente = juego.cliente
        self.fase = None
        self.t_local = 0.0            # segundos desde que empezó la fase (para animaciones)
        self.tiempo = 0.0
        self.indice = 0               # opción elegida en la votación
        self.pagina = 0
        self.enviado = False          # ya mandó su voto / listo en esta fase
        self.vista: VistaNivel = None
        self._acciones_enviadas = None
        self._cache_mapa = (None, None)

    # --- Lógica --------------------------------------------------------------------------------
    def update(self, dt, acciones):
        self.tiempo += dt
        self.t_local += dt
        c = self.cliente
        if c is not None:
            c.actualizar()
        if c is None or c.error or not c.conectado or c.estado is None:
            aviso = (c.error if c else "") or "SE PERDIÓ LA CONEXIÓN"
            self.juego.cerrar_red()
            self.juego.escenas.cambiar("sala", aviso=aviso)
            return
        e = c.estado
        if e["fase"] != self.fase:
            self._entrar(e["fase"])
        entrada = acciones[settings.JUGADOR_LOCAL]
        if self.fase == ss.SALA:
            self.juego.escenas.cambiar("sala")
        elif self.fase == ss.NIVEL:
            self._nivel(dt, entrada, e)
        elif self.fase == ss.INFORME:
            if entrada.pulso(im.DERECHA) or entrada.pulso(im.IZQUIERDA):
                self.pagina, self.t_local = 1 - self.pagina, 0.5
            claves = list(e["datos"]["rutas"])
            if self.pagina == 1 and e["anfitrion"] == c.id and len(claves) > 1 and not self.enviado \
                    and (entrada.pulso(im.ARRIBA) or entrada.pulso(im.ABAJO)):
                c.enviar("ruta", clave=claves[(claves.index(e["datos"]["clave"]) + 1) % len(claves)])
                audio.efecto("mover")
            self._listo_con_confirmar(entrada)
        elif self.fase == ss.VOTACION:
            self._elegir(entrada, len(DECISIONES))
            if entrada.pulso(im.CONFIRMAR):
                c.enviar("voto", decision=DECISIONES[self.indice][0])
                self.enviado = True
                audio.efecto("sello")
        elif self.fase == ss.RESULTADO:
            self._listo_con_confirmar(entrada)
        elif self.fase == ss.FINAL:
            if entrada.pulso(im.CONFIRMAR) and e["anfitrion"] == c.id and self.t_local > 1.5:
                c.enviar("sala")
            elif entrada.pulso(im.CANCELAR) and self.t_local > 1.5:
                self.juego.cerrar_red()
                self.juego.escenas.cambiar("menu")

    def _entrar(self, fase: str) -> None:
        self.fase, self.t_local, self.indice, self.pagina, self.enviado = fase, 0.0, 0, 0, False
        self._acciones_enviadas = None
        if fase != ss.NIVEL:
            self.vista = None
        musica = {ss.INFORME: "decision", ss.VOTACION: "decision", ss.RESULTADO: "noticias", ss.FINAL: "final"}
        if fase == ss.RESULTADO:
            audio.efecto("sello")
        if fase == ss.FINAL and not self.cliente.estado["datos"].get("derrota"):
            audio.presentar("bienvenida", "final")
        elif fase in musica:
            audio.musica(musica[fase])

    def _elegir(self, entrada, cantidad: int) -> None:
        paso = int(entrada.pulso(im.DERECHA) or entrada.pulso(im.ABAJO)) - \
            int(entrada.pulso(im.IZQUIERDA) or entrada.pulso(im.ARRIBA))
        if paso:
            self.indice = (self.indice + paso) % cantidad
            audio.efecto("mover")

    def _listo_con_confirmar(self, entrada) -> None:
        if entrada.pulso(im.CONFIRMAR) and not self.enviado and self.t_local > 0.4:
            self.cliente.enviar("listo")
            self.enviado = True
            audio.efecto("confirmar")

    def _nivel(self, dt: float, entrada, e: dict) -> None:
        mundo = e.get("mundo")
        if mundo is None:
            return
        # Se manda solo cuando cambia algo: lo mantenido sigue vigente en el servidor
        mantenidas = sorted(a for a in ACCIONES_DE_JUEGO if entrada.mantiene(a))
        pulsadas = sorted(a for a in ACCIONES_DE_JUEGO if entrada.pulso(a))
        if pulsadas or mantenidas != self._acciones_enviadas:
            self.cliente.enviar("acciones", m=mantenidas, p=pulsadas)
            self._acciones_enviadas = mantenidas
        eventos, self.cliente.eventos = self.cliente.eventos, []
        if self.vista is None or self.vista.numero != mundo["numero_nivel"]:
            self.vista = VistaNivel(self.juego, mundo, self.cliente.id)
        self.vista.aplicar(mundo, eventos, dt)
        if entrada.pulso(im.AYUDA):
            self.juego.escenas.apilar("ayuda", superpuesta=True)

    # --- Dibujo --------------------------------------------------------------------------------
    def draw(self, sup):
        c = self.cliente
        if c is None or c.estado is None or self.fase is None:
            sup.fill((8, 8, 32))
            dibujar_texto(sup, "ESPERANDO AL SERVIDOR...", (128, 100), C["blanco"], centrado=True)
            return
        e = c.estado
        if self.fase == ss.NIVEL:
            if self.vista is not None:
                self.vista.draw(sup)
            return
        sup.fill((10, 10, 26))
        dibujo = {ss.INFORME: self._informe, ss.VOTACION: self._votacion, ss.RESULTADO: self._resultado,
                  ss.FINAL: self._final}.get(self.fase)
        if dibujo:
            dibujo(sup, e, e["datos"])

    def _pie(self, sup, e: dict, texto: str, marca: str = "listo") -> None:
        _fila_jugadores(sup, e["jugadores"], 192, self.cliente.id, marca)
        if int(self.tiempo * 2) % 2 == 0 or self.enviado:
            dibujar_texto(sup, "ESPERANDO A LOS DEMÁS..." if self.enviado else texto, (128, 212), C["blanco"],
                          centrado=True)

    def _informe(self, sup, e, d):
        dibujar_texto(sup, f"NIVEL {d['nivel']}: {d['nombre']}", (8, 3), C["amarillo"])
        dibujar_texto(sup, "LA RUTA" if self.pagina else "LOS DAÑOS", (248, 3), C["cian"], derecha=True)
        area = pygame.Rect(8, 13, 240, 86)
        dibujar_marco(sup, area, fondo=(16, 20, 40))
        mapa = self._mapa(d)
        elegida = d["rutas"][d["clave"]]
        if self.pagina == 0:
            dibujar_mapa(sup, mapa, area.inflate(-8, -8), d["nivel"], olas=d["olas"],
                         olas_visibles=1 + int(self.t_local / 0.9), tiempo=self.tiempo)
        else:
            alterna = [r["camino"] for clave, r in d["rutas"].items() if clave != d["clave"]]
            dibujar_mapa(sup, mapa, area.inflate(-8, -8), d["nivel"], ruta=elegida["camino"], tramos_ruta=9,
                         tiempo=self.tiempo, ruta_alterna=alterna[0] if alterna else ())
            dibujar_texto(sup, f"{NOMBRE_RUTA[d['clave']]}  PELIGRO {elegida['peligro']}", (14, area.bottom - 14),
                          C["blanco"], sombra=False)
        caja = pygame.Rect(8, 100, 240, 88)
        dibujar_marco(sup, caja)
        dibujar_texto(sup, d["jefe"], (14, 104), C["naranja"])
        dibujar_parrafo(sup, d["paginas"][self.pagina], (14, 116), 228, C["blanco"], interlineado=0)
        soy_anfitrion = e["anfitrion"] == self.cliente.id
        if self.pagina == 1 and len(d["rutas"]) > 1:
            pie = "ARRIBA/ABAJO: RUTA  ENTER: LISTO" if soy_anfitrion else "EL ANFITRIÓN ELIGE LA RUTA. ENTER: LISTO"
        else:
            pie = "< > PÁGINA   ENTER: LISTO"
        self._pie(sup, e, pie)

    def _mapa(self, d: dict) -> Mapa:
        if self._cache_mapa[0] != d["nivel"]:
            self._cache_mapa = (d["nivel"], Mapa.from_dict(d["mapa"]))
        return self._cache_mapa[1]

    def _botones(self, sup, opciones, y: int) -> None:
        for i, (_, texto) in enumerate(opciones):
            elegido = i == self.indice
            caja = pygame.Rect(8 + i * 82, y, 76, 18)
            pygame.draw.rect(sup, (60, 40, 10) if elegido else (24, 24, 48), caja)
            pygame.draw.rect(sup, C["amarillo"] if elegido else C["gris"], caja, 1 + elegido)
            dibujar_texto(sup, texto, (caja.centerx, caja.y + 4), C["amarillo"] if elegido else C["blanco"],
                          centrado=True)

    def _reloj(self, sup, restante: float, total: float, y: int) -> None:
        color = C["rojo"] if restante <= 5 else C["cian"]
        pygame.draw.rect(sup, C["gris_oscuro"], (8, y, 240, 4))
        pygame.draw.rect(sup, color, (8, y, int(240 * restante / total), 4))
        dibujar_texto(sup, f"TIEMPO {int(restante + 0.99)}", (248, y + 6), color, derecha=True)

    def _votacion(self, sup, e, d):
        dibujar_texto(sup, f"NIVEL {d['nivel']} SUPERADO", (128, 4), C["gris"], centrado=True)
        dibujar_texto(sup, d["jefe"], (128, 15), C["naranja"], centrado=True)
        imagen = self.juego.sprites.frame(f"jefe{d['tipo_jefe']}", "quieto", 0)
        sup.blit(imagen, imagen.get_rect(midbottom=(128, 104)))
        dibujar_texto(sup, "VOTEN: ¿QUÉ HACEMOS CON ÉL?", (128, 108), C["amarillo"], centrado=True)
        self._botones(sup, DECISIONES, 122)
        self._reloj(sup, d["restante"], settings.TIEMPO_DECISION, 146)
        dibujar_texto(sup, "EL VOTO DEL PRESIDENTE VALE DOBLE", (8, 154), C["gris"], sombra=False)
        dibujar_texto(sup, "SI NADIE VOTA, EL JEFE ESCAPA", (8, 164), C["gris"], sombra=False)
        self._pie(sup, e, "< > ELEGIR   ENTER: VOTAR", marca="voto")

    def _resultado(self, sup, e, d):
        """Qué se decidió con los votos y cómo quedó la opinión (viene del árbol del servidor)."""
        dibujar_texto(sup, f"NIVEL {d['nivel']}: {d['jefe']}", (128, 4), C["naranja"], centrado=True)
        imagen = self.juego.sprites.frame(f"jefe{d['tipo_jefe']}", "quieto", 0)
        sup.blit(imagen, imagen.get_rect(midbottom=(128, 92)))
        texto = "¡SE ESCAPÓ!" if d["escapo"] else SELLOS[d["decision"]]
        color = C["rojo"] if d["decision"] == LIBERAR else C["verde"]
        caja = pygame.Rect(0, 0, 180, 26)
        caja.center = (128, 60)
        pygame.draw.rect(sup, C["negro"], caja)
        pygame.draw.rect(sup, color, caja, 2)
        dibujar_texto(sup, texto, (128, 52), color, 2, centrado=True)
        nombres = dict(DECISIONES)
        for i, j in enumerate(e["jugadores"]):                 # el voto de cada uno
            voto = d["votos"].get(str(j["id"]), "")
            dibujar_texto(sup, f"{j['id']}P: {nombres.get(voto, 'NO VOTÓ')}", (8 + (i % 2) * 124, 98 + (i // 2) * 10),
                          ROLES[j["rol"]]["color"], sombra=False)
        dibujar_barras_opinion(sup, d["opinion"], 12, 124, ancho=120, alto=6, separacion=11)
        for i, c in enumerate(CATEGORIAS):
            cambio = d["opinion"][c] - d["opinion_antes"][c]
            if cambio:
                dibujar_texto(sup, f"{cambio:+d}", (236, 123 + i * 11), C["verde"] if cambio > 0 else C["rojo"])
        if d["cambios_mapa"]:
            dibujar_texto(sup, d["cambios_mapa"][0][:40], (128, 162), C["naranja"], centrado=True)
        self._pie(sup, e, "ENTER: LISTO")

    def _final(self, sup, e, d):
        dibujar_texto(sup, "RESULTADO DEL PAÍS", (128, 4), C["gris"], centrado=True)
        dibujar_texto(sup, d["titulo"], (128, 15), C["rojo"] if d["derrota"] else C["amarillo"], centrado=True)
        y = dibujar_parrafo(sup, d["resumen"].upper(), (12, 28), 232, C["blanco"], interlineado=0)
        dibujar_barras_opinion(sup, d["opinion"], 12, y + 6, ancho=130, alto=6, separacion=11)
        y += 46
        dibujar_texto(sup, "PUNTAJE INDIVIDUAL", (12, y), C["cian"])
        for i, fila in enumerate(d["tabla"]):
            rol = ROLES[fila["rol"]]
            yy = y + 12 + i * 11
            dibujar_texto(sup, f"{i + 1}. {fila['id']}P {fila['nombre']}", (12, yy), rol["color"])
            dibujar_texto(sup, rol["nombre"], (140, yy), C["gris"])
            dibujar_texto(sup, f"{fila['puntaje']:06d}", (244, yy), C["blanco"], derecha=True)
        if d["tabla"]:
            dibujar_texto(sup, f"MEJOR AGENTE: {d['tabla'][0]['nombre']}", (128, 186), C["amarillo"], centrado=True)
        if self.t_local > 1.5:
            soy_anfitrion = e["anfitrion"] == self.cliente.id
            dibujar_texto(sup, "ENTER: VOLVER A LA SALA" if soy_anfitrion else "ESPERANDO AL ANFITRIÓN",
                          (128, 200), C["blanco"], centrado=True)
            dibujar_texto(sup, "X / ESC: SALIR", (128, 211), C["gris"], centrado=True, sombra=False)
