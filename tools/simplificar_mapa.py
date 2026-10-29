"""Genera assets/mapa/colombia.json: los contornos de los departamentos de Colombia, simplificados.

Fuente: GeoJSON de los departamentos de Colombia publicado por John Alexis Guerra Gómez
(https://gist.github.com/john-guerra/43c7656821069d00dcbc), hecho con datos del DANE (marco
geoestadístico nacional). Se simplifica con Douglas-Peucker (tolerancia en grados) y se
redondea a 3 decimales: el mapa del juego mide unos 120 px de ancho, así que con esto sobra.

Uso:
    python tools/simplificar_mapa.py RUTA/Colombia.geo.json [--tolerancia 0.02]

El archivo resultante es lo único que usa el juego (render/mapa_colombia.py).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import List, Sequence, Tuple

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SALIDA = os.path.join(RAIZ, "assets", "mapa", "colombia.json")
Punto = Tuple[float, float]


def _distancia(p: Punto, a: Punto, b: Punto) -> float:
    (x, y), (x1, y1), (x2, y2) = p, a, b
    dx, dy = x2 - x1, y2 - y1
    if dx == dy == 0:
        return ((x - x1) ** 2 + (y - y1) ** 2) ** 0.5
    t = max(0.0, min(1.0, ((x - x1) * dx + (y - y1) * dy) / (dx * dx + dy * dy)))
    return ((x - x1 - t * dx) ** 2 + (y - y1 - t * dy) ** 2) ** 0.5


def douglas_peucker(puntos: Sequence[Punto], tolerancia: float) -> List[Punto]:
    """Simplificación clásica, sin recursión (una pila de tramos)."""
    if len(puntos) < 3:
        return list(puntos)
    conservar = [False] * len(puntos)
    conservar[0] = conservar[-1] = True
    pila = [(0, len(puntos) - 1)]
    while pila:
        i, j = pila.pop()
        mejor, indice = 0.0, -1
        for k in range(i + 1, j):
            d = _distancia(puntos[k], puntos[i], puntos[j])
            if d > mejor:
                mejor, indice = d, k
        if mejor > tolerancia:
            conservar[indice] = True
            pila += [(i, indice), (indice, j)]
    return [p for p, c in zip(puntos, conservar) if c]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("geojson")
    parser.add_argument("--tolerancia", type=float, default=0.02)
    args = parser.parse_args()
    with open(args.geojson, encoding="utf-8") as f:
        datos = json.load(f)
    departamentos = []
    for rasgo in datos["features"]:
        nombre = rasgo["properties"]["NOMBRE_DPT"]
        geo = rasgo["geometry"]
        poligonos = geo["coordinates"] if geo["type"] == "MultiPolygon" else [geo["coordinates"]]
        anillos = []
        for poligono in poligonos:
            exterior = [tuple(c[:2]) for c in poligono[0]]
            simple = douglas_peucker(exterior, args.tolerancia)
            if len(simple) >= 4:
                anillos.append([[round(x, 3), round(y, 3)] for x, y in simple])
        if anillos:
            departamentos.append({"nombre": nombre, "anillos": anillos})
    os.makedirs(os.path.dirname(SALIDA), exist_ok=True)
    with open(SALIDA, "w", encoding="utf-8") as f:
        json.dump({"fuente": "DANE vía gist john-guerra/43c7656821069d00dcbc", "tolerancia": args.tolerancia,
                   "departamentos": departamentos}, f, ensure_ascii=False, separators=(",", ":"))
    puntos = sum(len(a) for d in departamentos for a in d["anillos"])
    print(f"{len(departamentos)} departamentos, {puntos} puntos -> {SALIDA} ({os.path.getsize(SALIDA) // 1024} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
