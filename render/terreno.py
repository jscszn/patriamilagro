"""Terreno pintado UNA vez por nivel: suelo, plataformas y bloques con el estilo de cada lugar.

Todo el nivel queda en una sola superficie (largo x 224). Al jugar se copia el pedazo que se
ve: un blit por cuadro en vez de cientos de baldosas, y por eso el suelo puede tener mucho
más detalle (pasto, piedras, raíces, estratos, adoquines, ladrillos, ondas de arena).

Estilos (ambiente["estilo"]): "selva", "ciudad", "desierto". La geometría (lo que choca) no
cambia: este archivo solo decide cómo se ve.
"""
from __future__ import annotations

import math
import random
from typing import Tuple

import pygame

import settings

Color = Tuple[int, int, int]


def _mezclar(a: Color, b: Color, t: float) -> Color:
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def _oscuro(c: Color, k: float) -> Color:
    return tuple(max(0, int(v * k)) for v in c)


def _claro(c: Color, k: int) -> Color:
    return tuple(min(255, v + k) for v in c)


class PintorTerreno:
    def __init__(self, datos_nivel: dict, geometria):
        self.datos = datos_nivel
        self.amb = datos_nivel["ambiente"]
        self.estilo = self.amb.get("estilo", "selva")
        self.geo = geometria
        self.largo = datos_nivel["largo"]
        self.rng = random.Random(datos_nivel.get("numero", 1) * 97)
        self.sup = pygame.Surface((self.largo, settings.ALTO), pygame.SRCALPHA)

    # --- Entrada ------------------------------------------------------------------------------
    def pintar(self) -> pygame.Surface:
        bloques = {tuple(b) for b in self.datos.get("bloques", [])}
        suelos = [r for r in self.geo.solidos if (r.x, r.y, r.w, r.h) not in bloques]
        for r in suelos:
            self._suelo(r, suelos)
        for r in self.geo.solidos:
            if (r.x, r.y, r.w, r.h) in bloques:
                self._bloque(r)
        for p in self.geo.plataformas:
            self._plataforma(p)
        return self.sup

    # --- Suelo ------------------------------------------------------------------------------------
    def _suelo(self, r: pygame.Rect, suelos) -> None:
        sup, rng = self.sup, self.rng
        base, detalle, borde = self.amb["suelo"], self.amb["suelo_detalle"], self.amb["suelo_borde"]
        alto = settings.ALTO - r.top
        # Cuerpo con degradado: más oscuro hacia abajo
        for dy in range(alto):
            k = 1.0 - 0.45 * min(1.0, dy / 40)
            pygame.draw.line(sup, _oscuro(base, k), (r.left, r.top + dy), (r.right - 1, r.top + dy))
        getattr(self, f"_cuerpo_{self.estilo}", self._cuerpo_selva)(r, base, detalle)
        # Bordes de los precipicios: si no hay otro suelo pegado, el lado se oscurece
        for x_borde, hacia in ((r.left, 1), (r.right - 1, -1)):
            pegado = any(o is not r and o.left <= x_borde + (-1 if hacia > 0 else 1) < o.right and o.top <= r.top + 6
                         for o in suelos)
            if not pegado:
                for i in range(3):
                    pygame.draw.line(sup, _oscuro(base, 0.45 + i * 0.15),
                                     (x_borde + hacia * i, r.top + 4), (x_borde + hacia * i, settings.ALTO))
        getattr(self, f"_superficie_{self.estilo}", self._superficie_selva)(r, borde)

    # Selva: tierra con piedras, raíces y pasto que cuelga
    def _cuerpo_selva(self, r, base, detalle):
        sup, rng = self.sup, self.rng
        for y0 in (r.top + 14, r.top + 26):                       # vetas de tierra más oscura
            for x in range(r.left, r.right):
                y = y0 + int(math.sin(x * 0.09 + y0) * 2)
                sup.set_at((x, y), _oscuro(base, 0.62))
        for _ in range(r.w // 3):                                 # granitos
            x, y = rng.randrange(r.left, r.right), rng.randrange(r.top + 6, settings.ALTO)
            sup.fill(_oscuro(detalle, 0.9 if rng.random() < 0.5 else 0.7), (x, y, rng.choice((1, 2)), 1))
        for _ in range(max(1, r.w // 40)):                        # piedras
            x, y = rng.randrange(r.left + 4, max(r.left + 5, r.right - 6)), rng.randrange(r.top + 9, settings.ALTO - 4)
            w = rng.randint(3, 6)
            pygame.draw.ellipse(sup, (96, 84, 72), (x, y, w, max(2, w - 2)))
            sup.set_at((x + 1, y), (140, 128, 110))
            pygame.draw.line(sup, (60, 50, 40), (x + 1, y + max(2, w - 2)), (x + w - 2, y + max(2, w - 2)))
        for _ in range(max(1, r.w // 56)):                        # raíces
            x = rng.randrange(r.left + 3, max(r.left + 4, r.right - 3))
            y = r.top + 5
            for _ in range(rng.randint(6, 12)):
                sup.set_at((x, y), (70, 44, 22))
                y += 1
                x += rng.choice((-1, 0, 0, 1))

    def _superficie_selva(self, r, borde):
        sup, rng = self.sup, self.rng
        oscuro, claro = _oscuro(borde, 0.62), _claro(borde, 40)
        pygame.draw.rect(sup, borde, (r.left, r.top, r.w, 4))
        pygame.draw.line(sup, claro, (r.left, r.top), (r.right - 1, r.top))
        pygame.draw.line(sup, oscuro, (r.left, r.top + 4), (r.right - 1, r.top + 4))
        for x in range(r.left, r.right):                          # pasto que cuelga sobre la tierra
            if rng.random() < 0.35:
                largo = rng.choice((1, 1, 2, 3))
                pygame.draw.line(sup, borde if largo < 3 else oscuro, (x, r.top + 4), (x, r.top + 4 + largo))
            if rng.random() < 0.3:                                # hojas que asoman hacia arriba
                sup.set_at((x, r.top - 1), claro if rng.random() < 0.5 else borde)
                if rng.random() < 0.3:
                    sup.set_at((x, r.top - 2), borde)

    # Ciudad: bordillo, acera con juntas y muro de ladrillo con rejillas
    def _cuerpo_ciudad(self, r, base, detalle):
        sup, rng = self.sup, self.rng
        acera = _claro(base, 28)
        pygame.draw.rect(sup, acera, (r.left, r.top + 4, r.w, 7))
        pygame.draw.line(sup, _oscuro(acera, 0.7), (r.left, r.top + 11), (r.right - 1, r.top + 11))
        for x in range(r.left - r.left % 16, r.right, 16):        # juntas de la acera
            if x >= r.left:
                pygame.draw.line(sup, _oscuro(acera, 0.75), (x, r.top + 5), (x, r.top + 10))
        ladrillo = _oscuro(base, 0.85)
        junta = _oscuro(base, 0.55)
        for fila, y in enumerate(range(r.top + 12, settings.ALTO, 5)):
            k = 1.0 - 0.4 * min(1.0, (y - r.top) / 40)
            pygame.draw.rect(sup, _oscuro(ladrillo, k), (r.left, y, r.w, 4))
            pygame.draw.line(sup, _oscuro(junta, k), (r.left, y + 4), (r.right - 1, y + 4))
            desfase = 0 if fila % 2 else 6
            for x in range(r.left - (r.left % 12) + desfase, r.right, 12):
                if x >= r.left:
                    sup.set_at((x, y + 1), _oscuro(junta, k))
                    sup.set_at((x, y + 2), _oscuro(junta, k))
            if rng.random() < 0.5:                                # ladrillos sueltos más claros
                x = rng.randrange(r.left, max(r.left + 1, r.right - 6))
                pygame.draw.line(sup, _oscuro(_claro(ladrillo, 12), k), (x + 1, y + 1), (x + 4, y + 1))
        for x in range(r.left + 40, r.right - 20, 150):           # rejillas de alcantarilla
            x += rng.randint(-20, 20)
            pygame.draw.rect(sup, (24, 24, 30), (x, r.top + 14, 12, 7))
            for bx in range(x + 2, x + 11, 3):
                pygame.draw.line(sup, (90, 90, 100), (bx, r.top + 14), (bx, r.top + 20))
        for _ in range(max(1, r.w // 90)):                        # grietas
            x, y = rng.randrange(r.left, max(r.left + 1, r.right - 8)), r.top + 5
            for _ in range(5):
                sup.set_at((x, y), _oscuro(acera, 0.6))
                x += 1
                y += rng.choice((0, 1)) if y < r.top + 10 else 0

    def _superficie_ciudad(self, r, borde):
        sup = self.sup
        pygame.draw.rect(sup, borde, (r.left, r.top, r.w, 4))
        pygame.draw.line(sup, _claro(borde, 40), (r.left, r.top), (r.right - 1, r.top))
        pygame.draw.line(sup, _oscuro(borde, 0.6), (r.left, r.top + 3), (r.right - 1, r.top + 3))
        for x in range(r.left - r.left % 32, r.right, 32):        # marcas del bordillo
            if x >= r.left:
                pygame.draw.line(sup, _oscuro(borde, 0.75), (x, r.top + 1), (x, r.top + 2))

    # Desierto: arena con ondas, guijarros y estratos rojizos
    def _cuerpo_desierto(self, r, base, detalle):
        sup, rng = self.sup, self.rng
        colores = self.amb.get("estratos", [(196, 120, 76), (160, 96, 62), (176, 110, 70)])
        bandas = [(10, 6, colores[0]), (22, 7, colores[1]), (34, 9, colores[2])]
        for prof, grosor, color in bandas:
            for x in range(r.left, r.right):
                y0 = r.top + prof + int(math.sin(x * 0.05 + prof) * 2 + math.sin(x * 0.17) * 1)
                k = 1.0 - 0.35 * min(1.0, prof / 40)
                pygame.draw.line(sup, _oscuro(color, k), (x, y0), (x, y0 + grosor - 1))
                sup.set_at((x, y0), _oscuro(color, k * 1.12 if k * 1.12 <= 1 else 1))
        for y in range(r.top + 6, r.top + 10, 3):                 # ondas de la arena
            for x in range(r.left, r.right):
                if math.sin(x * 0.4 + y) > 0.6:
                    sup.set_at((x, y + int(math.sin(x * 0.12) * 1)), _oscuro(base, 0.86))
        for _ in range(r.w // 10):                                # guijarros
            x, y = rng.randrange(r.left, r.right), rng.randrange(r.top + 6, settings.ALTO)
            sup.fill((130, 96, 70) if rng.random() < 0.5 else (214, 176, 120), (x, y, rng.choice((1, 2)), 1))
        for _ in range(max(1, r.w // 120)):                       # huesos o piedras enterradas
            x, y = rng.randrange(r.left + 4, max(r.left + 5, r.right - 8)), rng.randrange(r.top + 16, settings.ALTO - 6)
            pygame.draw.ellipse(sup, (120, 84, 60), (x, y, 7, 4))
            sup.set_at((x + 2, y + 1), (160, 120, 90))

    def _superficie_desierto(self, r, borde):
        sup, rng = self.sup, self.rng
        claro = _claro(borde, 26)
        for x in range(r.left, r.right):                          # cresta irregular (dunas chicas)
            alto = 4 + (1 if math.sin(x * 0.07) + math.sin(x * 0.19) > 1.1 else 0)
            pygame.draw.line(sup, borde, (x, r.top + (4 - alto) + 1), (x, r.top + 4))
            sup.set_at((x, r.top + (4 - alto) + 1), claro)
            if rng.random() < 0.08:
                sup.set_at((x, r.top + 3), _oscuro(borde, 0.8))
        pygame.draw.line(sup, _oscuro(borde, 0.7), (r.left, r.top + 5), (r.right - 1, r.top + 5))

    # --- Plataformas ---------------------------------------------------------------------------
    def _plataforma(self, p: pygame.Rect) -> None:
        sup, color = self.sup, self.amb["plataforma"]
        oscuro, claro = _oscuro(color, 0.65), _claro(color, 35)
        if self.estilo == "ciudad":                               # balcón de metal con remaches y cerchas
            pygame.draw.rect(sup, color, (p.left, p.top, p.w, 4))
            pygame.draw.line(sup, claro, (p.left, p.top), (p.right - 1, p.top))
            pygame.draw.line(sup, oscuro, (p.left, p.top + 4), (p.right - 1, p.top + 4))
            for x in range(p.left + 3, p.right - 1, 8):
                sup.set_at((x, p.top + 2), oscuro)
            for x in range(p.left, p.right - 7, 8):               # cercha en X bajo el piso
                pygame.draw.line(sup, oscuro, (x, p.top + 5), (x + 7, p.top + 10))
                pygame.draw.line(sup, oscuro, (x + 7, p.top + 5), (x, p.top + 10))
            pygame.draw.line(sup, oscuro, (p.left, p.top + 10), (p.right - 1, p.top + 10))
        elif self.estilo == "desierto":                           # saliente de roca
            pygame.draw.rect(sup, color, (p.left, p.top, p.w, 5))
            pygame.draw.line(sup, self.amb["suelo_borde"], (p.left, p.top), (p.right - 1, p.top))
            pygame.draw.line(sup, claro, (p.left, p.top + 1), (p.right - 1, p.top + 1))
            for x in range(p.left, p.right):                      # borde inferior irregular
                colgar = int(3 + 2 * math.sin(x * 0.5) + 2 * math.sin(x * 0.23))
                if colgar > 0:
                    pygame.draw.line(sup, oscuro, (x, p.top + 5), (x, p.top + 4 + colgar))
            pygame.draw.line(sup, _oscuro(color, 0.5), (p.left, p.top), (p.left, p.top + 6))
            pygame.draw.line(sup, _oscuro(color, 0.5), (p.right - 1, p.top), (p.right - 1, p.top + 6))
        else:                                                     # tablones de madera con clavos y musgo
            pygame.draw.rect(sup, color, (p.left, p.top, p.w, 5))
            pygame.draw.line(sup, claro, (p.left, p.top), (p.right - 1, p.top))
            pygame.draw.line(sup, oscuro, (p.left, p.top + 4), (p.right - 1, p.top + 4))
            for x in range(p.left + 12, p.right - 1, 12):
                pygame.draw.line(sup, oscuro, (x, p.top + 1), (x, p.top + 3))
                sup.set_at((x - 2, p.top + 2), (200, 190, 170))
            for x in range(p.left + 1, p.right - 1):
                if self.rng.random() < 0.18:                      # musgo y lianitas que cuelgan
                    largo = self.rng.choice((1, 2, 2, 4))
                    pygame.draw.line(sup, (50, 130, 40), (x, p.top + 5), (x, p.top + 4 + largo))
            for x in (p.left + 3, p.right - 4):                   # cuerdas a los lados
                pygame.draw.line(sup, (150, 120, 70), (x, p.top + 5), (x, p.top + 8))

    # --- Bloques -------------------------------------------------------------------------------------
    def _bloque(self, r: pygame.Rect) -> None:
        if self.estilo == "ciudad":
            self._auto(r)
        elif self.estilo == "desierto":
            self._barriles(r)
        else:
            self._caja(r)

    def _caja(self, r):
        """Caja de madera con travesaño en diagonal."""
        sup = self.sup
        madera, oscuro, claro = (150, 100, 50), (90, 56, 26), (190, 140, 80)
        pygame.draw.rect(sup, madera, r)
        for y in range(r.top + 4, r.bottom - 1, 4):
            pygame.draw.line(sup, _oscuro(madera, 0.85), (r.left + 2, y), (r.right - 3, y))
        pygame.draw.line(sup, oscuro, (r.left + 2, r.bottom - 3), (r.right - 3, r.top + 2), 2)
        pygame.draw.rect(sup, oscuro, r, 2)
        pygame.draw.line(sup, claro, (r.left + 1, r.top + 1), (r.right - 2, r.top + 1))
        for x, y in ((r.left + 1, r.top + 1), (r.right - 2, r.top + 1), (r.left + 1, r.bottom - 2), (r.right - 2, r.bottom - 2)):
            sup.set_at((x, y), (210, 200, 180))

    def _auto(self, r):
        """Auto estacionado (32 x 16) visto de lado."""
        sup = self.sup
        colores = [(170, 40, 40), (40, 90, 160), (200, 170, 60), (70, 130, 90)]
        carro = colores[(r.left // 32) % len(colores)]
        oscuro, claro = _oscuro(carro, 0.6), _claro(carro, 50)
        x, y, w, h = r
        pygame.draw.rect(sup, carro, (x, y + 6, w, h - 9))                       # carrocería
        pygame.draw.polygon(sup, carro, [(x + 7, y + 6), (x + 10, y), (x + 23, y), (x + 27, y + 6)])  # cabina
        pygame.draw.polygon(sup, (140, 180, 210), [(x + 9, y + 6), (x + 11, y + 2), (x + 16, y + 2), (x + 16, y + 6)])
        pygame.draw.polygon(sup, (110, 150, 190), [(x + 18, y + 6), (x + 18, y + 2), (x + 22, y + 2), (x + 25, y + 6)])
        pygame.draw.line(sup, claro, (x + 1, y + 6), (x + w - 2, y + 6))
        pygame.draw.line(sup, oscuro, (x, y + h - 4), (x + w - 1, y + h - 4))
        pygame.draw.line(sup, oscuro, (x + 17, y + 7), (x + 17, y + h - 5))      # puerta
        sup.fill((255, 240, 170), (x + w - 2, y + 7, 2, 2))                     # faro
        sup.fill((200, 30, 30), (x, y + 7, 1, 2))                               # luz trasera
        for cx in (x + 7, x + w - 8):                                           # ruedas
            pygame.draw.circle(sup, (20, 20, 24), (cx, y + h - 3), 3)
            sup.set_at((cx, y + h - 3), (140, 140, 150))

    def _barriles(self, r):
        """Barriles oxidados apoyados uno al lado del otro."""
        sup = self.sup
        ancho = 12 if r.w >= 24 else r.w
        for i, x in enumerate(range(r.left, r.right - ancho + 1, ancho)):
            color = (150, 70, 40) if i % 2 == 0 else (110, 100, 60)
            pygame.draw.rect(sup, color, (x + 1, r.top + 1, ancho - 2, r.h - 1))
            pygame.draw.rect(sup, _oscuro(color, 0.55), (x + 1, r.top + 1, ancho - 2, r.h - 1), 1)
            for y in (r.top + 4, r.bottom - 5):
                pygame.draw.line(sup, _oscuro(color, 0.55), (x + 1, y), (x + ancho - 2, y))
            pygame.draw.line(sup, _claro(color, 45), (x + 3, r.top + 2), (x + 3, r.bottom - 2))
            pygame.draw.ellipse(sup, _oscuro(color, 0.8), (x + 1, r.top, ancho - 2, 3))


def pintar(datos_nivel: dict, geometria) -> pygame.Surface:
    return PintorTerreno(datos_nivel, geometria).pintar()
