"""La intro: corre entera sin errores, no se puede saltar y entrega la voz y el himno al menú."""
import os
import unittest

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import pygame  # noqa: E402

import input_manager as im  # noqa: E402
import settings  # noqa: E402
from main import Juego  # noqa: E402
from render.texto import fuente  # noqa: E402
from scenes import intro  # noqa: E402


class TestIntro(unittest.TestCase):
    def setUp(self):
        self.juego = Juego(headless=True, escena_inicial="intro")

    def escena(self):
        return type(self.juego.escenas.actual).__name__

    def avanzar(self, segundos):
        for _ in range(int(segundos * settings.FPS)):
            self.juego.frame()

    def test_el_juego_normal_sigue_abriendo_en_el_menu_para_las_pruebas(self):
        self.assertEqual(type(Juego(headless=True).escenas.actual).__name__, "MenuScene")

    def test_corre_entera_y_termina_en_el_menu_con_el_himno(self):
        partes = set()
        for _ in range(int((intro.DURACION + 1) * settings.FPS)):
            if self.escena() != "IntroScene":
                break
            partes.add(self.juego.escenas.actual.parte()[0])
            self.juego.frame()
        self.assertEqual(partes, {nombre for nombre, _ in intro.PARTES})        # pasó por todas
        self.assertEqual(self.escena(), "MenuScene")
        self.assertEqual(self.juego.audio.voz_actual, "bienvenida")             # la frase se dijo en la intro
        self.assertEqual(self.juego.audio.tema_actual, "menu")                  # y después arrancó el himno

    def test_el_menu_no_repite_la_frase_si_ya_se_dijo_en_la_intro(self):
        self.avanzar(intro.DURACION - 1.0)                                      # ya habló el presidente
        self.assertTrue(self.juego.escenas.actual.voz_lanzada)
        self.juego.audio.voz_actual = None
        self.avanzar(1.5)
        self.assertEqual(self.escena(), "MenuScene")
        self.assertIsNone(self.juego.audio.voz_actual)

    def test_no_se_puede_saltar(self):
        self.avanzar(2.0)
        for accion in (im.CONFIRMAR, im.CANCELAR, im.PAUSA, im.SALTAR, im.DISPARAR):
            self.juego.entrada.simular(accion)
            self.avanzar(0.1)
        pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_q))
        pygame.event.post(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(10, 10)))
        self.avanzar(0.2)
        self.assertEqual(self.escena(), "IntroScene")

    def test_solo_sale_al_abrir_el_juego(self):
        """Ninguna pantalla lleva a la intro: al volver al menú desde una partida no se repite."""
        carpeta = os.path.join(settings.RUTA_BASE, "scenes")
        for archivo in os.listdir(carpeta):
            if archivo.endswith(".py") and archivo != "intro.py":
                with open(os.path.join(carpeta, archivo), encoding="utf-8") as f:
                    self.assertNotIn('"intro"', f.read(), archivo)

    def test_en_la_accion_el_presidente_derriba_a_todos(self):
        antes = sum(d for nombre, d in intro.PARTES[:[n for n, _ in intro.PARTES].index("accion")])
        self.avanzar(antes + 4.0)
        escena = self.juego.escenas.actual
        self.assertEqual(escena.parte()[0], "accion")
        self.assertTrue(escena._balas)
        self.avanzar(dict(intro.PARTES)["accion"] - 4.2)
        self.assertEqual(escena._enemigos, [])                                  # no quedó ninguno en pie

    def test_la_musica_se_apaga_poco_a_poco_antes_de_la_voz(self):
        antes = sum(d for nombre, d in intro.PARTES[:-1])
        self.avanzar(antes - 2.0)
        self.assertEqual(self.juego.audio.tema_actual, "jefe")                  # todavía suena la de la intro
        self.avanzar(1.5)                                                       # ya empezó a apagarse...
        self.assertIsNone(self.juego.audio.tema_actual)
        self.assertFalse(self.juego.escenas.actual.voz_lanzada)                 # ...y el presidente aún no habla
        self.assertGreater(intro.APAGADO_MUSICA, intro.MOMENTO_VOZ)

    def test_las_letras_gigantes_avanzan_pixeles_enteros_y_salen_de_la_pantalla(self):
        self.assertEqual(intro.VEL_FRASE % settings.FPS, 0)
        escena = self.juego.escenas.actual
        self.assertLessEqual(settings.ANCHO + escena.frase.get_width(), intro.VEL_FRASE * dict(intro.PARTES)["frase"])

    def test_los_textos_caben_en_la_pantalla(self):
        textos = [intro.TEXTO_AMENAZA, intro.TEXTO_ACCION, intro.NOMBRE_PRESIDENTE, intro.FRASE_PRESIDENTE]
        textos += [t for _, zona, hace, _ in intro.JEFES for t in (zona, hace)]
        for texto in textos:
            self.assertLessEqual(fuente(1).size(texto)[0], settings.ANCHO - 8, texto)
        self.assertLessEqual(fuente(2).size(intro.ROTULO)[0], settings.ANCHO - 8)


if __name__ == "__main__":
    unittest.main()
