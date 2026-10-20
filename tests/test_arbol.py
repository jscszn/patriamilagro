"""Pruebas unitarias del árbol de decisiones (core/decision_tree.py)."""
import unittest

from core.decision_tree import (CAPTURAR, CATEGORIAS, DECISIONES, EXTRADITAR, FINALES, LIBERAR,
                                ArbolDecisiones, final_de)


class TestEstructura(unittest.TestCase):
    def setUp(self):
        self.arbol = ArbolDecisiones()

    def test_raiz_con_opinion_inicial(self):
        raiz = self.arbol.raiz
        self.assertEqual(raiz.nivel, 0)
        self.assertIsNone(raiz.decision)
        self.assertIsNone(raiz.padre)
        self.assertEqual(raiz.opinion, {"medios": 50, "influencers": 50, "pueblo": 50})
        self.assertIs(self.arbol.actual, raiz)

    def test_decidir_inserta_hijo_y_avanza(self):
        nodo = self.arbol.decidir(CAPTURAR)
        self.assertIs(self.arbol.raiz.hijos[CAPTURAR], nodo)
        self.assertIs(nodo.padre, self.arbol.raiz)
        self.assertEqual(nodo.nivel, 1)
        self.assertIs(self.arbol.actual, nodo)
        self.assertEqual(self.arbol.cantidad_nodos(), 2)

    def test_insertar_no_duplica(self):
        a = self.arbol.insertar(self.arbol.raiz, EXTRADITAR)
        b = self.arbol.insertar(self.arbol.raiz, EXTRADITAR)
        self.assertIs(a, b)
        self.assertEqual(len(self.arbol.raiz.hijos), 1)

    def test_maximo_tres_hijos_por_nodo(self):
        for d in DECISIONES:
            self.arbol.insertar(self.arbol.raiz, d)
        self.assertEqual(len(self.arbol.raiz.hijos), 3)
        with self.assertRaises(ValueError):
            self.arbol.insertar(self.arbol.raiz, "perdonar")

    def test_no_se_decide_despues_del_nivel_3(self):
        for d in (CAPTURAR, LIBERAR, EXTRADITAR):
            self.arbol.decidir(d)
        self.assertTrue(self.arbol.terminado)
        with self.assertRaises(ValueError):
            self.arbol.decidir(CAPTURAR)

    def test_arbol_completo_tiene_27_hojas(self):
        self.arbol.construir_completo()
        self.assertEqual(self.arbol.cantidad_nodos(), 1 + 3 + 9 + 27)
        self.assertEqual(len(self.arbol.hojas()), 27)
        self.assertEqual(self.arbol.altura(), 3)
        self.assertIs(self.arbol.actual, self.arbol.raiz)   # construir no mueve la partida
        caminos = {tuple(h.camino()) for h in self.arbol.hojas()}
        self.assertEqual(len(caminos), 27)

    def test_reiniciar(self):
        self.arbol.decidir(CAPTURAR)
        self.arbol.decidir(LIBERAR)
        self.arbol.reiniciar()
        self.assertIs(self.arbol.actual, self.arbol.raiz)
        self.assertEqual(self.arbol.cantidad_nodos(), 1)
        self.assertEqual(self.arbol.camino(), [])


class TestRecorridos(unittest.TestCase):
    def setUp(self):
        self.arbol = ArbolDecisiones()
        r = self.arbol.raiz
        cap = self.arbol.insertar(r, CAPTURAR)
        self.arbol.insertar(r, LIBERAR)
        self.arbol.insertar(cap, EXTRADITAR)
        self.arbol.insertar(cap, CAPTURAR)

    def nombres(self, nodos):
        return ["/".join(n.camino()) or "raiz" for n in nodos]

    def test_preorden(self):
        self.assertEqual(self.nombres(self.arbol.preorden()),
                         ["raiz", "capturar", "capturar/capturar", "capturar/extraditar", "liberar"])

    def test_bfs(self):
        self.assertEqual(self.nombres(self.arbol.bfs()),
                         ["raiz", "capturar", "liberar", "capturar/capturar", "capturar/extraditar"])

    def test_camino_de_hoja_a_raiz(self):
        self.arbol.decidir(LIBERAR)
        self.arbol.decidir(CAPTURAR)
        self.arbol.decidir(EXTRADITAR)
        self.assertEqual(self.arbol.camino(), [LIBERAR, CAPTURAR, EXTRADITAR])


class TestEfectos(unittest.TestCase):
    def test_opinion_siempre_entre_0_y_100(self):
        arbol = ArbolDecisiones()
        arbol.construir_completo()
        for nodo in arbol.preorden():
            for c in CATEGORIAS:
                self.assertTrue(0 <= nodo.opinion[c] <= 100, nodo)

    def test_limites_con_efectos_extremos(self):
        extremos = {d: {c: 80 for c in CATEGORIAS} for d in DECISIONES}
        extremos[LIBERAR] = {c: -80 for c in CATEGORIAS}
        arbol = ArbolDecisiones(efectos_base=extremos, ajustes_nivel={}, combinados={})
        self.assertEqual(arbol.decidir(CAPTURAR).opinion["pueblo"], 100)
        arbol.reiniciar()
        self.assertEqual(arbol.decidir(LIBERAR).opinion["pueblo"], 0)

    def test_efectos_son_acumulativos(self):
        arbol = ArbolDecisiones()
        n1 = arbol.decidir(CAPTURAR)
        cambio = arbol.efecto(n1, EXTRADITAR)
        n2 = arbol.decidir(EXTRADITAR)
        for c in CATEGORIAS:
            self.assertEqual(n2.opinion[c], max(0, min(100, n1.opinion[c] + cambio[c])))

    def test_el_nivel_modula_el_efecto(self):
        arbol = ArbolDecisiones(combinados={})
        nivel1 = arbol.efecto(arbol.raiz, CAPTURAR)
        n2 = arbol.insertar(arbol.insertar(arbol.raiz, EXTRADITAR), EXTRADITAR)   # padre en nivel 2
        nivel3 = arbol.efecto(n2, CAPTURAR)
        self.assertGreater(nivel3["pueblo"], nivel1["pueblo"])

    def test_liberar_dos_veces_empeora_mas(self):
        arbol = ArbolDecisiones()
        tras_capturar = arbol.insertar(arbol.raiz, CAPTURAR)
        tras_liberar = arbol.insertar(arbol.raiz, LIBERAR)
        normal = arbol.efecto(tras_capturar, LIBERAR)
        reincidente = arbol.efecto(tras_liberar, LIBERAR)
        for c in CATEGORIAS:
            self.assertLess(reincidente[c], normal[c])

    def test_efectos_configurables(self):
        propios = {CAPTURAR: {"medios": 1, "influencers": 1, "pueblo": 1},
                   EXTRADITAR: {}, LIBERAR: {}}
        arbol = ArbolDecisiones(efectos_base=propios, peso_nivel={1: 1}, ajustes_nivel={}, combinados={})
        self.assertEqual(arbol.decidir(CAPTURAR).opinion, {"medios": 51, "influencers": 51, "pueblo": 51})


class TestFinales(unittest.TestCase):
    def setUp(self):
        self.arbol = ArbolDecisiones()
        self.arbol.construir_completo()

    def test_cada_hoja_tiene_final(self):
        claves = {final_de(h).clave for h in self.arbol.hojas()}
        self.assertTrue(claves <= {f.clave for f in FINALES})

    def test_todos_los_finales_son_alcanzables(self):
        claves = {final_de(h).clave for h in self.arbol.hojas()}
        self.assertEqual(claves, {f.clave for f in FINALES})

    def test_finales_esperados(self):
        def final(*camino):
            nodo = self.arbol.raiz
            for d in camino:
                nodo = nodo.hijos[d]
            return final_de(nodo).clave
        self.assertEqual(final(LIBERAR, LIBERAR, LIBERAR), "cuestionado")
        self.assertEqual(final(CAPTURAR, CAPTURAR, CAPTURAR), "mano_dura")
        self.assertEqual(final(EXTRADITAR, EXTRADITAR, EXTRADITAR), "diplomatico")


class TestSerializacion(unittest.TestCase):
    def test_ida_y_vuelta(self):
        arbol = ArbolDecisiones()
        arbol.decidir(CAPTURAR)
        arbol.decidir(LIBERAR)
        arbol.insertar(arbol.raiz, EXTRADITAR)
        copia = ArbolDecisiones.from_dict(arbol.to_dict())
        self.assertEqual(copia.to_dict(), arbol.to_dict())
        self.assertEqual(copia.camino(), [CAPTURAR, LIBERAR])
        self.assertEqual(copia.opinion(), arbol.opinion())
        self.assertIs(copia.actual.padre.padre, copia.raiz)


if __name__ == "__main__":
    unittest.main()
