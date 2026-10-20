"""Datos de una partida completa (3 niveles): árbol de decisiones, mapa, puntaje y vidas.

Vive en el objeto Juego mientras dura la partida y pasa de una escena a otra. Aquí se juntan
las dos estructuras de datos:
  - el ÁRBOL guarda qué se decidió y la opinión que resultó;
  - el GRAFO (mapa del país) recibe cada decisión, que cambia el peligro de sus vías, y ofrece
    las rutas al nivel siguiente. La ruta elegida vuelve al juego: suma refuerzos enemigos al
    nivel y, si es larga, resta opinión en el nodo actual del árbol.
La SEMILLA es distinta en cada partida: de ella salen los retenes del mapa, las represalias y
los refuerzos de cada nivel.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import settings
from core.decision_tree import ArbolDecisiones, CATEGORIAS, LIBERAR
from core.mapa import SEGURA, ZONA_NIVEL, Mapa

REVOCACIONES = 1                  # cuántas veces se puede revocar una decisión en una partida
# Revocar se paga en opinión: el país ve a un presidente que duda
PENALIZACION_REVOCAR = {"medios": -6, "influencers": -4, "pueblo": -4}
AMPLIFICACION_INFLUENCER = 0.25   # con un INFLUENCER en la partida, cada decisión pesa un 25 % más
DECISION_POR_TIEMPO = LIBERAR     # si se acaba el tiempo para decidir, el jefe escapa


def semilla_nueva() -> int:
    """Semilla al azar de verdad (no depende del reloj ni de una semilla fija)."""
    return random.SystemRandom().randrange(1, 1_000_000)


@dataclass
class Partida:
    arbol: ArbolDecisiones = field(default_factory=ArbolDecisiones)
    nivel: int = 1                       # nivel que se está jugando o el siguiente
    puntaje: int = 0                     # acumulado al empezar `nivel`
    vidas: int = settings.JUGADOR["vidas"]
    jefes_derrotados: List[str] = field(default_factory=list)
    semilla: int = field(default_factory=semilla_nueva)
    mapa: Optional[Mapa] = None          # grafo del país
    revocaciones: int = REVOCACIONES
    roles: Tuple[str, ...] = ("presidente",)       # roles presentes (modo multijugador)
    cambios_mapa: List[str] = field(default_factory=list)   # qué cambió en el mapa con la última decisión
    rutas: Dict[int, dict] = field(default_factory=dict)    # ruta elegida para llegar a cada nivel

    def __post_init__(self):
        if self.mapa is None:
            self.mapa = Mapa(self.semilla)
        self._respaldo: Optional[dict] = None       # mapa antes de la última decisión (para revocar)

    # --- Niveles -----------------------------------------------------------------------------
    def terminar_nivel(self, puntaje: int, vidas: int, jefe: str) -> None:
        """Guarda lo logrado en el nivel recién superado."""
        self.puntaje, self.vidas = puntaje, vidas
        self.jefes_derrotados.append(jefe)

    def avanzar(self) -> None:
        self.nivel += 1

    # --- Rutas: grafo -> nivel y árbol ----------------------------------------------------------
    def opciones_ruta(self, numero: int) -> Dict[str, dict]:
        """Rutas posibles hacia el nivel (ver Mapa.rutas)."""
        return self.mapa.rutas(numero)

    def elegir_ruta(self, numero: int, clave: str = SEGURA) -> dict:
        """Fija la ruta hacia el nivel y aplica su efecto: los refuerzos quedan guardados para el
        nivel y el cambio de opinión se suma al nodo actual del árbol. Solo la primera elección
        de cada nivel cuenta (reintentar el nivel no vuelve a cobrar el viaje)."""
        if numero not in self.rutas:
            opciones = self.opciones_ruta(numero)
            ruta = dict(opciones.get(clave) or opciones[SEGURA], clave=clave if clave in opciones else SEGURA)
            self.rutas[numero] = ruta
            self.arbol.ajustar(self.arbol.actual, ruta["opinion"])
        return self.rutas[numero]

    def peligro(self, numero: int) -> int:
        """Refuerzos aleatorios extra del nivel: los de la ruta elegida (o los de la ruta segura
        si aún no se eligió, p. ej. al entrar directo a un nivel en modo desarrollo)."""
        if numero not in ZONA_NIVEL:                 # niveles de prueba: fuera del mapa
            return 0
        if numero in self.rutas:
            return self.rutas[numero]["refuerzos"]
        return self.mapa.peligro(numero)

    # --- Decisiones: árbol -> grafo -----------------------------------------------------------------
    def decidir(self, decision: str) -> None:
        """Registra la decisión del nivel actual: la INSERTA en el árbol y cambia las vías del
        mapa. Con un influencer en la partida, el efecto sobre la opinión se amplifica."""
        self._respaldo = self.mapa.to_dict()
        nodo = self.arbol.decidir(decision)
        if "influencer" in self.roles:
            efecto = self.arbol.efecto(nodo.padre, decision)
            self.arbol.ajustar(nodo, {c: round(efecto[c] * AMPLIFICACION_INFLUENCER) for c in CATEGORIAS})
        self.cambios_mapa = self.mapa.aplicar_decision(self.nivel, decision)

    @property
    def puede_revocar(self) -> bool:
        return self.revocaciones > 0 and self._respaldo is not None and self.arbol.actual.padre is not None

    def revocar(self) -> Optional[str]:
        """Revoca la última decisión: ELIMINA su nodo del árbol, devuelve el mapa a como estaba y
        cobra la duda en opinión (se resta en el nodo padre, así la hereda la nueva decisión).
        Solo se puede REVOCACIONES veces por partida. Devuelve la decisión revocada."""
        if not self.puede_revocar:
            return None
        decision = self.arbol.revocar()                     # eliminación en el árbol
        self.mapa = Mapa.from_dict(self._respaldo)
        self._respaldo = None
        self.revocaciones -= 1
        self.arbol.ajustar(self.arbol.actual, PENALIZACION_REVOCAR)
        self.cambios_mapa = []
        return decision

    # --- Serialización -----------------------------------------------------------------------
    def to_dict(self) -> dict:
        return {"arbol": self.arbol.to_dict(), "nivel": self.nivel, "puntaje": self.puntaje,
                "vidas": self.vidas, "jefes_derrotados": list(self.jefes_derrotados),
                "semilla": self.semilla, "mapa": self.mapa.to_dict(), "revocaciones": self.revocaciones,
                "roles": list(self.roles), "cambios_mapa": list(self.cambios_mapa),
                "rutas": {str(n): dict(r) for n, r in self.rutas.items()}}

    @classmethod
    def from_dict(cls, d: dict) -> "Partida":
        return cls(ArbolDecisiones.from_dict(d["arbol"]), d["nivel"], d["puntaje"], d["vidas"],
                   list(d["jefes_derrotados"]), d.get("semilla", 0),
                   Mapa.from_dict(d["mapa"]) if d.get("mapa") else None,
                   d.get("revocaciones", REVOCACIONES), tuple(d.get("roles", ("presidente",))),
                   list(d.get("cambios_mapa", [])), {int(n): dict(r) for n, r in d.get("rutas", {}).items()})
