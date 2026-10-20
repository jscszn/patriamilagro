"""Logros: pequeños objetivos que motivan a rejugar (y a probar los 5 finales).

El gestor recibe notificaciones de lo que pasa en el juego (notificar) y decide qué logros
se desbloquean. Se guardan en config/logros.json; en las pruebas se usan solo en memoria.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Dict, List, Optional

from core.decision_tree import FINALES


@dataclass(frozen=True)
class Logro:
    clave: str
    titulo: str
    descripcion: str


LOGROS: List[Logro] = [
    Logro("primera_captura", "PRIMERA CAPTURA", "Captura a un jefe criminal."),
    Logro("primera_extradicion", "SOCIO INTERNACIONAL", "Extradita a un jefe criminal."),
    Logro("corazon_blando", "¿SEGURO, PRESIDENTE?", "Deja libre a un jefe criminal."),
    Logro("potencia", "POTENCIA DE FUEGO", "Recoge el disparo triple."),
    Logro("cazador", "CAZADOR DE SICARIOS", "Derrota a 100 sicarios."),
    Logro("intachable", "INTACHABLE", "Supera un nivel sin perder vidas."),
    Logro("intocable", "INTOCABLE", "Vence a un jefe sin recibir daño."),
    Logro("bien_informado", "BIEN INFORMADO", "Lee el feed del teléfono entero."),
    Logro("estudiante", "ESTUDIANTE DE ÁRBOLES", "Mira los 4 recorridos del árbol."),
    Logro("mandato", "MANDATO CUMPLIDO", "Termina una partida completa."),
    Logro("todos_los_finales", "HISTORIADOR", "Descubre los 5 finales."),
]
POR_CLAVE = {l.clave: l for l in LOGROS}
SICARIOS_CAZADOR = 100
LOGRO_POR_DECISION = {"capturar": "primera_captura", "extraditar": "primera_extradicion",
                      "liberar": "corazon_blando"}


class GestorLogros:
    def __init__(self, ruta: Optional[str] = None):
        """ruta=None: solo en memoria (pruebas y modo headless)."""
        self.ruta = ruta
        self.desbloqueados: List[str] = []
        self.sicarios = 0
        self.finales_vistos: List[str] = []
        self._nuevos: List[Logro] = []
        self._cargar()

    # --- Persistencia -------------------------------------------------------------------------
    def _cargar(self) -> None:
        if not self.ruta:
            return
        try:
            with open(self.ruta, encoding="utf-8") as f:
                datos = json.load(f)
            self.desbloqueados = [c for c in datos.get("desbloqueados", []) if c in POR_CLAVE]
            self.sicarios = int(datos.get("sicarios", 0))
            self.finales_vistos = list(datos.get("finales_vistos", []))
        except (OSError, ValueError):
            pass

    def guardar(self) -> None:
        if not self.ruta:
            return
        os.makedirs(os.path.dirname(self.ruta), exist_ok=True)
        with open(self.ruta, "w", encoding="utf-8") as f:
            json.dump({"desbloqueados": self.desbloqueados, "sicarios": self.sicarios,
                       "finales_vistos": self.finales_vistos}, f, indent=2, ensure_ascii=False)

    # --- Reglas -------------------------------------------------------------------------------
    def desbloquear(self, clave: str) -> bool:
        if clave in self.desbloqueados:
            return False
        self.desbloqueados.append(clave)
        self._nuevos.append(POR_CLAVE[clave])
        self.guardar()
        return True

    def notificar(self, evento: str, **datos) -> None:
        """Eventos: decision, sicario_muere, powerup, nivel_superado, jefe_sin_dano,
        noticias_leidas, recorridos_vistos, final."""
        if evento == "decision":
            self.desbloquear(LOGRO_POR_DECISION[datos["decision"]])
        elif evento == "sicario_muere":
            self.sicarios += 1
            if self.sicarios >= SICARIOS_CAZADOR:
                self.desbloquear("cazador")
        elif evento == "powerup" and datos.get("clase") == "triple":
            self.desbloquear("potencia")
        elif evento == "nivel_superado":
            self.guardar()                                    # guarda el contador de sicarios
            if datos.get("vidas_perdidas", 1) == 0:
                self.desbloquear("intachable")
        elif evento == "jefe_sin_dano":
            self.desbloquear("intocable")
        elif evento == "noticias_leidas":
            self.desbloquear("bien_informado")
        elif evento == "recorridos_vistos":
            self.desbloquear("estudiante")
        elif evento == "final":
            if datos["clave"] not in self.finales_vistos:
                self.finales_vistos.append(datos["clave"])
            self.desbloquear("mandato")
            if len(self.finales_vistos) >= len(FINALES):
                self.desbloquear("todos_los_finales")
            self.guardar()

    def extraer_nuevos(self) -> List[Logro]:
        """Logros recién desbloqueados (para mostrar el aviso una sola vez)."""
        nuevos, self._nuevos = self._nuevos, []
        return nuevos

    def progreso(self) -> Dict[str, int]:
        return {"desbloqueados": len(self.desbloqueados), "total": len(LOGROS)}
