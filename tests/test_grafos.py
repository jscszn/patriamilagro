"""Grafo: la estructura genérica, el mapa del país y su unión con el árbol de decisiones."""
import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

from core.decision_tree import CAPTURAR, CATEGORIAS, EXTRADITAR, LIBERAR, ArbolDecisiones  # noqa: E402
from core.grafo import INFINITO, Grafo  # noqa: E402
from core.mapa import CORTA, OPINION_POR_TRAMO, PALACIO, SEGURA, ZONA_NIVEL, Mapa  # noqa: E402
from core.partida import PENALIZACION_REVOCAR, Partida  # noqa: E402


def rombo() -> Grafo:
    """a-b 1, a-c 4, b-c 1, b-d 5, c-d 1  y un vértice suelto e."""
    g = Grafo()
    for a, b, peso in (("a", "b", 1), ("a", "c", 4), ("b", "c", 1), ("b", "d", 5), ("c", "d", 1)):
        g.agregar_arista(a, b, peso)
    g.agregar_vertice("e")
    return g


class TestGrafo(unittest.TestCase):
    def test_insertar_vertices_y_aristas(self):
        g = rombo()
        self.assertEqual(len(g), 5)
        self.assertEqual(len(g.aristas()), 5)                 # no dirigido: cada arista una vez
        self.assertTrue(g.hay_arista("b", "a"))               # y vale en los dos sentidos
        self.assertEqual(g.grado("b"), 3)
        self.assertEqual(sorted(g.vecinos("c")), ["a", "b", "d"])

    def test_dirigido_solo_va_en_un_sentido(self):
        g = Grafo(dirigido=True)
        g.agregar_arista("a", "b", 0.5)
        self.assertTrue(g.hay_arista("a", "b"))
        self.assertFalse(g.hay_arista("b", "a"))

    def test_eliminar_arista(self):
        g = rombo()
        self.assertTrue(g.eliminar_arista("b", "c"))
        self.assertFalse(g.hay_arista("c", "b"))
        self.assertFalse(g.eliminar_arista("b", "c"))         # ya no existe
        self.assertEqual(g.camino_mas_barato("a", "d"), (5.0, ["a", "c", "d"]))

    def test_eliminar_vertice_quita_sus_aristas(self):
        g = rombo()
        self.assertEqual(g.eliminar_vertice("c"), 3)
        self.assertNotIn("c", g)
        self.assertTrue(all("c" not in (a, b) for a, b, _ in g.aristas()))
        self.assertEqual(g.camino_mas_barato("a", "d"), (6.0, ["a", "b", "d"]))
        with self.assertRaises(KeyError):
            g.eliminar_vertice("c")

    def test_eliminar_vertice_en_grafo_dirigido(self):
        g = Grafo(dirigido=True)
        g.agregar_arista("a", "b")
        g.agregar_arista("b", "c")
        g.agregar_arista("c", "b")
        self.assertEqual(g.eliminar_vertice("b"), 3)          # 1 que salía y 2 que llegaban
        self.assertEqual(g.aristas(), [])

    def test_bfs_por_olas_y_saltos(self):
        g = rombo()
        self.assertEqual(g.bfs_por_olas(["a"]), [["a"], ["b", "c"], ["d"]])
        self.assertEqual(g.bfs("a"), ["a", "b", "c", "d"])
        self.assertEqual(g.saltos("a"), {"a": 0, "b": 1, "c": 1, "d": 2})
        self.assertNotIn("e", g.saltos("a"))                  # inalcanzable

    def test_camino_con_menos_saltos_ignora_los_pesos(self):
        g = rombo()
        self.assertEqual(g.camino_con_menos_saltos("a", "d"), ["a", "b", "d"])       # 2 saltos, costo 6
        self.assertEqual(g.costo_de(["a", "b", "d"]), 6.0)
        self.assertEqual(g.camino_mas_barato("a", "d")[1], ["a", "b", "c", "d"])       # Dijkstra: 3 saltos, costo 3
        self.assertEqual(g.camino_con_menos_saltos("a", "a"), ["a"])
        self.assertEqual(g.camino_con_menos_saltos("a", "e"), [])                     # inalcanzable
        self.assertEqual(g.camino_con_menos_saltos("a", "zzz"), [])

    def test_dfs_va_a_lo_profundo(self):
        g = Grafo()
        for a, b in (("r", "a"), ("r", "b"), ("a", "c"), ("c", "d")):
            g.agregar_arista(a, b)
        self.assertEqual(list(g.dfs("r")), ["r", "a", "c", "d", "b"])

    def test_dijkstra_no_es_el_camino_con_menos_saltos(self):
        g = rombo()
        self.assertEqual(g.camino_mas_barato("a", "d"), (3.0, ["a", "b", "c", "d"]))   # 3 saltos, costo 3
        self.assertEqual(g.saltos("a")["d"], 2)                                          # hay uno de 2 saltos
        self.assertEqual(g.camino_mas_barato("a", "e"), (INFINITO, []))

    def test_cambiar_peso_cambia_la_ruta(self):
        g = rombo()
        g.cambiar_peso("b", "c", 9)
        self.assertEqual(g.camino_mas_barato("a", "d"), (5.0, ["a", "c", "d"]))
        with self.assertRaises(KeyError):
            g.cambiar_peso("a", "d", 1)

    def test_componentes(self):
        g = rombo()
        self.assertEqual(sorted(len(c) for c in g.componentes()), [1, 4])
        g.eliminar_vertice("b")
        g.eliminar_vertice("c")
        self.assertEqual(len(g.componentes()), 3)             # a, d y e quedaron aislados

    def test_serializacion(self):
        g = rombo()
        g.agregar_vertice("a", nombre="Inicio")
        copia = Grafo.from_dict(g.to_dict())
        self.assertEqual(copia.to_dict(), g.to_dict())
        self.assertEqual(copia.datos["a"]["nombre"], "Inicio")


class TestMapa(unittest.TestCase):
    def test_rutas_base(self):
        m = Mapa(con_retenes=False)
        self.assertEqual(m.ruta(1), (3.0, [PALACIO, "llanos", "selva"]))
        for nivel, zona in ZONA_NIVEL.items():
            costo, ruta = m.ruta(nivel)
            self.assertEqual((ruta[0], ruta[-1]), (PALACIO, zona))
            self.assertEqual(costo, m.costo_base[nivel])
            self.assertEqual(m.peligro(nivel), 0)             # mapa limpio: sin refuerzos extra

    def test_influencia_del_jefe_por_olas(self):
        olas = Mapa(con_retenes=False).influencia(1)
        self.assertEqual(olas[0], ["selva"])
        self.assertEqual(sorted(olas[1]), ["capital", "ciudad", "desierto", "llanos"])
        self.assertEqual(len(olas), 3)                        # hasta 2 saltos

    def test_liberar_empeora_y_capturar_calma(self):
        m = Mapa(con_retenes=False)
        antes = m.grafo.peso("llanos", "selva")
        m.aplicar_decision(1, LIBERAR)
        self.assertEqual(m.grafo.peso("llanos", "selva"), antes + 2)
        self.assertEqual(m.jefes_cerca(2), ["selva"])         # la ciudad está a 1 salto de la selva
        self.assertGreaterEqual(m.peligro(2), 1)
        otro = Mapa(con_retenes=False)
        otro.aplicar_decision(1, CAPTURAR)
        self.assertEqual(otro.grafo.peso("llanos", "selva"), antes - 1)
        self.assertEqual(otro.peligro(2), 0)

    def test_extraditar_trae_represalias_en_otra_via(self):
        m = Mapa(semilla=4, con_retenes=False)
        antes = {(a, b): p for a, b, p in m.grafo.aristas()}
        cambios = m.aplicar_decision(2, EXTRADITAR)
        subieron = [(a, b) for a, b, p in m.grafo.aristas() if p > antes[(a, b)]]
        self.assertEqual(len(subieron), 1)
        self.assertNotIn("ciudad", subieron[0])
        self.assertEqual(len(cambios), 2)

    def test_retenes_al_azar_cambian_entre_partidas(self):
        distintos = {tuple(map(tuple, Mapa(semilla=s).retenes)) for s in range(1, 12)}
        self.assertGreater(len(distintos), 3)
        self.assertEqual(Mapa(semilla=5).retenes, Mapa(semilla=5).retenes)   # misma semilla, mismo mapa

    def test_los_refuerzos_tienen_tope_por_nivel(self):
        m = Mapa(con_retenes=False)
        for a, b, _ in m.grafo.aristas():
            m.grafo.cambiar_peso(a, b, 30)                    # todo el país en llamas
        self.assertEqual(m.peligro(1), 1)                     # el nivel 1 nunca pasa de +1
        self.assertEqual(m.peligro(2), 2)
        self.assertEqual(m.peligro(3), 3)

    def test_dos_rutas_con_dos_algoritmos(self):
        """SEGURA = Dijkstra (menos peligro); CORTA = BFS (menos tramos). En los 3 niveles son
        distintas: la corta tiene menos tramos y más peligro."""
        m = Mapa(con_retenes=False)
        for nivel, zona in ZONA_NIVEL.items():
            with self.subTest(nivel=nivel):
                r = m.rutas(nivel)
                self.assertEqual(set(r), {SEGURA, CORTA})
                for ruta in r.values():
                    self.assertEqual((ruta["camino"][0], ruta["camino"][-1]), (PALACIO, zona))
                    self.assertEqual(ruta["peligro"], m.grafo.costo_de(ruta["camino"]))
                    self.assertEqual(ruta["tramos"], len(ruta["camino"]) - 1)
                self.assertEqual(r[SEGURA]["peligro"], m.grafo.camino_mas_barato(PALACIO, zona)[0])
                self.assertEqual(r[CORTA]["tramos"], m.grafo.saltos(PALACIO)[zona])
                self.assertLess(r[CORTA]["tramos"], r[SEGURA]["tramos"])
                self.assertGreater(r[CORTA]["peligro"], r[SEGURA]["peligro"])

    def test_cada_ruta_tiene_su_costo(self):
        """La corta trae más refuerzos; la segura llega tarde y cuesta opinión del pueblo."""
        r = Mapa(con_retenes=False).rutas(1)
        self.assertEqual(r[SEGURA]["camino"], [PALACIO, "llanos", "selva"])
        self.assertEqual(r[CORTA]["camino"], [PALACIO, "selva"])
        self.assertEqual((r[SEGURA]["refuerzos"], r[CORTA]["refuerzos"]), (0, 1))
        self.assertEqual(r[SEGURA]["opinion"], {"pueblo": -OPINION_POR_TRAMO})      # 1 tramo de más
        self.assertEqual(r[CORTA]["opinion"], {"pueblo": 0})

    def test_si_la_corta_no_es_mas_corta_solo_hay_una_ruta(self):
        m = Mapa(con_retenes=False)
        m.grafo.cambiar_peso("capital", "selva", 1)           # ahora la directa también es la segura
        r = m.rutas(1)
        self.assertEqual(list(r), [SEGURA])
        self.assertEqual(r[SEGURA]["camino"], [PALACIO, "selva"])
        self.assertEqual(r[SEGURA]["opinion"], {"pueblo": 0})

    def test_las_decisiones_cambian_las_rutas(self):
        m = Mapa(con_retenes=False)
        antes = m.rutas(2)[SEGURA]
        m.aplicar_decision(1, LIBERAR)                        # el Jaguar libre: +2 en las vías de la selva
        despues = m.rutas(2)[SEGURA]
        self.assertGreater(despues["refuerzos"], antes["refuerzos"])   # jefe libre a 1 salto de la ciudad
        self.assertNotIn("selva", despues["camino"])          # Dijkstra evita la zona que empeoró

    def test_serializacion(self):
        m = Mapa(semilla=3)
        m.aplicar_decision(1, LIBERAR)
        copia = Mapa.from_dict(m.to_dict())
        self.assertEqual(copia.to_dict(), m.to_dict())
        self.assertEqual(copia.peligro(2), m.peligro(2))
        liviano = Mapa.from_dict(m.to_dict(con_azar=False))   # lo que recibe un cliente en red
        self.assertEqual(liviano.rutas(3), m.rutas(3))


class TestDibujoDelMapa(unittest.TestCase):
    """Las posiciones de core/mapa.py -> ZONAS se eligieron para que las rutas no se enreden."""

    @staticmethod
    def puntos(alto=78.0):
        from core.mapa import ZONAS
        return {z: (x, fila * alto / 2) for z, (_, (x, fila)) in ZONAS.items()}

    def test_ninguna_via_cruza_otra(self):
        from core.mapa import VIAS
        p = self.puntos()

        def lado(a, b, c):
            return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
        for i, (a, b, _) in enumerate(VIAS):
            for c, d, _ in VIAS[i + 1:]:
                if len({a, b, c, d}) < 4:
                    continue                                    # comparten una zona: no se cruzan
                with self.subTest(via=(a, b), otra=(c, d)):
                    cruzan = lado(p[a], p[b], p[c]) * lado(p[a], p[b], p[d]) < 0 and \
                        lado(p[c], p[d], p[a]) * lado(p[c], p[d], p[b]) < 0
                    self.assertFalse(cruzan)

    def test_la_ruta_segura_y_la_corta_se_separan_a_la_vista(self):
        import math
        p = self.puntos()

        def angulo(o, u, w):
            d = abs(math.degrees(math.atan2(p[u][1] - p[o][1], p[u][0] - p[o][0]) -
                                 math.atan2(p[w][1] - p[o][1], p[w][0] - p[o][0]))) % 360
            return min(d, 360 - d)
        for semilla in range(40):
            m = Mapa(semilla)
            for nivel in ZONA_NIVEL:
                rutas = m.rutas(nivel)
                if CORTA not in rutas:
                    continue
                s, c = rutas[SEGURA]["camino"], rutas[CORTA]["camino"]
                i = 0
                while s[i + 1] == c[i + 1]:
                    i += 1                                      # tramo compartido
                self.assertGreaterEqual(angulo(s[i], s[i + 1], c[i + 1]), 15)    # al separarse
                self.assertGreaterEqual(angulo(s[-1], s[-2], c[-2]), 15)         # al llegar


class TestArbolEliminar(unittest.TestCase):
    def test_eliminar_quita_el_subarbol(self):
        arbol = ArbolDecisiones()
        arbol.construir_completo()
        self.assertEqual(arbol.cantidad_nodos(), 40)
        rama = arbol.raiz.hijos[CAPTURAR]
        self.assertEqual(arbol.eliminar(rama), 13)            # 1 + 3 + 9
        self.assertEqual(arbol.cantidad_nodos(), 27)
        self.assertNotIn(CAPTURAR, arbol.raiz.hijos)
        self.assertEqual(len(arbol.hojas()), 18)
        self.assertIsNone(rama.padre)

    def test_eliminar_una_hoja(self):
        arbol = ArbolDecisiones()
        arbol.construir_completo()
        self.assertEqual(arbol.eliminar(arbol.hojas()[0]), 1)
        self.assertEqual(arbol.cantidad_nodos(), 39)

    def test_no_se_elimina_la_raiz_ni_un_nodo_ajeno(self):
        arbol, otro = ArbolDecisiones(), ArbolDecisiones()
        with self.assertRaises(ValueError):
            arbol.eliminar(arbol.raiz)
        arbol.decidir(CAPTURAR)
        ajeno = otro.decidir(CAPTURAR)
        with self.assertRaises(ValueError):
            arbol.eliminar(ajeno)

    def test_si_la_partida_estaba_dentro_sube_al_padre(self):
        arbol = ArbolDecisiones()
        primero = arbol.decidir(CAPTURAR)
        arbol.decidir(LIBERAR)
        arbol.eliminar(primero)
        self.assertIs(arbol.actual, arbol.raiz)
        self.assertEqual(arbol.camino(), [])

    def test_revocar_deja_volver_a_decidir(self):
        arbol = ArbolDecisiones()
        arbol.decidir(EXTRADITAR)
        arbol.decidir(LIBERAR)
        self.assertEqual(arbol.revocar(), LIBERAR)
        self.assertEqual(arbol.camino(), [EXTRADITAR])
        arbol.decidir(CAPTURAR)                                # se inserta otra vez en ese lugar
        self.assertEqual(arbol.camino(), [EXTRADITAR, CAPTURAR])
        self.assertEqual(arbol.cantidad_nodos(), 3)
        self.assertIsNone(ArbolDecisiones().revocar())         # en la raíz no hay nada que revocar

    def test_ajustar_se_guarda_y_lo_heredan_los_hijos(self):
        arbol = ArbolDecisiones()
        nodo = arbol.decidir(CAPTURAR)
        base = dict(nodo.opinion)
        arbol.ajustar(nodo, {"pueblo": -5, "medios": 300})     # se limita a 100
        self.assertEqual(nodo.opinion["pueblo"], base["pueblo"] - 5)
        self.assertEqual(nodo.opinion["medios"], 100)
        self.assertEqual(nodo.ajuste["medios"], 100 - base["medios"])
        hijo = arbol.decidir(CAPTURAR)
        efecto = arbol.efecto(nodo, CAPTURAR)
        self.assertEqual(hijo.opinion["pueblo"], min(100, nodo.opinion["pueblo"] + efecto["pueblo"]))
        copia = ArbolDecisiones.from_dict(arbol.to_dict())
        self.assertEqual(copia.raiz.hijos[CAPTURAR].ajuste, nodo.ajuste)


class TestPartidaUneArbolYGrafo(unittest.TestCase):
    def test_decidir_inserta_en_el_arbol_y_cambia_el_mapa(self):
        p = Partida(semilla=3)
        antes = p.mapa.grafo.peso("llanos", "selva")
        p.decidir(LIBERAR)
        self.assertEqual(p.arbol.camino(), [LIBERAR])
        self.assertEqual(p.mapa.grafo.peso("llanos", "selva"), antes + 2)
        self.assertTrue(p.cambios_mapa)
        self.assertGreaterEqual(p.peligro(2), 1)               # más refuerzos en el nivel siguiente

    def test_la_opinion_sale_solo_del_arbol(self):
        """Sin red social: la opinión tras decidir es exactamente la del árbol puro."""
        for semilla in (1, 2, 3):
            p, puro = Partida(semilla=semilla), ArbolDecisiones()
            for nivel, decision in enumerate((CAPTURAR, LIBERAR, EXTRADITAR), start=1):
                p.nivel = nivel
                p.decidir(decision)
                puro.decidir(decision)
            self.assertEqual(p.arbol.opinion(), puro.opinion())

    def test_elegir_ruta_afecta_refuerzos_y_opinion(self):
        segura, corta = Partida(semilla=3), Partida(semilla=3)
        opciones = segura.opciones_ruta(1)
        self.assertEqual(set(opciones), {SEGURA, CORTA})
        a = segura.elegir_ruta(1, SEGURA)
        b = corta.elegir_ruta(1, CORTA)
        self.assertEqual((a["clave"], b["clave"]), (SEGURA, CORTA))
        # Opinión: la ruta larga resta al pueblo en el nodo actual del árbol (aquí, la raíz)
        self.assertEqual(segura.arbol.opinion()["pueblo"], 50 + opciones[SEGURA]["opinion"]["pueblo"])
        self.assertLess(segura.arbol.opinion()["pueblo"], corta.arbol.opinion()["pueblo"])
        self.assertEqual(segura.arbol.raiz.ajuste["pueblo"], opciones[SEGURA]["opinion"]["pueblo"])
        # Refuerzos: la ruta corta, más peligrosa, trae más enemigos al nivel
        self.assertEqual(segura.peligro(1), opciones[SEGURA]["refuerzos"])
        self.assertGreaterEqual(corta.peligro(1), segura.peligro(1))
        self.assertEqual(corta.peligro(1), opciones[CORTA]["refuerzos"])
        # y los hijos heredan la opinión ajustada
        segura.decidir(CAPTURAR)
        corta.decidir(CAPTURAR)
        self.assertLess(segura.arbol.opinion()["pueblo"], corta.arbol.opinion()["pueblo"])

    def test_la_ruta_se_cobra_una_sola_vez_por_nivel(self):
        p = Partida(semilla=3)
        p.elegir_ruta(1, SEGURA)
        opinion = p.arbol.opinion()
        self.assertEqual(p.elegir_ruta(1, CORTA)["clave"], SEGURA)      # reintentar no cambia la ruta
        self.assertEqual(p.arbol.opinion(), opinion)
        self.assertEqual(p.elegir_ruta(2, "inventada")["clave"], SEGURA)

    def test_sin_elegir_se_usa_la_ruta_segura(self):
        p = Partida(semilla=3)
        self.assertEqual(p.peligro(1), p.mapa.peligro(1))
        self.assertEqual(p.peligro(99), 0)                     # nivel de prueba: fuera del mapa

    def test_revocar_elimina_el_nodo_restaura_el_mapa_y_cuesta_opinion(self):
        p = Partida(semilla=8)
        p.elegir_ruta(1, CORTA)
        mapa, opinion = p.mapa.to_dict(), p.arbol.opinion()
        p.decidir(LIBERAR)
        self.assertNotEqual(p.mapa.to_dict(), mapa)
        self.assertTrue(p.puede_revocar)
        self.assertEqual(p.revocar(), LIBERAR)
        self.assertEqual(p.arbol.camino(), [])
        self.assertEqual(p.arbol.cantidad_nodos(), 1)          # el nodo se eliminó del árbol
        self.assertEqual(p.mapa.to_dict(), mapa)               # el mapa volvió a como estaba
        for c in CATEGORIAS:                                   # la duda se paga en opinión
            self.assertEqual(p.arbol.opinion()[c], opinion[c] + PENALIZACION_REVOCAR[c])
        p.decidir(CAPTURAR)                                    # la nueva decisión hereda la penalización
        puro = ArbolDecisiones()
        puro.decidir(CAPTURAR)
        self.assertLess(p.arbol.opinion()["medios"], puro.opinion()["medios"])
        self.assertFalse(p.puede_revocar)                      # solo una vez por partida
        self.assertIsNone(p.revocar())
        self.assertEqual(p.arbol.camino(), [CAPTURAR])

    def test_no_se_puede_revocar_sin_haber_decidido(self):
        p = Partida(semilla=1)
        self.assertFalse(p.puede_revocar)
        self.assertIsNone(p.revocar())

    def test_el_influencer_amplifica_el_efecto_de_la_decision(self):
        normal, con = Partida(semilla=4), Partida(semilla=4, roles=("presidente", "influencer"))
        normal.decidir(LIBERAR)
        con.decidir(LIBERAR)
        self.assertLess(con.arbol.opinion()["pueblo"], normal.arbol.opinion()["pueblo"])   # lo malo, peor
        normal2, con2 = Partida(semilla=4), Partida(semilla=4, roles=("influencer", "general"))
        normal2.decidir(CAPTURAR)
        con2.decidir(CAPTURAR)
        self.assertGreater(con2.arbol.opinion()["pueblo"], normal2.arbol.opinion()["pueblo"])  # lo bueno, mejor

    def test_serializacion(self):
        p = Partida(semilla=5)
        p.elegir_ruta(1, CORTA)
        p.decidir(EXTRADITAR)
        copia = Partida.from_dict(p.to_dict())
        self.assertEqual(copia.to_dict(), p.to_dict())
        self.assertEqual((copia.semilla, copia.rutas[1]["clave"]), (5, CORTA))

    def test_cada_partida_tiene_otra_semilla(self):
        self.assertGreater(len({Partida().semilla for _ in range(6)}), 1)


if __name__ == "__main__":
    unittest.main()
