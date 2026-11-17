"""La música grabada (tools/grabar_musica.py): existe, está al día y evita sintetizar al iniciar.

Sintetizar la música al arrancar llevaba el proceso a ~840 MB (y en la web, la memoria del
navegador no se reduce). Con los OGG grabados el juego no sintetiza ningún tema.
"""
import json
import os
import sys
import unittest

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))

import pygame  # noqa: E402

import grabar_musica  # noqa: E402
from audio import gestor, sintesis  # noqa: E402


class TestMusicaGrabada(unittest.TestCase):
    def test_hay_un_ogg_por_cada_tema_y_jingle(self):
        for nombre in grabar_musica.nombres():
            self.assertTrue(os.path.isfile(grabar_musica.ruta_de(nombre)), f"falta musica_{nombre}.ogg")

    def test_la_grabacion_esta_al_dia_con_el_codigo(self):
        """Si se cambian las notas o la síntesis, hay que volver a correr tools/grabar_musica.py."""
        with open(grabar_musica.RUTA_HUELLA, encoding="utf-8") as f:
            guardada = json.load(f)
        self.assertEqual(guardada["huella"], grabar_musica.huella(),
                         "la música cambió: corre python tools/grabar_musica.py")
        self.assertEqual(guardada["temas"], grabar_musica.nombres())

    def test_con_los_archivos_no_se_sintetiza_ningun_tema(self):
        llamadas = []
        tema, jingle = sintesis.tema, sintesis.jingle
        sintesis.tema = lambda *a, **k: llamadas.append(a) or tema(*a, **k)
        sintesis.jingle = lambda *a, **k: llamadas.append(a) or jingle(*a, **k)
        try:
            pygame.init()
            audio = gestor.Audio({"volumen_musica": 5, "volumen_efectos": 5}, activo=True)
            if not audio.activo:
                self.skipTest("sin mezclador de audio en este equipo")
            audio.precargar()
            self.assertEqual(llamadas, [], "se sintetizó música aunque existe el OGG grabado")
            for nombre in grabar_musica.nombres():
                sonido = audio._tema(nombre)
                self.assertIsNotNone(sonido)
                self.assertGreater(sonido.get_length(), 1.0, nombre)
        finally:
            sintesis.tema, sintesis.jingle = tema, jingle


if __name__ == "__main__":
    unittest.main()
