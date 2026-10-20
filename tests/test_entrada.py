"""Pruebas del gestor de entrada (sin control físico)."""
import os
import tempfile
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame  # noqa: E402

import input_manager as im  # noqa: E402


class TestEntrada(unittest.TestCase):
    def setUp(self):
        pygame.init()
        pygame.display.set_mode((1, 1))
        self.tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
        self.tmp.close()
        os.unlink(self.tmp.name)  # que no exista: debe usar valores por defecto
        self.entrada = im.InputManager(self.tmp.name)

    def tearDown(self):
        if os.path.exists(self.tmp.name):
            os.unlink(self.tmp.name)

    def test_pulsada_solo_un_paso(self):
        self.entrada.simular(im.SALTAR)
        self.entrada.actualizar()
        estado = self.entrada.consumir()[1]
        self.assertTrue(estado.pulso(im.SALTAR))
        self.assertTrue(estado.mantiene(im.SALTAR))
        # Siguiente paso del mismo frame: ya no es "pulsada"
        self.assertFalse(self.entrada.consumir()[1].pulso(im.SALTAR))

    def test_mantener_no_repite_pulsacion(self):
        self.entrada.simular(im.DISPARAR)
        self.entrada.actualizar()
        self.entrada.consumir()
        self.entrada.simular(im.DISPARAR)
        self.entrada.actualizar()
        estado = self.entrada.consumir()[1]
        self.assertTrue(estado.mantiene(im.DISPARAR))
        self.assertFalse(estado.pulso(im.DISPARAR))

    def test_serializacion(self):
        estado = im.EstadoAcciones(frozenset({im.ARRIBA, im.DISPARAR}), frozenset({im.DISPARAR}))
        self.assertEqual(im.EstadoAcciones.from_dict(estado.to_dict()), estado)

    def test_botones_derivados(self):
        boton_a = self.entrada.config["botones"][im.SALTAR]
        self.assertEqual(self.entrada._acciones_de_boton(boton_a), {im.SALTAR, im.CONFIRMAR})

    def test_remapeo_intercambia_y_guarda(self):
        b_saltar = self.entrada.config["botones"][im.SALTAR]
        b_disparar = self.entrada.config["botones"][im.DISPARAR]
        self.entrada.asignar_boton(im.SALTAR, b_disparar)
        self.assertEqual(self.entrada.config["botones"][im.SALTAR], b_disparar)
        self.assertEqual(self.entrada.config["botones"][im.DISPARAR], b_saltar)
        self.entrada.guardar()
        self.assertEqual(im.cargar_config(self.tmp.name)["botones"][im.SALTAR], b_disparar)


if __name__ == "__main__":
    unittest.main()
