"""Paisajes de fondo de los tres niveles, pintados por código en pixel art.

Cada paisaje es un cielo, varias capas de parallax pintadas UNA vez (se repiten cada 512 px y
empalman sin costura) y cosas vivas que se dibujan cuadro a cuadro entre las capas.

    vichada   La selva del Vichada, la de La Vorágine: no se ve el cielo, todo es selva. Al
              fondo, una muralla verde que la humedad vuelve neblina; después ceibas gigantes,
              troncos con matapalos y cambuches de la guerrilla; arriba, el dosel que se cierra.
              Vivo: lianas que se mecen, haces de luz, guacamayas, mariposas morpho, niebla y
              ojos que miran desde la espesura.
    medellin  Medellín de noche, años noventa: el valle de Aburrá con las comunas encendidas
              trepando las montañas, la aguja y la catedral de ladrillo, el metro elevado y
              edificios de ladrillo con rejas. Vivo: relámpagos, el tren, ventanas que se
              apagan, luces de las antenas, dos neones y un carro quemado que humea.
    guajira   La Guajira a pleno sol: el mar turquesa, molinos de viento, dunas amarillas,
              salinas con flamencos, rancherías wayuu con chinchorros, cardones, trupillos y un
              puesto de pimpinas de gasolina de contrabando. Vivo: aspas que giran y el mar.

Menos es más: lo que está detrás de donde se juega va más tenue (AIRE: perspectiva
atmosférica) para que los personajes y las balas se lean bien.

Nada de esto choca con nada: es solo decorado. Los nombres de los paisajes van en
levels/nivelN.py -> ambiente["paisaje"].
"""
from __future__ import annotations

import math
import random
from typing import Callable, List, Tuple

import numpy as np
import pygame

import settings
from render.texto import dibujar_texto
from render.ui import superficie_opaca

ANCHO = 512                     # cada capa se repite cada 512 px
MARGEN = 96                     # se pinta con margen y los bordes se doblan: empalme sin costura
ALTO = settings.ALTO
Color = Tuple[int, int, int]


# =============================================================================
# Herramientas
# =============================================================================
def _mezcla(a: Color, b: Color, t: float) -> Color:
    t = max(0.0, min(1.0, t))
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def _oscuro(c: Color, k: float) -> Color:
    return tuple(max(0, min(255, int(v * k))) for v in c)


def degradado(sup: pygame.Surface, y0: int, y1: int, colores: List[Color], bandas: int = 12) -> None:
    """Degradado vertical en franjas (como en la NES), con un tramado de damero en cada borde."""
    alto = max(1, y1 - y0)
    tramos = len(colores) - 1
    previo = None
    for b in range(bandas):
        t = b / max(1, bandas - 1)
        i = min(tramos - 1, int(t * tramos))
        color = _mezcla(colores[i], colores[i + 1], t * tramos - i)
        ya, yb = y0 + alto * b // bandas, y0 + alto * (b + 1) // bandas
        pygame.draw.rect(sup, color, (0, ya, sup.get_width(), yb - ya))
        if previo is not None:                                # tramado entre franjas
            for x in range(0, sup.get_width() - 1, 2):
                sup.set_at((x, ya), previo)
                sup.set_at((x + 1, ya + 1), previo)
        previo = color


class Lienzo:
    """Capa de 512 px que se pinta con margen a los lados; al cerrar, lo que se salió por un
    lado se suma por el otro, así la capa empalma consigo misma al repetirse."""

    def __init__(self):
        self.sup = pygame.Surface((ANCHO + 2 * MARGEN, ALTO), pygame.SRCALPHA)

    def x(self, x: float) -> int:
        return int(x) + MARGEN

    def cerrar(self) -> pygame.Surface:
        final = pygame.Surface((ANCHO, ALTO), pygame.SRCALPHA)
        final.blit(self.sup, (0, 0), pygame.Rect(MARGEN, 0, ANCHO, ALTO))
        final.blit(self.sup, (ANCHO - MARGEN, 0), pygame.Rect(0, 0, MARGEN, ALTO))
        final.blit(self.sup, (0, 0), pygame.Rect(ANCHO + MARGEN, 0, MARGEN, ALTO))
        return final


def _repetir(sup: pygame.Surface, capa_x: float, dibujar: Callable[[int], None], ancho: int = 40) -> None:
    """Llama dibujar(x_en_pantalla) para un objeto que vive en x = capa_x de una capa que se repite."""
    for k in (-1, 0, 1):
        x = int(capa_x + k * ANCHO)
        if -ancho < x < settings.ANCHO + ancho:
            dibujar(x)


def _pos_capa(x_capa: float, camara_x: float, factor: float) -> float:
    """Dónde cae en pantalla un punto x de una capa (sin repetir)."""
    return (x_capa - camara_x * factor) % ANCHO


class Paisaje:
    """Base: cielo, capas [(superficie, factor)] y animación entre capas.
    AIRE: cuánto se funde cada capa con el color del aire (perspectiva atmosférica: lo lejano se
    aclara y se desatura, y así el primer plano, donde se juega, resalta)."""
    nombre = ""
    AIRE: Tuple[float, ...] = ()
    COLOR_AIRE: Color = (128, 128, 128)

    def __init__(self, amb: dict):
        self.amb = amb
        self.rng = random.Random(sum(map(ord, self.nombre)))
        self.cielo = superficie_opaca((settings.ANCHO, ALTO))
        self.capas: List[Tuple[pygame.Surface, float]] = []
        self.pintar()
        self.capas = [(_aire(capa, self.COLOR_AIRE, self.AIRE[i] if i < len(self.AIRE) else 0.0), factor)
                      for i, (capa, factor) in enumerate(self.capas)]
        if pygame.display.get_surface() is not None:                # blits más rápidos
            self.capas = [(capa.convert_alpha(), factor) for capa, factor in self.capas]

    def pintar(self) -> None:
        raise NotImplementedError

    def cielo_vivo(self, sup, camara_x, t) -> None:
        """Lo que se mueve en el cielo, antes de la primera capa."""

    def entre(self, sup, n: int, camara_x: float, t: float) -> None:
        """Lo que va justo delante de la capa n (y detrás de la n + 1)."""

    def delante(self, sup, camara_x: float, t: float) -> None:
        """Lo que va delante de todas las capas y detrás del terreno."""

    def dibujar(self, sup: pygame.Surface, camara_x: float, t: float) -> None:
        sup.blit(self.cielo, (0, 0))
        self.cielo_vivo(sup, camara_x, t)
        for n, (imagen, factor) in enumerate(self.capas):
            d = -int(camara_x * factor) % ANCHO
            sup.blit(imagen, (d - ANCHO, 0))
            sup.blit(imagen, (d, 0))
            self.entre(sup, n, camara_x, t)
        self.delante(sup, camara_x, t)


def _aire(capa: pygame.Surface, color: Color, mezcla: float) -> pygame.Surface:
    """Funde los píxeles de la capa con el color del aire (más hacia abajo, como neblina)."""
    if mezcla <= 0:
        return capa
    rgb = pygame.surfarray.pixels3d(capa)
    filas = np.linspace(0.75, 1.25, capa.get_height(), dtype=np.float32)[None, :, None]
    k = np.clip(mezcla * filas, 0, 0.85)
    rgb[...] = (rgb * (1 - k) + np.array(color, np.float32) * k).astype(np.uint8)
    del rgb
    return capa


def _halo(radio: int, color: Color, alfa: int) -> pygame.Surface:
    sup = pygame.Surface((radio * 2 + 1, radio * 2 + 1), pygame.SRCALPHA)
    for r, a in ((radio, alfa // 3), (int(radio * 0.7), alfa // 2), (int(radio * 0.45), alfa)):
        pygame.draw.circle(sup, (*color, a), (radio, radio), max(1, r))
    return sup


_BOCANADAS = {}


def bocanada(radio: int, gris: int, alfa: int) -> pygame.Surface:
    """Bocanada de humo semitransparente (con caché)."""
    clave = (radio, gris // 8, alfa // 8)
    if clave not in _BOCANADAS:
        sup = pygame.Surface((radio * 2 + 1, radio * 2 + 1), pygame.SRCALPHA)
        pygame.draw.circle(sup, (gris, gris, gris + 6, alfa // 2), (radio, radio), radio)
        pygame.draw.circle(sup, (min(255, gris + 14), min(255, gris + 14), min(255, gris + 20), alfa),
                           (radio - radio // 3, radio - radio // 3), max(1, radio * 2 // 3))
        _BOCANADAS[clave] = sup
    return _BOCANADAS[clave]


def _niebla(ancho: int, alto: int, color: Color, alfa: int, semilla: int) -> pygame.Surface:
    """Banco de niebla: óvalos semitransparentes encimados, más denso al centro."""
    rng = random.Random(semilla)
    sup = pygame.Surface((ancho, alto), pygame.SRCALPHA)
    for _ in range(ancho // 6):
        w = rng.randint(30, 80)
        h = rng.randint(6, alto // 2)
        x = rng.randint(-20, ancho - 10)
        y = rng.randint(0, alto - h)
        capa = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.ellipse(capa, (*color, rng.randint(alfa // 3, alfa)), (0, 0, w, h))
        sup.blit(capa, (x, y))
    return sup


# =============================================================================
# LA SELVA DEL VICHADA
# =============================================================================
class Vichada(Paisaje):
    """La selva de La Vorágine: no se ve el cielo, solo selva. El fondo es verde y se aclara con
    la distancia (la humedad lo vuelve neblina); la luz baja en haces desde el dosel."""
    nombre = "vichada"

    def pintar(self):
        rng = self.rng
        # Fondo: el verde de la selva lejana, más claro arriba donde entra la luz
        degradado(self.cielo, 0, ALTO, [(190, 226, 150), (130, 196, 120), (84, 160, 100), (60, 128, 86)], 12)
        self.ojos: List[Tuple[int, int]] = []

        def copas(s, y_base, radio, colores, paso, ondas=(0.05, 0.13), altura=8):
            sombra, base, luz = colores
            for x in range(-20, s.get_width() + 20, paso):
                y = y_base + int(math.sin(x * ondas[0]) * altura + math.sin(x * ondas[1]) * altura / 2) + rng.randint(-3, 3)
                r = rng.randint(radio - 3, radio + 3)
                pygame.draw.circle(s, sombra, (x, y + 3), r)
                pygame.draw.circle(s, base, (x, y), r)
                pygame.draw.circle(s, luz, (x - r // 3, y - r // 3), max(2, r // 2))

        # Capa 0: muralla de selva lejana, casi neblina
        c = Lienzo()
        s = c.sup
        copas(s, 70, 16, ((150, 204, 140), (164, 214, 148), (182, 226, 160)), 13, altura=14)
        pygame.draw.rect(s, (150, 204, 140), (0, 76, s.get_width(), 150))
        for _ in range(9):                                                # troncos lejanos, apenas marcados
            x = rng.randint(0, s.get_width())
            pygame.draw.line(s, (138, 190, 132), (x, 80), (x, 200), 2)
        self.capas.append((c.cerrar(), 0.08))

        # Capa 1: ceibas gigantes y la pared media de la selva
        c = Lienzo()
        s = c.sup
        for i in range(6):
            x = i * 110 + rng.randint(0, 50)
            pygame.draw.rect(s, (96, 140, 96), (x, 40, 7, 170))
            pygame.draw.line(s, (120, 166, 112), (x + 1, 40), (x + 1, 210))
            for k in (-1, 1):                                             # raíces de tabla
                pygame.draw.polygon(s, (96, 140, 96), [(x + 3, 150), (x + 3 + k * 14, 190), (x + 3 + k * 3, 190)])
        copas(s, 54, 15, ((70, 140, 88), (96, 168, 100), (132, 196, 118)), 11, altura=10)
        copas(s, 110, 13, ((76, 148, 92), (100, 170, 104), (130, 194, 116)), 12, ondas=(0.07, 0.17), altura=6)
        pygame.draw.rect(s, (76, 148, 92), (0, 116, s.get_width(), 120))
        self.capas.append((c.cerrar(), 0.22))

        # Capa 2: troncos cercanos con matapalos y un par de cambuches de la guerrilla
        c = Lienzo()
        s = c.sup
        tronco, tronco_luz = (62, 92, 56), (92, 126, 74)
        for i in range(5):
            x = i * 130 + rng.randint(0, 60)
            ancho = rng.randint(10, 14)
            pygame.draw.rect(s, tronco, (x, 20, ancho, 190))
            pygame.draw.line(s, tronco_luz, (x + 2, 20), (x + 2, 210))
            for y in range(28, 170, 8):                                   # matapalo que lo abraza
                dx = int(math.sin(y * 0.3 + i) * ancho / 2)
                pygame.draw.line(s, (84, 118, 60), (x + ancho // 2 + dx, y), (x + ancho // 2 - dx, y + 7), 2)
            for k in (-1, 1):
                pygame.draw.polygon(s, tronco, [(x + ancho // 2, 150), (x + ancho // 2 + k * 20, 196),
                                                (x + ancho // 2 + k * 5, 196)])
            self.ojos.append((x + ancho + 8 - MARGEN, 150 + rng.randint(0, 14)))
        for x in (150, 150 + 256):                                        # cambuches: plástico negro y verde
            pygame.draw.polygon(s, (30, 54, 38), [(x - 22, 190), (x, 168), (x + 24, 190)])
            pygame.draw.polygon(s, (44, 74, 50), [(x - 18, 190), (x, 171), (x + 4, 190)])
            pygame.draw.line(s, (20, 30, 24), (x, 168), (x, 192))
        copas(s, 150, 9, ((40, 110, 60), (56, 136, 66), (88, 168, 80)), 8, ondas=(0.09, 0.21), altura=5)
        pygame.draw.rect(s, (40, 110, 60), (0, 156, s.get_width(), 60))
        for _ in range(8):                                                # heliconias
            x, y = rng.randint(0, s.get_width()), rng.randint(152, 170)
            pygame.draw.line(s, (30, 90, 44), (x, y + 10), (x + 1, y - 6))
            for k in range(4):
                lado = 1 if k % 2 else -1
                pygame.draw.polygon(s, (232, 56, 44), [(x + 1, y - k * 3), (x + 1 + lado * 5, y - k * 3 - 1), (x + 1, y - k * 3 + 2)])
                s.set_at((x + 1 + lado * 4, y - k * 3 - 1), (255, 214, 70))
        self.capas.append((c.cerrar(), 0.42))

        # Capa 3: el dosel que se cierra arriba ("la cárcel verde")
        c = Lienzo()
        s = c.sup
        for x in range(-10, s.get_width() + 10, 7):
            y = 30 + int(math.sin(x * 0.04) * 5 + math.sin(x * 0.11) * 3) + rng.randint(-2, 2)
            pygame.draw.circle(s, (30, 88, 50), (x, y - 6), rng.randint(8, 11))
            pygame.draw.circle(s, (48, 116, 60), (x - 2, y - 9), rng.randint(4, 7))
        pygame.draw.rect(s, (30, 88, 50), (0, 0, s.get_width(), 26))
        for _ in range(10):                                               # orquídeas
            s.fill(rng.choice([(236, 90, 180), (250, 220, 90)]), (rng.randint(0, s.get_width()), 30 + rng.randint(-4, 6), 2, 2))
        self.capas.append((c.cerrar(), 0.9))

        # Haces de luz que bajan del dosel (uno pintado, que se repite)
        self.haz = pygame.Surface((ANCHO, ALTO), pygame.SRCALPHA)
        for i in range(4):
            x = i * 128 + rng.randint(0, 50)
            for k, alfa in ((0, 22), (4, 18), (8, 14)):
                pygame.draw.polygon(self.haz, (255, 255, 210, alfa), [(x + k, 30), (x + 22 - k, 30),
                                                                     (x + 70 - k, 200), (x + 48 + k, 200)])
        self.niebla = _niebla(ANCHO, 40, (220, 240, 210), 60, 11)
        self.lianas = [(i * 47 + rng.randint(0, 20), rng.randint(36, 80), rng.random() * 6) for i in range(11)]
        self.mariposas = [(rng.random() * 300, 70 + rng.random() * 80, rng.random() * 6) for _ in range(3)]

    def cielo_vivo(self, sup, camara_x, t):
        for i in range(2):                                                # guacamayas cruzando
            fase = (t * 0.05 + i * 0.5) % 1.0
            x = int(fase * 330 - camara_x * 0.03) % 330 - 30
            y = int(60 + i * 16 + math.sin(t * 2 + i) * 4)
            ala = -2 if int(t * 8 + i) % 2 else 2
            cuerpo, alas = ((220, 30, 30), (40, 90, 230)) if i == 0 else ((250, 200, 30), (30, 120, 230))
            sup.fill(cuerpo, (x, y, 4, 2))
            sup.fill(cuerpo, (x - 3, y + 1, 3, 1))
            pygame.draw.line(sup, alas, (x + 1, y), (x - 1, y + ala))
            pygame.draw.line(sup, alas, (x + 2, y), (x + 4, y + ala))

    def entre(self, sup, n, camara_x, t):
        if n == 0:                                                        # neblina entre la selva lejana y la media
            d = int(-camara_x * 0.15 - t * 4) % ANCHO
            for x in (d - ANCHO, d):
                sup.blit(self.niebla, (x, 120))
        if n == 1:
            self.haz.set_alpha(int(200 + 55 * math.sin(t * 0.6)))
            d = -int(camara_x * 0.3) % ANCHO
            sup.blit(self.haz, (d - ANCHO, 0))
            sup.blit(self.haz, (d, 0))
        if n == 2:
            for i, (ox, oy) in enumerate(self.ojos):                      # ojos que miran desde la espesura
                if (t * 0.6 + i * 0.83) % 5.0 < 2.4 and int(t * 5 + i) % 13:
                    _repetir(sup, _pos_capa(ox, camara_x, 0.42),
                             lambda x, oy=oy: (sup.fill((255, 226, 60), (x, oy, 2, 1)),
                                               sup.fill((255, 226, 60), (x + 4, oy, 2, 1))))
            for i, (mx, my, fase) in enumerate(self.mariposas):           # mariposas morpho azules
                x = int((mx + t * 12 - camara_x * 0.5 + math.sin(t * 1.7 + fase) * 14) % 290) - 17
                y = int(my + math.sin(t * 2.3 + fase) * 8)
                abierta = int(t * 10 + i) % 2
                color = (60, 170, 255)
                sup.fill(color, (x - (2 if abierta else 1), y, 2 if abierta else 1, 2))
                sup.fill(color, (x + 1, y, 2 if abierta else 1, 2))
                sup.set_at((x, y), (20, 20, 30))

    def delante(self, sup, camara_x, t):
        for i, (lx, largo, fase) in enumerate(self.lianas):              # lianas vivas que se mecen
            x0 = (lx - camara_x * 0.85) % 560 - 30
            puntos = []
            for y in range(32, 32 + largo, 3):
                k = (y - 32) / largo
                puntos.append((x0 + math.sin(t * 1.2 + fase + y * 0.08) * 6 * k, y))
            if len(puntos) > 1:
                pygame.draw.lines(sup, (40, 110, 54), False, puntos, 1)
                for j, (x, y) in enumerate(puntos[2::3]):
                    sup.fill((66, 150, 66), (int(x) - 2 + j % 2 * 3, int(y), 3, 2))


# =============================================================================
# MEDELLÍN, AÑOS NOVENTA
# =============================================================================
class Medellin(Paisaje):
    nombre = "medellin"
    AIRE = (0.12, 0.32, 0.1)
    COLOR_AIRE = (96, 40, 66)

    def pintar(self):
        rng = self.rng
        degradado(self.cielo, 0, 160, [(16, 8, 30), (52, 20, 56), (110, 40, 64), (176, 84, 66)], 14)
        pygame.draw.rect(self.cielo, (176, 84, 66), (0, 160, settings.ANCHO, ALTO - 160))
        self.ventanas: List[Tuple[int, int]] = []     # ventanas que a ratos se apagan (capa 2)
        self.antenas: List[Tuple[int, int]] = []

        # Capa 0: montañas del valle de Aburrá con las comunas encendidas
        c = Lienzo()
        s = c.sup
        cerro = (44, 26, 56)
        puntos = [(0, ALTO)]
        for x in range(0, s.get_width() + 8, 8):
            y = 92 + int(math.sin(x * 0.011) * 18 + math.sin(x * 0.037 + 1) * 8 + math.sin(x * 0.09) * 3)
            puntos.append((x, y))
        puntos.append((s.get_width(), ALTO))
        pygame.draw.polygon(s, cerro, puntos)
        for (xa, ya), (xb, yb) in zip(puntos[1:-2], puntos[2:-1]):     # luces de las comunas
            for x in range(xa, xb):
                cima = ya + (yb - ya) * (x - xa) / max(1, xb - xa)
                for y in range(int(cima) + 3, 170, 3):
                    densidad = 0.08 + 0.5 * (y - cima) / 80
                    if rng.random() < densidad and (x + y) % 2 == 0:
                        s.set_at((x, y), rng.choice([(255, 196, 90), (255, 160, 70), (250, 230, 160), (200, 110, 70)]))
        for x in range(30, s.get_width(), 170):                          # antenas en las cimas
            cima = min(p[1] for p in puntos if abs(p[0] - x) < 6)
            pygame.draw.line(s, (20, 12, 26), (x, cima), (x, cima - 14))
            pygame.draw.line(s, (20, 12, 26), (x - 3, cima), (x, cima - 10))
            self.antenas.append((x - MARGEN, cima - 15))
        # una cruz grande en un cerro
        pygame.draw.line(s, (220, 210, 200), (260, 86), (260, 98))
        pygame.draw.line(s, (220, 210, 200), (256, 89), (264, 89))
        self.capas.append((c.cerrar(), 0.05))

        # Capa 1: el centro: la aguja, la catedral de ladrillo y edificios lejanos
        c = Lienzo()
        s = c.sup
        mole = (40, 24, 48)
        for i in range(14):
            x, w = i * 46 + rng.randint(0, 20), rng.randint(20, 34)
            h = rng.randint(30, 70)
            pygame.draw.rect(s, mole, (x, 168 - h, w, h + 50))
            for wy in range(168 - h + 4, 166, 5):
                for wx in range(x + 3, x + w - 2, 4):
                    if rng.random() < 0.25:
                        s.set_at((wx, wy), (160, 120, 80))
        for ax in (140, 140 + 256):                                      # la aguja
            pygame.draw.rect(s, (36, 22, 44), (ax, 64, 22, 110))
            pygame.draw.polygon(s, (36, 22, 44), [(ax, 64), (ax + 11, 26), (ax + 22, 64)])
            pygame.draw.line(s, (36, 22, 44), (ax + 11, 26), (ax + 11, 8))
            for wy in range(70, 170, 4):
                for wx in range(ax + 3, ax + 20, 3):
                    if rng.random() < 0.3:
                        s.set_at((wx, wy), (230, 180, 110))
            self.antenas.append((ax + 11 - MARGEN, 7))
        self._catedral(s, 330, 170)                                       # catedral de ladrillo
        self.capas.append((c.cerrar(), 0.14))

        # Capa 2: el metro elevado y los edificios de ladrillo
        c = Lienzo()
        s = c.sup
        ladrillo, ladrillo_osc = (112, 56, 44), (76, 38, 36)
        for i in range(11):
            x, w = i * 52 + rng.randint(0, 16), rng.randint(34, 48)
            h = rng.randint(40, 80)
            top = 196 - h
            pygame.draw.rect(s, ladrillo_osc, (x, top, w, h + 30))
            pygame.draw.rect(s, ladrillo, (x + 2, top + 2, w - 4, h + 30))
            for y in range(top + 4, 200, 3):                              # hiladas de ladrillo
                pygame.draw.line(s, ladrillo_osc, (x + 2, y), (x + w - 3, y))
            pygame.draw.rect(s, (60, 60, 70), (x + w // 2 - 5, top - 6, 10, 6))      # tanque de agua
            for wy in range(top + 6, 190, 11):
                for wx in range(x + 5, x + w - 8, 10):
                    encendida = rng.random() < 0.3
                    color = rng.choice([(250, 200, 110), (150, 190, 250), (255, 170, 90)]) if encendida else (30, 18, 26)
                    pygame.draw.rect(s, color, (wx, wy, 6, 6))
                    for k in range(wx + 1, wx + 6, 2):                    # rejas
                        pygame.draw.line(s, (20, 14, 18), (k, wy), (k, wy + 5))
                    pygame.draw.line(s, (90, 90, 100), (wx - 1, wy + 7), (wx + 6, wy + 7))   # balcón
                    if encendida:
                        self.ventanas.append((wx - MARGEN, wy))
        pygame.draw.rect(s, (86, 84, 96), (0, 110, s.get_width(), 6))    # viga del metro
        pygame.draw.line(s, (130, 128, 140), (0, 110), (s.get_width(), 110))
        pygame.draw.line(s, (50, 48, 60), (0, 116), (s.get_width(), 116))
        for x in range(0, s.get_width(), 48):                             # pilas
            pygame.draw.rect(s, (70, 68, 80), (x, 116, 6, 90))
            pygame.draw.rect(s, (96, 94, 106), (x - 2, 116, 10, 3))
        self.capas.append((c.cerrar(), 0.32))

        self.niebla = _niebla(ANCHO, 40, (120, 70, 90), 60, 21)
        self.carro_x = 200                                                # carro quemado (capa 2)

    @staticmethod
    def _catedral(s, cx, base):
        """Catedral de ladrillo de dos torres con rosetón encendido."""
        muro, osc = (96, 46, 40), (60, 30, 34)
        pygame.draw.rect(s, muro, (cx - 30, base - 44, 60, 60))
        for tx in (cx - 30, cx + 18):                                     # torres
            pygame.draw.rect(s, muro, (tx, base - 74, 12, 40))
            pygame.draw.polygon(s, osc, [(tx - 1, base - 74), (tx + 6, base - 96), (tx + 13, base - 74)])
            pygame.draw.line(s, (200, 180, 140), (tx + 6, base - 96), (tx + 6, base - 102))
            pygame.draw.line(s, (200, 180, 140), (tx + 4, base - 100), (tx + 8, base - 100))
            for wy in (base - 66, base - 54):
                pygame.draw.rect(s, (230, 150, 70), (tx + 4, wy, 4, 6))
        pygame.draw.polygon(s, osc, [(cx - 30, base - 44), (cx, base - 62), (cx + 30, base - 44)])
        pygame.draw.circle(s, (240, 170, 70), (cx, base - 34), 6)        # rosetón
        pygame.draw.circle(s, (200, 60, 60), (cx, base - 34), 3)
        for k in range(8):
            a = k * math.pi / 4
            s.set_at((int(cx + math.cos(a) * 5), int(base - 34 + math.sin(a) * 5)), osc)
        for wx in range(cx - 24, cx + 24, 8):                             # arcos
            pygame.draw.rect(s, (220, 140, 70), (wx, base - 20, 4, 8))
            s.set_at((wx + 1, base - 21), (220, 140, 70))
            s.set_at((wx + 2, base - 21), (220, 140, 70))

    def _relampago(self, t):
        """Fase del relámpago: cada ~9 s, unos cuadros de luz (determinista con el tiempo)."""
        ciclo = 9.0
        k = int(t / ciclo)
        inicio = k * ciclo + (math.sin(k * 12.9898) * 43758.5453 % 1.0) * 5
        return t - inicio, k

    def cielo_vivo(self, sup, camara_x, t):
        edad, k = self._relampago(t)
        if 0 <= edad < 0.35 and int(edad * 30) % 3 != 1:
            sup.fill((40, 30, 50), (0, 0, settings.ANCHO, 140), special_flags=pygame.BLEND_RGB_ADD)
            rng = random.Random(k)
            x, y = rng.randint(30, 220), 0
            while y < 90:                                                 # rayo quebrado
                nx, ny = x + rng.randint(-8, 8), y + rng.randint(6, 12)
                pygame.draw.line(sup, (250, 240, 255), (x, y), (nx, ny))
                x, y = nx, ny
        pygame.draw.circle(sup, (150, 130, 150), (52, 40), 9)             # luna entre nubes
        pygame.draw.circle(sup, (110, 90, 120), (55, 38), 7)

    def entre(self, sup, n, camara_x, t):
        if n == 0:
            for x, y in self.antenas[:3]:                                 # luces rojas de las antenas
                if int(t * 1.5 + x) % 2:
                    _repetir(sup, _pos_capa(x, camara_x, 0.05), lambda px, y=y: sup.fill((255, 40, 40), (px, y, 2, 2)))
        if n == 1:
            for x, y in self.antenas[3:]:
                if int(t * 1.2) % 2:
                    _repetir(sup, _pos_capa(x, camara_x, 0.14), lambda px, y=y: sup.fill((255, 40, 40), (px - 1, y, 2, 2)))
            d = int(-camara_x * 0.2 - t * 3) % ANCHO
            for x in (d - ANCHO, d):
                sup.blit(self.niebla, (x, 140))
        if n == 2:
            for i, (x, y) in enumerate(self.ventanas[::7]):               # ventanas que se apagan
                if int(t * 0.8 + i * 1.3) % 9 == 0:
                    _repetir(sup, _pos_capa(x, camara_x, 0.32), lambda px, y=y: sup.fill((30, 18, 26), (px, y, 6, 6)))
            vuelta = 11.0                                                 # el metro pasa por la viga
            fase = (t % vuelta) / vuelta
            tren_x = -120 + fase * (settings.ANCHO + 240)
            for vagon in range(3):
                vx = int(tren_x + vagon * 34)
                pygame.draw.rect(sup, (200, 200, 210), (vx, 100, 32, 10))
                pygame.draw.rect(sup, (60, 120, 200), (vx, 106, 32, 2))
                for wx in range(vx + 3, vx + 30, 6):
                    sup.fill((255, 240, 180), (wx, 102, 4, 3))
            base = _pos_capa(self.carro_x, camara_x, 0.32)                # carro quemado que humea

            def carro(x):
                pygame.draw.rect(sup, (30, 26, 28), (x - 10, 190, 20, 7))
                pygame.draw.rect(sup, (24, 20, 22), (x - 6, 186, 12, 5))
                fuego = int(t * 10) % 3
                sup.fill((255, 140, 40), (x - 4 + fuego, 185, 3, 3))
                sup.fill((255, 220, 90), (x - 3 + fuego, 186, 1, 1))
                for k in range(6):
                    edad = (t * 0.3 + k / 6) % 1.0
                    r = 2 + int(edad * 6)
                    b = bocanada(r, int(60 + 40 * edad), int(120 * (1 - edad)))
                    sup.blit(b, (int(x + math.sin(edad * 5 + t) * 6 * edad + edad * 20) - r, int(182 - edad * 110) - r))
            _repetir(sup, base, carro, 60)
            for i, (texto, color, nx, ny) in enumerate(NEONES_MEDELLIN):   # letreros de neón
                encendido = int(t * 3 + i * 1.7) % 9 != 0 and not (i == 2 and int(t * 11) % 5 == 0)
                ancho = len(texto) * 6 + 4

                def letrero(x, texto=texto, color=color, ny=ny, encendido=encendido, ancho=ancho):
                    pygame.draw.rect(sup, (18, 10, 22), (x, ny, ancho, 11))
                    pygame.draw.rect(sup, color if encendido else (60, 40, 60), (x, ny, ancho, 11), 1)
                    if encendido:
                        sup.blit(_halo_sirena(tuple(c // 2 for c in color)), (x + ancho // 2 - 16, ny - 4),
                                 special_flags=pygame.BLEND_RGB_ADD)
                        dibujar_texto(sup, texto, (x + 3, ny), color, sombra=False)
                _repetir(sup, _pos_capa(nx, camara_x, 0.32), letrero, 70)


# Letreros de neón de la cuadra: (texto, color, x en la capa, y)
NEONES_MEDELLIN = [("BILLAR", (255, 60, 170), 60, 132), ("MOTEL", (255, 210, 60), 330, 128)]

_SIRENAS = {}


def _halo_sirena(color) -> pygame.Surface:
    if color not in _SIRENAS:
        sup = pygame.Surface((33, 20))
        for r, k in ((16, 0.18), (10, 0.3), (5, 0.5)):
            pygame.draw.ellipse(sup, tuple(int(c * k) for c in color), (16 - r, 10 - r // 2, r * 2, r))
        _SIRENAS[color] = sup
    return _SIRENAS[color]


# =============================================================================
# LA GUAJIRA
# =============================================================================
class Guajira(Paisaje):
    nombre = "guajira"
    AIRE = (0.18, 0.22, 0.06)
    COLOR_AIRE = (250, 236, 190)

    def pintar(self):
        rng = self.rng
        degradado(self.cielo, 0, 140, [(46, 150, 214), (110, 196, 232), (200, 232, 232), (255, 236, 160)], 14)
        pygame.draw.rect(self.cielo, (255, 236, 160), (0, 140, settings.ANCHO, ALTO - 140))
        self.sol = _halo(40, (255, 250, 210), 150)
        self.molinos: List[int] = []
        self.flamencos: List[Tuple[int, int]] = []

        # Capa 0: el mar Caribe, el Pilón de Azúcar y los molinos de viento en el horizonte
        c = Lienzo()
        s = c.sup
        pygame.draw.rect(s, (40, 180, 196), (0, 138, s.get_width(), 20))
        pygame.draw.rect(s, (90, 214, 214), (0, 138, s.get_width(), 3))
        pygame.draw.rect(s, (20, 140, 176), (0, 150, s.get_width(), 8))
        for x in range(0, s.get_width(), 4):
            if rng.random() < 0.5:
                s.set_at((x, 143 + rng.randint(0, 9)), (200, 246, 240))
        cerro = [(150 + k, 140 - int(26 * math.sin(k / 50 * math.pi) ** 0.7)) for k in range(0, 51, 2)]
        pygame.draw.polygon(s, (200, 120, 80), cerro + [(200, 141), (150, 141)])   # el Pilón de Azúcar
        pygame.draw.polygon(s, (228, 150, 96), cerro[:9] + [(166, 141), (150, 141)])
        pygame.draw.line(s, (170, 96, 66), (176, 115), (184, 140))
        pygame.draw.rect(s, (236, 196, 110), (0, 154, s.get_width(), 70))
        for i in range(7):                                                # torres de los molinos
            x = 228 + i * 44 + rng.randint(-6, 6)
            self.molinos.append(x - MARGEN)
            pygame.draw.line(s, (240, 244, 248), (x, 152), (x, 118), 1)
            s.fill((240, 244, 248), (x - 1, 116, 3, 3))
        self.capas.append((c.cerrar(), 0.05))

        # Capa 1: dunas amarillas y salinas rosadas con flamencos
        c = Lienzo()
        s = c.sup
        for i in range(8):
            x = i * 80 + rng.randint(-10, 10)
            w, h = rng.randint(90, 140), rng.randint(20, 34)
            puntos = [(x - w // 2 + k, 170 - int(h * math.sin(k / w * math.pi) ** 1.5)) for k in range(0, w + 1, 3)]
            pygame.draw.polygon(s, (250, 204, 90), puntos + [(x + w // 2, 172), (x - w // 2, 172)])
            sombra = [(px, py) for px, py in puntos if px > x]          # lado de sotavento
            if len(sombra) > 2:
                pygame.draw.polygon(s, (226, 168, 70), sombra + [(x + w // 2, 172), (x, 172)])
            pygame.draw.lines(s, (255, 232, 150), False, puntos[:len(puntos) // 2], 1)
        pygame.draw.rect(s, (240, 190, 90), (0, 170, s.get_width(), 60))
        for px in (100, 380):                                             # salinas
            pygame.draw.ellipse(s, (236, 150, 170), (px, 166, 80, 12))
            pygame.draw.ellipse(s, (250, 190, 200), (px + 6, 168, 60, 6))
            for k in range(5):                                            # montañas de sal
                pygame.draw.polygon(s, (250, 250, 250), [(px + 84 + k * 10, 172), (px + 88 + k * 10, 162 - k % 2 * 3),
                                                         (px + 93 + k * 10, 172)])
            for k in range(4):
                self.flamencos.append((px + 14 + k * 14 - MARGEN, 167))
        self.capas.append((c.cerrar(), 0.14))

        # Capa 2: rancherías wayuu, cardones, trupillos y un puesto de pimpinas
        c = Lienzo()
        s = c.sup
        pygame.draw.rect(s, (232, 176, 80), (0, 186, s.get_width(), 40))
        for i in range(3):
            x = 40 + i * 180 + rng.randint(-10, 10)
            self._rancheria(s, x, 188, rng)
        for _ in range(7):
            x = rng.randint(0, s.get_width())
            if rng.random() < 0.6:
                self._cardon(s, x, 190, rng.randint(22, 40))
            else:
                self._trupillo(s, x, 190)
        for x in (300,):                                                  # gasolina de contrabando
            pygame.draw.rect(s, (130, 90, 50), (x, 176, 26, 3))
            pygame.draw.line(s, (100, 70, 40), (x + 2, 179), (x + 2, 190))
            pygame.draw.line(s, (100, 70, 40), (x + 23, 179), (x + 23, 190))
            for k in range(5):
                s.fill((240, 200, 40) if k % 2 else (220, 60, 40), (x + 2 + k * 5, 170, 4, 6))
                s.fill((40, 40, 40), (x + 3 + k * 5, 169, 2, 1))
            pygame.draw.rect(s, (250, 250, 240), (x - 12, 158, 51, 10))
            pygame.draw.rect(s, (200, 40, 30), (x - 12, 158, 51, 10), 1)
            dibujar_texto(s, "GASOLINA", (x - 10, 159), (200, 40, 30), sombra=False)
            pygame.draw.line(s, (100, 70, 40), (x + 13, 168), (x + 13, 176))
        self.capas.append((c.cerrar(), 0.34))


    @staticmethod
    def _cardon(s, x, base, alto, color=(80, 150, 80)):
        """Cardón: cactus columnar con brazos que suben."""
        claro = tuple(min(255, c + 40) for c in color)
        pygame.draw.rect(s, color, (x, base - alto, 4, alto))
        pygame.draw.line(s, claro, (x + 1, base - alto), (x + 1, base - 1))
        for lado, y in ((-1, base - alto * 0.55), (1, base - alto * 0.7)):
            y = int(y)
            bx = x - 5 if lado < 0 else x + 4
            pygame.draw.rect(s, color, (bx, y, 5, 3))
            pygame.draw.rect(s, color, (bx if lado < 0 else bx + 2, y - 10, 3, 12))

    @staticmethod
    def _trupillo(s, x, base):
        """Trupillo: árbol torcido del desierto, copa plana verde oliva."""
        pygame.draw.line(s, (110, 80, 50), (x, base), (x + 3, base - 10), 2)
        pygame.draw.line(s, (110, 80, 50), (x + 3, base - 10), (x - 2, base - 16), 1)
        pygame.draw.line(s, (110, 80, 50), (x + 3, base - 10), (x + 9, base - 15), 1)
        pygame.draw.ellipse(s, (120, 140, 60), (x - 10, base - 22, 24, 8))
        pygame.draw.ellipse(s, (150, 170, 70), (x - 6, base - 23, 14, 4))

    @staticmethod
    def _rancheria(s, x, base, rng):
        """Ranchería wayuu: casa de yotojoro, enramada y chinchorros de colores."""
        pygame.draw.rect(s, (180, 120, 70), (x, base - 16, 22, 16))                 # muro de barro
        for k in range(x + 2, x + 21, 4):
            pygame.draw.line(s, (140, 90, 50), (k, base - 15), (k, base - 1))       # varas de yotojoro
        pygame.draw.rect(s, (120, 80, 50), (x - 2, base - 19, 26, 3))               # techo plano
        pygame.draw.rect(s, (60, 40, 30), (x + 8, base - 9, 5, 9))                  # puerta
        ex = x + 30                                                                  # enramada
        for k in (0, 24):
            pygame.draw.line(s, (120, 86, 50), (ex + k, base), (ex + k, base - 16))
        pygame.draw.rect(s, (150, 120, 70), (ex - 2, base - 18, 28, 3))
        colores = [(220, 40, 80), (40, 170, 90), (240, 170, 30), (140, 60, 200), (30, 140, 210)]
        rng.shuffle(colores)
        for k in range(2):                                                          # chinchorros
            y0 = base - 14 + k * 5
            for j in range(22):
                y = y0 + int(math.sin(j / 21 * math.pi) * 4)
                s.set_at((ex + 1 + j, y), colores[(j // 3 + k) % len(colores)])
                s.set_at((ex + 1 + j, y + 1), colores[(j // 3 + k + 1) % len(colores)])

    def cielo_vivo(self, sup, camara_x, t):
        sup.blit(self.sol, (206 - 40, 40 - 40))
        pygame.draw.circle(sup, (255, 255, 236), (206, 40), 15)

    def entre(self, sup, n, camara_x, t):
        if n == 0:
            for k in range(14):                                           # el mar brilla
                if int(t * 3 + k * 1.7) % 4 == 0:
                    x = int((k * 37 - camara_x * 0.05) % settings.ANCHO)
                    sup.fill((255, 255, 255), (x, 141 + (k * 5) % 12, 2, 1))
            for i, mx in enumerate(self.molinos):                         # aspas que giran
                ang = t * 2.2 + i * 0.7

                def aspas(x, ang=ang):
                    for k in range(3):
                        a = ang + k * math.tau / 3
                        pygame.draw.line(sup, (250, 252, 255), (x, 117), (x + math.cos(a) * 9, 117 + math.sin(a) * 9))
                _repetir(sup, _pos_capa(mx, camara_x, 0.05), aspas, 12)
        if n == 1:
            for i, (fx, fy) in enumerate(self.flamencos):                 # flamencos rosados
                def flamenco(x, fy=fy, i=i):
                    pygame.draw.line(sup, (240, 110, 140), (x, fy), (x, fy - 4))
                    sup.fill((250, 140, 170), (x - 1, fy - 7, 4, 3))
                    cuello = 1 if int(t * 0.7 + i) % 5 == 0 else 0
                    pygame.draw.line(sup, (250, 140, 170), (x + 2, fy - 7), (x + 3, fy - 10 + cuello * 3))
                _repetir(sup, _pos_capa(fx, camara_x, 0.14), flamenco, 8)


PAISAJES = {"vichada": Vichada, "medellin": Medellin, "guajira": Guajira}


def crear(amb: dict):
    """El paisaje del ambiente, o None si el nivel usa las capas simples de antes."""
    clase = PAISAJES.get(amb.get("paisaje"))
    return clase(amb) if clase else None
