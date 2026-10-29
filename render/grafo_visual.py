"""Dibujo del grafo del juego sobre el mapa de Colombia (render/mapa_colombia.py).

No calcula nada: recibe el grafo y el resultado de sus operaciones (las rutas de Dijkstra y de
BFS, las olas de influencia, el recorrido ya hecho) y los muestra. Cada zona va en su lugar real.

El mapa se encuadra con zoom sobre las zonas que importan en cada pantalla (`enfoque`). Para que
se lea de un vistazo:
  - ruta segura en CIAN y ruta corta en MAGENTA (colores que no aparecen en el paisaje), con
    borde oscuro; la elegida va sólida y con flecha de llegada, la otra punteada;
  - lo ya recorrido en niveles anteriores, en blanco;
  - en la página de rutas no se dibujan las demás vías, y solo llevan número las de las rutas.
"""
from __future__ import annotations

import math
from typing import Dict, Optional, Sequence, Tuple

import pygame

import settings
from core.mapa import PALACIO, ZONA_NIVEL, Mapa
from render import fuente_mini, mapa_colombia

C = settings.COLORES
COLOR_SEGURA = (40, 232, 255)                                    # cian
COLOR_CORTA = (255, 64, 200)                                     # magenta
COLOR_RUTA_ALTERNA = COLOR_CORTA                                 # (nombre de antes)
COLOR_OLA = [(236, 30, 20), (255, 150, 30), (255, 236, 60)]      # zona del jefe, 1 salto, 2 saltos
COLOR_RECORRIDO = (255, 255, 255)                                # lo que el presidente ya viajó
BORDE = (12, 10, 18)
VIA = (40, 30, 30)
ROJO_RETEN = (230, 30, 20)
FONDO_ETIQUETA = (12, 14, 28)
# Departamento de cada zona: se resalta el del jefe del nivel
DEPARTAMENTO = {"capital": "SANTAFE DE BOGOTA D.C", "llanos": "META", "selva": "VICHADA",
                "casanare": "CASANARE", "puerto": "SANTANDER", "ciudad": "ANTIOQUIA",
                "caribe": "BOLIVAR", "sierra": "MAGDALENA", "frontera": "LA GUAJIRA"}


# =============================================================================
# Encuadre y posiciones
# =============================================================================
_ENCUADRES: Dict[tuple, tuple] = {}


def _encuadre(mapa: Mapa, area: pygame.Rect, enfoque: Optional[Sequence[str]]):
    """(mapa pintado, esquina) para el área, con zoom sobre las zonas de `enfoque`."""
    zonas = tuple(sorted(enfoque)) if enfoque else tuple(sorted(mapa.grafo.vertices()))
    clave = (area.x, area.y, area.w, area.h, zonas)
    if clave not in _ENCUADRES:
        puntos = [tuple(mapa.grafo.datos[z]["pos"]) for z in zonas]
        caja, escala = mapa_colombia.encuadre(puntos, area.w, area.h)
        _ENCUADRES[clave] = (mapa_colombia.mapa(area.w, area.h, caja, escala), (area.x, area.y))
    return _ENCUADRES[clave]


def _punto(mapa: Mapa, zona: str, area: pygame.Rect, enfoque=None) -> Tuple[int, int]:
    m, (ox, oy) = _encuadre(mapa, area, enfoque)
    lon, lat = mapa.grafo.datos[zona]["pos"]
    x, y = m.proy.a_pixel(lon, lat)
    return int(ox + x), int(oy + y)


_NOMBRES: Dict[tuple, Dict[str, pygame.Rect]] = {}


def _cajas_nombres(mapa: Mapa, area: pygame.Rect, zonas: Sequence[str], segmentos, enfoque) -> Dict[str, pygame.Rect]:
    """Dónde va el nombre de cada zona: el lado que no tape otro nombre, otra zona ni una ruta,
    y no se salga del área. Las zonas no se mueven, así que se guarda."""
    clave = (area.x, area.y, area.w, area.h, tuple(zonas), tuple(sorted(enfoque or ())), tuple(segmentos))
    if clave in _NOMBRES:
        return _NOMBRES[clave]
    puntos = {z: _punto(mapa, z, area, enfoque) for z in mapa.grafo.vertices()}
    cajas: Dict[str, pygame.Rect] = {}
    for zona in zonas:
        x, y = puntos[zona]
        ancho, alto = fuente_mini.tamano(mapa.corto(zona))
        ancho, alto = ancho + 3, alto + 2
        lados = []
        for dist in (5, 9):                       # pegada a la zona y, si no cabe, un poco más lejos
            lados += [pygame.Rect(x + dist, y - alto // 2, ancho, alto), pygame.Rect(x - dist - ancho, y - alto // 2, ancho, alto),
                      pygame.Rect(x - ancho // 2, y - dist - alto, ancho, alto), pygame.Rect(x - ancho // 2, y + dist, ancho, alto),
                      pygame.Rect(x + dist - 1, y - dist - alto + 2, ancho, alto), pygame.Rect(x - dist - ancho + 1, y - dist - alto + 2, ancho, alto),
                      pygame.Rect(x + dist - 1, y + dist - 2, ancho, alto), pygame.Rect(x - dist - ancho + 1, y + dist - 2, ancho, alto)]

        def costo(caja, zona=zona):
            fuera = not area.contains(caja)
            encima = sum(caja.colliderect(c.inflate(2, 2)) for c in cajas.values())
            tapa = sum(caja.colliderect((px - 4, py - 4, 9, 9)) for z, (px, py) in puntos.items() if z != zona)
            cruces = sum(bool(caja.clipline(puntos[a], puntos[b])) for a, b in segmentos)
            return fuera * 200 + encima * 80 + tapa * 40 + cruces * 15 + lados.index(caja) * 0.2

        cajas[zona] = min(lados, key=costo)
    _NOMBRES[clave] = cajas
    return cajas


# =============================================================================
# Trazos
# =============================================================================
def _linea_punteada(sup, color, pa, pb, grosor: int = 1, paso: int = 4) -> None:
    dx, dy = pb[0] - pa[0], pb[1] - pa[1]
    largo = max(1.0, (dx * dx + dy * dy) ** 0.5)
    for i in range(0, int(largo), paso * 2):
        t0, t1 = i / largo, min(1.0, (i + paso) / largo)
        pygame.draw.line(sup, color, (pa[0] + dx * t0, pa[1] + dy * t0), (pa[0] + dx * t1, pa[1] + dy * t1), grosor)


def _tramo(sup, color, pa, pb, avance: float = 1.0, grosor: int = 3, punteado: bool = False) -> None:
    """Tramo de una ruta con borde oscuro (se lee sobre cualquier color del mapa)."""
    hasta = (pa[0] + (pb[0] - pa[0]) * avance, pa[1] + (pb[1] - pa[1]) * avance)
    if punteado:
        _linea_punteada(sup, BORDE, pa, hasta, grosor + 2)
        _linea_punteada(sup, color, pa, hasta, grosor)
    else:
        pygame.draw.line(sup, BORDE, pa, hasta, grosor + 2)
        pygame.draw.line(sup, color, pa, hasta, grosor)


def _flecha(sup, color, pa, pb) -> None:
    """Punta de flecha que llega a pb (la dirección del viaje)."""
    ang = math.atan2(pb[1] - pa[1], pb[0] - pa[0])
    punta = (pb[0] - math.cos(ang) * 5, pb[1] - math.sin(ang) * 5)
    puntos = [punta] + [(punta[0] - math.cos(ang + d) * 7, punta[1] - math.sin(ang + d) * 7) for d in (0.55, -0.55)]
    pygame.draw.polygon(sup, BORDE, puntos, 3)
    pygame.draw.polygon(sup, color, puntos)


def _caja_peso(pa, pb, peso: float, lado: int, t: float = 0.5, separacion: int = 7) -> pygame.Rect:
    dx, dy = pb[0] - pa[0], pb[1] - pa[1]
    largo = max(1.0, (dx * dx + dy * dy) ** 0.5)
    nx, ny = dy / largo, -dx / largo
    if ny > 0:
        nx, ny = -nx, -ny
    caja = pygame.Rect(0, 0, fuente_mini.tamano(str(int(peso)))[0] + 4, 9)
    caja.center = (int(pa[0] + dx * t + nx * separacion * lado), int(pa[1] + dy * t + ny * separacion * lado))
    return caja


def _dibujar_pesos(sup, pesos, ocupado, area: pygame.Rect) -> None:
    """Cada peso en un recuadro con el borde del color de su ruta, junto a su vía, donde no tape
    un nombre, una zona ni otro peso (los de vías secundarias se omiten si no caben)."""
    ocupado = list(ocupado)
    for pa, pb, peso, color, importante in sorted(pesos, key=lambda p: not p[4]):
        lados = [_caja_peso(pa, pb, peso, lado, t, separacion=6) for lado in (1, -1) for t in (0.5, 0.4, 0.6, 0.3, 0.7)]
        lados += [_caja_peso(pa, pb, peso, lado, 0.5, separacion=d) for d in (9, 12) for lado in (1, -1)]
        lados += [_caja_peso(pa, pb, peso, 1, t, separacion=0) for t in (0.5, 0.4, 0.6)]     # sobre la línea
        libres = [c for c in lados if c.collidelist(ocupado) < 0 and area.contains(c)]
        if libres:
            caja = libres[0]
        elif importante:
            caja = min(lados, key=lambda c: len(c.collidelistall(ocupado)))
        else:
            continue
        ocupado.append(caja)
        pygame.draw.rect(sup, FONDO_ETIQUETA, caja)
        pygame.draw.rect(sup, color, caja, 1)
        fuente_mini.dibujar(sup, str(int(peso)), (caja.x + 2, caja.y + 1), C["blanco"])


def _zona(sup, x, y, color, radio: int) -> None:
    pygame.draw.circle(sup, BORDE, (x, y), radio + 1)
    pygame.draw.circle(sup, color, (x, y), radio)
    sup.set_at((x - 1, y - 1), tuple(min(255, c + 80) for c in color))


def _estrella(sup, x, y, color) -> None:
    """La capital: una estrella."""
    rayos = [(0, -4), (-4, -1), (4, -1), (-3, 3), (3, 3)]
    for dx, dy in rayos:
        pygame.draw.line(sup, BORDE, (x, y), (x + dx, y + dy), 3)
    for dx, dy in rayos:
        pygame.draw.line(sup, color, (x, y), (x + dx, y + dy), 1)


# =============================================================================
# Mapa
# =============================================================================
def dibujar_mapa(sup: pygame.Surface, mapa: Mapa, area: pygame.Rect, nivel: Optional[int] = None,
                 ruta: Sequence[str] = (), tramos_ruta: float = 0.0, olas: Sequence[Sequence[str]] = (),
                 olas_visibles: int = 0, tiempo: float = 0.0, ruta_alterna: Sequence[str] = (),
                 simple: bool = False, color_ruta=None, color_alterna=COLOR_CORTA,
                 recorrido: Sequence[Sequence[str]] = (), colores_recorrido: Sequence = (),
                 enfoque: Optional[Sequence[str]] = None) -> dict:
    """El mapa de Colombia (con zoom sobre `enfoque`) y el grafo encima.
    ruta / ruta_alterna: la elegida (sólida, se traza hasta `tramos_ruta` tramos) y la otra (punteada).
    olas: las zonas que alcanza el jefe, por saltos (se ven las primeras `olas_visibles`).
    recorrido: caminos ya viajados en niveles anteriores (con `colores_recorrido`, o en blanco).
    simple: pantalla de una sola idea; si hay rutas, las demás vías no se dibujan.
    Devuelve dónde quedaron los nombres y las zonas (para las pruebas)."""
    g = mapa.grafo
    m, esquina = _encuadre(mapa, area, enfoque)
    anterior = sup.get_clip()
    sup.set_clip(area)
    sup.blit(m.imagen, esquina)
    color_ruta = color_ruta or COLOR_SEGURA
    destino = ZONA_NIVEL.get(nivel)
    retenes = {frozenset(r) for r in mapa.retenes}
    en_ruta = list(zip(ruta, ruta[1:]))
    compartidos = {frozenset(t) for t in en_ruta}
    en_alterna = [(a, b) for a, b in zip(ruta_alterna, ruta_alterna[1:]) if frozenset((a, b)) not in compartidos]
    p = {z: _punto(mapa, z, area, enfoque) for z in g.vertices()}
    ola_de: Dict[str, int] = {z: k for k, ola in enumerate(olas[:olas_visibles]) for z in ola}
    if destino and int(tiempo * 3) % 2 == 0:                     # el departamento del jefe late
        sup.blit(m.contorno(DEPARTAMENTO[destino], (255, 250, 230)), esquina)
    pesos = []
    # 1) Vías de fondo: en el mapa completo todas, con su peso; en las olas, tenues; con rutas, nada
    if not simple or not (ruta or ruta_alterna):
        for a, b, peso in g.aristas():
            reten = frozenset((a, b)) in retenes
            pygame.draw.line(sup, ROJO_RETEN if reten and not simple else VIA, p[a], p[b], 1)
            if not simple:
                pesos.append((p[a], p[b], peso, ROJO_RETEN if reten else (150, 150, 160), False))
    # 2) Lo ya recorrido
    for i, camino in enumerate(recorrido):
        color = colores_recorrido[i] if i < len(colores_recorrido) else COLOR_RECORRIDO
        for a, b in zip(camino, camino[1:]):
            _tramo(sup, color, p[a], p[b], grosor=2)
            if colores_recorrido:
                pesos.append((p[a], p[b], g.peso(a, b), color, True))
    # 3) Ruta alterna (punteada) y ruta elegida, tramo por tramo, con flecha al llegar
    for a, b in en_alterna:
        _tramo(sup, color_alterna, p[a], p[b], grosor=2, punteado=True)
        pesos.append((p[a], p[b], g.peso(a, b), ROJO_RETEN if frozenset((a, b)) in retenes else color_alterna, True))
    for i, (a, b) in enumerate(en_ruta):
        avance = max(0.0, min(1.0, tramos_ruta - i))
        if avance <= 0:
            break
        _tramo(sup, color_ruta, p[a], p[b], avance)
        pesos.append((p[a], p[b], g.peso(a, b), ROJO_RETEN if frozenset((a, b)) in retenes else color_ruta, True))
        if avance >= 1 and i == len(en_ruta) - 1:
            _flecha(sup, color_ruta, p[a], p[b])
    # 4) Zonas: solo las que importan en la pantalla
    if simple and (ruta or ruta_alterna):
        visibles = set(ruta) | set(ruta_alterna) | {z for c in recorrido for z in c}
    else:
        visibles = set(g.vertices())
    for zona in visibles:
        x, y = p[zona]
        color = (226, 226, 236)
        if zona in ola_de:
            color = COLOR_OLA[min(ola_de[zona], len(COLOR_OLA) - 1)]
        elif zona in ruta[:int(tramos_ruta) + 1] and tramos_ruta > 0:
            color = color_ruta
        if zona == destino and int(tiempo * 4) % 2 == 0:
            pygame.draw.circle(sup, BORDE, (x, y), 8, 3)
            pygame.draw.circle(sup, C["blanco"], (x, y), 7, 1)
        if zona == PALACIO:
            _estrella(sup, x, y, C["amarillo"] if zona not in ola_de else color)
        else:
            _zona(sup, x, y, color, 3)
        if zona in mapa.jefes_libres:                           # jefe libre: una X encima
            pygame.draw.line(sup, BORDE, (x - 2, y - 2), (x + 2, y + 2))
            pygame.draw.line(sup, BORDE, (x - 2, y + 2), (x + 2, y - 2))
    # 5) Nombres
    if simple and (ruta or ruta_alterna):
        con_nombre = [z for z in g.vertices() if z in set(ruta) | set(ruta_alterna)]
    elif simple and recorrido and not olas:                  # el recorrido completo (pantalla final)
        con_nombre = [z for z in g.vertices() if z in {x for c in recorrido for x in c}]
    elif simple:                     # las olas: el jefe y lo que alcanza en un salto
        cerca = set(olas[0]) | (set(olas[1]) if len(olas) > 1 else set()) if olas else set()
        con_nombre = [z for z in g.vertices() if (z in ola_de and z in cerca) or z == destino]
    else:
        con_nombre = list(g.vertices())
    segmentos = en_ruta + en_alterna + [(a, b) for c in recorrido for a, b in zip(c, c[1:])]
    if not simple or not (ruta or ruta_alterna):              # también las vías de fondo que se ven
        segmentos += [(a, b) for a, b, _ in g.aristas()]
    segmentos = tuple(segmentos)
    cajas = _cajas_nombres(mapa, area, con_nombre, segmentos, enfoque)
    for zona, caja in cajas.items():
        importante = zona == destino or zona in ruta or zona in ola_de or not simple
        pygame.draw.rect(sup, FONDO_ETIQUETA, caja)
        fuente_mini.dibujar(sup, mapa.corto(zona), (caja.x + 2, caja.y + 1), C["blanco"] if importante else (190, 190, 200))
    zonas = [pygame.Rect(p[z][0] - 4, p[z][1] - 4, 9, 9) for z in visibles]
    _dibujar_pesos(sup, pesos, list(cajas.values()) + zonas, area)
    sup.set_clip(anterior)
    return {"nombres": dict(cajas), "zonas": {z: p[z] for z in visibles}}
