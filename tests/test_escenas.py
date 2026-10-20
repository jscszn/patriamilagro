"""Prueba de humo: recorre las escenas en modo headless simulando entradas."""
import os
import unittest

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import input_manager as im  # noqa: E402
from main import Juego  # noqa: E402


class TestEscenas(unittest.TestCase):
    def setUp(self):
        self.juego = Juego(headless=True)

    def pulsar(self, *acciones, frames_despues=2):
        self.juego.entrada.simular(*acciones)
        self.juego.frame()
        for _ in range(frames_despues):
            self.juego.frame()

    def nombre_actual(self):
        return type(self.juego.escenas.actual).__name__

    def test_recorrido_menu(self):
        self.assertEqual(self.nombre_actual(), "MenuScene")
        self.pulsar(im.CONFIRMAR)                       # JUGAR
        self.assertEqual(self.nombre_actual(), "HistoriaScene")   # informe antes del nivel
        for _ in range(4):                              # completa el texto y pasa las 2 páginas
            self.pulsar(im.CONFIRMAR)
        self.assertEqual(self.nombre_actual(), "LevelScene")
        self.pulsar(im.PAUSA)
        self.assertEqual(self.nombre_actual(), "PauseScene")
        self.pulsar(im.AYUDA)
        self.assertEqual(self.nombre_actual(), "HelpScene")
        self.pulsar(im.CANCELAR)
        self.assertEqual(self.nombre_actual(), "PauseScene")
        self.pulsar(im.ABAJO)
        self.pulsar(im.ABAJO)
        self.pulsar(im.CONFIRMAR)                       # SALIR AL MENU
        self.assertEqual(self.nombre_actual(), "MenuScene")
        self.pulsar(im.ABAJO)
        self.pulsar(im.ABAJO)
        self.pulsar(im.CONFIRMAR)                       # OPCIONES (3.ª: JUGAR, AYUDA, OPCIONES, ...)
        self.assertEqual(self.nombre_actual(), "OptionsScene")
        self.pulsar(im.ABAJO)
        self.pulsar(im.ABAJO)
        self.pulsar(im.ABAJO)
        self.pulsar(im.ABAJO)
        self.pulsar(im.ABAJO)
        self.pulsar(im.CONFIRMAR)                       # Configurar control
        self.assertEqual(self.nombre_actual(), "RemapScene")
        for _ in range(60):
            self.juego.frame()

    def test_salir(self):
        self.pulsar(im.ARRIBA)                          # el cursor da la vuelta hasta SALIR
        self.pulsar(im.CONFIRMAR)
        self.assertFalse(self.juego.corriendo)


if __name__ == "__main__":
    unittest.main()
