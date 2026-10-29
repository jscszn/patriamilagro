"""Escena de nivel: conecta el estado lógico (core.game_state) con el dibujo y los efectos.

La escena NO decide reglas del juego: llama a estado.update(dt, acciones) y luego dibuja.
Los efectos visuales (explosiones, casquillos, polvo, temblor, mensajes) salen de los eventos
del estado; viven en render/efectos.py. La "pausa de impacto" (congelar unos cuadros al recibir
o dar un golpe fuerte) también es solo de la vista: el estado no se entera.
"""
from __future__ import annotations

import math
import random
from typing import List

import pygame

import input_manager as im
import settings
from audio import gestor as audio
from core import motivacion
from core.game_state import EstadoJuego
from core.player import Jugador
from render import efectos as fx
from render.animacion import anim_correr_jugador
from render.fondos import Fondo
from render.hud import dibujar_hud
from render.texto import dibujar_texto, fuente
from render.ui import ListaOpciones, dibujar_marco, oscurecer
from scenes.base import Scene

C = settings.COLORES

ANIM_JEFE = {"rafaga": "disparar", "abanico": "disparar", "dirigido": "disparar", "barrido": "disparar",
             "saltar": "saltar",
             "onda": "saltar", "embestida": "correr", "preparar": "especial", "invocar": "especial"}
SPRITE_BALA = {"normal": "bala_enemigo", "jefe": "bala_jefe", "onda": "onda"}
# Fogonazos en la boca del arma (efecto aparte: los sprites no lo traen dibujado)
# Evento lógico -> efecto de sonido
SONIDO_EVENTO = {"disparo_jugador": "disparo_jugador", "disparo_enemigo": "disparo_enemigo",
                 "disparo_jefe": "disparo_jefe", "sicario_muere": "explosion", "jugador_herido": "herido",
                 "jugador_muere": "muerte", "impacto_jefe": "impacto", "temblor": "temblor",
                 "onda_choque": "temblor", "powerup": "powerup", "jefe_derrotado": "explosion_grande",
                 "salto": "salto", "chispa": "impacto", "aviso_vehiculo": "alerta",
                 "suministro": "suministro"}
AVISO_VEHICULO = {"dron": "¡DRON ARMADO!", "moto": "¡SICARIOS EN MOTO!", "camioneta": "¡CAMIONETA BLINDADA!"}
COLOR_FOGONAZO = {"disparo_jugador": (255, 240, 150), "disparo_enemigo": (255, 200, 60),
                  "disparo_jefe": (200, 120, 255)}
# Pausa de impacto (cuadros congelados) según el golpe
CONGELAR = {"jugador_herido": 3, "jugador_muere": 6, "jefe_derrotado": 10, "camioneta": 4, "fase2": 6}
# Piezas que se mueven sobre los sprites de los refuerzos (relativas al ancla, mirando a la derecha)
HELICES_DRON = ((-14, -9), (14, -9))
RUEDAS = {"moto": ((-14, -7, 4), (13, -7, 4)), "camioneta": ((-19, -6, 4), (19, -6, 4))}
ESCAPE = {"moto": (-17, -10), "camioneta": (-37, -14)}
COLOR_BALA_ENEMIGA = {"normal": (255, 170, 60), "jefe": (200, 110, 255), "onda": (255, 160, 80)}


class LevelScene(Scene):
    def __init__(self, juego, numero: int = 1, puntaje: int = 0, vidas: int = None, **datos):
        super().__init__(juego, **datos)
        self.numero = numero
        if juego.partida is None:            # se entró directo al nivel (modo desarrollo)
            juego.nueva_partida().nivel = numero
        self.partida = juego.partida
        # Al reintentar tras GAME OVER: mismo puntaje de inicio del nivel y vidas completas
        self.inicio = {"numero": numero, "puntaje": puntaje, "vidas": None}
        jugador = Jugador(id_jugador=settings.JUGADOR_LOCAL, puntaje=puntaje)
        if vidas is not None:
            jugador.vidas = vidas
        self.estado = EstadoJuego.nuevo(numero, [jugador], opinion=self.partida.arbol.opinion(),
                                        en_arena=juego.arena, semilla=self.partida.semilla,
                                        peligro=self.partida.peligro(numero))
        self.preparar_vista(numero)

    def preparar_vista(self, numero: int) -> None:
        """Todo lo que hace falta para DIBUJAR self.estado y sus efectos. El modo en red lo usa
        con un estado que llega del servidor (scenes/multijugador.py)."""
        juego = self.juego
        self.fondo = Fondo(self.estado.datos)
        self.sprites = juego.sprites
        self.rng = random.Random(numero)   # solo para efectos visuales, no afecta la lógica
        self.efectos = fx.Efectos(self.rng)
        self.fogonazos: List[list] = []     # [x, y, tiempo_restante, color]
        self.congelar = 0                   # cuadros de pausa de impacto que quedan
        self._en_suelo = {}                 # id_jugador -> estaba en el suelo el paso anterior
        self._t_polvo = 0.0
        self._t_humo = 0.0
        amb = self.estado.datos["ambiente"]
        self.color_polvo = tuple(min(255, int(c * 0.55 + 100)) for c in amb["suelo"])
        self._velo_negro = pygame.Surface((settings.ANCHO, settings.ALTO))
        self.temblor = 0.0
        self.fuerza_temblor = 0
        self.destello = 0.0
        self.tiempo = 0.0
        self.opinion_mostrada = {k: float(v) for k, v in self.estado.opinion.items()}
        # Mensajes en pantalla: cartel grande (título, subtítulo, segundos) y caja de tutorial
        self.cartel = (f"NIVEL {numero}", self.estado.datos["nombre"], 2.5)
        self.mensaje = ("", 0.0)
        self.tutorial_pendiente = list(self.estado.datos.get("tutorial", [])) \
            if juego.opciones.get("tutorial", True) else []
        self.explosiones_jefe = 0.0
        self.menu_game_over = ListaOpciones(["REINTENTAR", "MENÚ PRINCIPAL"])
        self.muertes = 0                   # para el logro "intachable"
        self.golpes_en_arena = 0           # para el logro "intocable"
        self.aviso_fase2 = False
        self.avisos_borde: List[list] = []  # [lado, segundos]: flecha que avisa por dónde entra un refuerzo
        self.texto_game_over = self.rng.choice(motivacion.GAME_OVER)
        audio.musica(f"nivel{numero}" if numero in (1, 2, 3) else "nivel1")

    @property
    def id_local(self) -> int:
        return settings.JUGADOR_LOCAL

    def jugador_local(self) -> Jugador:
        return self.estado.jugador(self.id_local) or self.estado.jugadores[0]

    # --- Actualización ------------------------------------------------------------------
    def update(self, dt, acciones):
        self.tiempo += dt
        entrada = acciones.get(settings.JUGADOR_LOCAL, im.EstadoAcciones())

        if self.estado.game_over:
            if self.menu_game_over.update(dt, entrada):
                if self.menu_game_over.seleccion == "REINTENTAR":
                    self.juego.escenas.cambiar("nivel", **self.inicio)
                else:
                    self.juego.escenas.cambiar("menu")
            self._actualizar_efectos(dt)
            return

        if entrada.pulso(im.PAUSA):
            self.juego.escenas.apilar("pausa")
            return
        if entrada.pulso(im.AYUDA):
            self.juego.escenas.apilar("ayuda", superpuesta=True)
            return
        if self.congelar > 0:                 # pausa de impacto: todo quieto un instante
            self.congelar -= 1
            return

        self.estado.update(dt, acciones)
        for evento in self.estado.extraer_eventos():
            self._procesar_evento(evento)
        self._actualizar_tutorial(dt)
        self._actualizar_efectos(dt)

        jefe = self.estado.jefe
        if jefe is not None and jefe.vivo and jefe.fase2 and not self.aviso_fase2:
            self.aviso_fase2 = True
            self.mensaje = (self.rng.choice(motivacion.FASE_2_JEFE), 2.0)
            self.congelar = CONGELAR["fase2"]
            self._temblar(3, 0.3)

        if self.estado.victoria:
            self.juego.logros.notificar("nivel_superado", vidas_perdidas=self.muertes)
            jefe = self.estado.jefe
            self.partida.terminar_nivel(self.estado.puntaje_total, self.jugador_local().vidas, jefe.nombre)
            self.juego.escenas.cambiar("decision", jefe=jefe.nombre, tipo_jefe=jefe.tipo)

    def _procesar_evento(self, e: dict) -> None:
        """Traduce eventos lógicos en efectos visuales (en la etapa g, también sonidos)."""
        tipo = e["tipo"]
        if tipo in SONIDO_EVENTO:
            audio.efecto(SONIDO_EVENTO[tipo])
        self._registrar_logros(e)
        fx_ = self.efectos
        if tipo in COLOR_FOGONAZO:
            self.fogonazos.append([e["x"], e["y"], 0.07, COLOR_FOGONAZO[tipo]])
            if tipo == "disparo_jugador":
                self._casquillo(e["x"])
        elif tipo == "sicario_muere":
            self._abatir_sicario(e)
        elif tipo in ("jugador_herido", "jugador_muere"):
            self.destello = 0.15
            fx_.chispas(e["x"], e["y"], 14 if tipo == "jugador_muere" else 6, [C["blanco"], C["rojo"]])
            if tipo == "jugador_muere":
                fx_.explosion(e["x"], e["y"], 1.0)
            self._temblar(2, 0.2)
            self.congelar = max(self.congelar, CONGELAR[tipo])
        elif tipo == "impacto_jefe":
            fx_.impacto(e["x"], e["y"], (255, 120, 80))
        elif tipo == "chispa":
            fx_.impacto(e["x"], e["y"])
        elif tipo == "temblor":
            self._temblar(e["fuerza"], 0.35)
            jefe = self.estado.jefe
            if jefe is not None:                              # aterrizaje pesado: polvo a los dos lados
                fx_.polvo(jefe.centro[0] - jefe.ancho / 2, jefe.pie, 6, self.color_polvo, -1)
                fx_.polvo(jefe.centro[0] + jefe.ancho / 2, jefe.pie, 6, self.color_polvo, 1)
        elif tipo == "arena":
            self.cartel = ("¡JEFE!", e["nombre"], 2.0)
            audio.musica("jefe")
        elif tipo == "jefe_derrotado":
            self.explosiones_jefe = 2.2
            self._temblar(6, 1.5)
            self.congelar = CONGELAR["jefe_derrotado"]
            fx_.explosion(e["x"], e["y"], 2.5)
            jefe = self.estado.jefe
            if jefe is not None:
                fx_.flotante(e["x"], e["y"] - 40, f"+{settings.JEFES[jefe.tipo]['puntos']}", C["amarillo"])
            self.cartel = ("¡JEFE DERROTADO!", self.rng.choice(motivacion.NIVEL_SUPERADO), 3.0)
            audio.jingle("victoria")
        elif tipo == "game_over":
            audio.jingle("game_over")
        elif tipo == "powerup":
            self.mensaje = (settings.POWERUPS[e["clase"]]["mensaje"], 2.0)
            fx_.chispas(e["x"] + 6, e["y"] + 6, 12, [C["cian"], C["blanco"], C["amarillo"]], velocidad=60, gravedad=40)
            fx_.anillos.append(fx.Anillo(e["x"] + 6, e["y"] + 6, 16, 0.3, C["cian"]))
            puntos = settings.POWERUPS[e["clase"]].get("puntos", 0)
            if puntos:
                fx_.flotante(e["x"] + 6, e["y"] - 4, f"+{puntos}", C["cian"])
        elif tipo == "aviso_vehiculo":
            self.mensaje = (AVISO_VEHICULO[e["clase"]], 1.8)
            self.avisos_borde.append([e["lado"], 1.2])
        elif tipo == "suministro":
            self.mensaje = ("¡SUMINISTRO EN CAMINO!", 1.8)
        elif tipo == "vehiculo_muere":
            grande = e["clase"] == "camioneta"
            audio.efecto("explosion_grande" if grande else "explosion")
            fx_.explosion(e["x"], e["y"], 2.2 if grande else 1.2)
            fx_.flotante(e["x"], e["y"] - 18, f"+{settings.VEHICULOS[e['clase']]['puntos']}", C["amarillo"])
            if grande:
                self._temblar(4, 0.4)
                self.congelar = max(self.congelar, CONGELAR["camioneta"])
            else:
                self._temblar(2, 0.15)
        elif tipo == "invocacion":
            self.mensaje = ("¡REFUERZOS!", 1.5)
        elif tipo == "onda_choque":
            fx_.chispas(e["x"], e["y"], 8, [C["naranja"], C["gris"]], velocidad=60)
            fx_.polvo(e["x"], e["y"], 8, self.color_polvo)
        elif tipo == "salto":
            j = self._jugador_cerca(e.get("x"))
            if j is not None:
                fx_.polvo(j.centro[0], j.pie, 4, self.color_polvo)

    def _registrar_logros(self, e: dict) -> None:
        """Avisa al gestor de logros y cuenta muertes y golpes en la arena."""
        tipo, logros = e["tipo"], self.juego.logros
        if tipo == "sicario_muere":
            logros.notificar("sicario_muere")
        elif tipo == "vehiculo_muere":
            logros.notificar("vehiculo_muere", clase=e["clase"])
        elif tipo == "powerup":
            logros.notificar("powerup", clase=e["clase"])
        elif tipo in ("jugador_herido", "jugador_muere"):
            if self.estado.arena_activa:
                self.golpes_en_arena += 1
            if tipo == "jugador_muere":
                self.muertes += 1
                if self.jugador_local().vidas > 0:        # mensaje de ánimo al reaparecer
                    self.mensaje = (self.rng.choice(motivacion.AL_REAPARECER), 2.5)
        elif tipo == "jefe_derrotado" and self.golpes_en_arena == 0:
            logros.notificar("jefe_sin_dano")

    def _actualizar_tutorial(self, dt: float) -> None:
        texto, t = self.mensaje
        self.mensaje = (texto, t - dt)
        jugador = self.jugador_local()
        if self.tutorial_pendiente and t <= 0.5 and self.cartel[2] <= 0 \
                and jugador.x >= self.tutorial_pendiente[0][0]:
            self.mensaje = (self.tutorial_pendiente.pop(0)[1], 3.5)

    # --- Efectos ------------------------------------------------------------------------
    def _jugador_cerca(self, x=None):
        """El jugador más cercano a x (o el local si no se sabe dónde ocurrió)."""
        activos = [j for j in self.estado.jugadores if j.activo]
        if not activos:
            return None
        if x is None:
            local = self.jugador_local()
            return local if local.activo else activos[0]
        return min(activos, key=lambda j: abs(j.centro[0] - x))

    def _casquillo(self, x: float) -> None:
        j = self._jugador_cerca(x)
        if j is not None:
            self.efectos.casquillo(j.centro[0] + j.mirando * 3, j.y + 14, j.mirando, j.pie)

    def _abatir_sicario(self, e: dict) -> None:
        """El sicario sale despedido (estilo arcade) con un estallido pequeño y sus puntos."""
        mira = e.get("mira", 1)
        imagen = self.sprites.frame("sicario", "quieto", 0, voltear=mira < 0)
        ax, ay = self.sprites.ancla("sicario", imagen, mira < 0)
        pie = e.get("pie", e["y"] + 20)
        self.efectos.cuerpo(imagen, self.sprites.silueta(imagen), e["x"] - ax, pie - ay, e.get("golpe", -mira))
        self.efectos.chispas(e["x"], e["y"], 8, [C["naranja"], C["amarillo"], C["rojo"]], velocidad=80)
        self.efectos.anillos.append(fx.Anillo(e["x"], e["y"], 9, 0.16, (255, 230, 170)))
        if e.get("puntos"):
            self.efectos.flotante(e["x"], e["y"] - 16, f"+{e['puntos']}", C["blanco"])

    def _efectos_continuos(self, dt: float) -> None:
        """Polvo al aterrizar y al correr, humo de los escapes y del blindaje roto."""
        fx_ = self.efectos
        self._t_polvo -= dt
        self._t_humo -= dt
        for j in self.estado.jugadores:
            antes = self._en_suelo.get(j.id_jugador, True)
            if j.activo and j.en_suelo and not antes:
                fx_.polvo(j.centro[0], j.pie, 6, self.color_polvo)
            elif j.activo and j.en_suelo and abs(j.vx) > 1 and self._t_polvo <= 0:
                fx_.polvo(j.centro[0] - j.mirando * 6, j.pie, 1, self.color_polvo, -j.mirando)
            self._en_suelo[j.id_jugador] = j.en_suelo
        if self._t_polvo <= 0:
            self._t_polvo = 0.22
        if self._t_humo <= 0:
            self._t_humo = 0.09
            for v in self.estado.vehiculos:
                if v.estado == "aviso" or not v.vivo or v.clase not in ESCAPE:
                    continue
                ex, ey = ESCAPE[v.clase]
                fx_.humo(v.centro[0] + ex * v.direccion, v.pie + ey, 1.6 + self.rng.random())
                if v.clase == "camioneta" and v.vida <= v.vida_max // 2:    # motor herido: humo negro
                    fx_.humo(v.centro[0] + 22 * v.direccion, v.pie - 30, 3 + self.rng.random() * 2)

    def _temblar(self, fuerza: int, duracion: float) -> None:
        self.fuerza_temblor = max(self.fuerza_temblor if self.temblor > 0 else 0, fuerza)
        self.temblor = max(self.temblor, duracion)

    def _actualizar_efectos(self, dt: float) -> None:
        self.efectos.update(dt)
        self._efectos_continuos(dt)
        for f in self.fogonazos:
            f[2] -= dt
        self.fogonazos = [f for f in self.fogonazos if f[2] > 0]
        self.temblor = max(0.0, self.temblor - dt)
        self.destello = max(0.0, self.destello - dt)
        for aviso in self.avisos_borde:
            aviso[1] -= dt
        self.avisos_borde = [a for a in self.avisos_borde if a[1] > 0]
        titulo, sub, t = self.cartel
        self.cartel = (titulo, sub, t - dt)
        # Cadena de explosiones sobre el jefe derrotado (8 por segundo)
        if self.explosiones_jefe > 0 and self.estado.jefe is not None:
            antes = self.explosiones_jefe
            self.explosiones_jefe -= dt
            if int(antes * 8) != int(self.explosiones_jefe * 8):
                j = self.estado.jefe
                self.efectos.explosion(j.x + self.rng.uniform(0, j.ancho), j.y + self.rng.uniform(0, j.alto),
                                       self.rng.uniform(0.9, 1.6))
                audio.efecto("explosion")
        # Las barras de opinión se animan hacia el valor real
        for clave, valor in self.estado.opinion.items():
            actual = self.opinion_mostrada[clave]
            self.opinion_mostrada[clave] = actual + (valor - actual) * min(1.0, dt * 4)

    # --- Dibujo -------------------------------------------------------------------------
    def draw(self, sup):
        e = self.estado
        dx = dy = 0
        if self.temblor > 0:   # screen shake
            dx = self.rng.randint(-self.fuerza_temblor, self.fuerza_temblor)
            dy = self.rng.randint(-self.fuerza_temblor, self.fuerza_temblor)
        cam = e.camara_x - dx

        contraste = self.juego.opciones.get("alto_contraste", False)
        self.fondo.dibujar_fondo(sup, cam, self.tiempo)
        if contraste:                                     # fondo oscurecido: las figuras resaltan
            self._velo_negro.set_alpha(170)
            sup.blit(self._velo_negro, (0, 0))
        self.fondo.dibujar_terreno(sup, e.geometria, cam, alto_contraste=contraste)
        if not contraste:                                 # adornos y partículas: solo decorado
            self.fondo.dibujar_adornos(sup, cam, self.tiempo)
        contorno_enemigo = C["amarillo"] if contraste else None
        contorno_jugador = C["blanco"] if contraste else None
        self._dibujar_sombras(sup, cam)
        self.efectos.dibujar_detras(sup, cam)

        for p in e.powerups:
            if p.vivo:
                flota = 0 if p.cayendo else math.sin(self.tiempo * 4 + p.x) * 2
                if p.cayendo:
                    self._dibujar_paracaidas(sup, int(p.x + 6 - cam), int(p.y))
                self.sprites.dibujar(sup, f"powerup_{p.tipo}", "quieto", self.tiempo, p.x + 6, p.y + 12 + flota, cam)
        for s in e.sicarios:
            anim = "apuntar" if s.estado == "apuntar" else ("correr" if abs(s.vx) > 1 else "quieto")
            self.sprites.dibujar(sup, "sicario", anim, s.t_anim, s.centro[0], s.pie, cam,
                                 voltear=s.direccion < 0, contorno=contorno_enemigo)
            if s.estado == "apuntar" and s.t_estado > settings.SICARIO["apuntar"] - 0.15:   # aviso antes de disparar
                bx, by = settings.SICARIO["arma"]
                pygame.draw.circle(sup, C["amarillo"], (int(s.centro[0] + s.direccion * bx - cam), int(s.y + by)), 2)
        for v in e.vehiculos:
            if v.estado == "aviso":
                continue
            tinte = (130, 130, 130) if v.t_golpe > 0 else None
            pie = v.centro[1] if v.clase == "dron" else v.pie        # el ancla del dron es su centro
            # Suspensión: la carrocería salta 1 px sobre el terreno al andar
            salto = 1 if v.clase != "dron" and int(v.t_anim * 9) % 3 == 0 else 0
            self.sprites.dibujar(sup, v.clase, "quieto", v.t_anim, v.centro[0], pie - salto, cam,
                                 voltear=v.direccion < 0, tinte=tinte, contorno=contorno_enemigo)
            self._dibujar_mecanica(sup, v, pie, cam)
            if v.clase == "camioneta" and v.vida < v.vida_max:      # blindaje que le queda
                bx, by = int(v.x - cam), int(v.y - 16)
                pygame.draw.rect(sup, C["negro"], (bx, by, v.ancho, 3))
                pygame.draw.rect(sup, C["naranja"], (bx, by, int(v.ancho * v.vida / v.vida_max), 3))
        self._dibujar_jefe(sup, cam, contorno_enemigo)
        varios = len(e.jugadores) > 1
        for j in e.jugadores:
            if not j.activo or (j.invulnerable > 0 and int(self.tiempo * 20) % 2):
                continue   # oculto mientras reaparece, o parpadeando por invulnerabilidad
            if varios:      # en red todos usan el sprite del presidente: los distingue color y número
                contorno_jugador = j.stats_rol["color"]
                dibujar_texto(sup, f"{j.id_jugador}P", (int(j.centro[0] - cam), int(j.y) - 12),
                              contorno_jugador, centrado=True)
            pose = j.pose()
            if j.en_suelo and abs(j.vx) > 1:              # apuntando arriba o en diagonal, también corre
                pose = anim_correr_jugador(pose) or pose
            # El rebote solo hace falta si la pose tiene un único cuadro
            un_cuadro = len(self.sprites.animaciones("jugador").get(pose, [None])) == 1
            rebote = self._rebote(j.vx, j.t_anim) if j.en_suelo and un_cuadro else 0
            self.sprites.dibujar(sup, "jugador", pose, j.t_anim, j.centro[0], j.pie - rebote, cam,
                                 voltear=j.mirando < 0, contorno=contorno_jugador)
        for b in e.balas:
            nombre = "bala_jugador" if b.del_jugador else SPRITE_BALA[b.tipo]
            pie = b.y if b.tipo == "onda" else b.y + b.radio + 1
            bx, by = int(b.x - cam), int(b.y)
            if b.del_jugador:                              # estela corta detrás de la bala
                rapidez = math.hypot(b.vx, b.vy) or 1.0
                ux, uy = b.vx / rapidez, b.vy / rapidez
                pygame.draw.line(sup, (255, 200, 90), (bx - int(ux * 7), by - int(uy * 7)), (bx - int(ux * 2), by - int(uy * 2)))
            elif not contraste and b.tipo != "onda":       # brillo alrededor de las balas enemigas
                r = b.radio + 4
                sup.blit(self.efectos.halo(r, COLOR_BALA_ENEMIGA[b.tipo], 80), (bx - r, by - r),
                         special_flags=pygame.BLEND_RGB_ADD)
            if contraste and not b.del_jugador:            # aro amarillo: las balas enemigas se ven siempre
                pygame.draw.circle(sup, C["amarillo"], (bx, int(b.y - (b.alto // 2))), b.radio + 3, 1)
            self.sprites.dibujar(sup, nombre, "quieto", self.tiempo, b.x, pie, cam)
        self.efectos.dibujar(sup, cam)
        for x, y, t, color in self.fogonazos:   # estrella de 4 puntas en la boca del arma
            cx, cy, r = int(x - cam), int(y), 2 + int(t * 40)
            sup.blit(self.efectos.halo(4, color, 60), (cx - 4, cy - 4), special_flags=pygame.BLEND_RGB_ADD)
            pygame.draw.line(sup, color, (cx - r, cy), (cx + r, cy))
            pygame.draw.line(sup, color, (cx, cy - r + 1), (cx, cy + r - 1))
            pygame.draw.circle(sup, (255, 255, 255), (cx, cy), 1)

        if dy:
            sup.scroll(0, dy)
        if self.destello > 0:
            sup.fill((90, 20, 10), special_flags=pygame.BLEND_RGB_ADD)

        for lado, t in self.avisos_borde:                # flecha que parpadea en el borde por donde entra
            if int(t * 10) % 2:
                x = settings.ANCHO - 8 if lado > 0 else 8
                pygame.draw.polygon(sup, C["rojo"], [(x - 5 * lado, 104), (x - 5 * lado, 120), (x + 4 * lado, 112)])
                dibujar_texto(sup, "!", (x - 14 * lado - 2, 108), C["amarillo"])
        dibujar_hud(sup, e, self.opinion_mostrada, self.sprites, self.id_local, tiempo=self.tiempo)
        self._dibujar_mensajes(sup)
        if e.game_over:
            self._dibujar_game_over(sup)

    @staticmethod
    def _dibujar_paracaidas(sup, x: int, y: int) -> None:
        """Paracaídas del suministro: media cúpula a rayas y dos cuerdas."""
        for i, color in enumerate((C["blanco"], C["rojo"], C["blanco"], C["rojo"])):
            pygame.draw.rect(sup, color, (x - 8 + i * 4, y - 14, 4, 5))
        pygame.draw.line(sup, C["blanco"], (x - 7, y - 16), (x + 6, y - 16))
        pygame.draw.line(sup, C["gris"], (x - 8, y - 9), (x - 3, y))
        pygame.draw.line(sup, C["gris"], (x + 7, y - 9), (x + 2, y))

    def _dibujar_sombras(self, sup, cam) -> None:
        """Sombras bajo los pies: asientan a los personajes en el suelo."""
        g = self.estado.geometria
        for s in self.estado.sicarios:
            fx.dibujar_sombra(sup, g, s.centro[0], s.pie, 18, cam)
        for v in self.estado.vehiculos:
            if v.estado != "aviso":
                fx.dibujar_sombra(sup, g, v.centro[0], v.pie, v.ancho + 6, cam)
        j = self.estado.jefe
        if j is not None and (j.vivo or self.explosiones_jefe > 0):
            fx.dibujar_sombra(sup, g, j.centro[0], j.pie, j.ancho + 14, cam)
        for jugador in self.estado.jugadores:
            if jugador.activo:
                fx.dibujar_sombra(sup, g, jugador.centro[0], jugador.pie, 20 if not jugador.agachado else 34, cam)

    def _dibujar_mecanica(self, sup, v, pie: float, cam: float) -> None:
        """Hélices del dron y ruedas que giran (dibujadas sobre el sprite de una sola pose)."""
        lado = v.direccion if v.direccion else 1
        cx = v.centro[0] - cam
        if v.clase == "dron":
            fase = int(v.t_anim * 30) % 3
            for hx, hy in HELICES_DRON:
                x, y = int(cx + hx * lado), int(pie + hy)
                ancho = (11, 7, 9)[fase]
                pygame.draw.line(sup, (200, 210, 225), (x - ancho // 2, y), (x + ancho // 2, y))
                if fase == 1:
                    pygame.draw.line(sup, (120, 130, 150), (x - 5, y + 1), (x + 5, y + 1))
        for rx, ry, radio in RUEDAS.get(v.clase, ()):
            x, y = cx + rx * lado, pie + ry
            ang = -v.t_anim * 14 * lado
            for k in range(2):                              # dos rayos claros opuestos
                a = ang + k * math.pi
                sup.set_at((int(x + math.cos(a) * (radio - 1)), int(y + math.sin(a) * (radio - 1))), (150, 150, 160))
                sup.set_at((int(x + math.cos(a) * (radio - 2)), int(y + math.sin(a) * (radio - 2))), (110, 110, 120))

    @staticmethod
    def _rebote(vx: float, t: float) -> int:
        """Sube 1 px cada otro paso al correr: da vida a los sprites de un solo cuadro."""
        return 1 if abs(vx) > 1 and int(t * 10) % 2 else 0

    def _dibujar_jefe(self, sup, cam, contorno=None):
        j = self.estado.jefe
        if j is None or (not j.vivo and self.explosiones_jefe <= 0):
            return
        anim = ANIM_JEFE.get(j.estado, "quieto")
        if anim == "quieto" and abs(j.vx) > 1:              # entrando a la arena o acomodándose
            anim = "correr"
        un_cuadro = len(self.sprites.animaciones(f"jefe{j.tipo}").get(anim, [None])) == 1
        dx = int(math.sin(self.tiempo * 60) * 1.5) if j.estado == "preparar" else 0   # tiembla antes de embestir
        if anim == "disparar" and int(self.tiempo * 16) % 2:                         # culatazo: 1 px atrás
            dx -= j.mirando
        # Golpe: se aclara (tinte); derrotado: parpadea como silueta
        destello = (255, 90, 50) if not j.vivo and int(self.tiempo * 15) % 2 else None
        tinte = (64, 40, 30) if j.t_golpe > 0.05 and j.vivo else None     # destello suave de 2 cuadros por impacto
        # Agazapado (jefe 2 al embestir): el dibujo baja y se ensancha como su caja
        alto_normal = settings.JEFES[j.tipo]["alto"]
        escala = (1.0, 1.0) if j.alto == alto_normal else (1.15, j.alto / alto_normal)
        rebote = self._rebote(j.vx, self.tiempo) if un_cuadro else 0
        self.sprites.dibujar(sup, f"jefe{j.tipo}", anim, self.tiempo, j.centro[0], j.pie - rebote, cam,
                             voltear=j.mirando < 0, destello=destello, dx=dx, contorno=contorno, escala=escala,
                             tinte=tinte)
        if j.estado == "aturdido":   # estrellitas sobre la cabeza
            for i in range(3):
                ang = self.tiempo * 6 + i * math.tau / 3
                sup.fill(C["amarillo"], (int(j.centro[0] - cam + math.cos(ang) * 8),
                                         int(j.y - 4 + math.sin(ang) * 2), 2, 2))

    def _dibujar_mensajes(self, sup):
        titulo, sub, t = self.cartel
        if t > 0:
            dibujar_texto(sup, titulo, (128, 76), C["amarillo"], 2, centrado=True)
            if sub:
                dibujar_texto(sup, sub, (128, 96), C["blanco"], 1, centrado=True)
        texto, t = self.mensaje
        if t > 0 and texto:
            caja = pygame.Rect(0, 0, fuente(1).size(texto)[0] + 12, 15)
            caja.midtop = (128, 30)
            dibujar_marco(sup, caja, fondo=(0, 0, 60))
            dibujar_texto(sup, texto, (128, 33), C["blanco"], 1, centrado=True)

    def _dibujar_game_over(self, sup):
        oscurecer(sup, 170)
        dibujar_texto(sup, "GAME OVER", (128, 70), C["rojo"], 3, centrado=True)
        dibujar_texto(sup, f"PUNTAJE {self.estado.puntaje_total:06d}", (128, 100), C["blanco"], 1, centrado=True)
        dibujar_texto(sup, self.texto_game_over, (128, 112), C["amarillo"], 1, centrado=True)
        self.menu_game_over.draw(sup, 128, 130)
