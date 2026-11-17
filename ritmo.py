"""Ritmo de los cuadros: que cada imagen llegue a tiempo y avance exactamente un paso del juego.

El reloj de pygame (`Clock.tick(60)`) trabaja en milisegundos enteros: en la práctica daba 58,9
cuadros por segundo en vez de 60. Como la simulación va a paso fijo (1/60 s), esa diferencia se
acumulaba y más o menos una vez por segundo un cuadro avanzaba DOS pasos (un tironcito al
desplazarse el fondo). Aquí hay dos piezas que lo evitan:

  - `Ritmo.esperar()` marca los cuadros con el reloj de alta resolución: duerme casi todo el
    tiempo que falta y afina el último milisegundo, así el periodo es de 16,67 ms de verdad.
  - `ajustar(dt)` trata como "un cuadro exacto" cualquier intervalo cercano al periodo: la
    simulación avanza un paso por imagen aunque el reloj tiemble unas décimas de milisegundo.

En la versión web el navegador marca los cuadros (no se usa `Ritmo`), pero `ajustar` sirve igual.
"""
from __future__ import annotations

import time

MARGEN_FINO = 0.001      # el último milisegundo se espera mirando el reloj (dormir no es tan preciso)
SIESTA_MINIMA = 0.0002   # no vale la pena dormir menos que esto
TOLERANCIA = 0.25        # un intervalo a menos del 25 % del periodo cuenta como un cuadro exacto


def ajustar(dt_real: float, periodo: float) -> float:
    """Devuelve `periodo` si dt_real está cerca de él (el temblor normal del reloj); si no, deja
    dt_real como está (un cuadro que de verdad tardó de más o de menos)."""
    return periodo if abs(dt_real - periodo) <= periodo * TOLERANCIA else dt_real


class Ritmo:
    """Marcapasos de los cuadros. `esperar()` se llama una vez por cuadro."""

    def __init__(self, fps: float, reloj=time.perf_counter, dormir=time.sleep):
        self.periodo = 1.0 / fps
        self._reloj = reloj
        self._dormir = dormir
        self._anterior = reloj()
        self._meta = self._anterior + self.periodo

    def medir(self) -> float:
        """Versión web: el navegador ya marca los cuadros (uno por refresco de pantalla), así que
        aquí NO se espera; solo se devuelven los segundos reales desde la llamada anterior."""
        ahora = self._reloj()
        dt = ahora - self._anterior
        self._anterior = ahora
        self._meta = ahora + self.periodo
        return dt

    def esperar(self) -> float:
        """Espera hasta la hora del siguiente cuadro y devuelve los segundos reales que pasaron
        desde la llamada anterior."""
        reloj = self._reloj
        # Dormir se pasa de largo (en macOS, hasta un 25 % de lo pedido): se duerme la MITAD de lo
        # que falta, varias veces, y el último milisegundo se espera mirando el reloj.
        while True:
            falta = self._meta - reloj() - MARGEN_FINO
            if falta <= SIESTA_MINIMA:
                break
            self._dormir(max(falta * 0.5, SIESTA_MINIMA))
        while reloj() < self._meta:
            pass
        ahora = reloj()
        dt = ahora - self._anterior
        self._anterior = ahora
        self._meta += self.periodo
        if self._meta <= ahora:        # cuadro lento (o ventana arrastrada): no intenta recuperar
            self._meta = ahora + self.periodo
        return dt
