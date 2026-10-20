"""Fuente bitmap 5x7 generada por código (estilo NES, solo mayúsculas).

Cada glifo es una lista de 7 filas de 5 caracteres ('#' = píxel encendido).
Las vocales con tilde y la Ñ se construyen con el glifo base más una marca encima,
por eso la celda mide 9 píxeles de alto (2 filas extra para tildes).
"""
from __future__ import annotations

from typing import Dict, Tuple

import pygame

ANCHO_GLIFO, ALTO_GLIFO, MARGEN_SUP = 5, 7, 2
AVANCE = ANCHO_GLIFO + 1            # 1 píxel de espacio entre letras
ALTO_LINEA = ALTO_GLIFO + MARGEN_SUP + 1

_G = {
    "A": [" ### ", "#   #", "#   #", "#####", "#   #", "#   #", "#   #"],
    "B": ["#### ", "#   #", "#   #", "#### ", "#   #", "#   #", "#### "],
    "C": [" ### ", "#   #", "#    ", "#    ", "#    ", "#   #", " ### "],
    "D": ["#### ", "#   #", "#   #", "#   #", "#   #", "#   #", "#### "],
    "E": ["#####", "#    ", "#    ", "#### ", "#    ", "#    ", "#####"],
    "F": ["#####", "#    ", "#    ", "#### ", "#    ", "#    ", "#    "],
    "G": [" ### ", "#   #", "#    ", "# ###", "#   #", "#   #", " ####"],
    "H": ["#   #", "#   #", "#   #", "#####", "#   #", "#   #", "#   #"],
    "I": [" ### ", "  #  ", "  #  ", "  #  ", "  #  ", "  #  ", " ### "],
    "J": ["  ###", "   # ", "   # ", "   # ", "   # ", "#  # ", " ##  "],
    "K": ["#   #", "#  # ", "# #  ", "##   ", "# #  ", "#  # ", "#   #"],
    "L": ["#    ", "#    ", "#    ", "#    ", "#    ", "#    ", "#####"],
    "M": ["#   #", "## ##", "# # #", "# # #", "#   #", "#   #", "#   #"],
    "N": ["#   #", "##  #", "# # #", "#  ##", "#   #", "#   #", "#   #"],
    "O": [" ### ", "#   #", "#   #", "#   #", "#   #", "#   #", " ### "],
    "P": ["#### ", "#   #", "#   #", "#### ", "#    ", "#    ", "#    "],
    "Q": [" ### ", "#   #", "#   #", "#   #", "# # #", "#  # ", " ## #"],
    "R": ["#### ", "#   #", "#   #", "#### ", "# #  ", "#  # ", "#   #"],
    "S": [" ####", "#    ", "#    ", " ### ", "    #", "    #", "#### "],
    "T": ["#####", "  #  ", "  #  ", "  #  ", "  #  ", "  #  ", "  #  "],
    "U": ["#   #", "#   #", "#   #", "#   #", "#   #", "#   #", " ### "],
    "V": ["#   #", "#   #", "#   #", "#   #", "#   #", " # # ", "  #  "],
    "W": ["#   #", "#   #", "#   #", "# # #", "# # #", "# # #", " # # "],
    "X": ["#   #", "#   #", " # # ", "  #  ", " # # ", "#   #", "#   #"],
    "Y": ["#   #", "#   #", " # # ", "  #  ", "  #  ", "  #  ", "  #  "],
    "Z": ["#####", "    #", "   # ", "  #  ", " #   ", "#    ", "#####"],
    "0": [" ### ", "#   #", "#  ##", "# # #", "##  #", "#   #", " ### "],
    "1": ["  #  ", " ##  ", "  #  ", "  #  ", "  #  ", "  #  ", " ### "],
    "2": [" ### ", "#   #", "    #", "   # ", "  #  ", " #   ", "#####"],
    "3": ["#####", "   # ", "  #  ", "   # ", "    #", "#   #", " ### "],
    "4": ["   # ", "  ## ", " # # ", "#  # ", "#####", "   # ", "   # "],
    "5": ["#####", "#    ", "#### ", "    #", "    #", "#   #", " ### "],
    "6": ["  ## ", " #   ", "#    ", "#### ", "#   #", "#   #", " ### "],
    "7": ["#####", "    #", "   # ", "  #  ", " #   ", " #   ", " #   "],
    "8": [" ### ", "#   #", "#   #", " ### ", "#   #", "#   #", " ### "],
    "9": [" ### ", "#   #", "#   #", " ####", "    #", "   # ", " ##  "],
    " ": ["     "] * 7,
    ".": ["     ", "     ", "     ", "     ", "     ", " ##  ", " ##  "],
    ",": ["     ", "     ", "     ", "     ", " ##  ", "  #  ", " #   "],
    ":": ["     ", " ##  ", " ##  ", "     ", " ##  ", " ##  ", "     "],
    ";": ["     ", " ##  ", " ##  ", "     ", " ##  ", "  #  ", " #   "],
    "!": ["  #  ", "  #  ", "  #  ", "  #  ", "  #  ", "     ", "  #  "],
    "¡": ["  #  ", "     ", "  #  ", "  #  ", "  #  ", "  #  ", "  #  "],
    "?": [" ### ", "#   #", "    #", "   # ", "  #  ", "     ", "  #  "],
    "¿": ["  #  ", "     ", "  #  ", " #   ", "#    ", "#   #", " ### "],
    "-": ["     ", "     ", "     ", " ### ", "     ", "     ", "     "],
    "+": ["     ", "  #  ", "  #  ", "#####", "  #  ", "  #  ", "     "],
    "=": ["     ", "     ", "#####", "     ", "#####", "     ", "     "],
    "/": ["    #", "    #", "   # ", "  #  ", " #   ", "#    ", "#    "],
    "(": ["   # ", "  #  ", " #   ", " #   ", " #   ", "  #  ", "   # "],
    ")": [" #   ", "  #  ", "   # ", "   # ", "   # ", "  #  ", " #   "],
    "'": ["  #  ", "  #  ", " #   ", "     ", "     ", "     ", "     "],
    '"': [" # # ", " # # ", "     ", "     ", "     ", "     ", "     "],
    "%": ["##   ", "##  #", "   # ", "  #  ", " #   ", "#  ##", "   ##"],
    "<": ["   # ", "  #  ", " #   ", "#    ", " #   ", "  #  ", "   # "],
    ">": [" #   ", "  #  ", "   # ", "    #", "   # ", "  #  ", " #   "],
    "_": ["     ", "     ", "     ", "     ", "     ", "     ", "#####"],
    "#": [" # # ", " # # ", "#####", " # # ", "#####", " # # ", " # # "],
    "*": ["     ", "# # #", " ### ", "#####", " ### ", "# # #", "     "],
    "@": [" ### ", "#   #", "# ###", "# # #", "# ###", "#    ", " ####"],
    "$": ["  #  ", " ####", "# #  ", " ### ", "  # #", "#### ", "  #  "],
    "&": [" ##  ", "#  # ", "# #  ", " #   ", "# # #", "#  # ", " ## #"],
}

# Letras con marca: (letra base, marca). Las marcas se dibujan en las 2 filas superiores.
_ACENTOS = {"Á": ("A", "tilde"), "É": ("E", "tilde"), "Í": ("I", "tilde"), "Ó": ("O", "tilde"),
            "Ú": ("U", "tilde"), "Ü": ("U", "dieresis"), "Ñ": ("N", "virgulilla")}
_MARCAS = {"tilde": ["   # ", "  #  "], "dieresis": [" # # ", "     "], "virgulilla": [" ## #", "#  # "]}


def _mascara(caracter: str):
    """Devuelve las 9 filas (2 de marca + 7 de glifo) para un carácter."""
    c = caracter.upper()
    if c in _ACENTOS:
        base, marca = _ACENTOS[c]
        return _MARCAS[marca] + _G[base]
    return ["     ", "     "] + _G.get(c, _G["?"])


class FuentePixel:
    """Imita la interfaz mínima de pygame.font.Font (render, size, get_linesize)."""

    def __init__(self, escala: int = 1):
        self.escala = escala
        self._cache: Dict[Tuple[str, Tuple[int, int, int]], pygame.Surface] = {}

    def _glifo(self, caracter: str, color) -> pygame.Surface:
        clave = (caracter, tuple(color[:3]))
        if clave not in self._cache:
            sup = pygame.Surface((ANCHO_GLIFO, MARGEN_SUP + ALTO_GLIFO), pygame.SRCALPHA)
            for y, fila in enumerate(_mascara(caracter)):
                for x, pixel in enumerate(fila):
                    if pixel == "#":
                        sup.set_at((x, y), color)
            if self.escala > 1:
                sup = pygame.transform.scale_by(sup, self.escala)
            self._cache[clave] = sup
        return self._cache[clave]

    def size(self, texto: str) -> Tuple[int, int]:
        ancho = max(0, len(texto) * AVANCE - 1) * self.escala
        return ancho, (MARGEN_SUP + ALTO_GLIFO) * self.escala

    def get_linesize(self) -> int:
        return ALTO_LINEA * self.escala

    def render(self, texto: str, _antialias, color) -> pygame.Surface:
        sup = pygame.Surface(self.size(texto), pygame.SRCALPHA)
        for i, caracter in enumerate(texto):
            sup.blit(self._glifo(caracter, color), (i * AVANCE * self.escala, 0))
        return sup
