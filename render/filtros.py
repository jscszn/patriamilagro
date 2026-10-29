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


# --- Filtro CRT (opcional) ---------------------------------------------------------------------
_crt_cache = {}


def mascara_crt(ancho: int, alto: int, escala: int) -> pygame.Surface:
    """Capa que se MULTIPLICA sobre la imagen ya escalada: líneas de barrido (la última fila de
    cada píxel más oscura), una rejilla de color muy suave si la escala es grande y las
    esquinas oscurecidas como en un televisor de tubo. Se calcula una vez por tamaño."""
    clave = (ancho, alto, escala)
    if clave in _crt_cache:
        return _crt_cache[clave]
    filas = np.ones(alto, np.float32)
    if escala >= 2:
        filas[escala - 1::escala] = 0.72                   # línea de barrido
        if escala >= 4:
            filas[escala - 2::escala] = 0.9
    columnas = np.ones((ancho, 3), np.float32)
    if escala >= 4:                                        # rejilla de fósforo (rojo, verde, azul)
        for canal in range(3):
            columnas[canal::3, :] *= 0.94
            columnas[canal::3, canal] = 1.0
    x = np.linspace(-1, 1, ancho, dtype=np.float32)[:, None]
    y = np.linspace(-1, 1, alto, dtype=np.float32)[None, :]
    vineta = np.clip(1.0 - 0.22 * (x ** 2 + y ** 2) ** 2, 0, 1)        # (ancho, alto)
    valor = columnas[:, None, :] * (filas[None, :, None] * vineta[:, :, None])
    sup = pygame.Surface((ancho, alto))
    pygame.surfarray.blit_array(sup, (valor * 255).astype(np.uint8))
    if len(_crt_cache) > 4:
        _crt_cache.clear()
    _crt_cache[clave] = sup
    return sup
