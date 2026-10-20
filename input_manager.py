"""Gestor de entrada: unifica teclado y gamepad (control NES USB) en ACCIONES abstractas.

La lógica del juego nunca pregunta por teclas ni botones: recibe un diccionario
{id_jugador: EstadoAcciones}. Así, en el futuro, las acciones de un jugador remoto
podrán llegar por red (EstadoAcciones.to_dict / from_dict) sin cambiar la lógica.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Dict, FrozenSet, Optional, Set

import pygame

import settings

# --- Acciones abstractas ----------------------------------------------------
IZQUIERDA = "IZQUIERDA"
DERECHA = "DERECHA"
ARRIBA = "ARRIBA"
ABAJO = "ABAJO"
SALTAR = "SALTAR"
DISPARAR = "DISPARAR"
PAUSA = "PAUSA"
CONFIRMAR = "CONFIRMAR"
CANCELAR = "CANCELAR"
AYUDA = "AYUDA"

ACCIONES = (IZQUIERDA, DERECHA, ARRIBA, ABAJO, SALTAR, DISPARAR,
            PAUSA, CONFIRMAR, CANCELAR, AYUDA)

# Acciones que se asignan a botones físicos del gamepad (se pueden remapear).
ACCIONES_REMAPEABLES = (SALTAR, DISPARAR, PAUSA, AYUDA)

# En el gamepad, CONFIRMAR y CANCELAR se derivan de otros botones (convención NES).
DERIVADAS_GAMEPAD = {
    CONFIRMAR: (SALTAR, PAUSA),   # A o START confirman
    CANCELAR: (DISPARAR,),        # B cancela / vuelve
}

# Teclado de respaldo (siempre activo).
TECLADO = {
    IZQUIERDA: (pygame.K_LEFT,),
    DERECHA: (pygame.K_RIGHT,),
    ARRIBA: (pygame.K_UP,),
    ABAJO: (pygame.K_DOWN,),
    SALTAR: (pygame.K_z,),
    DISPARAR: (pygame.K_x,),
    PAUSA: (pygame.K_RETURN, pygame.K_ESCAPE),
    CONFIRMAR: (pygame.K_RETURN, pygame.K_z, pygame.K_SPACE),
    CANCELAR: (pygame.K_ESCAPE, pygame.K_x),
    AYUDA: (pygame.K_F1, pygame.K_TAB),
}

CONFIG_POR_DEFECTO = {
    "botones": {SALTAR: 1, DISPARAR: 2, PAUSA: 9, AYUDA: 8},
    "eje_x": 0,
    "eje_y": 1,
    "umbral_eje": 0.5,
    "invertir_eje_y": False,
}


@dataclass(frozen=True)
class EstadoAcciones:
    """Acciones de UN jugador en un paso de simulación.

    mantenidas: acciones presionadas en este momento.
    pulsadas: acciones que se empezaron a presionar desde el paso anterior.
    """
    mantenidas: FrozenSet[str] = frozenset()
    pulsadas: FrozenSet[str] = frozenset()

    def mantiene(self, accion: str) -> bool:
        return accion in self.mantenidas

    def pulso(self, accion: str) -> bool:
        return accion in self.pulsadas

    def to_dict(self) -> dict:
        return {"mantenidas": sorted(self.mantenidas), "pulsadas": sorted(self.pulsadas)}

    @classmethod
    def from_dict(cls, datos: dict) -> "EstadoAcciones":
        return cls(frozenset(datos.get("mantenidas", ())), frozenset(datos.get("pulsadas", ())))


def cargar_config(ruta: str = settings.RUTA_GAMEPAD) -> dict:
    """Lee config/gamepad.json completando con valores por defecto."""
    config = json.loads(json.dumps(CONFIG_POR_DEFECTO))  # copia profunda
    try:
        with open(ruta, encoding="utf-8") as f:
            datos = json.load(f)
        config["botones"].update(datos.get("botones", {}))
        for clave in ("eje_x", "eje_y", "umbral_eje", "invertir_eje_y"):
            if clave in datos:
                config[clave] = datos[clave]
    except (OSError, ValueError):
        pass
    return config


def guardar_config(config: dict, ruta: str = settings.RUTA_GAMEPAD) -> None:
    """Guarda el mapeo del gamepad conservando el texto de ayuda."""
    datos = {"_ayuda": "IDs de botones del control NES USB. Usa tools/probar_control.py "
                       "para descubrirlos o remapea desde Opciones > Configurar control."}
    datos.update(config)
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(datos, f, indent=2, ensure_ascii=False)


class InputManager:
    """Traduce teclado + gamepads a EstadoAcciones por jugador."""

    def __init__(self, ruta_config: str = settings.RUTA_GAMEPAD):
        self.ruta_config = ruta_config
        self.config = cargar_config(ruta_config)
        self.joysticks: Dict[int, pygame.joystick.JoystickType] = {}  # instance_id -> joystick
        self._mantenidas: Set[str] = set()
        self._anteriores: Set[str] = set()
        self._pulsadas_pendientes: Set[str] = set()
        self._simuladas: Set[str] = set()   # entradas inyectadas (pruebas / demo)
        pygame.joystick.init()

    # --- Conexión en caliente ----------------------------------------------
    def procesar_evento(self, evento: pygame.event.Event) -> None:
        """Atiende conexión/desconexión de controles y registra pulsaciones muy rápidas."""
        if evento.type == pygame.JOYDEVICEADDED:
            joy = pygame.joystick.Joystick(evento.device_index)
            self.joysticks[joy.get_instance_id()] = joy
            print(f"[entrada] Control conectado: {joy.get_name()}")
        elif evento.type == pygame.JOYDEVICEREMOVED:
            joy = self.joysticks.pop(evento.instance_id, None)
            if joy is not None:
                print("[entrada] Control desconectado")
        elif evento.type == pygame.KEYDOWN:
            # Un toque más corto que un frame no se perdería con la detección por flancos.
            for accion, teclas in TECLADO.items():
                if evento.key in teclas:
                    self._pulsadas_pendientes.add(accion)
        elif evento.type == pygame.JOYBUTTONDOWN:
            self._pulsadas_pendientes |= self._acciones_de_boton(evento.button)

    @property
    def hay_control(self) -> bool:
        return bool(self.joysticks)

    def nombre_control(self) -> Optional[str]:
        for joy in self.joysticks.values():
            return joy.get_name()
        return None

    # --- Lectura por frame ---------------------------------------------------
    def actualizar(self) -> None:
        """Se llama una vez por frame, después de procesar los eventos."""
        actuales = self._leer_teclado() | self._simuladas
        for joy in self.joysticks.values():
            actuales |= self._leer_joystick(joy)
        self._pulsadas_pendientes |= actuales - self._anteriores
        self._anteriores = actuales
        self._mantenidas = actuales
        self._simuladas = set()

    def consumir(self) -> Dict[int, EstadoAcciones]:
        """Entrega las acciones para UN paso de simulación y vacía las pulsaciones."""
        estado = EstadoAcciones(frozenset(self._mantenidas), frozenset(self._pulsadas_pendientes))
        self._pulsadas_pendientes = set()
        return {settings.JUGADOR_LOCAL: estado}

    def limpiar_pulsadas(self) -> None:
        """Descarta pulsaciones pendientes (útil al cambiar de escena)."""
        self._pulsadas_pendientes = set()

    def simular(self, *acciones: str) -> None:
        """Inyecta acciones como si se presionaran durante un frame (pruebas headless)."""
        self._simuladas |= set(acciones)

    # --- Detalles de lectura -------------------------------------------------
    def _leer_teclado(self) -> Set[str]:
        teclas = pygame.key.get_pressed()
        return {accion for accion, codigos in TECLADO.items() if any(teclas[c] for c in codigos)}

    def _acciones_de_boton(self, boton: int) -> Set[str]:
        """Acciones asociadas a un botón físico, incluyendo las derivadas."""
        directas = {a for a, b in self.config["botones"].items() if b == boton}
        derivadas = {d for d, fuentes in DERIVADAS_GAMEPAD.items() if directas & set(fuentes)}
        return directas | derivadas

    def _leer_joystick(self, joy) -> Set[str]:
        activas: Set[str] = set()
        # Botones
        for boton in range(joy.get_numbuttons()):
            if joy.get_button(boton):
                activas |= self._acciones_de_boton(boton)
        # Cruceta como "hat"
        for h in range(joy.get_numhats()):
            x, y = joy.get_hat(h)
            if x < 0:
                activas.add(IZQUIERDA)
            elif x > 0:
                activas.add(DERECHA)
            if y > 0:
                activas.add(ARRIBA)
            elif y < 0:
                activas.add(ABAJO)
        # Cruceta como ejes (muchos controles NES USB baratos la reportan así)
        umbral = self.config["umbral_eje"]
        ex, ey = self.config["eje_x"], self.config["eje_y"]
        if ex < joy.get_numaxes():
            vx = joy.get_axis(ex)
            if vx <= -umbral:
                activas.add(IZQUIERDA)
            elif vx >= umbral:
                activas.add(DERECHA)
        if ey < joy.get_numaxes():
            vy = joy.get_axis(ey)
            if self.config["invertir_eje_y"]:
                vy = -vy
            if vy <= -umbral:
                activas.add(ARRIBA)
            elif vy >= umbral:
                activas.add(ABAJO)
        return activas

    # --- Remapeo ---------------------------------------------------------------
    def asignar_boton(self, accion: str, boton: int) -> None:
        """Asigna un botón a una acción; si otra acción lo tenía, intercambia."""
        botones = self.config["botones"]
        anterior = botones.get(accion)
        for otra, b in botones.items():
            if b == boton and otra != accion:
                botones[otra] = anterior
        botones[accion] = boton

    def guardar(self) -> None:
        guardar_config(self.config, self.ruta_config)
