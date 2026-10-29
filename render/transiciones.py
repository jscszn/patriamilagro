"""Transición entre escenas al estilo NES: una cortina de rombos negros que barre la pantalla.

Primera mitad: los rombos crecen sobre el último cuadro de la escena anterior hasta taparla.
Segunda mitad: se encogen en el mismo orden y destapan la escena nueva. El barrido va de la
esquina de arriba a la izquierda hacia la de abajo a la derecha.
"""
from __future__ import annotations

from typing import Optional

import pygame

import settings

CELDA = 16
COLUMNAS = settings.ANCHO // CELDA + 1
FILAS = settings.ALTO // CELDA + 1
DESFASE = 0.55            # qué parte de cada mitad ocupa el retraso del barrido


def _rombos(sup: pygame.Surface, progreso: float, destapando: bool = False) -> None:
    """progreso 0 = nada tapado; 1 = todo negro. Al destapar, el orden se invierte para que el
    barrido siga en la misma dirección (lo primero que se tapó es lo primero que se ve)."""
    if progreso <= 0:
        return
    if progreso >= 1:
        sup.fill((0, 0, 0))
        return
    total = COLUMNAS + FILAS * 0.6
    for fila in range(FILAS):
        for col in range(COLUMNAS):
            orden = (col + fila * 0.6) / total
            retraso = (1 - orden if destapando else orden) * DESFASE
            local = (progreso - retraso) / (1 - DESFASE)
            if local <= 0:
                continue
            cx, cy = col * CELDA + CELDA // 2, fila * CELDA + CELDA // 2
            if local >= 1:
                sup.fill((0, 0, 0), (cx - CELDA // 2, cy - CELDA // 2, CELDA, CELDA))
                continue
            r = int(local * CELDA)
            pygame.draw.polygon(sup, (0, 0, 0), [(cx, cy - r), (cx + r, cy), (cx, cy + r), (cx - r, cy)])


class Transicion:
    def __init__(self, duracion: float = 0.4):
        self.duracion = duracion
        self.t = duracion                       # terminada
        self.anterior: Optional[pygame.Surface] = None

    @property
    def activa(self) -> bool:
        return self.t < self.duracion

    def iniciar(self, ultimo_cuadro: pygame.Surface) -> None:
        self.anterior = ultimo_cuadro.copy()
        self.t = 0.0

    def avanzar(self, dt: float) -> None:
        self.t = min(self.duracion, self.t + dt)
        if not self.activa:
            self.anterior = None

    def dibujar(self, sup: pygame.Surface) -> None:
        """Se llama DESPUÉS de dibujar la escena nueva en `sup`."""
        if not self.activa:
            return
        mitad = self.duracion / 2
        if self.t < mitad:                       # tapando la escena anterior
            if self.anterior is not None:
                sup.blit(self.anterior, (0, 0))
            _rombos(sup, self.t / mitad)
        else:                                    # destapando la nueva
            _rombos(sup, 1 - (self.t - mitad) / mitad, destapando=True)
