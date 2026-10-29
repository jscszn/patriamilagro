"""Grafo del país: las zonas de Colombia donde ocurre la historia y las vías que las unen.

Vértices = zonas (con su latitud y longitud reales). Aristas = vías, con un peso = PELIGRO de
la vía (retenes, emboscadas). Es un grafo no dirigido y ponderado (core/grafo.py). Es el único
grafo del juego, y se dibuja sobre el mapa de Colombia (render/mapa_colombia.py).

El recorrido del presidente cruza el país de sur a norte:
    BOGOTÁ (el palacio) -> la selva del VICHADA (nivel 1) -> MEDELLÍN (nivel 2) -> LA GUAJIRA (nivel 3)

Qué resuelve:
  1. LA RUTA DEL PRESIDENTE. Antes de cada nivel hay que llegar de donde está (el palacio al
     empezar; después, la zona del jefe anterior) a la zona del jefe, y el grafo ofrece dos
     caminos calculados con dos algoritmos distintos:
       - RUTA SEGURA: la de menor peligro total (Dijkstra sobre los pesos).
       - RUTA CORTA:  la de menos tramos (BFS, que no mira los pesos).
     El jugador elige y eso cambia el nivel: una ruta peligrosa trae más refuerzos enemigos; una
     ruta larga hace que el presidente llegue tarde y le cuesta opinión del pueblo.
  2. LOS DAÑOS DE CADA JEFE (BFS por olas): las zonas a 1 y 2 saltos de la zona de un jefe son
     las que alcanza su red. Un jefe que quedó LIBRE sigue operando: suma refuerzos a los
     niveles cuya zona esté a 2 saltos o menos.
  3. Se conecta con el ÁRBOL de decisiones: cada decisión cambia los pesos de las vías (capturar
     pacifica la zona, liberar la empeora, extraditar provoca represalias en otra vía).

El azar: al empezar cada partida aparecen retenes ilegales en vías elegidas al azar.
"""
from __future__ import annotations

import math
import random
from typing import Dict, List, Tuple

from core.decision_tree import EXTRADITAR, LIBERAR
from core.grafo import Grafo

PALACIO = "capital"
# zona: (nombre, nombre corto para el mapa, (longitud, latitud)). Posiciones reales; en el mapa
# ninguna vía cruza otra y, en todas las parejas de rutas segura / corta que salen al jugar, las
# dos se abren al menos 15 grados al separarse y al juntarse (tests/test_grafos.py).
ZONAS: Dict[str, Tuple[str, str, Tuple[float, float]]] = {
    "capital": ("BOGOTÁ", "BOGOTÁ", (-74.08, 4.60)),                # Casa de Nariño
    "llanos": ("EL META", "META", (-73.00, 3.00)),
    "selva": ("EL VICHADA", "VICHADA", (-69.50, 3.50)),             # la selva de La Vorágine
    "casanare": ("CASANARE", "CASANARE", (-72.40, 5.35)),
    "puerto": ("BARRANCABERMEJA", "BARRANCA", (-73.85, 7.07)),      # puerto petrolero del Magdalena
    "ciudad": ("MEDELLÍN", "MEDELLÍN", (-75.57, 6.25)),
    "caribe": ("CARTAGENA", "CARTAGENA", (-75.51, 10.39)),
    "sierra": ("SANTA MARTA", "SANTA MARTA", (-74.20, 11.24)),
    "frontera": ("LA GUAJIRA", "GUAJIRA", (-72.24, 11.38)),          # Maicao, la raya con Venezuela
}
# (zona, zona, peligro inicial de la vía). Las vías DIRECTAS son cortas pero peligrosas: por
# eso la ruta corta (BFS) y la ruta segura (Dijkstra) no coinciden en ningún nivel.
VIAS = [
    ("capital", "llanos", 1), ("llanos", "selva", 2), ("capital", "selva", 6),
    ("capital", "casanare", 2), ("casanare", "selva", 3), ("casanare", "puerto", 2),
    ("capital", "puerto", 3), ("capital", "ciudad", 5), ("puerto", "ciudad", 2),
    ("ciudad", "caribe", 3), ("caribe", "puerto", 3), ("caribe", "sierra", 2),
    ("sierra", "frontera", 2), ("puerto", "sierra", 4), ("puerto", "frontera", 8),
]
ZONA_NIVEL = {1: "selva", 2: "ciudad", 3: "frontera"}
# De dónde sale el presidente hacia cada nivel: del palacio y luego de donde venció al jefe anterior
ORIGEN_NIVEL = {1: PALACIO, 2: "selva", 3: "ciudad"}
SEGURA, CORTA = "segura", "corta"
NOMBRE_RUTA = {SEGURA: "RUTA SEGURA", CORTA: "RUTA CORTA"}
REFUERZOS_MAXIMOS = {1: 2, 2: 2, 3: 3}    # tope de refuerzos extra (con 1 en el nivel 1, un retén
                                           # dejaba la ruta corta igual de "barata" que la segura)
PELIGRO_POR_REFUERZO = 2                   # cada 2 puntos de peligro extra de la ruta, 1 refuerzo
OPINION_POR_TRAMO = 3                      # puntos del pueblo que cuesta cada tramo de más
ALCANCE_JEFE = 2                           # un jefe libre afecta las zonas a 2 saltos o menos
RETENES = (1, 2)                           # retenes ilegales al azar al empezar: (mínimo, máximo)


class Mapa:
    def __init__(self, semilla: int = 0, con_retenes: bool = True):
        self.grafo = Grafo(dirigido=False)
        for zona, (nombre, corto, pos) in ZONAS.items():
            self.grafo.agregar_vertice(zona, nombre=nombre, corto=corto, pos=list(pos))
        for a, b, peligro in VIAS:
            self.grafo.agregar_arista(a, b, peligro)
        # Peligro de la ruta segura con el mapa "limpio": contra esto se mide el peligro extra
        self.costo_base = {n: self.grafo.camino_mas_barato(ORIGEN_NIVEL[n], z)[0] for n, z in ZONA_NIVEL.items()}
        self.jefes_libres: List[str] = []           # zonas cuyo jefe quedó libre
        self.retenes: List[List[str]] = []          # vías con retén ilegal (evento aleatorio)
        self.rng = random.Random(semilla * 7 + 3)
        if con_retenes:
            vias = [(a, b) for a, b, _ in self.grafo.aristas()]
            for a, b in self.rng.sample(vias, self.rng.randint(*RETENES)):
                self.grafo.cambiar_peso(a, b, self.grafo.peso(a, b) + self.rng.randint(1, 2))
                self.retenes.append([a, b])

    # --- Consultas ---------------------------------------------------------------------------
    def nombre(self, zona: str) -> str:
        return self.grafo.datos[zona]["nombre"]

    def corto(self, zona: str) -> str:
        """Nombre corto, el que se escribe sobre el mapa."""
        datos = self.grafo.datos[zona]
        return datos.get("corto", datos["nombre"])

    @staticmethod
    def origen(nivel: int) -> str:
        return ORIGEN_NIVEL.get(nivel, PALACIO)

    def ruta(self, nivel: int) -> Tuple[float, List[str]]:
        """Camino menos peligroso del origen a la zona del nivel (Dijkstra): (peligro, zonas)."""
        return self.grafo.camino_mas_barato(self.origen(nivel), ZONA_NIVEL[nivel])

    def influencia(self, nivel: int) -> List[List[str]]:
        """Zonas que sufren al jefe del nivel, por olas: [su zona], [a 1 salto], [a 2 saltos]."""
        return self.grafo.bfs_por_olas([ZONA_NIVEL[nivel]])[:ALCANCE_JEFE + 1]

    def jefes_cerca(self, nivel: int) -> List[str]:
        """Zonas de jefes libres a ALCANCE_JEFE saltos o menos de la zona del nivel."""
        saltos = self.grafo.saltos(ZONA_NIVEL[nivel])
        return [z for z in self.jefes_libres if saltos.get(z, 99) <= ALCANCE_JEFE]

    def refuerzos(self, nivel: int, peligro_ruta: float) -> int:
        """Refuerzos extra del nivel = lo que la ruta tiene de más peligrosa que la ruta segura
        del mapa limpio (1 por cada PELIGRO_POR_REFUERZO) + jefes libres operando cerca."""
        de_mas = max(0.0, peligro_ruta - self.costo_base[nivel])
        extra = math.ceil(de_mas / PELIGRO_POR_REFUERZO) + len(self.jefes_cerca(nivel))
        return min(REFUERZOS_MAXIMOS.get(nivel, 3), extra)

    def rutas(self, nivel: int) -> Dict[str, dict]:
        """Las rutas entre las que elige el jugador. Siempre está la SEGURA; la CORTA solo
        aparece si de verdad tiene menos tramos. De cada una:
            camino     zonas, del origen (palacio o jefe anterior) a la zona del jefe
            peligro    suma de los pesos de sus vías
            tramos     número de vías
            refuerzos  enemigos extra que trae al nivel
            opinion    cambio de opinión por llegar tarde (tramos de más respecto a la más corta)
        """
        destino = ZONA_NIVEL[nivel]
        _, segura = self.ruta(nivel)
        corta = self.grafo.camino_con_menos_saltos(self.origen(nivel), destino)
        caminos = {SEGURA: segura}
        if len(corta) < len(segura):
            caminos[CORTA] = corta
        menos_tramos = min(len(c) for c in caminos.values()) - 1
        opciones = {}
        for clave, camino in caminos.items():
            peligro = self.grafo.costo_de(camino)
            tramos = len(camino) - 1
            opciones[clave] = {"camino": list(camino), "peligro": int(peligro), "tramos": tramos,
                               "refuerzos": self.refuerzos(nivel, peligro),
                               "opinion": {"pueblo": -OPINION_POR_TRAMO * (tramos - menos_tramos)}}
        return opciones

    def peligro(self, nivel: int) -> int:
        """Refuerzos extra del nivel si se va por la ruta segura (valor por defecto)."""
        return self.rutas(nivel)[SEGURA]["refuerzos"]

    # --- Cambios por las decisiones del árbol --------------------------------------------------
    def aplicar_decision(self, nivel: int, decision: str) -> List[str]:
        """Cambia los pesos de las vías según lo que se hizo con el jefe del nivel.
        Devuelve frases cortas que describen qué cambió (para mostrarlas)."""
        zona = ZONA_NIVEL[nivel]
        cambios = []
        if decision == LIBERAR:
            self.jefes_libres.append(zona)
            for vecino in self.grafo.vecinos(zona):
                self.grafo.cambiar_peso(zona, vecino, self.grafo.peso(zona, vecino) + 2)
            cambios.append(f"LAS VÍAS DE {self.nombre(zona)} SON MÁS PELIGROSAS")
        else:
            for vecino in self.grafo.vecinos(zona):
                self.grafo.cambiar_peso(zona, vecino, max(1, self.grafo.peso(zona, vecino) - 1))
            cambios.append(f"{self.nombre(zona)} QUEDA MÁS SEGURA")
            if decision == EXTRADITAR:          # sus socios toman represalias en otra vía, al azar
                otras = [(a, b) for a, b, _ in self.grafo.aristas() if zona not in (a, b)]
                a, b = self.rng.choice(otras)
                self.grafo.cambiar_peso(a, b, self.grafo.peso(a, b) + 1)
                cambios.append(f"REPRESALIAS ENTRE {self.nombre(a)} Y {self.nombre(b)}")
        return cambios

    # --- Serialización -----------------------------------------------------------------------
    def to_dict(self, con_azar: bool = True) -> dict:
        """con_azar=False omite el estado del generador aleatorio: basta para dibujar y consultar
        (es lo que el servidor manda a los clientes)."""
        datos = {"grafo": self.grafo.to_dict(), "costo_base": {str(k): v for k, v in self.costo_base.items()},
                 "jefes_libres": list(self.jefes_libres), "retenes": [list(r) for r in self.retenes]}
        if con_azar:
            version, estado, gauss = self.rng.getstate()
            datos["rng"] = [version, list(estado), gauss]
        return datos

    @classmethod
    def from_dict(cls, d: dict) -> "Mapa":
        mapa = cls(con_retenes=False)
        mapa.grafo = Grafo.from_dict(d["grafo"])
        mapa.costo_base = {int(k): v for k, v in d["costo_base"].items()}
        mapa.jefes_libres = list(d["jefes_libres"])
        mapa.retenes = [list(r) for r in d["retenes"]]
        if "rng" in d:
            mapa.rng.setstate((d["rng"][0], tuple(d["rng"][1]), d["rng"][2]))
        return mapa
