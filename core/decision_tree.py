"""Árbol de decisiones de la partida (árbol n-ario implementado a mano).

Cada nodo es el estado del país después de una decisión:
  - la raíz (nivel 0) es el inicio, con opinión 50/50/50;
  - cada nodo tiene hasta 3 hijos, uno por decisión (capturar, extraditar, liberar);
  - las hojas están en el nivel 3: 3 x 3 x 3 = 27 caminos posibles.

Variante: árbol n-ario (n = 3) con puntero al padre y diccionario de hijos, que se construye
de forma PEREZOSA. Un nodo solo se inserta cuando el jugador toma esa decisión.

La opinión de un nodo = opinión del padre + efecto de la decisión, limitada a [0, 100].
El efecto depende de la decisión, del nivel y del camino previo (efectos combinados).
Además, la opinión de un nodo se puede AJUSTAR desde fuera (core/partida.py): por la ruta con que se
llegó al nivel o por revocar una decisión. El ajuste se guarda en el nodo y lo heredan sus hijos.

Operaciones: insertar (decidir), ELIMINAR un nodo con todo su subárbol (revocar una decisión),
ajustar, y los recorridos preorden, BFS y camino hoja -> raíz.
"""
from __future__ import annotations

from collections import deque
from typing import Callable, Dict, Iterator, List, Optional

CAPTURAR = "capturar"
EXTRADITAR = "extraditar"
LIBERAR = "liberar"
DECISIONES = (CAPTURAR, EXTRADITAR, LIBERAR)
CATEGORIAS = ("medios", "influencers", "pueblo")
NIVELES = 3
OPINION_INICIAL = {"medios": 50, "influencers": 50, "pueblo": 50}

# -----------------------------------------------------------------------------
# Efectos configurables
# -----------------------------------------------------------------------------
# Efecto base de cada decisión sobre cada categoría de opinión.
EFECTOS_BASE: Dict[str, Dict[str, int]] = {
    CAPTURAR:   {"medios": +6,  "influencers": +8,  "pueblo": +12},
    EXTRADITAR: {"medios": +12, "influencers": +4,  "pueblo": -4},
    LIBERAR:    {"medios": -12, "influencers": -6,  "pueblo": -14},
}

# Peso de cada nivel: las decisiones tardías pesan más (el país ya está mirando).
PESO_NIVEL: Dict[int, float] = {1: 1.0, 2: 1.25, 3: 1.5}

# Ajustes propios de cada (nivel, decisión), para que los niveles no sean iguales.
AJUSTES_NIVEL: Dict[tuple, Dict[str, int]] = {
    (1, LIBERAR):    {"influencers": +4},   # en la selva pocos se enteran
    (2, CAPTURAR):   {"medios": +4},        # captura en la ciudad: transmisión en vivo
    (2, EXTRADITAR): {"pueblo": -4},        # "¿y la justicia nacional?"
    (3, EXTRADITAR): {"pueblo": +8},        # en la frontera, extraditar parece lo lógico
    (3, LIBERAR):    {"pueblo": -6},
}

# Efectos combinados: dependen de la decisión ANTERIOR y de la actual.
EFECTOS_COMBINADOS: Dict[tuple, Dict[str, int]] = {
    (LIBERAR, LIBERAR):       {"medios": -10, "influencers": -10, "pueblo": -12},  # "¿otra vez?"
    (CAPTURAR, CAPTURAR):     {"medios": -4, "pueblo": +4},                          # mano dura
    (EXTRADITAR, EXTRADITAR): {"influencers": -6, "pueblo": -4},                     # "entreguista"
    (LIBERAR, CAPTURAR):      {"medios": +5},                                        # rectificó
}

Efectos = Dict[str, Dict[str, int]]


def limitar(valor: float) -> int:
    """Mantiene la opinión entre 0 y 100."""
    return int(max(0, min(100, round(valor))))


# -----------------------------------------------------------------------------
# Nodo
# -----------------------------------------------------------------------------
class Nodo:
    """Un estado del país tras una decisión."""

    def __init__(self, nivel: int, decision: Optional[str], opinion: Dict[str, int],
                 padre: Optional["Nodo"] = None):
        self.nivel = nivel                     # 0 = raíz, 1..3 = nivel en que se decidió
        self.decision = decision               # None en la raíz
        self.opinion = dict(opinion)           # {"medios", "influencers", "pueblo"} en 0..100
        self.padre = padre
        self.hijos: Dict[str, Nodo] = {}       # decisión -> Nodo hijo
        self.ajuste = {c: 0 for c in CATEGORIAS}   # lo que sumó o restó la propagación en la red

    @property
    def es_raiz(self) -> bool:
        return self.padre is None

    @property
    def es_hoja(self) -> bool:
        return self.nivel == NIVELES

    @property
    def promedio(self) -> float:
        return sum(self.opinion.values()) / len(self.opinion)

    def camino(self) -> List[str]:
        """Decisiones desde la raíz hasta este nodo (sube por los padres y luego invierte)."""
        decisiones = []
        nodo = self
        while nodo.padre is not None:          # recorrido hoja -> raíz
            decisiones.append(nodo.decision)
            nodo = nodo.padre
        decisiones.reverse()
        return decisiones

    def __repr__(self) -> str:
        return f"Nodo(nivel={self.nivel}, decision={self.decision}, opinion={self.opinion})"


# -----------------------------------------------------------------------------
# Árbol
# -----------------------------------------------------------------------------
class ArbolDecisiones:
    def __init__(self, efectos_base: Efectos = None, peso_nivel: Dict[int, float] = None,
                 ajustes_nivel: Dict[tuple, Dict[str, int]] = None,
                 combinados: Dict[tuple, Dict[str, int]] = None):
        self.efectos_base = efectos_base or EFECTOS_BASE
        self.peso_nivel = peso_nivel or PESO_NIVEL
        self.ajustes_nivel = AJUSTES_NIVEL if ajustes_nivel is None else ajustes_nivel
        self.combinados = EFECTOS_COMBINADOS if combinados is None else combinados
        self.raiz = Nodo(0, None, OPINION_INICIAL)
        self.actual = self.raiz                # nodo en el que va la partida

    # --- Efectos ------------------------------------------------------------------
    def efecto(self, padre: Nodo, decision: str) -> Dict[str, int]:
        """Cambio de opinión al tomar `decision` desde `padre`."""
        nivel = padre.nivel + 1
        peso = self.peso_nivel.get(nivel, 1.0)
        cambio = {c: self.efectos_base[decision].get(c, 0) * peso for c in CATEGORIAS}
        for c, v in self.ajustes_nivel.get((nivel, decision), {}).items():
            cambio[c] += v
        if padre.decision is not None:
            for c, v in self.combinados.get((padre.decision, decision), {}).items():
                cambio[c] += v
        return {c: round(v) for c, v in cambio.items()}

    # --- Inserción ----------------------------------------------------------------
    def insertar(self, padre: Nodo, decision: str) -> Nodo:
        """Devuelve el hijo de `padre` para `decision`; lo crea si no existe (inserción)."""
        if decision not in DECISIONES:
            raise ValueError(f"Decisión inválida: {decision!r}")
        if padre.es_hoja:
            raise ValueError("No se puede decidir más allá del nivel 3")
        if decision not in padre.hijos:
            cambio = self.efecto(padre, decision)
            opinion = {c: limitar(padre.opinion[c] + cambio[c]) for c in CATEGORIAS}
            padre.hijos[decision] = Nodo(padre.nivel + 1, decision, opinion, padre)
        return padre.hijos[decision]

    def decidir(self, decision: str) -> Nodo:
        """El jugador decide en el nivel actual: inserta (si hace falta) y avanza."""
        self.actual = self.insertar(self.actual, decision)
        return self.actual

    def ajustar(self, nodo: Nodo, cambios: Dict[str, int]) -> Dict[str, int]:
        """Suma `cambios` a la opinión del nodo (limitada a 0..100) y los anota en nodo.ajuste.
        Lo usa la red social: el alcance de la noticia modifica el efecto de la decisión."""
        for c in CATEGORIAS:
            antes = nodo.opinion[c]
            nodo.opinion[c] = limitar(antes + cambios.get(c, 0))
            nodo.ajuste[c] += nodo.opinion[c] - antes
        return dict(nodo.opinion)

    # --- Eliminación --------------------------------------------------------------
    def eliminar(self, nodo: Nodo) -> int:
        """Elimina `nodo` y TODO su subárbol; devuelve cuántos nodos se quitaron.

        1. La raíz no se puede eliminar (para empezar de cero está reiniciar()).
        2. Se cuenta el subárbol (preorden) y se desengancha del padre borrando la entrada
           padre.hijos[decisión]: al no quedar referencias, el subárbol entero desaparece.
        3. Si la partida iba por dentro de lo eliminado, `actual` sube al padre.
        En el juego es REVOCAR la última decisión: el jefe vuelve a estar en manos del presidente."""
        if nodo.padre is None:
            raise ValueError("La raíz no se puede eliminar")
        raiz = nodo
        while raiz.padre is not None:              # sube hasta la raíz para saber de qué árbol es
            raiz = raiz.padre
        if raiz is not self.raiz or nodo.padre.hijos.get(nodo.decision) is not nodo:
            raise ValueError("El nodo no pertenece a este árbol")
        quitados = list(self.preorden(nodo))
        del nodo.padre.hijos[nodo.decision]
        if any(n is self.actual for n in quitados):
            self.actual = nodo.padre
        nodo.padre = None
        return len(quitados)

    def revocar(self) -> Optional[str]:
        """Deshace la última decisión de la partida (elimina el nodo actual). Devuelve la
        decisión revocada, o None si la partida está en la raíz."""
        if self.actual.padre is None:
            return None
        decision = self.actual.decision
        self.eliminar(self.actual)
        return decision

    def construir_completo(self) -> None:
        """Inserta los 40 nodos posibles (1 + 3 + 9 + 27) sin mover la partida.
        Se usa para mostrar el árbol entero en la pantalla final y en las pruebas."""
        pendientes = [self.raiz]
        while pendientes:
            nodo = pendientes.pop()
            if not nodo.es_hoja:
                for d in DECISIONES:
                    pendientes.append(self.insertar(nodo, d))

    # --- Consultas ----------------------------------------------------------------
    def camino(self) -> List[str]:
        """Decisiones tomadas en la partida actual (recorre de la hoja a la raíz)."""
        return self.actual.camino()

    def opinion(self) -> Dict[str, int]:
        return dict(self.actual.opinion)

    @property
    def terminado(self) -> bool:
        return self.actual.es_hoja

    # --- Recorridos ---------------------------------------------------------------
    def preorden(self, nodo: Nodo = None) -> Iterator[Nodo]:
        """Recorrido en PREORDEN (profundidad): nodo, luego cada hijo en orden de DECISIONES."""
        nodo = nodo or self.raiz
        yield nodo
        for d in DECISIONES:
            if d in nodo.hijos:
                yield from self.preorden(nodo.hijos[d])

    def bfs(self) -> List[Nodo]:
        """Recorrido por NIVELES (anchura) usando una cola."""
        resultado, cola = [], deque([self.raiz])
        while cola:
            nodo = cola.popleft()
            resultado.append(nodo)
            for d in DECISIONES:
                if d in nodo.hijos:
                    cola.append(nodo.hijos[d])
        return resultado

    def hojas(self) -> List[Nodo]:
        return [n for n in self.preorden() if n.es_hoja]

    def cantidad_nodos(self) -> int:
        return sum(1 for _ in self.preorden())

    def altura(self) -> int:
        return max(n.nivel for n in self.preorden())

    # --- Reinicio -------------------------------------------------------------------
    def reiniciar(self) -> None:
        """Nueva partida: vuelve a la raíz y borra todos los nodos insertados."""
        self.raiz = Nodo(0, None, OPINION_INICIAL)
        self.actual = self.raiz

    # --- Serialización (para guardar o enviar por red) -------------------------------
    def to_dict(self) -> dict:
        def nodo_a_dict(n: Nodo) -> dict:
            return {"nivel": n.nivel, "decision": n.decision, "opinion": dict(n.opinion),
                    "ajuste": dict(n.ajuste), "hijos": {d: nodo_a_dict(h) for d, h in n.hijos.items()}}
        return {"raiz": nodo_a_dict(self.raiz), "camino": self.camino()}

    @classmethod
    def from_dict(cls, datos: dict) -> "ArbolDecisiones":
        arbol = cls()

        def dict_a_nodo(d: dict, padre: Optional[Nodo]) -> Nodo:
            n = Nodo(d["nivel"], d["decision"], d["opinion"], padre)
            n.ajuste.update(d.get("ajuste", {}))
            n.hijos = {k: dict_a_nodo(h, n) for k, h in d["hijos"].items()}
            return n
        arbol.raiz = dict_a_nodo(datos["raiz"], None)
        arbol.actual = arbol.raiz
        for d in datos["camino"]:
            arbol.actual = arbol.actual.hijos[d]
        return arbol


# -----------------------------------------------------------------------------
# Finales: las 27 hojas se agrupan en 5 finales
# -----------------------------------------------------------------------------
class Final:
    def __init__(self, clave: str, titulo: str, resumen: str, regla: str, condicion: Callable[[Nodo], bool]):
        self.clave, self.titulo, self.resumen, self.condicion = clave, titulo, resumen, condicion
        self.regla = regla          # la condición explicada en palabras (pantalla final y README)


def _cuenta(nodo: Nodo, decision: str) -> int:
    return nodo.camino().count(decision)


# Se evalúan en orden: gana el primero que se cumpla. El último siempre se cumple.
FINALES: List[Final] = [
    Final("cuestionado", "PRESIDENTE CUESTIONADO",
          "Los jefes criminales siguen libres y el país ya no le cree a nadie en palacio.",
          "Liberó 2 o más veces, o el promedio de opinión es menor a 35.",
          lambda n: _cuenta(n, LIBERAR) >= 2 or n.promedio < 35),
    Final("mano_dura", "PRESIDENTE DE MANO DURA",
          "Cárceles llenas, aplausos en la calle y editoriales preocupados por los excesos.",
          "Capturó 2 o más veces, la última fue capturar y los medios están bajo 70.",
          lambda n: _cuenta(n, CAPTURAR) >= 2 and n.decision == CAPTURAR and n.opinion["medios"] < 70),
    Final("diplomatico", "PRESIDENTE DIPLOMÁTICO",
          "Los socios internacionales lo felicitan; en casa, algunos dicen que delegó la justicia.",
          "Extraditó 2 o más veces y los medios están en 55 o más.",
          lambda n: _cuenta(n, EXTRADITAR) >= 2 and n.opinion["medios"] >= 55),
    Final("del_pueblo", "PRESIDENTE DEL PUEBLO",
          "Ganó la calle y también los titulares: la gente común lo defiende.",
          "El pueblo está en 65 o más.",
          lambda n: n.opinion["pueblo"] >= 65),
    Final("equilibrista", "PRESIDENTE EQUILIBRISTA",
          "Un poco de todo: nadie lo ama, nadie lo odia y la historia aún no decide.",
          "Ninguna de las anteriores.",
          lambda n: True),
]


def final_de(nodo: Nodo) -> Final:
    """Final que corresponde a una hoja (o a cualquier nodo, por si se consulta antes)."""
    for final in FINALES:
        if final.condicion(nodo):
            return final
    return FINALES[-1]
