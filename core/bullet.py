"""Balas y proyectiles (incluye la onda de choque del jefe 3)."""
from __future__ import annotations

from dataclasses import asdict, dataclass

import pygame


@dataclass
class Bala:
    x: float                     # centro
    y: float
    vx: float
    vy: float
    del_jugador: bool            # True = la disparó un jugador; False = enemigo o jefe
    dano: int = 1
    tipo: str = "normal"         # normal | jefe | onda  (solo cambia cómo se dibuja)
    radio: int = 2
    alto: int = 0                # para la onda: es una caja alta pegada al suelo
    dueno: int = 0               # id del jugador que disparó (para el puntaje)
    vivo: bool = True

    @property
    def rect(self) -> pygame.Rect:
        if self.alto:
            return pygame.Rect(int(self.x - 5), int(self.y - self.alto), 10, self.alto)
        return pygame.Rect(int(self.x - self.radio), int(self.y - self.radio), self.radio * 2, self.radio * 2)

    def update(self, dt: float) -> None:
        self.x += self.vx * dt
        self.y += self.vy * dt

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Bala":
        return cls(**d)
