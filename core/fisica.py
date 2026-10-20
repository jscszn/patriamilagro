"""Física sencilla: cuerpos con gravedad que chocan contra la geometría del nivel.

La geometría (suelo, bloques, plataformas) son pygame.Rect estáticos construidos a partir
de los datos de levels/. Los cuerpos guardan su posición en float para moverse suave y
se comparan contra los Rect con aritmética de punto flotante (evita errores de redondeo).
"""
from __future__ import annotations

from dataclasses import dataclass

import pygame

import settings


@dataclass
class Cuerpo:
    """Caja que se mueve. (x, y) es la esquina superior izquierda."""
    x: float = 0.0
    y: float = 0.0
    ancho: int = 10
    alto: int = 22
    vx: float = 0.0
    vy: float = 0.0
    en_suelo: bool = False
    choco_pared: bool = False

    @property
    def rect(self) -> pygame.Rect:
        return pygame.Rect(int(self.x), int(self.y), self.ancho, self.alto)

    @property
    def centro(self):
        return self.x + self.ancho / 2, self.y + self.alto / 2

    @property
    def pie(self) -> float:
        return self.y + self.alto


def _se_solapan(c: Cuerpo, r: pygame.Rect) -> bool:
    return c.x < r.right and c.x + c.ancho > r.left and c.y < r.bottom and c.y + c.alto > r.top


class Geometria:
    """Colisiones estáticas de un nivel."""

    def __init__(self, datos_nivel: dict):
        fondo = settings.ALTO + 64
        self.largo = datos_nivel["largo"]
        # Suelo: tramos [x_inicio, x_fin, y_superficie]; los huecos entre tramos son precipicios.
        self.solidos = [pygame.Rect(x0, y, x1 - x0, fondo - y) for x0, x1, y in datos_nivel["suelo"]]
        # Bloques sólidos [x, y, ancho, alto] (cajas, muros bajos).
        self.solidos += [pygame.Rect(*b) for b in datos_nivel.get("bloques", [])]
        # Plataformas de una sola vía [x, y, ancho]: se atraviesan desde abajo.
        self.plataformas = [pygame.Rect(x, y, w, 4) for x, y, w in datos_nivel.get("plataformas", [])]

    def mover(self, c: Cuerpo, dt: float, atravesar_plataformas: bool = False) -> None:
        """Aplica gravedad y mueve el cuerpo resolviendo colisiones eje por eje."""
        # 1) Eje horizontal
        c.choco_pared = False
        c.x += c.vx * dt
        for s in self.solidos:
            if _se_solapan(c, s):
                if c.vx > 0:
                    c.x = s.left - c.ancho
                elif c.vx < 0:
                    c.x = s.right
                c.choco_pared = True

        # 2) Eje vertical
        c.vy = min(c.vy + settings.GRAVEDAD * dt, settings.VEL_CAIDA_MAX)
        pie_antes = c.pie
        c.y += c.vy * dt
        c.en_suelo = False
        for s in self.solidos:
            if _se_solapan(c, s):
                if c.vy > 0:
                    c.y = s.top - c.alto
                    c.en_suelo = True
                elif c.vy < 0:
                    c.y = s.bottom
                c.vy = 0.0
        if c.vy >= 0 and not atravesar_plataformas:
            for p in self.plataformas:
                # Solo se aterriza si antes del paso los pies estaban por encima de la plataforma.
                if _se_solapan(c, p) and pie_antes <= p.top + 0.01:
                    c.y = p.top - c.alto
                    c.vy = 0.0
                    c.en_suelo = True

    def hay_suelo_bajo(self, x: float, y_pie: float) -> bool:
        """¿Hay suelo o plataforma justo debajo del punto (x, y_pie)?"""
        punto = pygame.Rect(int(x), int(y_pie) + 1, 1, 2)
        return any(punto.colliderect(r) for r in self.solidos + self.plataformas)

    def altura_suelo(self, x: float) -> float:
        """Altura de la superficie de suelo en la columna x (o un valor bajo si es precipicio)."""
        alturas = [s.top for s in self.solidos if s.left <= x < s.right]
        return min(alturas) if alturas else settings.ALTO + 64

    def sobre_plataforma(self, c: Cuerpo) -> bool:
        """¿El cuerpo está parado sobre una plataforma de una vía (y no sobre suelo sólido)?"""
        for p in self.plataformas:
            if abs(c.pie - p.top) < 1 and c.x < p.right and c.x + c.ancho > p.left:
                return True
        return False
