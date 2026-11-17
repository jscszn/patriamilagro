"""Guardado del jugador: archivo en escritorio, almacenamiento del navegador en la versión web."""
import json
import os
import tempfile
import unittest

import almacen
import settings
from core.logros import GestorLogros


class NavegadorFalso:
    """Imita el localStorage del navegador (guarda textos por clave)."""

    def __init__(self):
        self.datos = {}

    def getItem(self, clave):
        return self.datos.get(clave)

    def setItem(self, clave, valor):
        self.datos[clave] = valor


class NavegadorBloqueado:
    def getItem(self, clave):
        raise RuntimeError("almacenamiento bloqueado")

    setItem = getItem


class ComoEnLaWeb(unittest.TestCase):
    """Hace creer a `almacen` que corre en un navegador."""

    def setUp(self):
        self.navegador = NavegadorFalso()
        self._web, self._nav = almacen.WEB, almacen._navegador
        almacen.WEB = True
        almacen._navegador = lambda: self.navegador

    def tearDown(self):
        almacen.WEB, almacen._navegador = self._web, self._nav


class TestEscritorio(unittest.TestCase):
    def test_guarda_y_lee_un_archivo_creando_la_carpeta(self):
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = os.path.join(carpeta, "config", "cosa.json")
            self.assertIsNone(almacen.leer(ruta))
            almacen.guardar(ruta, {"música": 7})
            self.assertEqual(almacen.leer(ruta), {"música": 7})
            with open(ruta, encoding="utf-8") as f:
                self.assertEqual(json.load(f), {"música": 7})

    def test_un_archivo_danado_cuenta_como_vacio(self):
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = os.path.join(carpeta, "roto.json")
            with open(ruta, "w") as f:
                f.write("{esto no es json")
            self.assertIsNone(almacen.leer(ruta))


class TestWeb(ComoEnLaWeb):
    def test_no_toca_el_disco_y_usa_una_clave_por_archivo(self):
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = os.path.join(carpeta, "config", "logros.json")
            almacen.guardar(ruta, {"desbloqueados": ["primera_captura"]})
            self.assertFalse(os.path.exists(os.path.dirname(ruta)))
            self.assertEqual(list(self.navegador.datos), ["patriamilagro:logros.json"])
            self.assertEqual(almacen.leer(ruta), {"desbloqueados": ["primera_captura"]})

    def test_sin_nada_guardado_o_con_basura_devuelve_none(self):
        self.assertIsNone(almacen.leer("config/opciones.json"))
        for basura in ("null", "undefined", "", "{roto"):
            self.navegador.datos["patriamilagro:opciones.json"] = basura
            self.assertIsNone(almacen.leer("config/opciones.json"), basura)

    def test_si_el_navegador_no_deja_guardar_el_juego_sigue(self):
        almacen._navegador = lambda: NavegadorBloqueado()
        almacen.guardar("config/opciones.json", {"a": 1})        # no lanza error
        self.assertIsNone(almacen.leer("config/opciones.json"))

    def test_las_opciones_sobreviven_a_cerrar_la_pagina(self):
        opciones = settings.cargar_opciones()
        self.assertEqual(opciones, settings.OPCIONES_POR_DEFECTO)   # primera visita: valores de fábrica
        opciones["volumen_musica"] = 2
        opciones["daltonismo"] = "protanopia"
        settings.guardar_opciones(opciones)
        self.assertEqual(settings.cargar_opciones()["volumen_musica"], 2)       # "segunda visita"
        self.assertEqual(settings.cargar_opciones()["daltonismo"], "protanopia")

    def test_los_logros_sobreviven_a_cerrar_la_pagina(self):
        logros = GestorLogros(settings.RUTA_LOGROS)
        self.assertEqual(logros.desbloqueados, [])
        clave = next(iter(__import__("core.logros", fromlist=["POR_CLAVE"]).POR_CLAVE))
        self.assertTrue(logros.desbloquear(clave))
        self.assertEqual(GestorLogros(settings.RUTA_LOGROS).desbloqueados, [clave])   # "segunda visita"

    def test_el_menu_web_no_ofrece_salir(self):
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
        os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
        from main import Juego
        from scenes.menu import MenuScene
        juego = Juego(headless=True)
        self.assertIn("SALIR", juego.escenas.actual.lista.opciones)             # escritorio: sí
        web = settings.WEB
        settings.WEB = True
        try:
            menu = MenuScene(juego)
            self.assertNotIn("SALIR", menu.lista.opciones)
            self.assertEqual(menu.lista.opciones[0], "JUGAR")
        finally:
            settings.WEB = web


if __name__ == "__main__":
    unittest.main()
