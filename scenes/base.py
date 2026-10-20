"""Máquina de escenas: clase base Scene y SceneManager con pila (para pausa/ayuda superpuestas)."""
from __future__ import annotations

from typing import Callable, Dict, List, Optional, Tuple

import pygame

import settings


class Scene:
    """Escena del juego. Cada pantalla (menú, nivel, teléfono...) hereda de esta clase."""

    # Si es True, la escena de abajo en la pila también se dibuja (p. ej. menú de pausa).
    transparente = False

    def __init__(self, juego, **datos):
        self.juego = juego
        self.datos = datos

    def handle_events(self, eventos: List[pygame.event.Event]) -> None:
        """Eventos crudos de pygame. Solo para casos especiales (p. ej. remapeo de botones)."""

    def update(self, dt: float, acciones: Dict) -> None:
        """Avanza la escena un paso fijo dt. acciones = {id_jugador: EstadoAcciones}."""

    def draw(self, superficie: pygame.Surface) -> None:
        """Dibuja la escena en la superficie interna de 256x224."""


class SceneManager:
    """Administra una pila de escenas. Los cambios se aplican al final del paso para
    no modificar la pila mientras una escena se está actualizando."""

    def __init__(self, juego):
        self.juego = juego
        self.fabricas: Dict[str, Callable[..., Scene]] = {}
        self.pila: List[Scene] = []
        self._pendiente: Optional[Tuple[str, Optional[str], dict]] = None

    def registrar(self, nombre: str, clase: Callable[..., Scene]) -> None:
        self.fabricas[nombre] = clase

    # --- Solicitudes de cambio ------------------------------------------------
    def cambiar(self, nombre: str, **datos) -> None:
        """Reemplaza toda la pila por una nueva escena."""
        self._pendiente = ("cambiar", nombre, datos)

    def apilar(self, nombre: str, **datos) -> None:
        """Pone una escena encima de la actual (la actual queda congelada)."""
        self._pendiente = ("apilar", nombre, datos)

    def desapilar(self) -> None:
        """Quita la escena de arriba y vuelve a la anterior."""
        self._pendiente = ("desapilar", None, {})

    def aplicar_cambios(self) -> None:
        if self._pendiente is None:
            return
        tipo, nombre, datos = self._pendiente
        self._pendiente = None
        if tipo == "cambiar":
            self.pila = [self.fabricas[nombre](self.juego, **datos)]
            self.juego.fundido = settings.DURACION_FUNDIDO     # fundido desde negro
        elif tipo == "apilar":
            self.pila.append(self.fabricas[nombre](self.juego, **datos))
        elif tipo == "desapilar" and len(self.pila) > 1:
            self.pila.pop()
        # Evita que la tecla que causó el cambio active algo en la escena nueva.
        self.juego.entrada.limpiar_pulsadas()

    @property
    def actual(self) -> Optional[Scene]:
        return self.pila[-1] if self.pila else None

    # --- Bucle --------------------------------------------------------------------
    def handle_events(self, eventos) -> None:
        if self.actual:
            self.actual.handle_events(eventos)
        self.aplicar_cambios()

    def update(self, dt: float, acciones: Dict) -> None:
        if self.actual:
            self.actual.update(dt, acciones)
        self.aplicar_cambios()

    def draw(self, superficie: pygame.Surface) -> None:
        # Busca la escena más alta que no sea transparente y dibuja desde ahí hacia arriba.
        inicio = len(self.pila) - 1
        while inicio > 0 and self.pila[inicio].transparente:
            inicio -= 1
        for escena in self.pila[inicio:]:
            escena.draw(superficie)
