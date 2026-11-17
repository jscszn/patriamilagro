"""Bustos de los personajes de los reportajes del final (dibujados por código).

Mismo estilo que los sprites del juego: colores de la paleta compartida (assets/paleta.json),
luz desde la izquierda (sombra a la derecha) y contorno negro de 1 px. Cada personaje se arma
con piezas: cabeza, peinado (cuadrículas de texto, como render/pixelart.py), ropa y accesorios.

retrato(clave, boca, parpadeo, voltear) devuelve el busto en un LIENZO de 88 x 116 con la boca en
BOCA_LIENZO = (44, 42). Todos miran a la DERECHA; con voltear=True miran a la izquierda.
El dibujo por código mide 44 x 58 (ANCHO x ALTO, boca en (22, 21)) y se duplica exacto al lienzo.

Sprites propios: si existe assets/reportajes/<clave>.png se usa en lugar del dibujo por código
(ver assets/reportajes/LEEME.txt). Estados: <clave>.png (boca cerrada), <clave>_habla1.png
(entreabierta), <clave>_habla2.png (abierta) y <clave>_parpadeo.png. Los que falten se toman
del más parecido que exista.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import os
from typing import Dict, List, Optional, Tuple

import pygame

import settings

from render.pixelart import cuadricula

Color = Tuple[int, int, int]
ANCHO, ALTO = 44, 58                         # el busto dibujado por código
LIENZO = (88, 116)                           # el que devuelve retrato() (el doble, sin estirar)
BOCA_LIENZO = (44, 42)                       # la boca en el LIENZO
CONTORNO: Color = (13, 9, 10)

# --- Colores (casi todos de assets/paleta.json) ---------------------------------------------
PIELES = {
    "clara": ((231, 165, 124), (191, 112, 74)),
    "trigueña": ((214, 140, 98), (175, 98, 62)),
    "morena": ((175, 108, 66), (130, 70, 38)),
}
BOCA: Color = (110, 30, 34)
LENGUA: Color = (188, 27, 31)
LABIOS: Color = (175, 21, 31)
OJO_BLANCO: Color = (240, 240, 240)
OJO: Color = (19, 29, 55)
ORO: Color = (246, 205, 26)
BLANCO: Color = (240, 240, 240)
BLANCO_SOMBRA: Color = (180, 191, 199)


def _oscuro(c: Color, k: float = 0.72) -> Color:
    return tuple(int(v * k) for v in c)


@dataclass
class Aspecto:
    piel: str = "clara"
    pelo: Color = (51, 42, 33)
    peinado: str = "corto"              # ver PEINADOS
    ropa: Color = (32, 51, 99)
    prenda: str = "traje"               # traje, blazer, camiseta, sudadera, chaqueta, delantal, chal
    detalle: Color = (188, 27, 31)      # corbata, camiseta de debajo, estampado...
    gafas: bool = False
    bigote: bool = False
    aretes: bool = False
    labios: bool = False
    audifonos: bool = False
    rubor: bool = False
    arrugas: bool = False
    extras: List[str] = field(default_factory=list)


ASPECTOS: Dict[str, Aspecto] = {
    # Noticiero
    "presentadora": Aspecto(piel="clara", pelo=(88, 68, 39), peinado="melena", ropa=(188, 27, 31),
                            prenda="blazer", detalle=BLANCO, aretes=True, labios=True),
    "analista": Aspecto(piel="trigueña", pelo=(180, 191, 199), peinado="entradas", ropa=(74, 79, 82),
                        prenda="traje", detalle=(7, 51, 147), gafas=True, bigote=True, arrugas=True),
    # En vivo
    "influencer": Aspecto(piel="trigueña", pelo=(228, 92, 220), peinado="coleta", ropa=(240, 240, 240),
                          prenda="sudadera", detalle=(228, 92, 220), audifonos=True, labios=True,
                          rubor=True),
    # La calle
    "reportera": Aspecto(piel="morena", pelo=(13, 9, 10), peinado="cola", ropa=(7, 51, 147),
                         prenda="chaqueta", detalle=BLANCO, aretes=True),
    "jhon": Aspecto(piel="morena", pelo=(13, 9, 10), peinado="gorra", ropa=(87, 99, 59),
                    prenda="chaqueta", detalle=(246, 205, 26), bigote=True),
    "efrain": Aspecto(piel="clara", pelo=(158, 165, 173), peinado="calvo", ropa=(117, 131, 141),
                      prenda="delantal", detalle=(220, 218, 216), bigote=True, arrugas=True),
    "carmen": Aspecto(piel="clara", pelo=(220, 218, 216), peinado="moño", ropa=(112, 60, 120),
                      prenda="chal", detalle=(175, 142, 98), gafas=True, arrugas=True, rubor=True),
}

# --- Geometría (mirando a la derecha) --------------------------------------------------------
CABEZA = pygame.Rect(13, 5, 18, 21)          # el óvalo de la cara
OJOS_Y = 14
OJO_IZQ_X, OJO_DER_X = 18, 25                # columna izquierda de cada ojo (2 px de ancho)
BOCA_Y = 21
BOCA_X = 20
CUELLO = pygame.Rect(18, 24, 8, 6)
HOMBROS_Y = 30

# --- Peinados: cuadrículas de 24 columnas desde (10, 0). H = pelo, h = sombra, A = adorno ----
# "atras" se dibuja ANTES de la cabeza (pelo largo detrás de la cara y los hombros).
PEINADOS: Dict[str, Dict[str, List[str]]] = {
    "corto": {"frente": [
        "........................",
        "........................",
        ".......HHHHHHHh.........",
        ".....HHHHHHHHHHHh.......",
        "....HHHHHHHHHHHHHh......",
        "...HHHHHHHHHHHHHHHh.....",
        "...HHHHHHHHHHHHHHHhh....",
        "...HHH..HH.HHHHHHHhh....",
        "...HH...........HHhh....",
        "...HH............Hhh....",
        "...H..............hh....",
        "...H..............h.....",
    ]},
    "entradas": {"frente": [
        "........................",
        "........................",
        "........................",
        "........................",
        "........................",
        "........................",
        "...HH.............hh....",
        "...HHH............hhh...",
        "...HHH............hhh...",
        "...HH.............hh....",
        "...H..............h.....",
        "...H..............h.....",
    ]},
    "calvo": {"frente": [
        "........................",
        "........................",
        "........................",
        "........................",
        "........................",
        "........................",
        "........................",
        "...HH.............hh....",
        "...HHH............hhh...",
        "...HHH............hhh...",
        "...HH.............hh....",
        "...H..............h.....",
    ]},
    "melena": {
        "atras": [
            "........................",
            "........................",
            "........................",
            "........................",
            "........................",
            "........................",
            "........................",
            "..HHH..............hhh..",
            "..HHH..............hhh..",
            "..HHH..............hhh..",
            "..HHH..............hhh..",
            "..HHH..............hhh..",
            "..HHHH............hhhh..",
            "..HHHH............hhhh..",
            "..HHHH............hhhh..",
            "..HHHH............hhhh..",
            "..HHHHH..........hhhhh..",
            "..HHHHH..........hhhhh..",
            "..HHHHH..........hhhhh..",
            "..HHHHH..........hhhhh..",
            "..HHHHHH........hhhhhh..",
            "..HHHHHH........hhhhhh..",
            "...HHHHH........hhhhh...",
            "...HHHHH........hhhhh...",
            "....HHHH........hhhh....",
            "....HHH..........hhh....",
            ".....H............h.....",
        ],
        "frente": [
            "........................",
            "........................",
            "........HHHHHHh.........",
            "......HHHHHHHHHHh.......",
            ".....HHHHHHHHHHHHh......",
            "....HHHHHHHHHHHHHHh.....",
            "...HHHHHHHHHHHHHHHhh....",
            "...HHHHHHHHHHHHHHHhh....",
            "...HHHHHHHHH.....hhh....",
            "...HHHHHH.........hh....",
            "...HHHH...........hh....",
            "...HHH............hh....",
            "...HH.............hh....",
        ]},
    "cola": {
        "atras": [
            "........................",
            "........................",
            "........................",
            "........................",
            "........................",
            "........................",
            "........................",
            "....................hh..",
            "....................hhh.",
            ".....................hhh",
            ".....................hhh",
            "......................hh",
            "......................hh",
            "......................h.",
        ],
        "frente": [
            "........................",
            "........................",
            "........HHHHHHh.........",
            "......HHHHHHHHHHh.......",
            ".....HHHHHHHHHHHHh......",
            "....HHHHHHHHHHHHHHh.....",
            "...HHHHHHHHHHHHHHHhhAA..",
            "...HHHHHHHHHHHHHHHhhAA..",
            "...HHH.HHHHH.HHHHHhh....",
            "...HH.............hh....",
            "...H..............hh....",
            "...H..............h.....",
        ]},
    "coleta": {     # cola alta (la influencer)
        "atras": [
            "...................hh...",
            "..................hhhh..",
            "..................hhhhh.",
            "...................hhhh.",
            "....................hhh.",
            ".....................hh.",
            ".....................hh.",
            "......................h.",
        ],
        "frente": [
            "........................",
            "........................",
            "........HHHHHHAA........",
            "......HHHHHHHHAAh.......",
            ".....HHHHHHHHHHHHh......",
            "....HHHHHHHHHHHHHHh.....",
            "...HHHHHHHHHHHHHHHhh....",
            "...HHHHHHHHHHHHHHHhh....",
            "...HHHHHHHH.HHHHHHhh....",
            "...HHHH...........hh....",
            "...HH.............h.....",
            "...H....................",
        ]},
    "moño": {"frente": [
        ".........HHHHh..........",
        "........HHHHHhh.........",
        "........HHHHhhh.........",
        ".......HHHHHHHHh........",
        ".....HHHHHHHHHHHHh......",
        "....HHHHHHHHHHHHHHh.....",
        "...HHHHHHHHHHHHHHHhh....",
        "...HHHH.HHHHHHHHHHhh....",
        "...HHH.......HHHHHhh....",
        "...HH.............hh....",
        "...H..............hh....",
        "...H..............h.....",
    ]},
    "gorra": {"frente": [   # gorra amarilla de taxista (A = visera)
        "........................",
        "........................",
        "........DDDDDDd.........",
        "......DDDDDDDDDDd.......",
        ".....DDDDDDDDDDDDd......",
        "....DDDDDDDDDDDDDDd.....",
        "...DDDDDDDDDDDDDDDdd....",
        "...DdDDDDDDDDDDDDDAAAAA.",
        "...HH.........AAAAAAAAA.",
        "...HH.............hh....",
        "...H..............h.....",
        "...H....................",
    ]},
}
ORIGEN_PELO = (10, 0)


def _sombra_borde(sup: pygame.Surface, base: Color, sombra: Color, ancho: int, hasta: int = None) -> None:
    """Pinta con `sombra` los píxeles `base` que están a menos de `ancho` px del borde derecho de la
    figura: la sombra sigue la forma (hombros, mejillas) en vez de ser una franja recta."""
    w, h = sup.get_size()
    cambiar = []
    for y in range(h):
        for x in range(w):
            c = sup.get_at((x, y))
            if not c.a or tuple(c)[:3] != base:
                continue
            for d in range(1, ancho + 1):
                if x + d >= w or not sup.get_at((x + d, y)).a or (hasta is not None and x + d > hasta
                                                                      and tuple(sup.get_at((x + d, y)))[:3] != base):
                    cambiar.append((x, y))
                    break
    for p in cambiar:
        sup.set_at(p, sombra)


def _contorno(sup: pygame.Surface) -> pygame.Surface:
    """Contorno negro de 1 px alrededor de todo lo opaco (como en tools/procesar_sprites.py)."""
    salida = sup.copy()
    w, h = sup.get_size()
    for y in range(h):
        for x in range(w):
            if sup.get_at((x, y)).a:
                continue
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nx, ny = x + dx, y + dy
                if 0 <= nx < w and 0 <= ny < h and sup.get_at((nx, ny)).a:
                    salida.set_at((x, y), CONTORNO)
                    break
    return salida


def _pelo(sup: pygame.Surface, a: Aspecto, capa: str) -> None:
    filas = PEINADOS[a.peinado].get(capa)
    if not filas:
        return
    paleta = {"H": a.pelo, "h": _oscuro(a.pelo), "A": a.detalle,
              "D": (246, 205, 26), "d": (211, 157, 25)}
    if a.peinado == "gorra":
        paleta["A"] = (211, 157, 25)
    if a.peinado == "coleta":
        paleta["A"] = (246, 217, 104)            # la moña de la cola
    capa_sup = cuadricula(filas, paleta, 24, len(filas))
    sup.blit(capa_sup, ORIGEN_PELO)


def _torso(sup: pygame.Surface, a: Aspecto) -> None:
    ropa, sombra = a.ropa, _oscuro(a.ropa)
    piel, piel_s = PIELES[a.piel]
    puntos = [(5, ALTO), (5, 38), (8, 33), (15, HOMBROS_Y - 1), (29, HOMBROS_Y - 1), (36, 33), (39, 38),
              (39, ALTO)]
    if a.prenda == "sudadera":                   # la capucha sobresale detrás del cuello
        pygame.draw.ellipse(sup, sombra, (12, 25, 20, 9))
    pygame.draw.polygon(sup, ropa, puntos)
    # Cuello (y escote según la prenda)
    pygame.draw.rect(sup, piel_s, CUELLO)
    cx = 22
    if a.prenda in ("traje", "blazer"):
        pygame.draw.polygon(sup, a.detalle if a.prenda == "blazer" else BLANCO,
                            [(cx - 4, HOMBROS_Y - 1), (cx + 4, HOMBROS_Y - 1), (cx, 41)])
        if a.prenda == "blazer":                 # escote en la blusa
            pygame.draw.polygon(sup, piel, [(cx - 2, HOMBROS_Y - 1), (cx + 2, HOMBROS_Y - 1), (cx, 34)])
        else:                                    # corbata
            pygame.draw.polygon(sup, a.detalle, [(cx - 1, HOMBROS_Y), (cx + 1, HOMBROS_Y), (cx + 2, 40),
                                                 (cx, 43), (cx - 2, 40)])
            sup.set_at((cx, HOMBROS_Y), _oscuro(a.detalle))
        for lado in (-1, 1):                     # solapas
            pygame.draw.line(sup, sombra, (cx + lado * 5, HOMBROS_Y - 1), (cx + lado * 1, 43))
            pygame.draw.line(sup, sombra, (cx + lado * 5, HOMBROS_Y), (cx + lado * 8, 37))
        for y in (47, 52):                       # botones
            sup.set_at((cx - 1, y), _oscuro(sombra))
    elif a.prenda == "sudadera":
        pygame.draw.ellipse(sup, piel_s, (cx - 4, HOMBROS_Y - 3, 9, 5))
        for dx in (-3, 3):                       # cordones
            pygame.draw.line(sup, a.detalle, (cx + dx, HOMBROS_Y + 1), (cx + dx, 38))
        pygame.draw.rect(sup, sombra, (cx - 7, 46, 15, 1))           # bolsillo canguro
        pygame.draw.rect(sup, a.detalle, (cx - 3, 40, 7, 4))         # logo
    elif a.prenda == "chaqueta":
        pygame.draw.polygon(sup, a.detalle, [(cx - 4, HOMBROS_Y - 1), (cx + 4, HOMBROS_Y - 1), (cx + 4, ALTO),
                                             (cx - 4, ALTO)])
        pygame.draw.ellipse(sup, piel_s, (cx - 3, HOMBROS_Y - 2, 7, 4))
        for lado in (-1, 1):
            pygame.draw.line(sup, sombra, (cx + lado * 4, HOMBROS_Y), (cx + lado * 4, ALTO))
            pygame.draw.line(sup, sombra, (cx + lado * 5, HOMBROS_Y - 1), (cx + lado * 9, 35))
    elif a.prenda == "delantal":
        pygame.draw.ellipse(sup, piel_s, (cx - 3, HOMBROS_Y - 2, 7, 4))
        pygame.draw.rect(sup, a.detalle, (cx - 7, 38, 15, ALTO - 38))
        for lado in (-1, 1):                     # tirantes
            pygame.draw.line(sup, a.detalle, (cx + lado * 7, 38), (cx + lado * 8, HOMBROS_Y))
        pygame.draw.rect(sup, _oscuro(a.detalle, 0.8), (cx - 4, 44, 9, 5), 1)   # bolsillo
    elif a.prenda == "chal":
        pygame.draw.ellipse(sup, piel_s, (cx - 3, HOMBROS_Y - 2, 7, 4))
        chal, chal_s = a.detalle, _oscuro(a.detalle)
        pygame.draw.polygon(sup, chal, [(5, 38), (8, 33), (15, HOMBROS_Y - 1), (cx - 3, HOMBROS_Y + 1),
                                        (cx, 44), (cx + 3, HOMBROS_Y + 1), (29, HOMBROS_Y - 1), (36, 33),
                                        (39, 38), (39, 41), (cx, 50), (5, 41)])
        for x in range(7, 38, 3):                # flecos
            y = 41 + int(9 * (1 - abs(x - cx) / 18))
            pygame.draw.line(sup, chal_s, (x, y), (x, y + 2))
        sup.set_at((cx, 44), ORO)                # broche
    else:                                        # camiseta
        pygame.draw.ellipse(sup, piel_s, (cx - 3, HOMBROS_Y - 2, 7, 4))
    # Mangas: la costura del brazo y el hueco entre el brazo y el cuerpo
    for x in (10, 34):
        pygame.draw.line(sup, _oscuro(sombra, 0.8), (x, 39), (x, ALTO))
        sup.set_at((x - 1 if x < cx else x + 1, 38), _oscuro(sombra, 0.8))
    # Sombra que sigue el borde derecho de la figura (luz desde la izquierda)
    _sombra_borde(sup, ropa, sombra, 4)
    if a.prenda in ("chaqueta", "chal", "delantal") and a.detalle != ropa:
        _sombra_borde(sup, a.detalle, _oscuro(a.detalle, 0.85), 2, hasta=cx + 2)


def _cara(sup: pygame.Surface, a: Aspecto, boca: int, parpadeo: bool) -> None:
    piel, piel_s = PIELES[a.piel]
    pygame.draw.rect(sup, piel, (CABEZA.x - 1, 12, 3, 6))          # orejas
    pygame.draw.rect(sup, piel_s, (CABEZA.right - 2, 12, 3, 6))
    pygame.draw.ellipse(sup, piel, CABEZA)
    pygame.draw.rect(sup, piel, (CABEZA.x + 1, 8, CABEZA.w - 2, 10))   # frente y pómulos más rectos
    _sombra_borde(sup, piel, piel_s, 3)
    pygame.draw.line(sup, piel_s, (CABEZA.x + 4, CABEZA.bottom - 1), (CABEZA.right - 5, CABEZA.bottom - 1))
    if a.aretes:
        sup.set_at((CABEZA.x - 1, 18), ORO)
        sup.set_at((CABEZA.x - 1, 19), ORO)
    # Cejas
    ceja = _oscuro(a.pelo, 0.6) if sum(a.pelo) > 300 else a.pelo
    if a.peinado == "coleta":
        ceja = (88, 68, 39)
    for x in (OJO_IZQ_X - 1, OJO_DER_X):
        pygame.draw.line(sup, ceja, (x, OJOS_Y - 2), (x + 2, OJOS_Y - 2))
    # Ojos: blanco + pupila mirando hacia adelante (la derecha)
    for x in (OJO_IZQ_X, OJO_DER_X):
        if parpadeo:
            pygame.draw.line(sup, piel_s, (x, OJOS_Y), (x + 1, OJOS_Y))
            pygame.draw.line(sup, OJO, (x, OJOS_Y + 1), (x + 1, OJOS_Y + 1))
        else:
            pygame.draw.rect(sup, OJO_BLANCO, (x, OJOS_Y, 2, 2))
            pygame.draw.rect(sup, OJO, (x + 1, OJOS_Y, 1, 2))
    if a.arrugas:
        sup.set_at((OJO_DER_X + 3, OJOS_Y + 1), piel_s)
        sup.set_at((OJO_IZQ_X - 1, OJOS_Y + 3), piel_s)
    # Nariz (sombra hacia la derecha)
    nx = OJO_DER_X - 1
    pygame.draw.line(sup, piel_s, (nx, OJOS_Y + 1), (nx, OJOS_Y + 4))
    sup.set_at((nx + 1, OJOS_Y + 4), piel_s)
    if a.rubor:
        for x in (OJO_IZQ_X - 1, OJO_DER_X + 2):
            sup.set_at((x, OJOS_Y + 3), (240, 120, 110))
    if a.bigote:
        bigote = a.pelo if a.peinado != "gorra" else (51, 42, 33)
        pygame.draw.rect(sup, bigote, (BOCA_X - 1, BOCA_Y - 2, 7, 2))
        sup.set_at((BOCA_X - 1, BOCA_Y - 1), piel)
    # Boca: 0 cerrada, 1 entreabierta, 2 abierta
    if boca == 0:
        pygame.draw.line(sup, LABIOS if a.labios else BOCA, (BOCA_X, BOCA_Y), (BOCA_X + 4, BOCA_Y))
    elif boca == 1:
        pygame.draw.rect(sup, BOCA, (BOCA_X + 1, BOCA_Y, 3, 2))
        if a.labios:
            pygame.draw.line(sup, LABIOS, (BOCA_X + 1, BOCA_Y + 2), (BOCA_X + 3, BOCA_Y + 2))
    else:
        pygame.draw.rect(sup, BOCA, (BOCA_X, BOCA_Y - 1, 5, 3))
        pygame.draw.line(sup, LENGUA, (BOCA_X + 1, BOCA_Y + 1), (BOCA_X + 3, BOCA_Y + 1))
        if a.labios:
            pygame.draw.line(sup, LABIOS, (BOCA_X + 1, BOCA_Y + 2), (BOCA_X + 3, BOCA_Y + 2))
    if a.gafas:
        marco = (51, 42, 33)
        for x in (OJO_IZQ_X - 1, OJO_DER_X - 1):
            pygame.draw.rect(sup, marco, (x, OJOS_Y - 1, 4, 4), 1)
        pygame.draw.line(sup, marco, (OJO_IZQ_X + 3, OJOS_Y), (OJO_DER_X - 1, OJOS_Y))
        pygame.draw.line(sup, marco, (CABEZA.x, OJOS_Y), (OJO_IZQ_X - 1, OJOS_Y))


def _audifonos(sup: pygame.Surface, a: Aspecto) -> None:
    oscuro, claro = (32, 51, 99), a.detalle
    pygame.draw.arc(sup, oscuro, (CABEZA.x - 3, 1, CABEZA.w + 6, 22), 0.15, 3.0, 2)
    pygame.draw.rect(sup, oscuro, (CABEZA.x - 3, 11, 4, 8))
    pygame.draw.rect(sup, claro, (CABEZA.x - 2, 13, 2, 4))
    pygame.draw.line(sup, oscuro, (CABEZA.x, 18), (BOCA_X - 1, BOCA_Y + 1))   # micrófono de diadema
    sup.set_at((BOCA_X - 1, BOCA_Y + 1), (74, 79, 82))


def dibujar(a: Aspecto, boca: int = 0, parpadeo: bool = False) -> pygame.Surface:
    """Tres capas, cada una con su contorno (así la barbilla se separa del pecho, como en los
    sprites de los jefes): pelo de atrás, torso y cabeza."""
    sup = pygame.Surface((ANCHO, ALTO), pygame.SRCALPHA)
    for pintar in (lambda s: _pelo(s, a, "atras"), lambda s: _torso(s, a), lambda s: _cabeza(s, a, boca, parpadeo)):
        capa = pygame.Surface((ANCHO, ALTO), pygame.SRCALPHA)
        pintar(capa)
        sup.blit(_contorno(capa), (0, 0))
    return sup


def _cabeza(sup: pygame.Surface, a: Aspecto, boca: int, parpadeo: bool) -> None:
    _cara(sup, a, boca, parpadeo)
    _pelo(sup, a, "frente")
    if a.audifonos:
        _audifonos(sup, a)


_cache: Dict[tuple, pygame.Surface] = {}


RUTA_PROPIOS = os.path.join(settings.RUTA_ASSETS, "reportajes")
SUFIJOS = {(0, False): "", (1, False): "_habla1", (2, False): "_habla2", (0, True): "_parpadeo"}


def ajustar(imagen: pygame.Surface) -> pygame.Surface:
    """Lleva un PNG propio al LIENZO (88 x 116) sin suavizar. Si mide un múltiplo o un divisor
    exacto (44 x 58, 176 x 232...) se escala entero; si no, se pega sin escalar, centrado y arriba
    (nunca se estira: el corte de abajo lo tapan las escenas)."""
    w, h = imagen.get_size()
    W, H = LIENZO
    if (w, h) == LIENZO:
        return imagen
    if w * H == h * W and (W % w == 0 or w % W == 0):
        return pygame.transform.scale(imagen, LIENZO)
    lienzo = pygame.Surface(LIENZO, pygame.SRCALPHA)
    lienzo.blit(imagen, imagen.get_rect(midtop=(W // 2, 0)))
    return lienzo


def tiene_propio(clave: str) -> bool:
    """True si el personaje tiene su PNG en assets/reportajes/."""
    return os.path.isfile(os.path.join(RUTA_PROPIOS, f"{clave}.png"))


def propio(clave: str, boca: int, parpadeo: bool) -> Optional[pygame.Surface]:
    """El PNG propio de ese estado, o del estado más parecido que exista (None si no hay ninguno)."""
    candidatos = [SUFIJOS.get((boca, parpadeo), "")]
    if boca:
        candidatos += ["_habla2" if boca == 1 else "_habla1"]
    candidatos += [""]
    for sufijo in candidatos:
        ruta = os.path.join(RUTA_PROPIOS, f"{clave}{sufijo}.png")
        if os.path.isfile(ruta):
            try:
                return ajustar(pygame.image.load(ruta))
            except pygame.error as e:
                print(f"[reportajes] No se pudo leer {ruta}: {e}")
    return None


def retrato(clave: str, boca: int = 0, parpadeo: bool = False, voltear: bool = False) -> pygame.Surface:
    """El busto del personaje `clave` (ASPECTOS) en ese estado (cacheado). Usa el PNG propio si
    existe; si no, el dibujado por código."""
    llave = (clave, boca, parpadeo, voltear)
    imagen = _cache.get(llave)
    if imagen is None:
        imagen = propio(clave, boca, parpadeo)
        if imagen is None:                                   # dibujo por código, al doble exacto
            imagen = pygame.transform.scale(dibujar(ASPECTOS[clave], boca, parpadeo), LIENZO)
        if voltear:
            imagen = pygame.transform.flip(imagen, True, False)
        if pygame.display.get_surface() is not None:
            imagen = imagen.convert_alpha()
        _cache[llave] = imagen
    return imagen


def boca_al_hablar(t: float) -> int:
    """Secuencia de la boca mientras habla (no es periódica para que no parezca un metrónomo)."""
    secuencia = (2, 1, 0, 2, 1, 2, 0, 1, 2, 0)
    return secuencia[int(t * 11) % len(secuencia)]


def parpadea(t: float, desfase: float = 0.0) -> bool:
    """Parpadeo cada ~3,3 s (con desfase para que no parpadeen todos a la vez)."""
    return (t + desfase) % 3.3 < 0.12
