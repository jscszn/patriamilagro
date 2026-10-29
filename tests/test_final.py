"""Pruebas de la pantalla final y de la visualización del árbol."""
import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame  # noqa: E402

import input_manager as im  # noqa: E402
from core.decision_tree import CAPTURAR, EXTRADITAR, LIBERAR, ArbolDecisiones  # noqa: E402
from main import Juego  # noqa: E402
from render import arbol_visual as av  # noqa: E402
from scenes.ending import AREA_ARBOL, MODOS, PAGINAS  # noqa: E402


class TestVisualizacionArbol(unittest.TestCase):
    def setUp(self):
        pygame.init()
        self.arbol = ArbolDecisiones()
        for d in (CAPTURAR, LIBERAR, EXTRADITAR):
            self.arbol.decidir(d)
        self.vis = av.arbol_completo(self.arbol)

    def test_copia_completa_no_modifica_la_partida(self):
        self.assertEqual(self.vis.cantidad_nodos(), 40)
        self.assertEqual(self.arbol.cantidad_nodos(), 4)            # la partida sigue con su camino
        self.assertEqual(self.vis.camino(), self.arbol.camino())

    def test_posiciones(self):
        pos = av.posiciones(self.vis, AREA_ARBOL)
        self.assertEqual(len(pos), 40)
        hojas = [pos[id(h)][0] for h in self.vis.hojas()]
        self.assertEqual(hojas, sorted(hojas))                      # hojas de izquierda a derecha
        self.assertTrue(all(AREA_ARBOL.left <= x <= AREA_ARBOL.right for x in hojas))
        for n in self.vis.preorden():
            if not n.es_hoja:                                       # cada padre centrado sobre sus hijos
                xs = [pos[id(h)][0] for h in n.hijos.values()]
                self.assertAlmostEqual(pos[id(n)][0], sum(xs) / len(xs))
            self.assertAlmostEqual(pos[id(n)][1], AREA_ARBOL.y + AREA_ARBOL.h * n.nivel / 3)

    def test_ruta_resaltada(self):
        ruta = av.ids_ruta(self.vis)
        self.assertEqual(len(ruta), 4)
        self.assertIn(id(self.vis.raiz), ruta)
        self.assertIn(id(self.vis.actual), ruta)

    def test_secuencias_de_los_recorridos(self):
        self.assertEqual(len(av.secuencia(self.vis, "preorden")), 40)
        self.assertEqual(len(av.secuencia(self.vis, "bfs")), 40)
        subida = av.secuencia(self.vis, "hoja_raiz")
        self.assertEqual([n.nivel for n in subida], [3, 2, 1, 0])   # camino(): de la hoja a la raíz


class TestPantallaFinal(unittest.TestCase):
    def setUp(self):
        self.juego = Juego(headless=True)
        p = self.juego.nueva_partida()
        for d in (EXTRADITAR, EXTRADITAR, EXTRADITAR):
            p.arbol.decidir(d)
        p.jefes_derrotados = ["A", "B", "C"]
        p.nivel = 3
        self.juego.escenas.cambiar("final")
        self.juego.escenas.aplicar_cambios()
        self.escena = self.juego.escenas.actual

    def paso(self, *pulsadas):
        self.escena.update(1 / 60, {1: im.EstadoAcciones(frozenset(), frozenset(pulsadas))})
        self.juego.escenas.aplicar_cambios()

    def test_final_y_conteo(self):
        self.assertEqual(self.escena.final.clave, "diplomatico")
        self.assertEqual(sum(self.escena.conteo_finales.values()), 27)
        self.assertEqual(len(self.escena.historial), 4)              # inicio + 3 decisiones

    def test_paginas_y_modos(self):
        self.paso(im.DERECHA)
        self.assertEqual(self.escena.pagina, 1)
        for i in range(len(MODOS)):
            self.assertEqual(self.escena.modo, i)
            self.escena.draw(self.juego.lienzo)                     # dibujar cada modo sin errores
            self.paso(im.ABAJO)
        self.assertEqual(self.escena.modo, 0)
        self.paso(im.IZQUIERDA)
        self.paso(im.IZQUIERDA)                                     # da la vuelta hasta la última
        self.assertEqual(self.escena.pagina, len(PAGINAS) - 1)
        for _ in PAGINAS:                                           # todas las páginas se dibujan
            self.escena.draw(self.juego.lienzo)
            self.paso(im.DERECHA)

    def test_animacion_avanza(self):
        self.escena.modo = 1                                         # preorden
        self.escena.t_modo = 0.0
        visitados, _ = self.escena.paso_animacion()
        self.assertEqual(len(visitados), 1)
        self.escena.t_modo = 0.12 * 10
        visitados, actual = self.escena.paso_animacion()
        self.assertEqual(len(visitados), 11)
        self.assertIs(actual, visitados[-1])

    def test_ninguna_pagina_invade_el_pie(self):
        """Peor caso: 3 jefes libres, los dos retenes de nombres más largos y jefes de nombre
        largo. Entre el contenido y la línea del pie quedan 2 filas vacías en todas las páginas."""
        from scenes.ending import LIMITE_CONTENIDO
        p = self.escena.partida
        p.jefes_derrotados = ["LA SOMBRA DE LA RAYA"] * 3
        p.mapa.jefes_libres = ["selva", "ciudad", "frontera"]
        p.mapa.retenes = [["caribe", "puerto"], ["casanare", "puerto"]]
        for n in (1, 2, 3):
            p.rutas[n] = {"clave": "segura", "peligro": 12, "refuerzos": 3}
        fondo = (8, 8, 24)
        for pagina in range(len(PAGINAS)):
            for modo in range(len(MODOS)) if PAGINAS[pagina] == "ÁRBOL" else (0,):
                self.escena.pagina, self.escena.modo, self.escena.t_modo = pagina, modo, 99.0
                self.escena.draw(self.juego.lienzo)
                for y in (LIMITE_CONTENIDO + 1, LIMITE_CONTENIDO + 2):
                    with self.subTest(pagina=PAGINAS[pagina], modo=modo, fila=y):
                        fila = {tuple(self.juego.lienzo.get_at((x, y)))[:3] for x in range(256)}
                        self.assertEqual(fila, {fondo})

    def test_sin_evidencia_en_pruebas_y_vuelve_al_menu(self):
        self.assertIsNone(self.escena.archivo_evidencia)
        for _ in range(100):
            self.paso()
        self.paso(im.CONFIRMAR)
        self.assertEqual(type(self.juego.escenas.actual).__name__, "MenuScene")
        self.assertIsNone(self.juego.partida)


if __name__ == "__main__":
    unittest.main()


class TestEvidencia(TestPantallaFinal):
    def test_guarda_imagen_y_json(self):
        import json
        import tempfile
        from scenes import ending
        with tempfile.TemporaryDirectory() as carpeta:
            original, ending.RUTA_CAPTURAS = ending.RUTA_CAPTURAS, carpeta
            try:
                png = self.escena.guardar_evidencia()
            finally:
                ending.RUTA_CAPTURAS = original
            self.assertTrue(os.path.isfile(png))
            self.assertEqual(pygame.image.load(png).get_size(), (256 * 4, 224 * 4))
            with open(png.replace(".png", ".json"), encoding="utf-8") as f:
                datos = json.load(f)
            self.assertEqual(datos["camino"], [EXTRADITAR] * 3)
            self.assertEqual(datos["final"], "PRESIDENTE DIPLOMÁTICO")
            self.assertEqual(len(datos["historial_opinion"]), 4)
