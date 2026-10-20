"""El cargador de sprites usa el PNG si existe y, si no, el placeholder dibujado por código."""
import json
import os
import shutil
import tempfile
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame  # noqa: E402

import settings  # noqa: E402
from render.sprites import GestorSprites  # noqa: E402


class TestSprites(unittest.TestCase):
    def setUp(self):
        pygame.init()
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_sin_png_usa_placeholder(self):
        gestor = GestorSprites(os.path.join(self.tmp, "no_existe.json"))
        self.assertEqual(gestor.frame("jugador", "quieto", 0).get_size(), (16, 24))
        for pose in ("quieto", "disparar", "correr", "saltar", "agachado", "arriba", "diag_arriba", "diag_abajo", "abajo", "herido"):
            self.assertIn(pose, gestor.animaciones("jugador"))

    def test_png_reemplaza_y_variantes_usan_su_base(self):
        # Hoja de 2 cuadros de 20x30: rojo (quieto) y verde (correr)
        hoja = pygame.Surface((40, 30), pygame.SRCALPHA)
        hoja.fill((255, 0, 0), (0, 0, 20, 30))
        hoja.fill((0, 255, 0), (20, 0, 20, 30))
        ruta_png = os.path.join(settings.RUTA_ASSETS, "sprites", "_prueba.png")
        pygame.image.save(hoja, ruta_png)
        try:
            ruta_json = os.path.join(self.tmp, "sprites.json")
            with open(ruta_json, "w") as f:
                json.dump({"jugador": {"archivo": "sprites/_prueba.png", "frame": [20, 30],
                                       "animaciones": {"quieto": [0], "correr": [1]}}}, f)
            gestor = GestorSprites(ruta_json)
            self.assertEqual(gestor.frame("jugador", "quieto", 0).get_at((5, 5))[:3], (255, 0, 0))
            self.assertEqual(gestor.frame("jugador", "correr", 0).get_at((5, 5))[:3], (0, 255, 0))
            # Pose que el PNG no trae: usa el "quieto" del PNG, nunca el placeholder
            self.assertEqual(gestor.frame("jugador", "diag_arriba", 0).get_at((5, 5))[:3], (255, 0, 0))
            # Sin placeholders mezclados: "agachado" se deriva aplastando el "quieto" del PNG
            agachado = gestor.frame("jugador", "agachado", 0)
            self.assertEqual(agachado.get_size(), (20, 18))
            self.assertEqual(agachado.get_at((5, 5))[:3], (255, 0, 0))
        finally:
            os.remove(ruta_png)


if __name__ == "__main__":
    unittest.main()
