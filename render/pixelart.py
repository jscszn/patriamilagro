"""Sprites PLACEHOLDER dibujados por código (pixel art a partir de cuadrículas de texto).

Cada generador devuelve {nombre_animacion: [Surface, ...]}. Todos los sprites miran a la
DERECHA; el render los voltea cuando el personaje mira a la izquierda.
Se reemplazan por PNG editando assets/sprites.json (ver render/sprites.py).
"""
from __future__ import annotations

import math
from typing import Dict, List, Tuple

import pygame

Anims = Dict[str, List[pygame.Surface]]


def cuadricula(filas: List[str], paleta: Dict[str, Tuple[int, int, int]], ancho: int, alto: int,
               superficie: pygame.Surface = None, dy: int = 0) -> pygame.Surface:
    """Convierte filas de texto en una superficie. '.' o ' ' = transparente."""
    sup = superficie or pygame.Surface((ancho, alto), pygame.SRCALPHA)
    for y, fila in enumerate(filas):
        for x, c in enumerate(fila[:ancho]):
            if c in paleta and 0 <= y + dy < alto:
                sup.set_at((x, y + dy), paleta[c])
    return sup


def _brazo(sup: pygame.Surface, hombro: Tuple[int, int], ax: int, ay: int,
           manga, piel, arma=(70, 70, 80), largo_arma: int = 5) -> None:
    """Dibuja brazo + arma apuntando en (ax, ay)."""
    n = math.hypot(ax, ay) or 1
    dx, dy = ax / n, ay / n
    hx, hy = hombro
    codo = (hx + dx * 4, hy + dy * 4)
    mano = (hx + dx * 6, hy + dy * 6)
    punta = (mano[0] + dx * largo_arma, mano[1] + dy * largo_arma)
    pygame.draw.line(sup, manga, hombro, codo, 2)
    pygame.draw.line(sup, arma, mano, punta, 2)
    pygame.draw.rect(sup, piel, (round(mano[0]) - 1, round(mano[1]) - 1, 2, 2))


# =============================================================================
# Presidente A. Milagro (16x24)
# =============================================================================
PAL_PRESIDENTE = {
    "K": (24, 20, 30), "H": (60, 50, 50), "G": (170, 170, 170), "S": (232, 176, 128),
    "s": (190, 130, 90), "W": (240, 240, 240), "N": (34, 46, 110), "n": (20, 26, 70),
    "Y": (248, 216, 32), "B": (0, 88, 248), "R": (216, 40, 0), "k": (20, 20, 20),
}

TORSO_PRESIDENTE = [
    "......KKKK......",
    ".....KHHHHKK....",
    "....KHHHHHHGK...",
    "....KHHSSSSSK...",
    "....KHSSSSKSK...",
    ".....KSSSSSSK...",
    ".....KsSSSsK....",
    "......KsssK.....",
    "....KNNWWNNK....",
    "...KNNYWWNNNK...",
    "...KNNNBWNNNK...",
    "...KNNNNRNNNK...",
    "...KNNNNNYNNK...",
    "...KNNNNNNBNK...",
    "....KNNNNNNRK...",
]

# Piernas (9 filas) compartidas por el presidente y el sicario (cambia la paleta).
PIERNAS = {
    "quieto": [
        "....KnnnnnnK....",
        "....KNNKKNNK....",
        "....KNNK.KNNK...",
        "....KNNK.KNNK...",
        "....KNNK.KNNK...",
        "....KNNK.KNNK...",
        "....KNNK.KNNK...",
        "...KkkkK.KkkkK..",
        "...KKKKK.KKKKK..",
    ],
    "correr0": [
        "....KnnnnnnK....",
        "...KNNNKKNNNK...",
        "..KNNK...KNNK...",
        "..KNNK....KNNK..",
        ".KNNK.....KNNK..",
        ".KNNK......KNNK.",
        "KkkK.......KkkkK",
        "KKK.........KKKK",
        "................",
    ],
    "correr1": [
        "....KnnnnnnK....",
        "....KNNNNNNK....",
        "....KNNKNNK.....",
        "....KNNKNNK.....",
        "...KNNK.KNNK....",
        "...KNNK.KNNK....",
        "...KNNK.KkkK....",
        "..KkkkK..KKK....",
        "..KKKKK.........",
    ],
    "correr2": [
        "....KnnnnnnK....",
        "....KNNKKNNNK...",
        "...KNNK..KNNK...",
        "...KNNK...KNNK..",
        "..KNNK....KNNK..",
        "..KNNK.....KkkK.",
        ".KkkkK......KKK.",
        ".KKKKK..........",
        "................",
    ],
    "saltar": [
        "....KnnnnnnK....",
        "...KNNNNNNNNK...",
        "...KNNNNNNNNkK..",
        "....KNNK..KkkK..",
        "....KkkK...KK...",
        ".....KK.........",
        "................",
        "................",
        "................",
    ],
}



def _cuerpo(torso, piernas, paleta, ancho=16, alto=24) -> pygame.Surface:
    sup = cuadricula(torso, paleta, ancho, alto)
    return cuadricula(piernas, paleta, ancho, alto, sup, dy=len(torso))


def generar_presidente() -> Anims:
    p = PAL_PRESIDENTE
    anims: Anims = {}

    def con_brazo(piernas: str, apunte) -> pygame.Surface:
        sup = _cuerpo(TORSO_PRESIDENTE, PIERNAS[piernas], p)
        _brazo(sup, (8, 10), *apunte, manga=p["N"], piel=p["S"])
        return sup

    # Mismos nombres que Jugador.pose()
    anims["quieto"] = [con_brazo("quieto", (1, 0))]
    anims["disparar"] = anims["quieto"]
    anims["correr"] = [con_brazo(f"correr{i}", (1, 0)) for i in range(3)]
    anims["saltar"] = [con_brazo("saltar", (1, 0))]
    anims["arriba"] = [con_brazo("quieto", (0, -1))]
    anims["diag_arriba"] = [con_brazo("quieto", (1, -1))]
    anims["diag_abajo"] = [con_brazo("quieto", (1, 1))]
    anims["abajo"] = [con_brazo("saltar", (0, 1))]
    anims["herido"] = [con_brazo("saltar", (1, -1))]
    # Agachado: el torso baja 10 píxeles y las piernas se doblan.
    agachado = pygame.Surface((16, 24), pygame.SRCALPHA)
    cuadricula(TORSO_PRESIDENTE[:12], p, 16, 24, agachado, dy=10)
    cuadricula(["...KNNNNNNNNK...", "..KNNNNNKKNNNK..", "..KkkkK...KkkkK."], p, 16, 24, agachado, dy=21)
    _brazo(agachado, (8, 19), 1, 0, manga=p["N"], piel=p["S"])
    anims["agachado"] = [agachado]
    return anims


# =============================================================================
# Sicario raso (16x24): gorra, buzo oscuro, jean
# =============================================================================
PAL_SICARIO = {
    "K": (20, 16, 20), "H": (150, 30, 30), "h": (100, 20, 20), "S": (196, 140, 96),
    "s": (150, 100, 60), "N": (50, 70, 140), "n": (36, 50, 100), "C": (64, 64, 72),
    "c": (44, 44, 52), "k": (230, 230, 230),
}

TORSO_SICARIO = [
    "......KKKK......",
    ".....KHHHHK.....",
    "....KHHHHHHKKK..",
    "....KhhhhhhhhK..",
    "....KSSSSKSK....",
    ".....KSSSSSK....",
    ".....KsSSSsK....",
    "......KsssK.....",
    "....KCCCCCCK....",
    "...KCCCCCCCCK...",
    "...KCCcCCcCCK...",
    "...KCCcCCcCCK...",
    "...KCCCCCCCCK...",
    "...KCCCCCCCCK...",
    "....KcccccccK...",
]


def generar_sicario() -> Anims:
    p = PAL_SICARIO

    def frame(piernas: str, apuntando: bool) -> pygame.Surface:
        sup = _cuerpo(TORSO_SICARIO, PIERNAS[piernas], p)
        if apuntando:
            _brazo(sup, (8, 10), 1, 0, manga=p["C"], piel=p["S"], largo_arma=3)
        else:  # brazo colgando con la pistola abajo
            pygame.draw.line(sup, p["C"], (8, 10), (9, 15), 2)
            pygame.draw.rect(sup, (70, 70, 80), (9, 16, 3, 2))
        return sup

    return {
        "quieto": [frame("quieto", False)],
        "correr": [frame(f"correr{i}", False) for i in range(3)],
        "apuntar": [frame("quieto", True)],
    }


# =============================================================================
# Jefes (24x32): misma plantilla, distinta paleta y accesorios
# =============================================================================
TORSO_JEFE = [
    "........KKKKKKK.........",
    ".......KHHHHHHHK........",
    "......KHHHHHHHHHK.......",
    "......KSSSSSSSSSK.......",
    "......KSSSSSSKSSK.......",
    "......KSSSSSSSSSK.......",
    "......KSSSSSSSSSK.......",
    ".......KSSsssSSK........",
    "........KSSSSSK.........",
    "....KKKKCCAACCCKKKK.....",
    "...KCCCCCCAACCCCCCCK....",
    "..KCCCCCCCCCCCCCCCCCK...",
    "..KCCCcCCCCCCCCcCCCCK...",
    "..KCCCcCCCCCCCCcCCCCK...",
    "..KCCCcCCCCCCCCcCCCCK...",
    "..KCCCCCCCCCCCCCCCCCK...",
    "..KSSKCCCCCCCCCCKSSK....",
    "..KSSKccccccccccKSSK....",
    "...KK.KccccccccK.KK.....",
    "......KPPPPPPPPK........",
    "......KPPPPPPPPK........",
]

PIERNAS_JEFE = {
    "quieto": [
        "......KPPPKKPPPK........",
        "......KPPPK.KPPPK.......",
        "......KPPPK.KPPPK.......",
        "......KPPPK.KPPPK.......",
        "......KPPPK.KPPPK.......",
        "......KPPPK.KPPPK.......",
        ".....KkkkkK.KkkkkK......",
        ".....KKKKKK.KKKKKK......",
        "........................",
        "........................",
        "........................",
    ],
    "correr0": [
        ".....KPPPKKKPPPK........",
        "....KPPPK...KPPPK.......",
        "...KPPPK.....KPPPK......",
        "..KPPPK.......KPPPK.....",
        "..KPPK.........KPPK.....",
        ".KkkkK.........KkkkK....",
        ".KKKKK.........KKKKK....",
        "........................",
        "........................",
        "........................",
        "........................",
    ],
    "correr1": [
        "......KPPPPPPPPK........",
        "......KPPPKPPPK.........",
        ".......KPPKPPK..........",
        ".......KPPKPPK..........",
        "......KPPK.KPPK.........",
        "......KPPK.KkkkK........",
        ".....KkkkK..KKKK........",
        ".....KKKKK..............",
        "........................",
        "........................",
        "........................",
    ],
}

PALETAS_JEFE = {
    1: {"H": (60, 90, 40), "C": (90, 110, 50), "c": (60, 80, 30), "A": (200, 160, 40),
        "P": (70, 80, 40), "S": (200, 150, 100), "s": (150, 100, 60)},
    2: {"H": (30, 30, 30), "C": (236, 236, 236), "c": (190, 190, 200), "A": (240, 200, 40),
        "P": (220, 220, 225), "S": (220, 170, 120), "s": (170, 120, 80)},
    3: {"H": (90, 60, 30), "C": (150, 60, 40), "c": (110, 40, 30), "A": (230, 200, 120),
        "P": (80, 60, 40), "S": (180, 120, 80), "s": (130, 80, 50)},
}


def _detalles_jefe(sup: pygame.Surface, tipo: int) -> None:
    """Accesorios dibujados encima de la plantilla para distinguir a cada jefe."""
    if tipo == 1:   # Jaguar: bandana roja y manchas de camuflado
        pygame.draw.line(sup, (200, 30, 30), (7, 3), (16, 3), 1)
        pygame.draw.line(sup, (200, 30, 30), (6, 3), (4, 6), 1)
        for x, y in ((5, 12), (12, 14), (16, 11), (8, 16)):
            sup.set_at((x, y), (40, 50, 20))
            sup.set_at((x + 1, y), (40, 50, 20))
    elif tipo == 2:  # Don Concreto: gafas oscuras y cadena de oro
        pygame.draw.line(sup, (10, 10, 10), (10, 4), (16, 4), 2)
        pygame.draw.lines(sup, (250, 210, 50), False, [(8, 10), (11, 14), (14, 10)], 1)
    elif tipo == 3:  # La Sombra: sombrero ancho y poncho a rayas
        pygame.draw.rect(sup, (60, 40, 20), (3, 1, 18, 2))
        pygame.draw.rect(sup, (80, 55, 30), (7, -1, 10, 3))
        for y in (12, 15):
            pygame.draw.line(sup, (230, 200, 120), (3, y), (19, y), 1)


def generar_jefe(tipo: int) -> Anims:
    paleta = {"K": (16, 12, 16), "k": (30, 24, 20)}
    paleta.update(PALETAS_JEFE[tipo])

    def frame(piernas: str, brazo: bool = False, brazos_arriba: bool = False) -> pygame.Surface:
        sup = _cuerpo(TORSO_JEFE, PIERNAS_JEFE[piernas], paleta, 24, 32)
        _detalles_jefe(sup, tipo)
        if brazo:
            _brazo(sup, (13, 12), 1, 0, manga=paleta["C"], piel=paleta["S"], largo_arma=8)
        if brazos_arriba:
            pygame.draw.line(sup, paleta["C"], (4, 11), (2, 3), 3)
            pygame.draw.line(sup, paleta["C"], (19, 11), (21, 3), 3)
        return sup

    return {
        "quieto": [frame("quieto")],
        "correr": [frame("correr0"), frame("correr1")],
        "disparar": [frame("quieto", brazo=True)],
        "saltar": [frame("correr1")],
        "especial": [frame("quieto", brazos_arriba=True)],
    }


# =============================================================================
# Power-ups y balas
# =============================================================================
ACERO, ACERO_CLARO, CULATA = (58, 62, 74), (150, 156, 170), (120, 78, 40)


def generar_arma(clase: str) -> Anims:
    """Armas que se recogen (16x12, apuntando a la derecha), sin letras:
    triple = escopeta de tres cañones; rapida = subfusil con cargador largo y estela."""
    frames = []
    for brillo in (0, 1):
        sup = pygame.Surface((16, 12), pygame.SRCALPHA)
        borde = (255, 255, 255) if brillo else (250, 210, 60)
        if clase == "triple":
            pygame.draw.rect(sup, CULATA, (0, 5, 4, 4))                 # culata
            pygame.draw.rect(sup, ACERO, (3, 4, 6, 4))                  # cuerpo
            for dy, largo in ((-2, 6), (0, 7), (2, 6)):                 # tres cañones en abanico
                pygame.draw.line(sup, ACERO_CLARO, (8, 6 + dy // 2), (8 + largo, 6 + dy))
                sup.set_at((9 + largo, 6 + dy), borde)
            pygame.draw.rect(sup, ACERO, (5, 8, 2, 3))                  # empuñadura
        else:
            pygame.draw.rect(sup, ACERO, (4, 4, 8, 3))                  # cuerpo
            pygame.draw.line(sup, ACERO_CLARO, (11, 5), (14, 5))        # cañón corto
            pygame.draw.rect(sup, ACERO, (5, 7, 2, 3))                  # empuñadura
            pygame.draw.rect(sup, ACERO_CLARO, (8, 7, 2, 5))            # cargador largo
            for y, x0 in ((3, 0), (5, 1), (7, 0)):                      # estela de velocidad
                pygame.draw.line(sup, borde, (x0 + brillo, y), (x0 + 2 + brillo, y))
        frames.append(sup)
    return {"quieto": frames}


def generar_vida() -> Anims:
    """Vida extra: una medalla con cinta tricolor (12x12)."""
    frames = []
    for brillo in (0, 1):
        sup = pygame.Surface((12, 12), pygame.SRCALPHA)
        for x, color in ((3, (248, 216, 32)), (5, (0, 88, 248)), (7, (216, 40, 0))):
            pygame.draw.rect(sup, color, (x, 0, 2, 5))
        pygame.draw.circle(sup, (255, 240, 150) if brillo else (248, 216, 32), (6, 8), 4)
        pygame.draw.circle(sup, (160, 110, 20), (6, 8), 4, 1)
        sup.set_at((6, 8), (255, 255, 255))
        frames.append(sup)
    return {"quieto": frames}


# =============================================================================
# Refuerzos aleatorios: dron, moto y camioneta blindada (miran a la derecha)
# =============================================================================
def generar_dron() -> Anims:
    frames = []
    for i in range(2):
        sup = pygame.Surface((22, 12), pygame.SRCALPHA)
        pygame.draw.rect(sup, (40, 42, 52), (6, 4, 10, 5), border_radius=2)        # cuerpo
        pygame.draw.line(sup, (90, 94, 110), (2, 4), (19, 4))                       # brazos
        for x in (3, 18):                                                           # hélices
            ancho = 4 if i == 0 else 2
            pygame.draw.line(sup, (200, 204, 220), (x - ancho, 2), (x + ancho, 2))
            pygame.draw.line(sup, (90, 94, 110), (x, 2), (x, 4))
        pygame.draw.rect(sup, (216, 40, 0) if i == 0 else (255, 140, 60), (10, 8, 2, 2))   # luz
        pygame.draw.line(sup, (90, 94, 110), (11, 9), (11, 11))                     # cañón
        frames.append(sup)
    return {"quieto": frames}


def _rueda(sup: pygame.Surface, x: int, y: int, radio: int, giro: int) -> None:
    pygame.draw.circle(sup, (14, 14, 18), (x, y), radio)
    pygame.draw.circle(sup, (120, 124, 136), (x, y), max(1, radio - 2))
    dx, dy = ((1, 0), (0, 1))[giro % 2]
    pygame.draw.line(sup, (40, 42, 50), (x - dx * (radio - 1), y - dy * (radio - 1)),
                     (x + dx * (radio - 1), y + dy * (radio - 1)))


def generar_moto() -> Anims:
    frames = []
    for i in range(2):
        sup = pygame.Surface((30, 26), pygame.SRCALPHA)
        _rueda(sup, 5, 21, 4, i)
        _rueda(sup, 24, 21, 4, i)
        pygame.draw.polygon(sup, (150, 30, 30), [(6, 19), (12, 14), (21, 14), (25, 19), (14, 20)])  # chasis
        pygame.draw.line(sup, (90, 94, 110), (22, 13), (26, 20), 2)                   # horquilla
        pygame.draw.line(sup, (60, 60, 70), (21, 11), (25, 11))                       # manubrio
        pygame.draw.rect(sup, (44, 44, 52), (10, 6, 7, 9))                            # torso del sicario
        pygame.draw.rect(sup, (196, 140, 96), (11, 2, 5, 4))                          # cara
        pygame.draw.rect(sup, (20, 20, 24), (10, 0, 7, 3))                            # casco
        pygame.draw.line(sup, (44, 44, 52), (15, 8), (22, 8), 2)                      # brazo
        pygame.draw.line(sup, (70, 70, 80), (22, 7), (27, 7), 2)                      # arma al frente
        pygame.draw.line(sup, (50, 70, 140), (12, 14), (16, 18), 2)                   # pierna
        frames.append(sup)
    return {"quieto": frames}


def generar_camioneta() -> Anims:
    """Camioneta blindada blanca con un tirador en el techo corredizo (58x40)."""
    blanco, sombra, vidrio = (236, 236, 240), (176, 180, 192), (40, 60, 90)
    frames = []
    for i in range(2):
        sup = pygame.Surface((58, 40), pygame.SRCALPHA)
        # Tirador asomado por el techo
        pygame.draw.rect(sup, (44, 44, 52), (22, 3, 8, 9))
        pygame.draw.rect(sup, (196, 140, 96), (23, 0, 5, 4))
        pygame.draw.rect(sup, (20, 20, 24), (22, -1, 7, 2))
        pygame.draw.line(sup, (70, 70, 80), (28, 5), (38, 5), 2)                      # fusil
        # Carrocería
        pygame.draw.polygon(sup, blanco, [(2, 36), (2, 22), (10, 12), (40, 12), (48, 22), (56, 24), (56, 36)])
        pygame.draw.polygon(sup, vidrio, [(12, 14), (24, 14), (24, 21), (7, 21)])     # vidrio trasero
        pygame.draw.polygon(sup, vidrio, [(27, 14), (39, 14), (45, 21), (27, 21)])    # vidrio delantero
        pygame.draw.rect(sup, sombra, (2, 30, 54, 6))                                 # faldón
        pygame.draw.rect(sup, (60, 64, 76), (2, 26, 54, 2))                           # franja del blindaje
        pygame.draw.rect(sup, (60, 64, 76), (53, 28, 5, 6))                           # defensa
        pygame.draw.rect(sup, (255, 230, 120), (53, 24, 3, 3))                        # faro
        pygame.draw.rect(sup, (216, 40, 0), (2, 23, 2, 3))                            # stop
        pygame.draw.line(sup, (120, 124, 136), (26, 14), (26, 30))                    # unión de puertas
        pygame.draw.polygon(sup, (16, 12, 16), [(2, 36), (2, 22), (10, 12), (40, 12), (48, 22), (56, 24),
                                                (56, 36)], 1)
        _rueda(sup, 13, 34, 5, i)
        _rueda(sup, 44, 34, 5, i)
        frames.append(sup)
    return {"quieto": frames}


def _bala(radio: int, centro, borde) -> Anims:
    frames = []
    for i in range(2):
        sup = pygame.Surface((radio * 2 + 2, radio * 2 + 2), pygame.SRCALPHA)
        c = radio + 1
        pygame.draw.circle(sup, borde, (c, c), radio + (i % 2) * 0 + 1)
        pygame.draw.circle(sup, centro, (c, c), max(1, radio - i))
        frames.append(sup)
    return {"quieto": frames}


def generar_onda() -> Anims:
    frames = []
    for i in range(3):
        sup = pygame.Surface((10, 12), pygame.SRCALPHA)
        for y in range(12):
            ancho = int((12 - y) / 12 * 5 + 1 + ((y + i) % 3 == 0))
            pygame.draw.line(sup, (255, 200 - y * 10, 60), (5 - ancho, 11 - y), (4 + ancho, 11 - y))
        frames.append(sup)
    return {"quieto": frames}


# =============================================================================
# Pulgar del presidente para la escena del teléfono (12x22, la punta arriba)
# =============================================================================
PAL_PULGAR = {"K": (0, 0, 0), "S": (238, 176, 135), "s": (191, 112, 75),
              "N": (240, 240, 240), "n": (223, 218, 214)}
PULGAR = [
    "...KKKKKK...",
    "..KnNNNNnK..",
    ".KSNNNNNNsK.",
    ".KSNNNNNNsK.",
    ".KSSnnnnSsK.",
    ".KSSSSSSSsK.",
    ".KSSSSSSSsK.",
    ".KSSSSSSSsK.",
    ".KSSSSSSSsK.",
    ".KSSsSSSSsK.",
    ".KSSSssSSsK.",
    ".KSSSSSSSsK.",
    "KSSSSSSSSssK",
    "KSSSSSSSSssK",
    "KSSSSSSSSssK",
    "KSSSSSSSSssK",
    "KSSSSSSSSssK",
    "KSSSSSSSSssK",
    "KSSSSSSSSssK",
    "KSSSSSSSSssK",
    "KSSSSSSSSssK",
    "KSSSSSSSSssK",
]


def generar_pulgar() -> Anims:
    """Placeholder: se alarga repitiendo la última fila para que la base quede fuera de pantalla."""
    filas = PULGAR + [PULGAR[-1]] * (64 - len(PULGAR))
    imagen = cuadricula(filas, PAL_PULGAR, 12, 64)
    return {"quieto": [imagen], "presionando": [imagen]}


GENERADORES = {
    "jugador": generar_presidente,
    "sicario": generar_sicario,
    "jefe1": lambda: generar_jefe(1),
    "jefe2": lambda: generar_jefe(2),
    "jefe3": lambda: generar_jefe(3),
    "powerup_triple": lambda: generar_arma("triple"),
    "powerup_rapida": lambda: generar_arma("rapida"),
    "powerup_vida": generar_vida,
    "dron": generar_dron,
    "moto": generar_moto,
    "camioneta": generar_camioneta,
    "bala_jugador": lambda: _bala(1, (255, 255, 255), (250, 210, 60)),
    "bala_enemigo": lambda: _bala(2, (255, 220, 200), (220, 40, 30)),
    "bala_jefe": lambda: _bala(3, (255, 255, 200), (240, 110, 20)),
    "onda": generar_onda,
    "pulgar": generar_pulgar,
    # Busto del menú: si falta el PNG, el presidente placeholder ampliado
    "presidente_menu": lambda: {"quieto": [pygame.transform.scale_by(generar_presidente()["quieto"][0], 3)]},
}
