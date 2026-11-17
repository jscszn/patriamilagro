"""Textos que deben caber enteros en su recuadro: el aviso de logro y el mensaje fijado del chat."""
import itertools
import os
import unittest

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import pygame  # noqa: E402

import settings  # noqa: E402
from core import reportajes as rep  # noqa: E402
from core.decision_tree import DECISIONES  # noqa: E402
from core.logros import LOGROS  # noqa: E402
from core.news import INFLUENCERS  # noqa: E402
from main import Juego  # noqa: E402
from render.texto import fuente  # noqa: E402

JEFES = ["EL JAGUAR DEL MONTE", "DON CONCRETO", "LA SOMBRA DE LA RAYA"]
OPINION = {"medios": 50, "influencers": 50, "pueblo": 50}
PANTALLA = pygame.Rect(0, 0, settings.ANCHO, settings.ALTO)


class TestAvisoDeLogro(unittest.TestCase):
    """El aviso "¡LOGRO DESBLOQUEADO!" + título: los dos renglones dentro del recuadro."""

    @classmethod
    def setUpClass(cls):
        cls.juego = Juego(headless=True)

    def renglones(self, abajo: bool, titulo: str):
        caja, y_rotulo, y_titulo = Juego.caja_aviso(1.0, abajo)
        f = fuente(1)
        hechos = []
        for texto, y in (("¡LOGRO DESBLOQUEADO!", y_rotulo), (titulo, y_titulo)):
            ancho, alto = f.size(texto)
            sombra = 0 if abajo else 1                      # abajo se dibuja sin sombra
            hechos.append(pygame.Rect(128 - ancho // 2, y, ancho + sombra, alto + sombra))
        return caja, hechos

    def test_los_dos_renglones_caben_sin_tocar_el_borde(self):
        for abajo in (False, True):
            # arriba el marco es doble (borde, hueco y borde interior); abajo, de un solo trazo
            margen = 1 if abajo else 3
            for logro in LOGROS:
                caja, (rotulo, titulo) = self.renglones(abajo, logro.titulo)
                interior = caja.inflate(-2 * margen, -2 * margen)
                with self.subTest(abajo=abajo, logro=logro.titulo):
                    self.assertTrue(interior.contains(rotulo), (interior, rotulo))
                    self.assertTrue(interior.contains(titulo), (interior, titulo))
                    self.assertFalse(rotulo.colliderect(titulo))

    def test_el_aviso_entero_queda_dentro_de_la_pantalla(self):
        for abajo in (False, True):
            caja, _, _ = Juego.caja_aviso(1.0, abajo)
            self.assertTrue(PANTALLA.contains(caja), caja)

    def test_abajo_tapa_toda_la_linea_de_navegacion_del_final(self):
        """En la pantalla final el aviso va en el pie: lo cubre de lado a lado (antes dejaba
        asomar "< >" y "MENÚ" a los costados) y no sube sobre el contenido."""
        from scenes.ending import LIMITE_CONTENIDO
        caja, _, _ = Juego.caja_aviso(1.0, True)
        self.assertLessEqual(caja.left, 8)
        self.assertGreaterEqual(caja.right, 248)
        self.assertGreaterEqual(caja.top, LIMITE_CONTENIDO)

    def test_se_dibuja_de_verdad_sin_pintar_fuera_del_recuadro(self):
        """Dibuja cada aviso sobre un fondo liso y comprueba que solo cambió el recuadro."""
        fondo = (1, 2, 3)
        for abajo in (False, True):
            self.juego.escenas.actual.__class__.avisos_abajo = abajo
            try:
                for logro in LOGROS:
                    lienzo = pygame.Surface(PANTALLA.size)
                    lienzo.fill(fondo)
                    self.juego.avisos = [[logro, 2.0]]
                    self.juego._dibujar_avisos(lienzo)
                    caja, _, _ = Juego.caja_aviso(1.0, abajo)
                    fuera = [(x, y) for x in range(PANTALLA.w) for y in range(PANTALLA.h)
                             if not caja.collidepoint(x, y) and lienzo.get_at((x, y))[:3] != fondo]
                    self.assertEqual(fuera, [], (abajo, logro.titulo))
            finally:
                self.juego.escenas.actual.__class__.avisos_abajo = False
                self.juego.avisos = []


class TestMensajeFijado(unittest.TestCase):
    """Directo del influencer: el nombre de quien pregunta se lee entero en el mensaje fijado."""

    def setUp(self):
        from render import reportajes as esc
        self.vivo = esc.EnVivo(Juego(headless=True), ["jefe1", "jefe2", "jefe3"], 50)

    def preguntas(self):
        vistas = set()
        for camino in itertools.product(DECISIONES, repeat=3):
            for n in (1, 2, 3):
                seg, = rep.guion(list(camino[:n]), JEFES, OPINION, categorias=[INFLUENCERS])
                for linea in seg.lineas:
                    if linea.hablante.startswith("@") and (linea.nombre, linea.texto) not in vistas:
                        vistas.add((linea.nombre, linea.texto))
                        yield linea

    def test_el_nombre_cabe_dentro_del_mensaje_y_la_chincheta_no_lo_tapa(self):
        nombres = set()
        for linea in self.preguntas():
            self.vivo.fijado = (linea.nombre, linea.texto.upper())
            caja, nombre, chincheta = self.vivo.caja_fijado(), self.vivo.nombre_fijado(), self.vivo.chincheta_fijado()
            nombres.add(linea.nombre)
            with self.subTest(nombre=linea.nombre):
                self.assertTrue(caja.inflate(-2, -2).contains(nombre), (caja, nombre))   # dentro del borde
                self.assertFalse(nombre.colliderect(chincheta), (nombre, chincheta))
                self.assertFalse(caja.colliderect(chincheta))                           # va en la barra
                self.assertTrue(self.vivo.CHAT.contains(chincheta))
        self.assertIn("@GAMERPATRIOTA", nombres)             # el más largo: el que se cortaba

    def test_los_nombres_del_chat_caben_en_el_panel(self):
        from render import reportajes as esc
        f = fuente(1)
        autores = {a for _ap, mensajes in vars(esc.EnVivo).items() if isinstance(mensajes, (list, tuple, dict))
                   for a in self._autores(mensajes)}
        autores |= {linea.nombre for linea in self.preguntas()}
        self.assertGreaterEqual(len(autores), 5)
        for autor in autores:
            self.assertLessEqual(5 + f.size(autor)[0], self.vivo.CHAT.w - 1, autor)

    @staticmethod
    def _autores(dato):
        """Todos los textos que empiezan por @ dentro de una estructura cualquiera."""
        if isinstance(dato, str):
            return [dato] if dato.startswith("@") else []
        if isinstance(dato, dict):
            dato = list(dato.values())
        if isinstance(dato, (list, tuple)):
            return [a for d in dato for a in TestMensajeFijado._autores(d)]
        return []


if __name__ == "__main__":
    unittest.main()
