"""Mapa de Colombia con relieve, en pixel art, para dibujar encima el grafo del país.

- Contornos REALES de los 33 departamentos (assets/mapa/colombia.json, ver
  tools/simplificar_mapa.py), en proyección equirrectangular.
- Relieve: un modelo de elevación hecho a mano con las tres cordilleras, la Sierra Nevada de
  Santa Marta, la serranía de Perijá, la Macarena y los volcanes, con colores de atlas
  (verdes en las tierras bajas, ocres y cafés en la montaña, gris de páramo y nieve) y sombreado
  de relieve con luz del noroeste. Las tierras bajas toman el color de su región: selva
  amazónica, llano, Pacífico, Caribe y el desierto amarillo de La Guajira.
- Ríos principales, mar con aguas someras junto a la costa y países vecinos apagados.

Se pinta una vez por tamaño (unos 40 ms) y se guarda.
"""
from __future__ import annotations

import json
import math
import os
from typing import Dict, List, Sequence, Tuple

import numpy as np
import pygame

import settings

RUTA = os.path.join(settings.RUTA_ASSETS, "mapa", "colombia.json")
LON0, LON1, LAT0, LAT1 = -79.15, -66.75, -4.35, 12.55          # caja del mapa (grados)
COS = math.cos(math.radians(4.0))                                # corrección de la longitud

# --- Relieve (longitud, latitud) ------------------------------------------------------------------
# (puntos de la cresta, ancho en grados, altura en metros)
CORDILLERAS = [
    ([(-76.4, 1.8), (-75.6, 2.6), (-75.0, 3.5), (-74.3, 4.4), (-73.9, 5.0), (-73.3, 5.8), (-72.9, 6.6),
      (-72.6, 7.3), (-72.4, 7.9), (-71.6, 8.6), (-70.6, 9.2)], 0.55, 3000),                  # Oriental
    ([(-72.6, 8.4), (-72.9, 9.2), (-72.95, 10.0), (-72.7, 10.6), (-72.45, 11.0)], 0.25, 2600),  # Perijá
    ([(-77.6, 0.8), (-76.6, 1.7), (-76.1, 2.6), (-75.6, 3.9), (-75.3, 4.9), (-75.4, 5.6), (-75.5, 6.4),
      (-75.6, 7.2), (-75.3, 7.8), (-74.9, 8.3)], 0.32, 3300),                                # Central
    ([(-78.1, 0.6), (-77.4, 1.6), (-77.0, 2.4), (-76.6, 3.4), (-76.3, 4.5), (-76.1, 5.4), (-76.0, 6.4),
      (-76.1, 7.2), (-75.9, 7.7)], 0.24, 2500),                                              # Occidental
    ([(-77.4, 4.6), (-77.4, 6.0), (-77.6, 7.0)], 0.12, 800),                                # Baudó
    ([(-78.6, -1.0), (-78.3, 0.2), (-77.8, 0.9)], 0.35, 3500),                              # Andes de Ecuador
]
CUMBRES = [  # (lon, lat, radio en grados, altura): nevados, volcanes y macizos
    (-73.75, 10.85, 0.42, 5600),    # Sierra Nevada de Santa Marta
    (-72.30, 6.45, 0.22, 2600),     # Sierra Nevada del Cocuy
    (-75.32, 4.89, 0.16, 2200),     # Nevado del Ruiz
    (-76.03, 2.93, 0.16, 2200),     # Nevado del Huila
    (-77.36, 1.22, 0.14, 1600),     # Galeras
    (-73.85, 2.75, 0.22, 1500),     # Serranía de la Macarena
    (-75.20, 9.60, 0.25, 500),      # Montes de María
    (-74.10, 4.65, 0.30, 600),      # altiplano cundiboyacense
]
RIOS = [
    [(-76.4, 1.9), (-75.9, 2.4), (-75.3, 3.2), (-74.85, 4.2), (-74.7, 5.2), (-74.55, 6.0), (-73.9, 7.05),
     (-73.85, 8.0), (-74.3, 8.8), (-74.65, 9.25), (-74.8, 10.0), (-74.85, 11.05)],          # Magdalena
    [(-76.6, 2.4), (-76.4, 3.5), (-75.9, 4.8), (-75.75, 5.6), (-75.65, 6.6), (-75.3, 7.7), (-74.9, 8.4),
     (-74.6, 9.1)],                                                                         # Cauca
    [(-73.6, 4.1), (-72.6, 4.3), (-71.4, 4.9), (-70.2, 5.6), (-69.0, 6.0), (-67.5, 6.2)],  # Meta
    [(-67.5, 6.25), (-67.65, 5.4), (-67.8, 4.4), (-67.7, 3.6), (-67.5, 2.4)],             # Orinoco
    [(-73.6, 2.6), (-72.6, 2.55), (-71.5, 2.8), (-70.3, 3.2), (-69.2, 3.7), (-67.9, 4.0)],  # Guaviare
    [(-71.5, 4.3), (-70.3, 4.6), (-69.0, 4.9), (-67.8, 4.9)],                              # Vichada
    [(-76.0, 1.4), (-74.5, 0.7), (-73.0, 0.0), (-71.5, -0.6), (-69.9, -1.1), (-69.4, -1.3)],  # Caquetá
    [(-76.5, 0.5), (-75.3, -0.1), (-73.8, -1.2), (-72.6, -2.4), (-71.0, -2.4), (-69.95, -2.5)],  # Putumayo
    [(-70.9, -3.8), (-69.95, -4.2)],                                                       # Amazonas
    [(-76.6, 5.4), (-76.65, 6.5), (-76.9, 7.3), (-77.05, 8.0)],                            # Atrato
    [(-76.3, 7.6), (-75.9, 8.7), (-75.95, 9.4)],                                           # Sinú
    [(-72.3, 7.0), (-71.0, 7.05), (-70.0, 6.95)],                                          # Arauca
]
# Mares (lo que no es Colombia ni mar es un país vecino). Pueden pisar la costa: Colombia va encima.
MARES = [
    [(-95, 25), (-55, 25), (-55, 10.65), (-68.3, 10.5), (-69.6, 11.5), (-70.2, 12.2), (-70.9, 11.3),
     (-71.5, 11.0), (-71.9, 11.6), (-72.9, 11.0), (-75.5, 9.5), (-77.3, 8.5), (-77.4, 8.7), (-79.5, 9.6),
     (-81.0, 8.9), (-82.3, 9.3), (-83.3, 10.4), (-83.6, 11.8), (-83.2, 14.9), (-85.0, 16.0), (-88.5, 16.0),
     (-95, 18)],                                                                            # Caribe
    [(-95, 10), (-85.8, 10.3), (-84.5, 9.3), (-83.0, 8.2), (-81.5, 7.5), (-80.5, 7.2), (-80.0, 7.6),
     (-79.5, 8.9), (-78.7, 8.4), (-78.2, 8.1), (-77.9, 7.3), (-77.5, 6.0), (-77.3, 4.0), (-77.5, 2.6),
     (-78.4, 1.7), (-78.85, 1.35), (-80.1, 0.8), (-80.5, -0.5), (-81.0, -2.2), (-80.3, -3.5), (-81.3, -5.0),
     (-81.0, -7.0), (-95, -12)],                                                            # Pacífico
    [(-71.98, 12.4), (-70.25, 12.3), (-70.0, 11.75), (-70.6, 11.25), (-71.35, 10.95), (-71.5, 10.4),
     (-71.75, 10.4), (-71.7, 11.0), (-71.98, 11.6)],                                       # golfo de Venezuela
]
LAGOS = [(-71.6, 9.8, 0.45, 0.65)]                                                        # Maracaibo (lon, lat, rx, ry)

# Región de cada departamento: el color de sus tierras bajas
REGION = {
    "AMAZONAS": "amazonia", "CAQUETA": "amazonia", "PUTUMAYO": "amazonia", "GUAVIARE": "amazonia",
    "VAUPES": "amazonia", "GUAINIA": "amazonia",
    "META": "llano", "CASANARE": "llano", "ARAUCA": "llano", "VICHADA": "llano",
    "CHOCO": "pacifico", "NARIÑO": "pacifico", "CAUCA": "pacifico", "VALLE DEL CAUCA": "pacifico",
    "ATLANTICO": "caribe", "BOLIVAR": "caribe", "SUCRE": "caribe", "CORDOBA": "caribe",
    "MAGDALENA": "caribe", "CESAR": "caribe", "LA GUAJIRA": "desierto",
}
TIERRA_BAJA = {"amazonia": (34, 122, 58), "llano": (132, 180, 76), "pacifico": (40, 132, 74),
               "caribe": (120, 176, 84), "desierto": (232, 204, 116), "andina": (100, 160, 76)}
# Rampa de altura (metros, color): de piedemonte a nieve
RAMPA = [(250, None), (700, (156, 180, 88)), (1300, (200, 184, 104)), (2000, (196, 148, 82)),
         (2800, (168, 112, 66)), (3600, (138, 88, 60)), (4400, (178, 168, 160)), (99999, (248, 248, 252))]
# Fuera de Colombia todo va apagado, para que el país se lea solo: mar oscuro, vecinos en pizarra
MAR, MAR_SOMERO = (24, 46, 88), (40, 76, 126)
VECINO, VECINO_ALTO = (62, 64, 74), (76, 78, 88)
CONTORNO, SOMBRA = (240, 228, 184), (10, 12, 22)                 # el borde del país y su sombra
RIO = (64, 130, 214)


def _datos():
    with open(RUTA, encoding="utf-8") as f:
        return json.load(f)["departamentos"]


class Proyeccion:
    """Grados -> píxeles del mapa. `caja` = (lon0, lon1, lat0, lat1) que se quiere ver; sin caja,
    el país entero cabe en ancho x alto. Con `escala` fija (px por grado), la caja se centra y el
    mapa mide exactamente ancho x alto (zoom sobre una región)."""

    def __init__(self, ancho: int, alto: int, caja=None, escala: float = None):
        lon0, lon1, lat0, lat1 = caja or (LON0, LON1, LAT0, LAT1)
        if escala is None:
            self.escala = min(ancho / ((lon1 - lon0) * COS), alto / (lat1 - lat0))
            self.ancho = int(round((lon1 - lon0) * COS * self.escala))
            self.alto = int(round((lat1 - lat0) * self.escala))
            self.lon0, self.lat1 = lon0, lat1
        else:
            self.escala, self.ancho, self.alto = escala, ancho, alto
            centro_lon, centro_lat = (lon0 + lon1) / 2, (lat0 + lat1) / 2
            self.lon0 = centro_lon - ancho / 2 / escala / COS
            self.lat1 = centro_lat + alto / 2 / escala

    def a_pixel(self, lon: float, lat: float) -> Tuple[float, float]:
        return (lon - self.lon0) * COS * self.escala, (self.lat1 - lat) * self.escala

    def rejilla(self):
        """Longitud y latitud del centro de cada píxel (arreglos de ancho x alto)."""
        xs = (np.arange(self.ancho) + 0.5) / self.escala / COS + self.lon0
        ys = self.lat1 - (np.arange(self.alto) + 0.5) / self.escala
        return np.meshgrid(xs, ys, indexing="ij")


def _distancia_a_linea(lon, lat, puntos: Sequence[Tuple[float, float]]):
    """Distancia (en grados) de cada píxel a una polilínea."""
    mejor = np.full(lon.shape, 1e9)
    for (x1, y1), (x2, y2) in zip(puntos, puntos[1:]):
        dx, dy = (x2 - x1) * COS, y2 - y1
        px, py = (lon - x1) * COS, lat - y1
        t = np.clip((px * dx + py * dy) / (dx * dx + dy * dy), 0, 1)
        mejor = np.minimum(mejor, np.hypot(px - t * dx, py - t * dy))
    return mejor


def elevacion(lon, lat):
    """Modelo de elevación (metros): crestas con perfil gaussiano más cumbres sueltas."""
    e = np.zeros(lon.shape)
    for puntos, ancho, altura in CORDILLERAS:
        d = _distancia_a_linea(lon, lat, puntos)
        e = np.maximum(e, altura * np.exp(-(d / ancho) ** 2) * (1 + 0.12 * np.sin(lon * 9) * np.cos(lat * 7)))
    for x, y, radio, altura in CUMBRES:
        d = np.hypot((lon - x) * COS, lat - y)
        e = e + altura * np.exp(-(d / radio) ** 2)
    return e


def _poligono(sup, color, anillo, proy: Proyeccion) -> None:
    puntos = [proy.a_pixel(x, y) for x, y in anillo]
    if len(puntos) >= 3:
        pygame.draw.polygon(sup, color, puntos)


_CACHE: Dict[Tuple[int, int], "MapaColombia"] = {}


class MapaColombia:
    def __init__(self, ancho: int, alto: int, caja=None, escala: float = None):
        self.proy = Proyeccion(ancho, alto, caja, escala)
        p = self.proy
        departamentos = _datos()
        self.nombres = [d["nombre"] for d in departamentos]
        # 1) Qué departamento hay en cada píxel (0 = fuera de Colombia) y qué es mar
        indice = pygame.Surface((p.ancho, p.alto))
        indice.fill((0, 0, 0))
        for i, d in enumerate(departamentos):
            for anillo in d["anillos"]:
                _poligono(indice, (i + 1, 0, 0), anillo, p)
        self.depto = pygame.surfarray.array3d(indice)[:, :, 0].astype(np.int32)      # (ancho, alto)
        mar = pygame.Surface((p.ancho, p.alto))
        mar.fill((0, 0, 0))
        for anillo in MARES:
            _poligono(mar, (255, 0, 0), anillo, p)
        for x, y, rx, ry in LAGOS:
            cx, cy = p.a_pixel(x, y)
            pygame.draw.ellipse(mar, (255, 0, 0), (cx - rx * p.escala, cy - ry * p.escala,
                                                   rx * 2 * p.escala, ry * 2 * p.escala))
        es_mar = (pygame.surfarray.array3d(mar)[:, :, 0] > 0) & (self.depto == 0)
        colombia = self.depto > 0
        # 2) Relieve y color
        lon, lat = p.rejilla()
        e = elevacion(lon, lat)
        region = np.full(self.depto.shape, "andina", dtype=object)
        for i, nombre in enumerate(self.nombres):
            region[self.depto == i + 1] = REGION.get(nombre, "andina")
        guajira_alta = (lat > 11.1) & (lon > -72.95)                              # el norte de La Guajira
        bayer = np.array([[0, 2], [3, 1]])[np.arange(p.ancho)[:, None] % 2, np.arange(p.alto)[None, :] % 2]
        rgb = np.zeros(self.depto.shape + (3,), np.float32)
        for nombre, color in TIERRA_BAJA.items():
            rgb[region == nombre] = color
        rgb[colombia & guajira_alta] = (240, 214, 120)
        rgb[colombia & (region == "desierto") & ~guajira_alta] = (196, 190, 104)   # sur de La Guajira: más verde
        if "VICHADA" in self.nombres:                                             # selva de galería del Vichada
            vichada = self.depto == self.nombres.index("VICHADA") + 1
            limite = 4.35 + 0.3 * np.sin(lon * 2.3) + 0.15 * np.sin(lon * 7.1 + lat * 3)
            rgb[vichada & (lat < limite - 0.2)] = (62, 146, 62)
            rgb[vichada & (lat >= limite - 0.2) & (lat < limite + 0.15) & (bayer % 2 == 0)] = (62, 146, 62)
        # Tramado ordenado (Bayer 2x2) en los saltos de altura: bordes de pixel art, no degradados
        e_tramada = e + (bayer - 1.5) * 90
        for (techo, _), (_, color) in zip(RAMPA, RAMPA[1:]):
            rgb[colombia & (e_tramada >= techo)] = color
        # Textura de cerca (con zoom): copas de árboles en la selva y matas en el llano
        if p.escala >= 14:
            ruido = (np.sin(lon * 91.7 + lat * 53.3) * 43758.5453) % 1.0
            selvatico = colombia & (e < 900) & np.isin(region, ["amazonia", "pacifico"])
            rgb[selvatico & (ruido < 0.12)] *= 0.8
            rgb[selvatico & (ruido > 0.93)] *= 1.15
            llanero = colombia & (e < 600) & (region == "llano")
            rgb[llanero & (ruido < 0.06)] *= 0.86
        # Sombreado de relieve (luz del noroeste); la pendiente se mide por grado, no por píxel
        gx, gy = np.gradient(e)
        k = 9.75 / p.escala
        gx, gy = gx * k, gy * k
        luz = np.clip(1.0 + (-gx * 0.6 - gy * 0.6) / 260.0, 0.72, 1.28)
        rgb[colombia] *= luz[colombia, None]
        # Vecinos: apagados, con un poco del mismo relieve
        vecino = ~colombia & ~es_mar
        rgb[vecino] = VECINO
        rgb[vecino & (e_tramada > 2200)] = VECINO_ALTO                            # sus Andes, apenas marcados
        # Mar: profundo, y somero pegado a la costa
        rgb[es_mar] = MAR
        tierra = ~es_mar
        costa = es_mar & (np.roll(tierra, 1, 0) | np.roll(tierra, -1, 0) | np.roll(tierra, 1, 1) | np.roll(tierra, -1, 1))
        rgb[costa] = MAR_SOMERO
        olas = es_mar & ~costa & (((np.arange(p.ancho)[:, None] * 7 + np.arange(p.alto)[None, :] * 3) % 23) == 0)
        rgb[olas] = (36, 64, 110)
        # Cuadrícula de meridianos y paralelos cada 2 grados, solo afuera (mapa de campaña)
        paso = 2.0
        cerca_lon = np.abs(((lon + 1000) % paso) - paso / 2) > paso / 2 - 0.5 / p.escala
        cerca_lat = np.abs(((lat + 1000) % paso) - paso / 2) > paso / 2 - 0.5 / p.escala
        rejilla = ~colombia & (cerca_lon | cerca_lat) & (bayer % 2 == 0)
        rgb[rejilla] *= 1.18
        # Bordes: líneas suaves entre departamentos, más marcadas en la frontera del país
        otro = np.zeros(self.depto.shape, bool)
        for eje, paso in ((0, 1), (1, 1)):
            vecino_depto = np.roll(self.depto, paso, eje)
            otro |= colombia & (vecino_depto > 0) & (vecino_depto != self.depto)
        rgb[otro] *= 0.86
        # El país, delimitado: contorno claro por dentro y sombra por fuera (abajo a la derecha)
        afuera = ~colombia
        borde = colombia & (np.roll(afuera, 1, 0) | np.roll(afuera, -1, 0) | np.roll(afuera, 1, 1) | np.roll(afuera, -1, 1))
        rgb[borde] = CONTORNO
        sombra = afuera & (np.roll(colombia, 1, 0) | np.roll(colombia, 1, 1)) & ~(np.roll(colombia, -1, 0) | np.roll(colombia, -1, 1))
        rgb[sombra] = SOMBRA
        self.imagen = pygame.Surface((p.ancho, p.alto))
        pygame.surfarray.blit_array(self.imagen, np.clip(rgb, 0, 255).astype(np.uint8))
        # 3) Ríos
        for i, rio in enumerate(RIOS):
            puntos = [p.a_pixel(x, y) for x, y in rio]
            grueso = 2 if p.escala >= 18 and i in (0, 2, 3) else 1          # Magdalena, Meta, Orinoco
            pygame.draw.lines(self.imagen, RIO, False, puntos, grueso)
        self.colombia = colombia
        self._contornos: Dict[str, pygame.Surface] = {}

    def contorno(self, departamento: str, color) -> pygame.Surface:
        """Borde de un departamento (para resaltar la zona de un jefe)."""
        clave = (departamento, tuple(color))
        if clave not in self._contornos:
            i = self.nombres.index(departamento) + 1
            dentro = self.depto == i
            borde = dentro & ~(np.roll(dentro, 1, 0) & np.roll(dentro, -1, 0) & np.roll(dentro, 1, 1) & np.roll(dentro, -1, 1))
            sup = pygame.Surface(self.imagen.get_size(), pygame.SRCALPHA)
            alfa = pygame.surfarray.pixels_alpha(sup)
            alfa[borde] = 255
            del alfa
            sup.fill((*color, 0), special_flags=pygame.BLEND_RGBA_MAX)
            self._contornos[clave] = sup
        return self._contornos[clave]


def mapa(ancho: int, alto: int, caja=None, escala: float = None) -> MapaColombia:
    """El mapa para un área de ancho x alto: el país entero o, con caja y escala, una región
    ampliada. Se pinta una vez por encuadre y se guarda."""
    clave = (ancho, alto, caja, escala)
    if clave not in _CACHE:
        if len(_CACHE) > 24:
            _CACHE.clear()
        _CACHE[clave] = MapaColombia(ancho, alto, caja, escala)
    return _CACHE[clave]


def encuadre(puntos, ancho: int, alto: int, margen_x: float = 30, margen_y: float = 14,
             escala_max: float = 34.0):
    """Caja y escala para ver `puntos` (lon, lat) con zoom dentro de ancho x alto, dejando
    margen para los nombres. Se redondea para que encuadres casi iguales usen el mismo mapa."""
    lons = [p[0] for p in puntos]
    lats = [p[1] for p in puntos]
    dlon = max(0.5, max(lons) - min(lons))
    dlat = max(0.5, max(lats) - min(lats))
    escala = min((ancho - 2 * margen_x) / (dlon * COS), (alto - 2 * margen_y) / dlat, escala_max)
    escala = max(6.0, float(int(escala)))
    centro = (round((max(lons) + min(lons)) / 2, 1), round((max(lats) + min(lats)) / 2, 1))
    caja = (centro[0] - 0.01, centro[0] + 0.01, centro[1] - 0.01, centro[1] + 0.01)
    return caja, escala
