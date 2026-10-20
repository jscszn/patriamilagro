"""Datos de los sprites que necesita la LÓGICA: de dónde sale la bala en cada pose.

Se leen de assets/sprites.json como datos JSON (sin pygame), así core/ sigue sin depender
del render. Si no hay PNG para una pose, se devuelve None y el jugador usa un punto genérico.
"""
from __future__ import annotations

import json
import os
from typing import Optional, Tuple

import settings

RUTA_JSON = os.path.join(settings.RUTA_ASSETS, "sprites.json")


def _cargar() -> dict:
    try:
        with open(RUTA_JSON, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


_DATOS = _cargar()


def cuadro(nombre: str, animacion: str, t: float):
    """Referencia del cuadro que se muestra en el tiempo t (misma fórmula que el render)."""
    conf = _DATOS.get(nombre, {})
    refs = conf.get("animaciones", {}).get(animacion)
    if not refs:
        return None
    return refs[int(t * conf.get("fps", 10)) % len(refs)]


def boca_sprite(nombre: str) -> Optional[Tuple[int, int]]:
    """Boca del arma guardada en un sprite de un solo cuadro (p. ej. el tirador del techo de la
    camioneta), relativa al ancla. None si el sprite no tiene PNG o no trae boca."""
    conf = _DATOS.get(nombre, {})
    if "boca" not in conf or not os.path.isfile(os.path.join(settings.RUTA_ASSETS, conf.get("archivo", ""))):
        return None
    return tuple(conf["boca"])


def boca_jugador(pose: str, t: float) -> Optional[Tuple[int, int]]:
    """Punta del arma relativa a los pies (x hacia donde mira, y negativa = arriba)."""
    ref = cuadro("jugador", pose, t)
    if not isinstance(ref, str) or not os.path.isfile(os.path.join(settings.RUTA_ASSETS, ref)):
        return None
    boca = _DATOS["jugador"].get("bocas", {}).get(ref)
    return tuple(boca) if boca else None
