"""Escena del teléfono: pantalla de carga entre niveles.

El presidente revisa PATRIANOTICIAS en su teléfono mientras carga el siguiente nivel: titulares
de los medios, publicaciones de influencers y comentarios del pueblo sobre su decisión
(core/news.py). A la derecha, la opinión popular se anima del valor anterior al nuevo.
Si el jugador no toca nada, el feed se desplaza solo y la escena dura DURACION segundos (se
puede saltar después de SALTAR_DESDE). Si desplaza el feed con ARRIBA/ABAJO, pasa a modo
MANUAL: el feed deja de moverse solo y la escena espera a que confirme para continuar.
"""
from __future__ import annotations

import math
import random

import pygame

import input_manager as im
import settings
from audio import gestor as audio
from core.news import INFLUENCERS, MEDIOS, PORTAL, PUEBLO, Publicacion, generar_feed
from levels import ULTIMO_NIVEL, cargar_nivel
from render.hud import COLORES_OPINION, ETIQUETAS_OPINION
from render.texto import dibujar_texto, envolver
from scenes.base import Scene

C = settings.COLORES
DURACION = 10.0
SALTAR_DESDE = 3.0
VEL_MANUAL = 110.0          # píxeles por segundo al mantener ARRIBA/ABAJO
NOMBRES_DECISION = {"capturar": "CAPTURAR", "extraditar": "EXTRADITAR", "liberar": "DEJAR LIBRE"}

# Geometría (pantalla de 256x224): teléfono a la izquierda y panel a la derecha, con el mismo
# margen a ambos lados (7 px) y el teléfono centrado en vertical.
TELEFONO = pygame.Rect(7, 5, 128, 214)
PANTALLA = pygame.Rect(TELEFONO.x + 6, TELEFONO.y + 12, 116, 190)
FEED = pygame.Rect(PANTALLA.x, PANTALLA.y + 24, PANTALLA.w, PANTALLA.h - 24)
ANCHO_TARJETA = FEED.w - 8

# Colores del tema oscuro del portal
FONDO_APP = (16, 18, 26)
FONDO_TARJETA = (34, 38, 52)
TEXTO_APP = (230, 232, 240)
GRIS_APP = (130, 134, 150)
COLOR_CATEGORIA = {MEDIOS: COLORES_OPINION["medios"], INFLUENCERS: COLORES_OPINION["influencers"],
                   PUEBLO: COLORES_OPINION["pueblo"], "tendencias": C["naranja"]}
X_PANEL = TELEFONO.right + 10

# Pulgar (sprite "pulgar"): la yema del fotograma "presionando" toca este punto de la pantalla.
# La base del sprite (la muñeca) queda por debajo del borde inferior y se ve cortada.
CONTACTO = (PANTALLA.x + 86, 180)
PRESION_TRAS_SOLTAR = 0.10      # el pulgar sigue presionado 100 ms después de soltar la cruceta
PRESION_TOQUE_AUTO = 0.25       # duración de cada toque automático


def formatear_numero(n: int) -> str:
    if n >= 1000:
        return f"{n / 1000:.1f}K".replace(".0K", "K")
    return str(n)


def dibujar_corazon(sup, x, y, color):
    pygame.draw.rect(sup, color, (x, y + 1, 5, 2))
    sup.set_at((x + 1, y), color)
    sup.set_at((x + 3, y), color)
    pygame.draw.rect(sup, color, (x + 1, y + 3, 3, 1))
    sup.set_at((x + 2, y + 4), color)


def renderizar_tarjeta(pub: Publicacion) -> pygame.Surface:
    """Dibuja una publicación como tarjeta del feed."""
    color = COLOR_CATEGORIA[pub.categoria]
    if pub.categoria == "tendencias":
        lineas = pub.texto.split("  ")
    else:
        lineas = envolver(pub.texto.upper(), 1, ANCHO_TARJETA - 8)
    alto = 6 + (10 if pub.destacada else 0) + 11 + len(lineas) * 10 + (10 if pub.categoria != "tendencias" else 0) + 2
    tarjeta = pygame.Surface((ANCHO_TARJETA, alto))
    tarjeta.fill(FONDO_TARJETA)
    pygame.draw.rect(tarjeta, color, (0, 0, 2, alto))                 # franja de la categoría
    y = 3
    if pub.destacada:
        pygame.draw.rect(tarjeta, C["rojo"], (4, y, 64, 9))
        dibujar_texto(tarjeta, "ÚLTIMA HORA", (6, y - 1), C["blanco"], sombra=False)
        y += 11
    # Cabecera: avatar con la inicial y nombre del autor
    if pub.categoria != "tendencias":
        pygame.draw.rect(tarjeta, color, (5, y, 9, 9))
        dibujar_texto(tarjeta, pub.autor[0] if pub.autor[0] != "@" else pub.autor[1], (7, y - 1),
                      FONDO_TARJETA, sombra=False)
        dibujar_texto(tarjeta, pub.autor[:14], (17, y - 1), color, sombra=False)
    else:
        dibujar_texto(tarjeta, "TENDENCIAS", (5, y - 1), color, sombra=False)
    y += 12
    for linea in lineas:
        dibujar_texto(tarjeta, linea, (5, y - 1), C["cian"] if pub.categoria == "tendencias" else TEXTO_APP,
                      sombra=False)
        y += 10
    if pub.categoria != "tendencias":
        dibujar_corazon(tarjeta, 5, y + 2, C["rojo"])
        dibujar_texto(tarjeta, formatear_numero(pub.reacciones), (12, y - 1), GRIS_APP, sombra=False)
    return tarjeta


class PhoneScene(Scene):
    def __init__(self, juego, decision: str = "capturar", opinion_antes: dict = None, **datos):
        super().__init__(juego, **datos)
        self.partida = juego.partida
        self.decision = decision
        camino = self.partida.arbol.camino() or [decision]
        jefe = self.partida.jefes_derrotados[-1] if self.partida.jefes_derrotados else "EL CAPO"
        self.feed = generar_feed(camino, jefe.title())
        self.contenido = self._componer_feed()
        self.antes = opinion_antes or self.partida.arbol.opinion()
        self.despues = self.partida.arbol.opinion()
        self.mostrada = {k: float(v) for k, v in self.antes.items()}
        self.tiempo = 0.0
        # Desplazamiento "a toques" del pulgar: cada toque da un impulso que se frena con fricción
        self.desplazamiento, self.velocidad = 0.0, 0.0
        self.maximo = max(0, self.contenido.get_height() - FEED.h)
        self.toques = 8
        self.proximo_toque = 1.6
        self.manual = False         # True cuando el jugador desplaza el feed por su cuenta
        audio.musica("noticias")
        self.t_presion = 0.0        # > 0: el pulgar está presionando la pantalla
        self.rng = random.Random(len(camino))
        siguiente = self.partida.nivel + 1
        self.siguiente = cargar_nivel(siguiente)["nombre"] if siguiente <= ULTIMO_NIVEL else None

    def _componer_feed(self) -> pygame.Surface:
        """Pre-dibuja todas las tarjetas en una superficie alta que luego se desplaza."""
        tarjetas = [renderizar_tarjeta(p) for p in self.feed]
        alto = sum(t.get_height() + 4 for t in tarjetas) + 4
        contenido = pygame.Surface((FEED.w, alto))
        contenido.fill(FONDO_APP)
        y = 4
        for t in tarjetas:
            contenido.blit(t, (4, y))
            y += t.get_height() + 4
        return contenido

    # --- Lógica de la escena ---------------------------------------------------------------
    def update(self, dt, acciones):
        self.tiempo += dt
        entrada = acciones[settings.JUGADOR_LOCAL]
        # Desplazamiento manual: ARRIBA/ABAJO (flechas o cruceta). Al soltar queda un poco de inercia.
        direccion = int(entrada.mantiene(im.ABAJO)) - int(entrada.mantiene(im.ARRIBA))
        if direccion:
            self.manual = True
            self.velocidad = direccion * VEL_MANUAL
            self.t_presion = PRESION_TRAS_SOLTAR
        else:
            self.t_presion = max(0.0, self.t_presion - dt)
        # Toques automáticos del pulgar: impulsos calculados para recorrer el feed en DURACION
        if not self.manual and self.tiempo >= self.proximo_toque and self.toques > 0:
            self.velocidad = 3.0 * self.maximo / 8 * self.rng.uniform(0.85, 1.15)
            self.toques -= 1
            self.proximo_toque += 1.0
            self.t_presion = PRESION_TOQUE_AUTO
        self.desplazamiento = max(0.0, min(self.maximo, self.desplazamiento + self.velocidad * dt))
        if self.manual and self.desplazamiento >= self.maximo:       # leyó hasta el final por su cuenta
            self.juego.logros.notificar("noticias_leidas")
        if not direccion:
            self.velocidad *= math.exp(-6.0 * dt if self.manual else -3.0 * dt)
        # La opinión se anima entre 1,5 s y 3,5 s
        avance = min(1.0, max(0.0, (self.tiempo - 1.5) / 2.0))
        suave = 1 - (1 - avance) ** 3
        for k in self.mostrada:
            self.mostrada[k] = self.antes[k] + (self.despues[k] - self.antes[k]) * suave

        if self.manual:
            if entrada.pulso(im.CONFIRMAR):        # leyendo a su ritmo: sigue cuando quiera
                self.continuar()
        elif self.tiempo >= DURACION or (self.tiempo >= SALTAR_DESDE and entrada.pulso(im.CONFIRMAR)):
            self.continuar()

    def continuar(self):
        p = self.partida
        if p.nivel >= ULTIMO_NIVEL:
            self.juego.escenas.cambiar("final")
        else:
            p.avanzar()
            self.juego.escenas.cambiar("historia", numero=p.nivel, puntaje=p.puntaje, vidas=p.vidas)

    # --- Dibujo --------------------------------------------------------------------------
    # --- Pulgar ------------------------------------------------------------------------------
    @property
    def anim_pulgar(self) -> str:
        return "presionando" if self.t_presion > 0 else "quieto"

    def yema(self, anim: str):
        """Yema del fotograma relativa a la base (del JSON; placeholder: arriba al centro)."""
        alto = self.juego.sprites.frame("pulgar", anim, 0).get_height()
        return tuple(self.juego.sprites.dato_cuadro("pulgar", anim, "yemas", [0, -alto]))

    @property
    def base_pulgar(self):
        """Posición fija de la base: la que pone la yema de "presionando" en CONTACTO."""
        dx, dy = self.yema("presionando")
        return CONTACTO[0] - dx, CONTACTO[1] - dy

    def draw(self, sup):
        sup.fill((12, 10, 20))
        pygame.draw.circle(sup, (24, 20, 36), TELEFONO.center, 110)        # resplandor de la pantalla
        self._dibujar_telefono(sup)
        self._dibujar_pulgar(sup)
        self._dibujar_panel(sup)

    def _dibujar_telefono(self, sup):
        pygame.draw.rect(sup, (28, 28, 34), TELEFONO, border_radius=12)
        pygame.draw.rect(sup, (90, 90, 104), TELEFONO, 1, border_radius=12)
        pygame.draw.rect(sup, (10, 10, 12), (TELEFONO.centerx - 12, TELEFONO.y + 5, 24, 4), border_radius=2)
        pygame.draw.rect(sup, FONDO_APP, PANTALLA)
        # Barra de estado y cabecera del portal
        dibujar_texto(sup, "12:00", (PANTALLA.x + 3, PANTALLA.y + 1), GRIS_APP, sombra=False)
        pygame.draw.rect(sup, GRIS_APP, (PANTALLA.right - 14, PANTALLA.y + 3, 10, 5), 1)
        pygame.draw.rect(sup, C["verde"], (PANTALLA.right - 13, PANTALLA.y + 4, 6, 3))
        pygame.draw.rect(sup, C["rojo"], (PANTALLA.x, PANTALLA.y + 11, PANTALLA.w, 12))
        dibujar_texto(sup, PORTAL, (PANTALLA.centerx, PANTALLA.y + 11), C["blanco"], centrado=True)
        # Feed desplazado
        sup.set_clip(FEED)
        sup.blit(self.contenido, (FEED.x, FEED.y - int(self.desplazamiento)))
        sup.set_clip(None)
        # Barra de desplazamiento
        if self.maximo > 0:
            alto = max(12, FEED.h * FEED.h // self.contenido.get_height())
            y = FEED.y + int((FEED.h - alto) * self.desplazamiento / self.maximo)
            pygame.draw.rect(sup, GRIS_APP, (PANTALLA.right - 2, y, 2, alto))
        pygame.draw.rect(sup, (70, 70, 80), (TELEFONO.centerx - 16, TELEFONO.bottom - 7, 32, 2))

    def _dibujar_pulgar(self, sup):
        """Solo el sprite del pulgar: extendido en reposo, flexionado mientras desplaza."""
        bx, by = self.base_pulgar
        self.juego.sprites.dibujar(sup, "pulgar", self.anim_pulgar, 0, bx, by, camara_x=0)

    def _dibujar_panel(self, sup):
        x = X_PANEL
        dibujar_texto(sup, "OPINIÓN", (x, 8), C["amarillo"])
        dibujar_texto(sup, "POPULAR", (x, 18), C["amarillo"])
        for i, clave in enumerate(("medios", "influencers", "pueblo")):
            y = 36 + i * 22
            color = COLORES_OPINION[clave]
            valor = self.mostrada[clave]
            dibujar_texto(sup, ETIQUETAS_OPINION[clave], (x, y), color)
            dibujar_texto(sup, f"{int(round(valor)):3d}", (x + 22, y), C["blanco"])
            cambio = self.despues[clave] - self.antes[clave]
            if self.tiempo >= 1.5 and cambio:
                signo = "+" if cambio > 0 else ""
                dibujar_texto(sup, f"{signo}{cambio}", (x + 48, y), C["verde"] if cambio > 0 else C["rojo"])
            pygame.draw.rect(sup, C["gris_oscuro"], (x, y + 10, 100, 5))
            pygame.draw.rect(sup, color, (x, y + 10, int(valor), 5))
            pygame.draw.rect(sup, C["blanco"], (x + 50, y + 10, 1, 5))

        dibujar_texto(sup, "TU DECISIÓN:", (x, 106), C["gris"])
        dibujar_texto(sup, NOMBRES_DECISION[self.decision], (x, 116), C["blanco"])

        progreso = 1.0 if self.manual else min(1.0, self.tiempo / DURACION)
        if self.siguiente:
            if self.manual:
                dibujar_texto(sup, f"NIVEL {self.partida.nivel + 1} LISTO", (x, 146), C["verde"])
            else:
                dibujar_texto(sup, f"CARGANDO NIVEL {self.partida.nivel + 1}", (x, 146), C["cian"])
            for i, linea in enumerate(envolver(self.siguiente, 1, 104)[:2]):
                dibujar_texto(sup, linea, (x, 156 + i * 10), C["blanco"])
        else:
            dibujar_texto(sup, "PREPARANDO EL", (x, 146), C["cian"])
            dibujar_texto(sup, "VEREDICTO...", (x, 156), C["cian"])
        pygame.draw.rect(sup, C["gris_oscuro"], (x, 180, 100, 6))
        pygame.draw.rect(sup, C["cian"], (x, 180, int(100 * (1 - (1 - progreso) ** 2)), 6))
        control = "CRUCETA" if self.juego.entrada.hay_control else "FLECHAS"
        if self.manual:
            dibujar_texto(sup, "ENTER: CONTINUAR", (x, 200), C["blanco"])
        else:
            dibujar_texto(sup, f"{control}: LEER", (x, 192), C["gris"])
            if self.tiempo >= SALTAR_DESDE and int(self.tiempo * 2) % 2 == 0:
                dibujar_texto(sup, "ENTER: SALTAR", (x, 204), C["blanco"])
