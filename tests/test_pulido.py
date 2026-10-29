"""Pruebas de la etapa (g): sonido sintetizado, filtros de accesibilidad, logros y opciones."""
import json
import os
import tempfile
import unittest

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
import numpy as np  # noqa: E402
import pygame  # noqa: E402

import input_manager as im  # noqa: E402
from audio import gestor, sintesis  # noqa: E402
from core.decision_tree import FINALES  # noqa: E402
from core.logros import LOGROS, SICARIOS_CAZADOR, GestorLogros  # noqa: E402
from main import Juego  # noqa: E402
from render.filtros import MATRICES, aplicar_daltonismo  # noqa: E402
from scenes.level import SONIDO_EVENTO  # noqa: E402


class TestSintesis(unittest.TestCase):
    def test_efectos_validos(self):
        efectos = sintesis.efectos()
        for nombre, datos in efectos.items():
            with self.subTest(efecto=nombre):
                self.assertEqual(datos.dtype, np.float32)
                self.assertGreater(len(datos), 0)
                self.assertLessEqual(float(np.max(np.abs(datos))), 1.0)
        for evento, sonido in SONIDO_EVENTO.items():          # cada evento tiene su sonido
            self.assertIn(sonido, efectos, evento)

    def test_temas_en_bucle(self):
        for nombre in sintesis.TEMAS:
            with self.subTest(tema=nombre):
                datos = sintesis.tema(nombre, repeticiones=1)
                self.assertGreater(len(datos) / sintesis.SR, 4)   # al menos 4 segundos
                self.assertLessEqual(float(np.max(np.abs(datos))), 1.0)

    def test_conversion_a_int16(self):
        estereo = sintesis.a_int16(np.array([0, 0.5, -1], np.float32), 2)
        self.assertEqual(estereo.shape, (3, 2))
        self.assertEqual(estereo.dtype, np.int16)

    def test_gestor_sin_tarjeta_no_falla(self):
        audio = gestor.Audio({}, activo=False)
        audio.efecto("salto")
        audio.musica("menu")
        self.assertEqual(audio.tema_actual, "menu")

    def test_gestor_con_mixer(self):
        pygame.init()
        audio = gestor.Audio({"volumen_efectos": 5, "volumen_musica": 0})
        if not audio.activo:
            self.skipTest("sin mixer")
        audio.efecto("powerup")
        audio.musica("nivel2")
        self.assertEqual(audio.tema_actual, "nivel2")


class TestFiltros(unittest.TestCase):
    def test_grises_no_cambian(self):
        for modo, m in MATRICES.items():
            for g in (0, 64, 128, 255):
                with self.subTest(modo=modo, gris=g):
                    np.testing.assert_allclose(m @ np.array([g, g, g], float), [g, g, g], atol=1.0)

    def test_ninguno_no_modifica_y_otro_si(self):
        pygame.init()
        sup = pygame.Surface((8, 8))
        sup.fill((216, 40, 0))
        aplicar_daltonismo(sup, "ninguno")
        self.assertEqual(tuple(sup.get_at((1, 1)))[:3], (216, 40, 0))
        aplicar_daltonismo(sup, "deuteranopia")
        self.assertNotEqual(tuple(sup.get_at((1, 1)))[:3], (216, 40, 0))


class TestLogros(unittest.TestCase):
    def test_decisiones_y_sin_duplicados(self):
        g = GestorLogros()
        g.notificar("decision", decision="capturar")
        g.notificar("decision", decision="capturar")
        self.assertEqual([l.clave for l in g.extraer_nuevos()], ["primera_captura"])
        self.assertEqual(g.extraer_nuevos(), [])

    def test_cazador(self):
        g = GestorLogros()
        for _ in range(SICARIOS_CAZADOR - 1):
            g.notificar("sicario_muere")
        self.assertNotIn("cazador", g.desbloqueados)
        g.notificar("sicario_muere")
        self.assertIn("cazador", g.desbloqueados)

    def test_todos_los_finales(self):
        g = GestorLogros()
        for f in FINALES:
            g.notificar("final", clave=f.clave)
        self.assertIn("mandato", g.desbloqueados)
        self.assertIn("todos_los_finales", g.desbloqueados)

    def test_persistencia(self):
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = os.path.join(carpeta, "logros.json")
            g = GestorLogros(ruta)
            g.notificar("decision", decision="liberar")
            g.notificar("sicario_muere")
            g.notificar("nivel_superado", vidas_perdidas=0)
            otro = GestorLogros(ruta)
            self.assertIn("corazon_blando", otro.desbloqueados)
            self.assertIn("intachable", otro.desbloqueados)
            self.assertEqual(otro.sicarios, 1)
            with open(ruta, encoding="utf-8") as f:
                self.assertIn("desbloqueados", json.load(f))

    def test_textos_caben_en_la_pantalla(self):
        for logro in LOGROS:
            extra = f" ({SICARIOS_CAZADOR}/{SICARIOS_CAZADOR})" if logro.clave == "cazador" else ""
            self.assertLessEqual(len(logro.descripcion + extra), 34, logro.descripcion)
            self.assertLessEqual(len(logro.titulo), 31, logro.titulo)    # cabe en el aviso

    def test_hay_once_logros(self):
        self.assertEqual(len(LOGROS), 11)
        self.assertEqual(len({l.clave for l in LOGROS}), 11)


class TestIntegracion(unittest.TestCase):
    def setUp(self):
        self.juego = Juego(headless=True)

    def frames(self, n):
        for _ in range(n):
            self.juego.frame()

    def test_logro_muestra_aviso(self):
        self.juego.logros.notificar("decision", decision="extraditar")
        self.frames(2)
        self.assertEqual(self.juego.avisos[0][0].clave, "primera_extradicion")
        self.frames(int(4 * 60))
        self.assertEqual(self.juego.avisos, [])

    def test_alto_contraste_y_daltonismo_dibujan(self):
        self.juego.opciones.update(alto_contraste=True, daltonismo="tritanopia")
        self.juego.escenas.cambiar("nivel", numero=1)
        self.juego.escenas.aplicar_cambios()
        self.frames(30)                                        # dibuja con contornos y filtro

    def test_opciones_se_aplican_al_instante(self):
        self.juego.opciones["volumen_musica"] = 5             # no depender de config/opciones.json
        self.juego.aplicar_opciones()
        self.juego.escenas.cambiar("opciones")
        self.juego.escenas.aplicar_cambios()
        for _ in range(3):                                     # bajar a "Música" (4.ª opción)
            self.juego.entrada.simular(im.ABAJO)
            self.frames(2)
        antes = self.juego.audio.vol_musica
        self.juego.entrada.simular(im.DERECHA)
        self.frames(2)
        self.assertGreater(self.juego.audio.vol_musica, antes)

    def test_menu_tiene_logros(self):
        for _ in range(3):                                  # JUGAR, AYUDA, OPCIONES, LOGROS
            self.juego.entrada.simular(im.ABAJO)
            self.frames(2)
        self.juego.entrada.simular(im.CONFIRMAR)
        self.frames(2)
        self.assertEqual(type(self.juego.escenas.actual).__name__, "LogrosScene")
        self.frames(5)


if __name__ == "__main__":
    unittest.main()
