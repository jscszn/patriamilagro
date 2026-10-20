"""Grafo ponderado implementado a mano con LISTAS DE ADYACENCIA (sin librerías de grafos).

    adyacencia = {vértice: {vecino: peso}}

Se eligió la lista de adyacencia (y no una matriz) porque los grafos del juego son dispersos
(pocos vecinos por vértice), cambian durante la partida (se quitan cuentas y relaciones) y
casi todo lo que se les pide es "¿quiénes son los vecinos de X?", que aquí cuesta O(grado).

Lo usa core/mapa.py: el grafo NO dirigido del país, con zonas unidas por vías que tienen un
peligro (peso). La clase es genérica (también admite grafos dirigidos).

Operaciones: insertar y eliminar vértices y aristas, cambiar pesos, recorridos BFS (también por
olas) y DFS, distancia en saltos, camino con menos saltos (BFS), camino más barato (Dijkstra),
componentes conexas y serialización. `heapq` es solo la cola de prioridad de Dijkstra.
"""
from __future__ import annotations

import heapq
from collections import deque
from typing import Dict, Iterable, Iterator, List, Optional, Tuple

INFINITO = float("inf")


class Grafo:
    def __init__(self, dirigido: bool = False):
        self.dirigido = dirigido
        self.adyacencia: Dict[str, Dict[str, float]] = {}
        self.datos: Dict[str, dict] = {}            # atributos de cada vértice (nombre, posición...)

    # --- Vértices ----------------------------------------------------------------------------
    def agregar_vertice(self, v: str, **datos) -> None:
        self.adyacencia.setdefault(v, {})
        self.datos.setdefault(v, {}).update(datos)

    def eliminar_vertice(self, v: str) -> int:
        """Quita el vértice y todas las aristas que lo tocan. Devuelve cuántas aristas se fueron."""
        if v not in self.adyacencia:
            raise KeyError(v)
        quitadas = len(self.adyacencia.pop(v))
        self.datos.pop(v, None)
        for vecinos in self.adyacencia.values():      # aristas que llegaban a v
            if v in vecinos:
                del vecinos[v]
                if self.dirigido:
                    quitadas += 1
        return quitadas

    def __contains__(self, v: str) -> bool:
        return v in self.adyacencia

    def __len__(self) -> int:
        return len(self.adyacencia)

    def vertices(self) -> List[str]:
        return list(self.adyacencia)

    # --- Aristas -----------------------------------------------------------------------------
    def agregar_arista(self, a: str, b: str, peso: float = 1.0) -> None:
        self.agregar_vertice(a)
        self.agregar_vertice(b)
        self.adyacencia[a][b] = peso
        if not self.dirigido:
            self.adyacencia[b][a] = peso

    def eliminar_arista(self, a: str, b: str) -> bool:
        """Devuelve True si la arista existía."""
        existia = b in self.adyacencia.get(a, {})
        if existia:
            del self.adyacencia[a][b]
            if not self.dirigido:
                self.adyacencia[b].pop(a, None)
        return existia

    def hay_arista(self, a: str, b: str) -> bool:
        return b in self.adyacencia.get(a, {})

    def peso(self, a: str, b: str) -> float:
        return self.adyacencia[a][b]

    def cambiar_peso(self, a: str, b: str, peso: float) -> None:
        if not self.hay_arista(a, b):
            raise KeyError((a, b))
        self.adyacencia[a][b] = peso
        if not self.dirigido:
            self.adyacencia[b][a] = peso

    def vecinos(self, v: str) -> List[str]:
        """A quiénes llega una arista desde v."""
        return list(self.adyacencia.get(v, {}))

    def grado(self, v: str) -> int:
        return len(self.adyacencia.get(v, {}))

    def aristas(self) -> List[Tuple[str, str, float]]:
        """(a, b, peso). En un grafo no dirigido cada arista sale una sola vez."""
        vistas, lista = set(), []
        for a, vecinos in self.adyacencia.items():
            for b, peso in vecinos.items():
                if self.dirigido or (b, a) not in vistas:
                    vistas.add((a, b))
                    lista.append((a, b, peso))
        return lista

    # --- Recorridos --------------------------------------------------------------------------
    def bfs(self, origen: str) -> List[str]:
        """Recorrido en ANCHURA con una cola: primero los vecinos, luego los vecinos de estos."""
        return [v for ola in self.bfs_por_olas([origen]) for v in ola]

    def bfs_por_olas(self, origenes: Iterable[str]) -> List[List[str]]:
        """BFS que devuelve los vértices agrupados por distancia: la ola 0 son los orígenes, la
        ola 1 sus vecinos, etc. Así se ve hasta dónde llega la red de un jefe."""
        ola = [v for v in dict.fromkeys(origenes) if v in self.adyacencia]
        visitados = set(ola)
        olas = []
        while ola:
            olas.append(ola)
            siguiente = []
            for v in ola:
                for vecino in self.adyacencia[v]:
                    if vecino not in visitados:
                        visitados.add(vecino)
                        siguiente.append(vecino)
            ola = siguiente
        return olas

    def saltos(self, origen: str) -> Dict[str, int]:
        """Distancia en número de aristas desde `origen` a cada vértice alcanzable."""
        return {v: d for d, ola in enumerate(self.bfs_por_olas([origen])) for v in ola}

    def camino_con_menos_saltos(self, origen: str, destino: str) -> List[str]:
        """Camino con MENOS ARISTAS (no mira los pesos): BFS que anota de dónde llegó a cada
        vértice y, al encontrar el destino, reconstruye el camino hacia atrás. [] si no hay."""
        if origen not in self.adyacencia or destino not in self.adyacencia:
            return []
        previo: Dict[str, Optional[str]] = {origen: None}
        cola = deque([origen])
        while cola:
            v = cola.popleft()
            if v == destino:
                camino = []
                while v is not None:
                    camino.append(v)
                    v = previo[v]
                return camino[::-1]
            for vecino in self.adyacencia[v]:
                if vecino not in previo:
                    previo[vecino] = v
                    cola.append(vecino)
        return []

    def costo_de(self, camino: List[str]) -> float:
        """Suma de los pesos de las aristas de un camino."""
        return float(sum(self.adyacencia[a][b] for a, b in zip(camino, camino[1:])))

    def dfs(self, origen: str) -> Iterator[str]:
        """Recorrido en PROFUNDIDAD con una pila explícita."""
        visitados, pila = set(), [origen]
        while pila:
            v = pila.pop()
            if v in visitados or v not in self.adyacencia:
                continue
            visitados.add(v)
            yield v
            pila.extend(reversed(self.vecinos(v)))

    def componentes(self) -> List[List[str]]:
        """Grupos de vértices conectados entre sí (ignora la dirección de las aristas)."""
        simetrico = {v: set(vecinos) for v, vecinos in self.adyacencia.items()}
        for a, vecinos in self.adyacencia.items():
            for b in vecinos:
                simetrico[b].add(a)
        pendientes, grupos = set(simetrico), []
        for v in self.adyacencia:
            if v in pendientes:
                grupo, cola = [], deque([v])
                pendientes.discard(v)
                while cola:
                    actual = cola.popleft()
                    grupo.append(actual)
                    for vecino in sorted(simetrico[actual]):
                        if vecino in pendientes:
                            pendientes.discard(vecino)
                            cola.append(vecino)
                grupos.append(grupo)
        return grupos

    # --- Camino más barato -------------------------------------------------------------------
    def dijkstra(self, origen: str) -> Tuple[Dict[str, float], Dict[str, Optional[str]]]:
        """Costo mínimo desde `origen` a cada vértice y de dónde se llega (para armar el camino).
        Los pesos deben ser >= 0."""
        costo = {v: INFINITO for v in self.adyacencia}
        previo: Dict[str, Optional[str]] = {v: None for v in self.adyacencia}
        costo[origen] = 0.0
        cola = [(0.0, origen)]
        while cola:
            acumulado, v = heapq.heappop(cola)
            if acumulado > costo[v]:
                continue                              # entrada vieja de la cola
            for vecino, peso in self.adyacencia[v].items():
                nuevo = acumulado + peso
                if nuevo < costo[vecino]:
                    costo[vecino], previo[vecino] = nuevo, v
                    heapq.heappush(cola, (nuevo, vecino))
        return costo, previo

    def camino_mas_barato(self, origen: str, destino: str) -> Tuple[float, List[str]]:
        """(costo, [origen, ..., destino]). Si no hay camino: (infinito, [])."""
        if origen not in self.adyacencia or destino not in self.adyacencia:
            return INFINITO, []
        costo, previo = self.dijkstra(origen)
        if costo[destino] == INFINITO:
            return INFINITO, []
        camino, v = [], destino
        while v is not None:                          # se arma de atrás hacia adelante
            camino.append(v)
            v = previo[v]
        return costo[destino], camino[::-1]

    # --- Serialización -----------------------------------------------------------------------
    def to_dict(self) -> dict:
        return {"dirigido": self.dirigido,
                "vertices": {v: dict(d) for v, d in self.datos.items()},
                "aristas": [[a, b, peso] for a, b, peso in self.aristas()]}

    @classmethod
    def from_dict(cls, d: dict) -> "Grafo":
        g = cls(d["dirigido"])
        for v, datos in d["vertices"].items():
            g.agregar_vertice(v, **datos)
        for a, b, peso in d["aristas"]:
            g.agregar_arista(a, b, peso)
        return g
