"""Filtros de accesibilidad que se aplican a la imagen final (256x224) antes de escalarla.

Daltonismo: "daltonización" (Fidaner, Lin y Ozguven, 2005). No simula la deficiencia: CORRIGE
los colores para quien la tiene. Se simula cómo ve la persona, se calcula el error (la
información de color que pierde) y se desplaza ese error a canales que sí distingue.
Todo se reduce a UNA matriz 3x3 por modo, que se aplica a cada píxel con numpy.
"""
from __future__ import annotations

import numpy as np
import pygame

RGB_A_LMS = np.array([[17.8824, 43.5161, 4.11935],
                      [3.45565, 27.1554, 3.86714],
                      [0.0299566, 0.184309, 1.46709]])
LMS_A_RGB = np.linalg.inv(RGB_A_LMS)

# Cómo ve cada deficiencia (en el espacio LMS de los conos)
SIMULACION = {
    "protanopia": np.array([[0, 2.02344, -2.52581], [0, 1, 0], [0, 0, 1]]),
    "deuteranopia": np.array([[1, 0, 0], [0.494207, 0, 1.24827], [0, 0, 1]]),
    "tritanopia": np.array([[1, 0, 0], [0, 1, 0], [-0.395913, 0.801109, 0]]),
}
# A dónde se lleva el error (matriz estándar del algoritmo, igual para los tres modos): el error
# del rojo se suma al verde y al azul, que la persona sí distingue.
DESPLAZAMIENTO_ESTANDAR = np.array([[0, 0, 0], [0.7, 1, 0], [0.7, 0, 1]])
DESPLAZAMIENTO = {modo: DESPLAZAMIENTO_ESTANDAR for modo in ("protanopia", "deuteranopia", "tritanopia")}


def matriz_daltonizacion(modo: str) -> np.ndarray:
    """resultado = original + D·(original - simulado) = (I + D·(I - T))·original."""
    simulado = LMS_A_RGB @ SIMULACION[modo] @ RGB_A_LMS
    return np.eye(3) + DESPLAZAMIENTO[modo] @ (np.eye(3) - simulado)


MATRICES = {modo: matriz_daltonizacion(modo).astype(np.float32) for modo in SIMULACION}


def aplicar_daltonismo(superficie: pygame.Surface, modo: str) -> None:
    """Corrige los colores de la superficie en el lugar (modo "ninguno" no hace nada)."""
    matriz = MATRICES.get(modo)
    if matriz is None:
        return
    pixeles = pygame.surfarray.pixels3d(superficie)
    corregidos = pixeles.reshape(-1, 3).astype(np.float32) @ matriz.T
    pixeles[...] = np.clip(corregidos, 0, 255).astype(np.uint8).reshape(pixeles.shape)
    del pixeles                                       # libera el bloqueo de la superficie
