"""Sesión multijugador: las REGLAS de una partida en red, sin sockets.

El servidor (net/servidor.py) solo mueve mensajes; quien decide todo es esta clase. Es
AUTORITATIVA: los clientes mandan lo que quieren hacer (botones, votos) y la sesión simula y
les devuelve el estado. Ningún cliente calcula nada del juego, así que todos ven lo mismo.

Fases:
  sala      los jugadores (2 a 4) eligen rol y marcan LISTO; el anfitrión empieza.
  informe   historia del nivel y rutas del mapa (grafo); el anfitrión elige la ruta. Sigue
            cuando todos están listos.
  nivel     la simulación (core.game_state) corre aquí con los botones de cada cliente.
  votacion  todos votan qué hacer con el jefe, con tiempo límite. El voto pesa según el rol.
  resultado qué se decidió y cómo quedó la opinión. Sigue cuando todos están listos.
  final     resultado del país (el final del árbol) y puntaje individual de cada jugador.
"""
from __future__ import annotations

from typing import Dict, List, Optional

import settings
from core import historia
from core.decision_tree import DECISIONES, final_de
from core.game_state import EstadoJuego
from core.mapa import SEGURA
from core.partida import DECISION_POR_TIEMPO, Partida
from core.player import Jugador
from input_manager import EstadoAcciones
from levels import ULTIMO_NIVEL, cargar_nivel

SALA, INFORME, NIVEL, VOTACION, RESULTADO, FINAL = "sala", "informe", "nivel", "votacion", "resultado", "final"
ESPERA_INFORME = 30.0         # segundos máximos en el informe si alguien no marca listo
ESPERA_RESULTADO = 12.0       # segundos máximos viendo el resultado de la votación


class Sesion:
    def __init__(self, minimo: int = 2, semilla: Optional[int] = None, en_arena: bool = False):
        self.minimo = minimo                     # jugadores necesarios para empezar
        self.semilla = semilla                   # None = al azar en cada partida
        self.en_arena = en_arena                 # (desarrollo) los niveles empiezan frente al jefe
        self.jugadores: Dict[int, dict] = {}
        self.anfitrion: Optional[int] = None
        self.fase = SALA
        self.t_fase = 0.0
        self.partida: Optional[Partida] = None
        self.estado: Optional[EstadoJuego] = None
        self.acciones: Dict[int, EstadoAcciones] = {}
        self.eventos: List[dict] = []            # efectos del nivel pendientes de enviar
        self.datos: dict = {}                    # datos propios de la fase actual
        self.aviso = ""                          # mensaje corto para la sala

    # --- Jugadores -----------------------------------------------------------------------------
    def conectados(self) -> List[int]:
        return [i for i, j in self.jugadores.items() if j["conectado"]]

    def _rol_libre(self, preferido: Optional[str] = None, excepto: Optional[int] = None) -> Optional[str]:
        usados = {j["rol"] for i, j in self.jugadores.items() if i != excepto}
        orden = list(settings.ORDEN_ROLES)
        if preferido in orden:                   # busca desde el preferido hacia adelante
            k = orden.index(preferido)
            orden = orden[k:] + orden[:k]
        for rol in orden:
            if rol not in usados:
                return rol
        return None

    def unir(self, nombre: str) -> Optional[int]:
        """Agrega un jugador en la sala. Devuelve su id, o None si no se puede entrar."""
        if self.fase != SALA or len(self.jugadores) >= settings.MAX_JUGADORES:
            return None
        nuevo = next(i for i in range(1, settings.MAX_JUGADORES + 1) if i not in self.jugadores)
        self.jugadores[nuevo] = {"nombre": (nombre or f"JUGADOR {nuevo}")[:10].upper(), "rol": self._rol_libre(),
                                 "listo": False, "conectado": True, "puntaje": 0,
                                 "vidas": settings.JUGADOR["vidas"], "voto": ""}
        if self.anfitrion is None:
            self.anfitrion = nuevo
        return nuevo

    def salir(self, id_jugador: int) -> None:
        """Un cliente se desconectó."""
        if id_jugador not in self.jugadores:
            return
        if self.fase == SALA:
            del self.jugadores[id_jugador]
        else:
            self.jugadores[id_jugador]["conectado"] = False
            if self.estado is not None:          # su personaje sale del nivel
                j = self.estado.jugador(id_jugador)
                if j is not None:
                    j.vidas = 0
        if not self.conectados():                # no queda nadie: la sesión vuelve a la sala
            self.jugadores, self.anfitrion = {}, None
            self._a_sala()
        elif self.anfitrion == id_jugador:
            self.anfitrion = min(self.conectados())

    # --- Mensajes de los clientes ----------------------------------------------------------------
    def recibir(self, id_jugador: int, m: dict) -> None:
        j = self.jugadores.get(id_jugador)
        if j is None:
            return
        tipo = m.get("t")
        if tipo == "acciones":
            anterior = self.acciones.get(id_jugador, EstadoAcciones())
            # Las pulsaciones se acumulan hasta el próximo paso (pueden llegar 2 mensajes juntos)
            self.acciones[id_jugador] = EstadoAcciones(frozenset(m.get("m", ())),
                                                       anterior.pulsadas | frozenset(m.get("p", ())))
        elif tipo == "rol" and self.fase == SALA and not j["listo"]:
            rol = self._rol_libre(m.get("rol"), excepto=id_jugador)
            if rol:
                j["rol"] = rol
        elif tipo == "listo":
            j["listo"] = bool(m.get("listo", True))
        elif tipo == "empezar" and self.fase == SALA and id_jugador == self.anfitrion:
            self._empezar()
        elif tipo == "voto" and self.fase == VOTACION and m.get("decision") in DECISIONES:
            j["voto"] = m["decision"]
        elif tipo == "ruta" and self.fase == INFORME and id_jugador == self.anfitrion \
                and m.get("clave") in self.datos["rutas"]:
            self.datos["clave"] = m["clave"]                 # el anfitrión elige por dónde se va
            self.datos["paginas"][1] = historia.pagina_ruta(self.partida.nivel, self.partida.mapa, m["clave"])
        elif tipo == "sala" and self.fase == FINAL and id_jugador == self.anfitrion:
            self._a_sala()

    # --- Cambios de fase -------------------------------------------------------------------------
    def _cambiar(self, fase: str, datos: Optional[dict] = None) -> None:
        self.fase, self.t_fase, self.datos = fase, 0.0, datos or {}
        for j in self.jugadores.values():
            j["listo"], j["voto"] = False, ""

    def _a_sala(self) -> None:
        self.partida = self.estado = None
        self.acciones, self.eventos = {}, []
        for j in self.jugadores.values():
            j["puntaje"], j["vidas"] = 0, settings.JUGADOR["vidas"]
        self.jugadores = {i: j for i, j in self.jugadores.items() if j["conectado"]}
        self._cambiar(SALA)

    def puede_empezar(self) -> bool:
        activos = self.conectados()
        return len(activos) >= self.minimo and all(self.jugadores[i]["listo"] for i in activos)

    def _empezar(self) -> None:
        if not self.puede_empezar():
            self.aviso = f"FALTAN JUGADORES LISTOS (MÍNIMO {self.minimo})"
            return
        self.aviso = ""
        roles = tuple(self.jugadores[i]["rol"] for i in sorted(self.jugadores))
        self.partida = Partida(roles=roles) if self.semilla is None else Partida(semilla=self.semilla, roles=roles)
        self._abrir_informe()

    def _abrir_informe(self) -> None:
        p = self.partida
        nivel = cargar_nivel(p.nivel)
        self.estado = None
        self._cambiar(INFORME, {
            "nivel": p.nivel, "nombre": nivel["nombre"], "jefe": settings.JEFES[nivel["jefe"]]["nombre"],
            "tipo_jefe": nivel["jefe"], "paginas": historia.informe(p.nivel, p.arbol.camino(), p.mapa),
            "rutas": p.opciones_ruta(p.nivel), "clave": SEGURA, "olas": p.mapa.influencia(p.nivel),
            "mapa": p.mapa.to_dict(con_azar=False)})

    def _abrir_nivel(self) -> None:
        p = self.partida
        p.elegir_ruta(p.nivel, self.datos.get("clave", SEGURA))     # grafo -> refuerzos y opinión
        jugadores = []
        for i in sorted(self.jugadores):
            j = self.jugadores[i]
            if j["conectado"]:
                jugadores.append(Jugador.con_rol(i, j["rol"], puntaje=j["puntaje"], vidas=max(1, j["vidas"])))
        self.estado = EstadoJuego.nuevo(p.nivel, jugadores, opinion=p.arbol.opinion(), en_arena=self.en_arena,
                                        semilla=p.semilla, peligro=p.peligro(p.nivel))
        self.acciones, self.eventos = {}, []
        self._cambiar(NIVEL, {"nivel": p.nivel})

    def _guardar_marcador(self) -> None:
        for j in self.estado.jugadores:
            self.jugadores[j.id_jugador]["puntaje"] = j.puntaje
            self.jugadores[j.id_jugador]["vidas"] = j.vidas

    def _abrir_votacion(self) -> None:
        jefe = self.estado.jefe
        self._guardar_marcador()
        self.partida.terminar_nivel(self.estado.puntaje_total, settings.JUGADOR["vidas"], jefe.nombre)
        self._cambiar(VOTACION, {"jefe": jefe.nombre, "tipo_jefe": jefe.tipo, "nivel": self.partida.nivel,
                                 "restante": settings.TIEMPO_DECISION})

    def _pesos(self, campo: str, opciones, peso_de) -> Dict[str, int]:
        pesos = {o: 0 for o in opciones}
        for i in self.conectados():
            j = self.jugadores[i]
            if j[campo] in pesos:
                pesos[j[campo]] += peso_de(j)
        return pesos

    def _cerrar_votacion(self) -> None:
        """Cuenta los votos (el del presidente vale doble). Sin votos, el jefe escapa."""
        pesos = self._pesos("voto", DECISIONES, lambda j: settings.ROLES[j["rol"]]["voto"])
        escapo = not any(pesos.values())
        if escapo:
            decision = DECISION_POR_TIEMPO
        else:
            mejor = max(pesos.values())
            empatadas = [d for d in DECISIONES if pesos[d] == mejor]
            del_presidente = [j["voto"] for j in self.jugadores.values() if j["rol"] == "presidente"]
            decision = del_presidente[0] if del_presidente and del_presidente[0] in empatadas else empatadas[0]
        p = self.partida
        antes = p.arbol.opinion()
        votos = {str(i): self.jugadores[i]["voto"] for i in self.conectados()}
        p.decidir(decision)                                # árbol + mapa
        self._cambiar(RESULTADO, {"decision": decision, "escapo": escapo, "votos": votos, "opinion_antes": antes,
                                  "opinion": p.arbol.opinion(), "cambios_mapa": list(p.cambios_mapa),
                                  "jefe": self.datos["jefe"], "tipo_jefe": self.datos["tipo_jefe"],
                                  "nivel": p.nivel})

    def _abrir_final(self, derrota: bool) -> None:
        p = self.partida
        if self.estado is not None:
            self._guardar_marcador()
        final = final_de(p.arbol.actual)
        tabla = sorted(({"id": i, "nombre": j["nombre"], "rol": j["rol"], "puntaje": j["puntaje"]}
                        for i, j in self.jugadores.items()), key=lambda f: -f["puntaje"])
        self.estado = None
        self._cambiar(FINAL, {"derrota": derrota, "titulo": "MISIÓN FALLIDA" if derrota else final.titulo,
                              "clave": final.clave, "nivel": p.nivel,
                              "resumen": "Los jefes criminales siguen mandando. El país espera otro intento."
                              if derrota else final.resumen,
                              "opinion": p.arbol.opinion(), "camino": p.arbol.camino(), "tabla": tabla,
                              "jefes": list(p.jefes_derrotados)})

    # --- Simulación ------------------------------------------------------------------------------
    def _todos(self, campo: str) -> bool:
        activos = self.conectados()
        return bool(activos) and all(self.jugadores[i][campo] for i in activos)

    def paso(self, dt: float) -> None:
        """Avanza la sesión un paso fijo."""
        self.t_fase += dt
        if self.fase == INFORME:
            if self._todos("listo") or self.t_fase >= ESPERA_INFORME:
                self._abrir_nivel()
        elif self.fase == NIVEL:
            self.estado.update(dt, self.acciones)
            # Las pulsaciones valen un solo paso; lo mantenido sigue hasta el próximo mensaje
            self.acciones = {i: EstadoAcciones(a.mantenidas) for i, a in self.acciones.items()}
            self.eventos += self.estado.extraer_eventos()
            for j in self.estado.jugadores:
                self.jugadores[j.id_jugador]["puntaje"] = j.puntaje
            if self.estado.victoria:
                self._abrir_votacion()
            elif self.estado.game_over:
                self._abrir_final(derrota=True)
        elif self.fase == VOTACION:
            self.datos["restante"] = max(0.0, settings.TIEMPO_DECISION - self.t_fase)
            if self._todos("voto") or self.datos["restante"] <= 0:
                self._cerrar_votacion()
        elif self.fase == RESULTADO:
            if self._todos("listo") or self.t_fase >= ESPERA_RESULTADO:
                if self.partida.nivel >= ULTIMO_NIVEL:
                    self._abrir_final(derrota=False)
                else:
                    self.partida.avanzar()
                    self._abrir_informe()

    # --- Lo que se envía a los clientes --------------------------------------------------------------
    def instantanea(self) -> dict:
        """Estado completo para dibujar la fase actual. En el nivel incluye el mundo y los eventos
        de efectos (sonidos, explosiones) ocurridos desde la instantánea anterior."""
        m = {"t": "estado", "fase": self.fase, "t_fase": round(self.t_fase, 3), "anfitrion": self.anfitrion,
             "minimo": self.minimo, "aviso": self.aviso, "datos": self.datos,
             "jugadores": [{"id": i, "nombre": j["nombre"], "rol": j["rol"], "listo": j["listo"],
                            "conectado": j["conectado"], "puntaje": j["puntaje"], "voto": bool(j["voto"])}
                           for i, j in sorted(self.jugadores.items())]}
        if self.fase == NIVEL and self.estado is not None:
            m["mundo"] = self.estado.to_dict()
            m["eventos"], self.eventos = self.eventos, []
        return m
