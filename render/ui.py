"""Componentes de interfaz reutilizables: lista navegable con cruceta y fondos."""
from __future__ import annotations

import math
from typing import List

import pygame

import input_manager as im
import settings
from audio import gestor as audio
from render.texto import dibujar_texto

C = settings.COLORES


class ListaOpciones:
    """Lista vertical de opciones navegable con ARRIBA/ABAJO (lógica separada del dibujo)."""

    def __init__(self, opciones: List[str]):
        self.opciones = opciones
        self.indice = 0
        self.tiempo = 0.0

    @property
    def seleccion(self) -> str:
        return self.opciones[self.indice]

    def update(self, dt: float, acciones: im.EstadoAcciones) -> bool:
        """Mueve la selección. Devuelve True si el jugador confirmó."""
        self.tiempo += dt
        if acciones.pulso(im.ARRIBA):
            self.indice = (self.indice - 1) % len(self.opciones)
            self.al_mover()
        if acciones.pulso(im.ABAJO):
            self.indice = (self.indice + 1) % len(self.opciones)
            self.al_mover()
        if acciones.pulso(im.CONFIRMAR):
            audio.efecto("confirmar")
            return True
        return False

    def al_mover(self) -> None:
        audio.efecto("mover")

    def draw(self, superficie: pygame.Surface, centro_x: int, y: int, separacion: int = 16,
             textos: List[str] = None, escala: int = 1) -> None:
        textos = textos or self.opciones
        for i, texto in enumerate(textos):
            seleccionado = i == self.indice
            color = C["amarillo"] if seleccionado else C["blanco"]
            rect = dibujar_texto(superficie, texto, (centro_x, y + i * separacion), color, escala, centrado=True)
            if seleccionado:
                # Flecha que "late" junto a la opción elegida
                dx = int(math.sin(self.tiempo * 8) * 2)
                punta = (rect.left - 6 + dx, rect.centery)
                pygame.draw.polygon(superficie, C["amarillo"],
                                    [(punta[0] - 4, punta[1] - 3), (punta[0] - 4, punta[1] + 3), punta])


def superficie_opaca(tam) -> pygame.Surface:
    """Superficie de 32 bits SIN canal alfa, para dibujar la imagen del juego.

    Sin máscara explícita, pygame copia el formato de la ventana, y en macOS la ventana tiene
    canal alfa (ARGB). Entonces el alfa del lienzo queda en 0 tras algunos blits, y al pegar
    encima una imagen con transparencia y set_alpha() (haces de luz, velos) SDL mezcla contra
    ese 0 y el resultado sale NEGRO. Con un lienzo sin alfa, las mezclas son las normales."""
    return pygame.Surface(tam, 0, 32, (0xFF0000, 0x00FF00, 0x0000FF, 0))


def dibujar_marco(superficie: pygame.Surface, rect: pygame.Rect,
                  fondo=(0, 0, 40), borde=C["blanco"]) -> None:
    """Recuadro estilo NES con borde doble."""
    pygame.draw.rect(superficie, fondo, rect)
    pygame.draw.rect(superficie, borde, rect, 1)
    pygame.draw.rect(superficie, C["gris"], rect.inflate(-4, -4), 1)


_velos = {}


def oscurecer(superficie: pygame.Surface, alfa: int = 160) -> None:
    """Cubre la pantalla con negro semitransparente (para menús superpuestos)."""
    velo = _velos.get((superficie.get_size(), alfa))
    if velo is None:
        velo = pygame.Surface(superficie.get_size(), pygame.SRCALPHA)
        velo.fill((0, 0, 0, alfa))
        _velos[(superficie.get_size(), alfa)] = velo
    superficie.blit(velo, (0, 0))
