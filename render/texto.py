"""Utilidades para dibujar texto en la superficie interna (pixel art, sin suavizado)."""
from __future__ import annotations

import os
from typing import Dict, List, Tuple

import pygame

import settings
from render.fuente_pixel import FuentePixel

_fuentes: Dict[int, object] = {}
RUTA_FUENTE = os.path.join(settings.RUTA_ASSETS, "fuentes", "pixel.ttf")


def fuente(escala: int = 1):
    """Fuente del juego en la escala dada (1 = 5x7 px).

    Si existe assets/fuentes/pixel.ttf se usa esa; si no, la fuente bitmap generada por código.
    """
    if escala not in _fuentes:
        if os.path.exists(RUTA_FUENTE):
            _fuentes[escala] = pygame.font.Font(RUTA_FUENTE, 8 * escala)
        else:
            _fuentes[escala] = FuentePixel(escala)
    return _fuentes[escala]


def dibujar_texto(superficie: pygame.Surface, texto: str, pos: Tuple[int, int],
                  color=settings.COLORES["blanco"], escala: int = 1,
                  centrado: bool = False, sombra: bool = True, derecha: bool = False) -> pygame.Rect:
    """Dibuja una línea de texto. pos es la esquina superior izquierda; con centrado=True es el
    centro superior y con derecha=True la esquina superior derecha."""
    f = fuente(escala)
    imagen = f.render(texto, False, color)
    rect = imagen.get_rect()
    if centrado:
        rect.midtop = pos
    elif derecha:
        rect.topright = pos
    else:
        rect.topleft = pos
    if sombra:
        superficie.blit(f.render(texto, False, settings.COLORES["negro"]), rect.move(1, 1))
    superficie.blit(imagen, rect)
    return rect


def envolver(texto: str, escala: int, ancho_max: int) -> List[str]:
    """Parte un texto en líneas que quepan en ancho_max píxeles."""
    f = fuente(escala)
    lineas: List[str] = []
    for parrafo in texto.split("\n"):
        actual = ""
        for palabra in parrafo.split(" "):
            prueba = palabra if not actual else actual + " " + palabra
            if f.size(prueba)[0] <= ancho_max:
                actual = prueba
            else:
                if actual:
                    lineas.append(actual)
                actual = palabra
        lineas.append(actual)
    return lineas


def dibujar_parrafo(superficie: pygame.Surface, texto: str, pos: Tuple[int, int], ancho_max: int,
                    color=settings.COLORES["blanco"], escala: int = 1, interlineado: int = 2) -> int:
    """Dibuja texto envuelto; devuelve la coordenada y donde terminó."""
    x, y = pos
    alto = fuente(escala).get_linesize() + interlineado
    for linea in envolver(texto, escala, ancho_max):
        dibujar_texto(superficie, linea, (x, y), color, escala)
        y += alto
    return y
