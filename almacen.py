"""Guardado de los datos del jugador (opciones, logros, mapeo del control) en formato JSON.

  - Escritorio: un archivo por cosa en config/ (como siempre).
  - Versión web: el almacenamiento local del navegador (localStorage), porque ahí no hay disco:
    cada archivo se guarda bajo la clave "patriamilagro:<nombre del archivo>". Así las opciones
    y los logros siguen ahí al volver a abrir la página en el mismo navegador.

Quien guarda y lee (settings, core/logros, input_manager) no necesita saber dónde corre.
"""
from __future__ import annotations

import json
import os
import sys
from typing import Optional

WEB = sys.platform == "emscripten"
PREFIJO = "patriamilagro:"


def _navegador():
    """El localStorage del navegador (solo existe en la versión web)."""
    import platform
    return platform.window.localStorage


def clave(ruta: str) -> str:
    """Clave del navegador para un archivo: "config/logros.json" -> "patriamilagro:logros.json"."""
    return PREFIJO + os.path.basename(ruta)


def leer(ruta: str) -> Optional[dict]:
    """Lo guardado en `ruta`, o None si no hay nada o está dañado."""
    if WEB:
        try:
            texto = _navegador().getItem(clave(ruta))
            if texto is None or str(texto) in ("", "null", "undefined"):
                return None
            return json.loads(str(texto))
        except Exception:                 # navegación privada, almacenamiento bloqueado o dato roto
            return None
    try:
        with open(ruta, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def guardar(ruta: str, datos: dict) -> None:
    """Guarda `datos` en `ruta` (o en el navegador). En la web, si el navegador no deja guardar
    (modo privado, espacio lleno), el juego sigue: solo no recordará ese dato."""
    if WEB:
        try:
            _navegador().setItem(clave(ruta), json.dumps(datos, ensure_ascii=False))
        except Exception:
            pass
        return
    carpeta = os.path.dirname(ruta)
    if carpeta:
        os.makedirs(carpeta, exist_ok=True)
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(datos, f, indent=2, ensure_ascii=False)
