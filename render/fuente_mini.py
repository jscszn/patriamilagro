"""Fuente pequeña (3 x 5 px, más una fila para las tildes) para escribir sobre el mapa.

La fuente normal del juego (5 x 7) tapa las vías y las zonas del grafo; con esta, "CARTAGENA"
ocupa 35 px en vez de 54. Cada letra avanza 4 px; el alto total es 6 (1 de tilde + 5).
"""
from __future__ import annotations

from typing import Dict, Tuple

import pygame

AVANCE, ALTO = 4, 6
_G = {
    "A": (".#.", "#.#", "###", "#.#", "#.#"), "B": ("##.", "#.#", "##.", "#.#", "##."),
    "C": (".##", "#..", "#..", "#..", ".##"), "D": ("##.", "#.#", "#.#", "#.#", "##."),
    "E": ("###", "#..", "##.", "#..", "###"), "F": ("###", "#..", "##.", "#..", "#.."),
    "G": (".##", "#..", "#.#", "#.#", ".##"), "H": ("#.#", "#.#", "###", "#.#", "#.#"),
    "I": ("###", ".#.", ".#.", ".#.", "###"), "J": ("..#", "..#", "..#", "#.#", ".#."),
    "K": ("#.#", "#.#", "##.", "#.#", "#.#"), "L": ("#..", "#..", "#..", "#..", "###"),
    "M": ("#.#", "###", "#.#", "#.#", "#.#"), "N": ("##.", "#.#", "#.#", "#.#", "#.#"),
    "O": (".#.", "#.#", "#.#", "#.#", ".#."), "P": ("##.", "#.#", "##.", "#..", "#.."),
    "Q": (".#.", "#.#", "#.#", "##.", ".##"), "R": ("##.", "#.#", "##.", "#.#", "#.#"),
    "S": (".##", "#..", ".#.", "..#", "##."), "T": ("###", ".#.", ".#.", ".#.", ".#."),
    "U": ("#.#", "#.#", "#.#", "#.#", "###"), "V": ("#.#", "#.#", "#.#", "#.#", ".#."),
    "W": ("#.#", "#.#", "###", "###", "#.#"), "X": ("#.#", "#.#", ".#.", "#.#", "#.#"),
    "Y": ("#.#", "#.#", ".#.", ".#.", ".#."), "Z": ("###", "..#", ".#.", "#..", "###"),
    "0": ("###", "#.#", "#.#", "#.#", "###"), "1": (".#.", "##.", ".#.", ".#.", "###"),
    "2": ("##.", "..#", ".#.", "#..", "###"), "3": ("##.", "..#", ".#.", "..#", "##."),
    "4": ("#.#", "#.#", "###", "..#", "..#"), "5": ("###", "#..", "##.", "..#", "##."),
    "6": (".##", "#..", "###", "#.#", "###"), "7": ("###", "..#", ".#.", ".#.", ".#."),
    "8": ("###", "#.#", "###", "#.#", "###"), "9": ("###", "#.#", "###", "..#", "##."),
    ".": ("...", "...", "...", "...", ".#."), "-": ("...", "...", "###", "...", "..."),
    "+": ("...", ".#.", "###", ".#.", "..."), " ": ("...", "...", "...", "...", "..."),
}
TILDES = {"Á": ("A", "..#"), "É": ("E", "..#"), "Í": ("I", "..#"), "Ó": ("O", "..#"), "Ú": ("U", "..#"),
          "Ñ": ("N", "###")}
_cache: Dict[Tuple[str, tuple], pygame.Surface] = {}


def tamano(texto: str) -> Tuple[int, int]:
    return max(0, len(texto) * AVANCE - 1), ALTO


def render(texto: str, color) -> pygame.Surface:
    texto = texto.upper()
    clave = (texto, tuple(color))
    if clave not in _cache:
        sup = pygame.Surface(tamano(texto), pygame.SRCALPHA)
        for i, letra in enumerate(texto):
            base, tilde = TILDES.get(letra, (letra, None))
            filas = _G.get(base, _G[" "])
            x0 = i * AVANCE
            if tilde:
                for dx, c in enumerate(tilde):
                    if c == "#":
                        sup.set_at((x0 + dx, 0), color)
            for dy, fila in enumerate(filas):
                for dx, c in enumerate(fila):
                    if c == "#":
                        sup.set_at((x0 + dx, dy + 1), color)
        if len(_cache) > 300:
            _cache.clear()
        _cache[clave] = sup
    return _cache[clave]


def dibujar(sup: pygame.Surface, texto: str, pos, color) -> None:
    sup.blit(render(texto, color), pos)
