"""Animación por código a partir de UN solo dibujo (los PNG de enemigos y jefes traen una pose).

Se generan cuadros nuevos moviendo partes del mismo sprite, sin inventar píxeles:
    piernas     tijera: la pierna de adelante avanza y la de atrás retrocede, más cuanto más
                cerca del pie; el cuerpo baja 1 px al apoyar (paso de caminata)
    respirar    los hombros suben 1 px de cuando en cuando
    retroceso   el cuerpo se corre 1 px hacia atrás (al disparar)
    inclinar    la parte de arriba se adelanta (embestida)
    encoger     las piernas se recogen (salto)
    agazapar    todo el cuerpo se aplasta un poco desde los pies (antes de un ataque)

Cada sprite dice qué animaciones quiere en PROCEDURALES. Si el PNG trae esa animación con
varios cuadros dibujados a mano, mandan ellos.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import pygame

# nombre del sprite -> {animación: (receta, parámetros)}
# cadera: fracción de la altura del cuerpo donde empiezan las piernas.
PROCEDURALES = {
    "sicario": {
        "correr": ("caminar", {"cadera": 0.66, "amplitud": 3}),
        "quieto": ("respirar", {"pecho": 0.45}),
        "apuntar": ("respirar", {"pecho": 0.45, "lento": True}),
    },
    # Los jefes NO están aquí: con sus dibujos (sacos largos, cuerpos anchos) cortar el sprite en
    # partes se ve como si se rompieran. Se mueven enteros en scenes/level.py (rebote al caminar,
    # culatazo al disparar).
    # El presidente sí tiene dos cuadros de carrera, pero no apuntando arriba o en diagonal:
    # esas poses "corren" con las piernas generadas aquí.
    "jugador": {
        "correr_arriba": ("caminar", {"base": "arriba", "cadera": 0.6, "amplitud": 3}),
        "correr_diag_arriba": ("caminar", {"base": "diag_arriba", "cadera": 0.6, "amplitud": 3}),
        "correr_diag_abajo": ("caminar", {"base": "diag_abajo", "cadera": 0.6, "amplitud": 3}),
    },
}


# --- Medidas del dibujo ----------------------------------------------------------------------
def caja_visible(imagen: pygame.Surface) -> pygame.Rect:
    """Rectángulo de los píxeles no transparentes."""
    return imagen.get_bounding_rect(min_alpha=1)


def _columna_entre_piernas(imagen: pygame.Surface, desde: int, hasta: int, caja: pygame.Rect) -> int:
    """Columna de la zona de piernas con menos píxeles (el hueco entre las dos piernas).
    Solo se busca en el tercio central de las piernas, para no tomar el borde del dibujo."""
    mascara = pygame.mask.from_surface(imagen)
    columnas = []
    izq, der = caja.left, caja.right
    # Las piernas ocupan menos ancho que el torso: se mide su propia caja
    xs = [x for x in range(izq, der) for y in range(desde, hasta) if mascara.get_at((x, y))]
    if not xs:
        return caja.centerx
    izq, der = min(xs), max(xs) + 1
    tercio = max(1, (der - izq) // 3)
    for x in range(izq + tercio, der - tercio + 1):
        columnas.append((sum(mascara.get_at((x, y)) for y in range(desde, hasta)), abs(x - (izq + der) / 2), x))
    return min(columnas)[2] if columnas else (izq + der) // 2


def _entrepierna(imagen: pygame.Surface, caja: pygame.Rect, corte: int) -> int:
    """Fila más alta donde, cerca de la columna `corte`, hay un hueco real entre las piernas
    (transparente entre dos zonas pintadas). Un saco largo tapa las piernas: ahí no se corta."""
    mascara = pygame.mask.from_surface(imagen)
    fila = caja.bottom
    for y in range(caja.bottom - 1, caja.top + caja.h // 2, -1):
        izq = any(mascara.get_at((x, y)) for x in range(max(caja.left, corte - 8), corte - 1))
        der = any(mascara.get_at((x, y)) for x in range(corte + 1, min(caja.right, corte + 8)))
        hueco = any(not mascara.get_at((x, y)) for x in range(corte - 1, corte + 2))
        if izq and der and hueco:
            fila = y
        elif fila < caja.bottom and y < fila - 1:
            break                                  # el hueco se cerró: de aquí para arriba es tela
    return fila


# --- Recetas -----------------------------------------------------------------------------------
def _vacia(imagen: pygame.Surface) -> pygame.Surface:
    return pygame.Surface(imagen.get_size(), pygame.SRCALPHA)


def _paso(imagen: pygame.Surface, fase: float, cadera_y: int, corte_x: int, pie_y: int,
          amplitud: int, bajar: int = 0, inclinar: int = 0) -> pygame.Surface:
    """Un cuadro de la caminata. fase en [-1, 1]: +1 = pierna derecha (la de adelante, porque
    los sprites miran a la derecha) adelantada al máximo."""
    ancho, alto = imagen.get_size()
    sup = _vacia(imagen)
    # Torso: igual, bajado `bajar` px y, si se inclina, cada fila corrida hacia adelante
    if inclinar:
        for y in range(cadera_y):
            dx = round(inclinar * (cadera_y - y) / max(1, cadera_y))
            sup.blit(imagen, (dx, y + bajar), pygame.Rect(0, y, ancho, 1))
    else:
        sup.blit(imagen, (0, bajar), pygame.Rect(0, 0, ancho, cadera_y))
    # Piernas: primero la de atrás, encima la de adelante
    largo = max(1, pie_y - cadera_y)
    for lado, signo in ((pygame.Rect(0, 0, corte_x, alto), -1), (pygame.Rect(corte_x, 0, ancho - corte_x, alto), 1)):
        for y in range(cadera_y, alto):
            t = min(1.0, (y - cadera_y) / largo)
            dx = round(signo * fase * amplitud * t)
            # Las filas de arriba de las piernas bajan con el torso; el pie queda en el suelo
            dy = round(bajar * (1 - t))
            sup.blit(imagen, (lado.x + dx, y + dy), pygame.Rect(lado.x, y, lado.w, 1))
    # Tela continua (pantalón ancho): si al abrir las piernas queda una raya vacía donde el
    # dibujo original no tenía hueco, se rellena con el color de la tela de al lado.
    if 0 < corte_x < ancho:
        for y in range(cadera_y, min(alto, pie_y)):
            t = min(1.0, (y - cadera_y) / largo)
            abre = round(fase * amplitud * t)
            if abre <= 0 or imagen.get_at((corte_x - 1, y)).a == 0 or imagen.get_at((corte_x, y)).a == 0:
                continue
            dy = round(bajar * (1 - t))
            color = imagen.get_at((corte_x - 1, y))
            for x in range(corte_x - abre, corte_x + abre):
                if 0 <= x < ancho and 0 <= y + dy < alto and sup.get_at((x, y + dy)).a == 0:
                    sup.set_at((x, y + dy), color)
    return sup


def caminar(imagen: pygame.Surface, cadera: float = 0.62, amplitud: int = 3,
            inclinar: int = 0) -> List[pygame.Surface]:
    """4 cuadros: paso derecho, cruce (cuerpo arriba), paso izquierdo, cruce."""
    caja = caja_visible(imagen)
    if caja.h < 8:
        return [imagen]
    cadera_y = caja.top + int(caja.h * cadera)
    corte = _columna_entre_piernas(imagen, cadera_y, caja.bottom, caja)
    # Si la ropa es larga, las piernas empiezan donde se abre el hueco entre ellas
    cadera_y = max(cadera_y, min(caja.bottom - 6, _entrepierna(imagen, caja, corte) - 2))
    return [_paso(imagen, 1, cadera_y, corte, caja.bottom, amplitud, bajar=1, inclinar=inclinar),
            _paso(imagen, 0, cadera_y, corte, caja.bottom, amplitud, inclinar=inclinar),
            _paso(imagen, -1, cadera_y, corte, caja.bottom, amplitud, bajar=1, inclinar=inclinar),
            _paso(imagen, 0, cadera_y, corte, caja.bottom, amplitud, inclinar=inclinar)]


def respirar(imagen: pygame.Surface, pecho: float = 0.5, lento: bool = False) -> List[pygame.Surface]:
    """Cuadros quietos con los hombros 1 px más arriba la mitad del tiempo (a 8 fps: 1 s por
    respiración, o 1,5 s si es lento)."""
    caja = caja_visible(imagen)
    corte = caja.top + int(caja.h * pecho)
    arriba = _vacia(imagen)
    arriba.blit(imagen, (0, 0))
    arriba.fill((0, 0, 0, 0), pygame.Rect(0, 0, imagen.get_width(), corte))
    arriba.blit(imagen, (0, -1), pygame.Rect(0, 0, imagen.get_width(), corte))
    veces = 6 if lento else 4
    return [imagen] * veces + [arriba] * veces


def retroceso(imagen: pygame.Surface) -> List[pygame.Surface]:
    """Culatazo: el cuerpo se corre 1 px atrás y vuelve."""
    atras = _vacia(imagen)
    atras.blit(imagen, (-1, 0))
    return [atras, imagen]


def encoger(imagen: pygame.Surface, cadera: float = 0.62) -> List[pygame.Surface]:
    """Piernas recogidas: la zona de las piernas se aplasta al 70 % (hacia arriba)."""
    caja = caja_visible(imagen)
    cadera_y = caja.top + int(caja.h * cadera)
    piernas = imagen.subsurface(pygame.Rect(0, cadera_y, imagen.get_width(), caja.bottom - cadera_y))
    alto = max(1, round(piernas.get_height() * 0.7))
    sup = _vacia(imagen)
    sup.blit(imagen, (0, 0), pygame.Rect(0, 0, imagen.get_width(), cadera_y))
    sup.blit(pygame.transform.scale(piernas, (piernas.get_width(), alto)), (0, cadera_y))
    return [sup]


def agazapar(imagen: pygame.Surface) -> List[pygame.Surface]:
    """Todo el cuerpo un poco más bajo y ancho, con los pies en el mismo lugar."""
    caja = caja_visible(imagen)
    ancho, alto = imagen.get_size()
    nuevo_alto = max(1, round(caja.h * 0.94))
    nuevo_ancho = round(caja.w * 1.04)
    cuerpo = pygame.transform.scale(imagen.subsurface(caja), (nuevo_ancho, nuevo_alto))
    sup = _vacia(imagen)
    sup.blit(cuerpo, (caja.centerx - nuevo_ancho // 2, caja.bottom - nuevo_alto))
    return [sup]


RECETAS = {
    "caminar": caminar,
    "embestir": lambda im, **k: caminar(im, inclinar=3, **k),
    "respirar": respirar,
    "retroceso": lambda im, **k: retroceso(im),
    "encoger": encoger,
    "agazapar": lambda im, **k: agazapar(im),
}


def completar(nombre: str, anims: Dict[str, List[pygame.Surface]], propias: set) -> None:
    """Agrega a `anims` las animaciones generadas de este sprite.
    propias: animaciones que vienen en el PNG. Si una trae VARIOS cuadros dibujados, manda
    ella; si trae uno solo (una pose quieta), se anima a partir de ese cuadro."""
    for anim, (receta, parametros) in PROCEDURALES.get(nombre, {}).items():
        if anim in propias and len(anims.get(anim, ())) > 1:
            continue
        parametros = dict(parametros)
        base = parametros.pop("base", "quieto")
        cuadros = anims.get(base)
        if not cuadros:
            continue
        anims[anim] = RECETAS[receta](cuadros[0], **parametros)


def anim_correr_jugador(pose: str) -> Optional[str]:
    """Animación de carrera para una pose de apunte sin cuadros propios (o None)."""
    nombre = f"correr_{pose}"
    return nombre if nombre in PROCEDURALES["jugador"] else None


def medidas(imagen: pygame.Surface, cadera: float) -> Tuple[int, int]:
    """(fila de la cadera, columna entre piernas): para revisar la detección en las pruebas."""
    caja = caja_visible(imagen)
    cadera_y = caja.top + int(caja.h * cadera)
    return cadera_y, _columna_entre_piernas(imagen, cadera_y, caja.bottom, caja)
