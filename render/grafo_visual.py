"""Dibujo del grafo del juego: el mapa del país.

No calcula nada: recibe el grafo y el resultado de sus operaciones (las rutas de Dijkstra y de
BFS, las olas de influencia) y los muestra paso a paso.
"""
from __future__ import annotations

from typing import Dict, Optional, Sequence, Tuple

import pygame

import settings
from core.mapa import PALACIO, ZONA_NIVEL, Mapa
from render.texto import dibujar_texto

C = settings.COLORES
GRIS_VIA = (70, 74, 90)
GRIS_VIA_TENUE = (42, 46, 64)                                    # vías que no importan en la pantalla
GRIS_ZONA_TENUE = (64, 68, 86)                                   # zonas fuera de las dos rutas
ROJO_RETEN = (150, 40, 30)
COLOR_OLA = [(216, 40, 0), (252, 152, 56), (248, 216, 32)]      # zona del jefe, 1 salto, 2 saltos
COLOR_RUTA_ALTERNA = (232, 124, 40)                              # la ruta que no está elegida (naranja)


# =============================================================================
# Mapa del país
# =============================================================================
MARGEN_ARRIBA, FRANJA_ABAJO = 8, 20       # sitio para la zona de arriba / leyenda de abajo


def _punto(mapa: Mapa, zona: str, area: pygame.Rect) -> Tuple[int, int]:
    """Píxel de una zona: su x y su fila (0 a 2) repartida en el alto disponible."""
    x, fila = mapa.grafo.datos[zona]["pos"]
    paso = (area.h - MARGEN_ARRIBA - FRANJA_ABAJO) / 2.0
    return int(area.x + 4 + x), int(area.y + MARGEN_ARRIBA + fila * paso)


_NOMBRES: Dict[tuple, Dict[str, pygame.Rect]] = {}     # posición de los nombres por área (no cambia)


def _corta_caja(pa, pb, caja: pygame.Rect) -> bool:
    return bool(caja.clipline(pa, pb))


def _cajas_nombres(mapa: Mapa, area: pygame.Rect, rutas: frozenset = frozenset()) -> Dict[str, pygame.Rect]:
    """Dónde va el nombre de cada zona: a la derecha, a la izquierda, encima o debajo, en el
    lado que no tape otro nombre ni otra zona, no se salga del área y cruce menos vías (sobre
    todo las de `rutas`, que se ven gruesas). Las zonas no se mueven, así que se guarda."""
    clave = (area.x, area.y, area.w, area.h, rutas)
    if clave in _NOMBRES:
        return _NOMBRES[clave]
    g = mapa.grafo
    puntos = {z: _punto(mapa, z, area) for z in g.vertices()}
    vias = [(puntos[a], puntos[b], a, b) for a, b, _ in g.aristas()]
    cajas: Dict[str, pygame.Rect] = {}
    libre = pygame.Rect(area.x - 1, area.y - 1, area.w + 2, area.h - 9)      # abajo va la leyenda
    for zona, (x, y) in puntos.items():
        ancho = len(_nombre_corto(mapa, zona)) * 6
        lados = [pygame.Rect(x + 7, y - 4, ancho, 9), pygame.Rect(x - 7 - ancho, y - 4, ancho, 9),
                 pygame.Rect(x - ancho // 2, y - 15, ancho, 9), pygame.Rect(x - ancho // 2, y + 7, ancho, 9)]

        def costo(caja):
            fuera = not libre.contains(caja)
            cruces = sum((8 if frozenset((a, b)) in rutas else 1) * _corta_caja(pa, pb, caja.inflate(2, 0))
                         for pa, pb, a, b in vias)
            encima = sum(caja.colliderect(c) for c in cajas.values())
            zonas = sum(caja.colliderect((px - 5, py - 5, 11, 11)) for z, (px, py) in puntos.items() if z != zona)
            return fuera * 100 + (encima + zonas) * 10 + cruces

        cajas[zona] = min(lados, key=costo)
    _NOMBRES[clave] = cajas
    return cajas


def _nombre_corto(mapa: Mapa, zona: str) -> str:
    return mapa.nombre(zona).replace("LA ", "").replace("LOS ", "").replace("EL ", "")


def _linea_punteada(sup: pygame.Surface, color, pa, pb, grosor: int = 2, paso: int = 4) -> None:
    dx, dy = pb[0] - pa[0], pb[1] - pa[1]
    largo = max(1.0, (dx * dx + dy * dy) ** 0.5)
    for i in range(0, int(largo), paso * 2):
        t0, t1 = i / largo, min(1.0, (i + paso) / largo)
        pygame.draw.line(sup, color, (pa[0] + dx * t0, pa[1] + dy * t0), (pa[0] + dx * t1, pa[1] + dy * t1), grosor)


def _caja_peso(pa, pb, peso: float, lado: int, t: float = 0.5, separacion: int = 7) -> pygame.Rect:
    """Recuadro del peso de una vía junto al punto `t` del tramo (0.5 = la mitad), corrido
    `separacion` px hacia un lado (1 = arriba, -1 = abajo) para que no lo tape la línea."""
    dx, dy = pb[0] - pa[0], pb[1] - pa[1]
    largo = max(1.0, (dx * dx + dy * dy) ** 0.5)
    nx, ny = dy / largo, -dx / largo                  # perpendicular
    if ny > 0:
        nx, ny = -nx, -ny                             # que (nx, ny) apunte hacia arriba
    caja = pygame.Rect(0, 0, 6 * len(str(int(peso))) + 3, 10)
    caja.center = (int(pa[0] + dx * t + nx * separacion * lado), int(pa[1] + dy * t + ny * separacion * lado))
    return caja


def _dibujar_pesos(sup: pygame.Surface, pesos, ocupado) -> None:
    """Pinta cada peso del lado de su vía que queda más lejos de la otra ruta (`lejos_de`) o,
    si ahí tapa un nombre u otro peso, del otro lado (y si no, más lejos o sobre la línea).
    Primero van los de la ruta elegida y, entre ellos, los de las vías más cortas; uno de la
    alterna que no cabe en ningún lado se omite antes que encimarlo."""
    ocupado = list(ocupado)
    # las vías cortas eligen primero: son las que tienen menos lugares donde poner su número
    largo = lambda p: (p[0][0] - p[1][0]) ** 2 + (p[0][1] - p[1][1]) ** 2   # noqa: E731
    for pa, pb, peso, color, elegida, lejos_de in sorted(pesos, key=lambda p: (not p[4], largo(p))):
        primero = 1
        if lejos_de is not None:
            lejos = [_caja_peso(pa, pb, peso, lado).center for lado in (1, -1)]
            d = [(x - lejos_de[0]) ** 2 + (y - lejos_de[1]) ** 2 for x, y in lejos]
            primero = 1 if d[0] >= d[1] else -1
        # junto a la mitad del tramo y, si no cabe, un poco antes o después; después más lejos
        # de la mitad y, como último recurso, sobre la misma línea (el recuadro la tapa)
        lados = [_caja_peso(pa, pb, peso, lado, t) for lado in (primero, -primero) for t in (0.5, 0.35, 0.65)]
        lados += [_caja_peso(pa, pb, peso, lado, t) for lado in (primero, -primero) for t in (0.25, 0.75)]
        lados += [_caja_peso(pa, pb, peso, 1, t, separacion=0) for t in (0.5, 0.35, 0.65, 0.25, 0.75)]
        # vías muy cortas (entre dos zonas casi pegadas): el número va más apartado, a un costado
        lados += [_caja_peso(pa, pb, peso, lado, 0.5, separacion=d) for d in (11, 15) for lado in (primero, -primero)]
        caja = next((c for c in lados if c.collidelist(ocupado) < 0), None)
        if caja is None:
            if not elegida:
                continue
            caja = min(lados, key=lambda c: len(c.collidelistall(ocupado)))     # lo menos encimado
        ocupado.append(caja)
        pygame.draw.rect(sup, (10, 12, 26), caja)
        dibujar_texto(sup, str(int(peso)), (caja.x + 2, caja.y + 1), color, sombra=False)


def _centro(mapa: Mapa, zonas: Sequence[str], area: pygame.Rect):
    """Punto medio de las zonas intermedias de una ruta (o de todas si es un solo tramo)."""
    medio = list(zonas[1:-1]) or list(zonas)
    if not medio:
        return None
    puntos = [_punto(mapa, z, area) for z in medio]
    return (sum(p[0] for p in puntos) / len(puntos), sum(p[1] for p in puntos) / len(puntos))


def dibujar_mapa(sup: pygame.Surface, mapa: Mapa, area: pygame.Rect, nivel: Optional[int] = None,
                 ruta: Sequence[str] = (), tramos_ruta: float = 0.0, olas: Sequence[Sequence[str]] = (),
                 olas_visibles: int = 0, tiempo: float = 0.0, ruta_alterna: Sequence[str] = (),
                 simple: bool = False, color_ruta=None, color_alterna=COLOR_RUTA_ALTERNA) -> None:
    """Vías con su peligro, zonas, la ruta elegida (cian, se pinta hasta `tramos_ruta` tramos), la
    ruta alterna (naranja punteada) y las olas de influencia del jefe (las primeras `olas_visibles`).
    `simple`: las vías van tenues y sin números; solo llevan peso las dos rutas, y las zonas que
    no están en ninguna se apagan (con 16 vías, mostrarlo todo enreda las rutas)."""
    g = mapa.grafo
    color_ruta = color_ruta or C["cian"]
    en_ruta = {frozenset(par) for par in zip(ruta, ruta[1:])}
    retenes = {frozenset(r) for r in mapa.retenes}
    eligiendo = bool(ruta)
    en_rutas = set(ruta) | set(ruta_alterna)
    pesos = []                       # los pesos se pintan al final, sobre los nombres
    centro_ruta, centro_alterna = _centro(mapa, ruta, area), _centro(mapa, ruta_alterna, area)
    # 1) Vías: gris, con su peso en el punto medio
    for a, b, peso in g.aristas():
        pa, pb = _punto(mapa, a, area), _punto(mapa, b, area)
        via = frozenset((a, b))
        if simple:
            reten = via in retenes and eligiendo           # el retén solo importa al elegir ruta
            pygame.draw.line(sup, ROJO_RETEN if reten else GRIS_VIA_TENUE, pa, pb, 1)
            continue
        pygame.draw.line(sup, GRIS_VIA, pa, pb, 1)
        if via not in en_ruta:
            pesos.append((pa, pb, peso, C["rojo"] if via in retenes else C["gris"], True, None))
    # 2) Nombres, sobre las vías tenues y debajo de las rutas
    destino = ZONA_NIVEL.get(nivel)
    vias_rutas = frozenset(frozenset(par) for camino in (ruta, ruta_alterna) for par in zip(camino, camino[1:]))
    cajas_nombre = _cajas_nombres(mapa, area, vias_rutas)
    for zona, caja in cajas_nombre.items():
        if zona in (PALACIO, destino):
            color_nombre = C["blanco"]
        else:
            color_nombre = GRIS_ZONA_TENUE if simple and eligiendo and zona not in en_rutas else C["gris"]
        pygame.draw.rect(sup, (16, 20, 40), caja.inflate(2, 0))      # las vías tenues pasan por debajo
        dibujar_texto(sup, _nombre_corto(mapa, zona), caja.topleft, color_nombre, sombra=False)
    # 3) Ruta alterna (punteada) y ruta elegida, tramo por tramo
    for a, b in zip(ruta_alterna, ruta_alterna[1:]):
        if frozenset((a, b)) in en_ruta:
            continue                                        # tramo compartido: lo pinta la elegida
        pa, pb = _punto(mapa, a, area), _punto(mapa, b, area)
        _linea_punteada(sup, color_alterna, pa, pb)
        if simple:
            color = C["rojo"] if frozenset((a, b)) in retenes else color_alterna
            pesos.append((pa, pb, g.peso(a, b), color, False, centro_ruta))
    for i, (a, b) in enumerate(zip(ruta, ruta[1:])):
        avance = max(0.0, min(1.0, tramos_ruta - i))
        if avance <= 0:
            break
        pa, pb = _punto(mapa, a, area), _punto(mapa, b, area)
        hasta = (pa[0] + (pb[0] - pa[0]) * avance, pa[1] + (pb[1] - pa[1]) * avance)
        pygame.draw.line(sup, color_ruta, pa, hasta, 3)
        color = C["rojo"] if frozenset((a, b)) in retenes else (color_ruta if simple else C["blanco"])
        pesos.append((pa, pb, g.peso(a, b), color, True, centro_alterna))
    # 4) Zonas
    ola_de: Dict[str, int] = {z: k for k, ola in enumerate(olas[:olas_visibles]) for z in ola}
    for zona in g.vertices():
        x, y = _punto(mapa, zona, area)
        apagada = simple and eligiendo and zona not in en_rutas
        color = GRIS_ZONA_TENUE if apagada else (110, 114, 130)
        if zona in ola_de:
            color = COLOR_OLA[min(ola_de[zona], len(COLOR_OLA) - 1)]
        elif zona in ruta[:int(tramos_ruta) + 1] and tramos_ruta > 0:
            color = color_ruta
        elif zona in ruta_alterna and simple:
            color = color_alterna
        radio = 5 if zona in (PALACIO, destino) else 4
        if zona == destino and int(tiempo * 4) % 2 == 0:
            pygame.draw.circle(sup, C["blanco"], (x, y), radio + 3, 1)
        pygame.draw.circle(sup, color, (x, y), radio)
        pygame.draw.circle(sup, C["negro"], (x, y), radio, 1)
        if zona in mapa.jefes_libres:                   # jefe libre: calavera mínima (una X)
            pygame.draw.line(sup, C["negro"], (x - 2, y - 2), (x + 2, y + 2))
            pygame.draw.line(sup, C["negro"], (x - 2, y + 2), (x + 2, y - 2))
    zonas = [pygame.Rect(x - 5, y - 5, 11, 11) for x, y in (_punto(mapa, z, area) for z in g.vertices())]
    _dibujar_pesos(sup, pesos, list(cajas_nombre.values()) + zonas)     # los pesos no tapan nombres ni zonas
