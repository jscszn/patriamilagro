"""Dibujo del árbol de decisiones: pantalla final y captura de evidencia para la sustentación.

Distribución: las 27 hojas se reparten de izquierda a derecha en el orden del PREORDEN
(capturar, extraditar, liberar) y cada nodo interno se centra sobre sus hijos. Cada nivel
del árbol es una fila. Las hojas se colorean según el final al que llevan.
"""
from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Tuple

import pygame

import settings
from core.decision_tree import ArbolDecisiones, Nodo, final_de
from render.texto import dibujar_texto

C = settings.COLORES
LETRA = {"capturar": "C", "extraditar": "E", "liberar": "L"}
COLOR_FINAL = {
    "cuestionado": (220, 64, 64),
    "mano_dura": (252, 152, 56),
    "diplomatico": (60, 188, 252),
    "del_pueblo": (248, 216, 32),
    "equilibrista": (180, 130, 240),
}
NOMBRE_CORTO = {"cuestionado": "CUESTIONADO", "mano_dura": "MANO DURA", "diplomatico": "DIPLOMÁTICO",
                "del_pueblo": "DEL PUEBLO", "equilibrista": "EQUILIBRISTA"}
GRIS_ARISTA = (70, 74, 90)


def arbol_completo(arbol: ArbolDecisiones) -> ArbolDecisiones:
    """Copia del árbol de la partida con los 40 nodos posibles (la partida no se modifica).
    La copia conserva el camino recorrido, así que su nodo actual es la hoja elegida."""
    copia = ArbolDecisiones.from_dict(arbol.to_dict())
    copia.construir_completo()
    return copia


def posiciones(arbol: ArbolDecisiones, area: pygame.Rect) -> Dict[int, Tuple[float, float]]:
    """{id(nodo): (x, y)}. Hojas equiespaciadas en preorden; padres centrados sobre sus hijos."""
    nodos = list(arbol.preorden())
    hojas = [n for n in nodos if n.es_hoja]
    paso = area.w / max(1, len(hojas))
    filas = max(n.nivel for n in nodos) or 1
    pos: Dict[int, Tuple[float, float]] = {}
    for i, hoja in enumerate(hojas):
        pos[id(hoja)] = (area.x + paso * (i + 0.5), area.y + area.h * hoja.nivel / filas)
    for nivel in range(filas - 1, -1, -1):
        for n in nodos:
            if n.nivel == nivel and not n.es_hoja:
                xs = [pos[id(h)][0] for h in n.hijos.values()]
                pos[id(n)] = (sum(xs) / len(xs), area.y + area.h * nivel / filas)
    return pos


def ids_ruta(arbol: ArbolDecisiones) -> set:
    """ids de los nodos de la ruta elegida (de la raíz a la hoja actual)."""
    ruta, nodo = set(), arbol.actual
    while nodo is not None:
        ruta.add(id(nodo))
        nodo = nodo.padre
    return ruta


def dibujar_arbol(sup: pygame.Surface, arbol: ArbolDecisiones, area: pygame.Rect, ruta: set,
                  visitados: Iterable[int] = (), actual: Optional[int] = None, tiempo: float = 0.0,
                  letras: bool = True) -> None:
    """Aristas, nodos y letras. ruta: se resalta en amarillo. visitados/actual: animación de un
    recorrido (los visitados en cian, el actual parpadea en blanco)."""
    pos = posiciones(arbol, area)
    visitados = set(visitados)
    nodos = list(arbol.preorden())
    # 1) Aristas (primero las grises para que la ruta quede encima)
    for capa in ("normal", "visitada", "ruta"):
        for n in nodos:
            for hijo in n.hijos.values():
                en_ruta = id(n) in ruta and id(hijo) in ruta
                visitada = id(hijo) in visitados
                tipo = "ruta" if en_ruta else ("visitada" if visitada else "normal")
                if tipo != capa:
                    continue
                color, grosor = {"ruta": (C["amarillo"], 2), "visitada": (C["cian"], 1),
                                 "normal": (GRIS_ARISTA, 1)}[tipo]
                pygame.draw.line(sup, color, pos[id(n)], pos[id(hijo)], grosor)
    # 2) Nodos
    for n in nodos:
        x, y = (int(round(v)) for v in pos[id(n)])
        if n.es_hoja:
            color = COLOR_FINAL[final_de(n).clave]
            if id(n) in ruta:
                pygame.draw.rect(sup, C["blanco"], (x - 4, y - 4, 9, 9))
            pygame.draw.rect(sup, color, (x - 2, y - 2, 5, 5))
        else:
            radio = 4 if n.es_raiz else 3
            relleno = C["amarillo"] if id(n) in ruta else (110, 114, 130)
            pygame.draw.circle(sup, relleno, (x, y), radio)
            pygame.draw.circle(sup, C["negro"], (x, y), radio, 1)
        if id(n) in visitados:
            pygame.draw.circle(sup, C["cian"], (x, y), 5, 1)
        if actual == id(n) and int(tiempo * 8) % 2 == 0:
            pygame.draw.circle(sup, C["blanco"], (x, y), 7, 1)
        # 3) Letra de la decisión que lleva a este nodo
        if letras and n.decision:
            color_letra = C["amarillo"] if id(n) in ruta else C["gris"]
            if n.es_hoja:
                dibujar_texto(sup, LETRA[n.decision], (x - 2, y + 4), color_letra, sombra=False)
            else:
                dibujar_texto(sup, LETRA[n.decision], (x - 13, y - 5), color_letra, sombra=False)   # fuera del aro


def dibujar_leyenda(sup: pygame.Surface, x: int, y: int, final_elegido: str = None) -> None:
    """Color de cada final, en dos filas."""
    for i, (clave, color) in enumerate(COLOR_FINAL.items()):
        cx, cy = x + (i % 3) * 82, y + (i // 3) * 11
        pygame.draw.rect(sup, color, (cx, cy + 1, 6, 6))
        texto_color = C["blanco"] if clave == final_elegido else C["gris"]
        dibujar_texto(sup, NOMBRE_CORTO[clave], (cx + 9, cy - 1), texto_color, sombra=False)


def camino_texto(nodo: Nodo) -> str:
    camino = nodo.camino()
    return " > ".join(LETRA[d] for d in camino) if camino else "RAÍZ"


def secuencia(arbol: ArbolDecisiones, modo: str) -> List[Nodo]:
    """Orden en que se visitan los nodos en cada modo de la pantalla del árbol."""
    if modo == "preorden":
        return list(arbol.preorden())
    if modo == "bfs":
        return arbol.bfs()
    if modo == "hoja_raiz":                         # lo que hace camino(): subir por los padres
        nodos, n = [], arbol.actual
        while n is not None:
            nodos.append(n)
            n = n.padre
        return nodos
    return []
