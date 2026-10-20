"""Pruebas de las noticias del teléfono (core/news.py)."""
import unittest

from core import news
from core.decision_tree import CAPTURAR, DECISIONES, EXTRADITAR, LIBERAR
from render.fuente_pixel import _ACENTOS, _G


class TestDatos(unittest.TestCase):
    def test_al_menos_3_variantes_por_categoria_y_decision(self):
        for decision in DECISIONES:
            for categoria in news.CATEGORIAS:
                with self.subTest(decision=decision, categoria=categoria):
                    self.assertGreaterEqual(len(news.NOTICIAS[decision]["normal"][categoria]), 3)

    def test_marcadores_validos(self):
        for texto in news.todos_los_textos():
            texto.format(jefe="X", lugar="Y", nivel=1)          # no debe lanzar KeyError

    def test_la_fuente_pixel_puede_dibujar_todo(self):
        permitidos = set(_G) | set(_ACENTOS)
        for texto in news.todos_los_textos():
            faltan = {c for c in texto.upper() if c not in permitidos and c not in "{}"}
            self.assertFalse(faltan, f"{texto!r} usa caracteres sin glifo: {faltan}")

    def test_nombres_de_autor_caben_en_la_tarjeta(self):
        autores = [a for lista in news.AUTORES.values() for a in lista] + [a for a, _ in news.entradas() if a]
        for autor in autores:
            self.assertLessEqual(len(autor), 14, autor)

    def test_hashtags_caben_en_una_linea(self):
        for lista in news.TENDENCIAS.values():
            for etiqueta in lista:
                self.assertLessEqual(len(etiqueta), 16, etiqueta)

    def test_textos_caben_en_el_telefono(self):
        for texto in news.todos_los_textos():
            self.assertLessEqual(len(texto.format(jefe="La Sombra De La Raya", lugar="la frontera", nivel=3)),
                                 100, texto)


class TestFeed(unittest.TestCase):
    def test_determinista(self):
        a = news.generar_feed([CAPTURAR], "El Jaguar")
        b = news.generar_feed([CAPTURAR], "El Jaguar")
        self.assertEqual([p.to_dict() for p in a], [p.to_dict() for p in b])

    def test_mezcla_las_tres_categorias_y_un_titular(self):
        feed = news.generar_feed([EXTRADITAR], "Don Concreto")
        categorias = {p.categoria for p in feed}
        self.assertTrue({news.MEDIOS, news.INFLUENCERS, news.PUEBLO} <= categorias)
        self.assertTrue(feed[0].destacada and feed[0].categoria == news.MEDIOS)
        self.assertEqual(sum(p.destacada for p in feed), 1)

    def test_cada_decision_tiene_su_titular(self):
        titulares = {d: news.generar_feed([d], "El Jaguar")[0].texto for d in DECISIONES}
        self.assertEqual(len(set(titulares.values())), 3)
        for d, titular in titulares.items():
            plantillas = [t.format(jefe="El Jaguar", lugar="la selva", nivel=1)
                          for t in news.NOTICIAS[d]["normal"][news.MEDIOS]]   # los titulares son textos simples
            self.assertIn(titular, plantillas)

    def test_contexto_segun_el_camino(self):
        self.assertEqual(news.contexto_de([LIBERAR]), "normal")
        self.assertEqual(news.contexto_de([LIBERAR, LIBERAR]), "reincidente")
        self.assertEqual(news.contexto_de([LIBERAR, EXTRADITAR, LIBERAR]), "reincidente")
        self.assertEqual(news.contexto_de([LIBERAR, CAPTURAR]), "rectifica")
        self.assertEqual(news.contexto_de([CAPTURAR, CAPTURAR]), "racha")
        self.assertEqual(news.contexto_de([EXTRADITAR, CAPTURAR]), "normal")

    def test_liberar_por_segunda_vez_es_mas_duro(self):
        primera = news.generar_feed([LIBERAR], "Don Concreto")[0].texto
        segunda = news.generar_feed([LIBERAR, LIBERAR], "Don Concreto")[0].texto
        duros = [t.format(jefe="Don Concreto", lugar="la ciudad", nivel=2)
                 for t in news.NOTICIAS[LIBERAR]["reincidente"][news.MEDIOS]]
        self.assertIn(segunda, duros)
        self.assertNotIn(primera, duros)

    def test_usa_nombre_del_jefe_y_lugar(self):
        feed = news.generar_feed([CAPTURAR, EXTRADITAR, CAPTURAR], "La Sombra")
        texto = " ".join(p.texto for p in feed)
        self.assertIn("La Sombra", texto)
        self.assertNotIn("{", texto)


if __name__ == "__main__":
    unittest.main()


class TestAutores(unittest.TestCase):
    def test_autores_al_azar_no_se_repiten_en_un_feed(self):
        from core.decision_tree import DECISIONES
        for d in DECISIONES:
            feed = news.generar_feed([d], "El Jaguar")
            for categoria in (news.MEDIOS, news.INFLUENCERS):
                autores = [p.autor for p in feed if p.categoria == categoria]
                self.assertEqual(len(autores), len(set(autores)), (d, categoria, autores))
