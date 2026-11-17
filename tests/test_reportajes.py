"""Reportajes al final de cada nivel (core/reportajes.py, render/reportajes.py, scenes/reportaje.py)."""
import itertools
import os
import unittest

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import pygame  # noqa: E402

import input_manager as im  # noqa: E402
from core import reportajes as rep  # noqa: E402
from core.decision_tree import CAPTURAR, DECISIONES, EXTRADITAR, LIBERAR  # noqa: E402
from core.news import INFLUENCERS, MEDIOS, PUEBLO, contraer  # noqa: E402
from main import Juego  # noqa: E402
from render import personajes  # noqa: E402
from render.fuente_pixel import _ACENTOS, _G  # noqa: E402
from scenes.reportaje import LINEAS_POR_CUADRO, paginas  # noqa: E402

JEFES = ["EL JAGUAR DEL MONTE", "DON CONCRETO", "LA SOMBRA DE LA RAYA"]
OPINION = {"medios": 50, "influencers": 50, "pueblo": 50}
CAMINOS = [list(c) for c in itertools.product(DECISIONES, repeat=3)]


class TestGuion(unittest.TestCase):
    def test_cada_nivel_comenta_solo_su_decision(self):
        for camino in CAMINOS:
            for nivel in (1, 2, 3):
                for categoria in (MEDIOS, INFLUENCERS, PUEBLO):
                    seg, = rep.guion(camino[:nivel], JEFES, OPINION, categorias=[categoria])
                    self.assertEqual(seg.categoria, categoria)
                    comentadas = [(l.nivel, l.decision) for l in seg.lineas if l.parte == "decision"]
                    self.assertEqual(comentadas, [(nivel, camino[nivel - 1])] * 2)   # pregunta y comentario
                    self.assertTrue(all(l.nivel == nivel for l in seg.lineas))
                    partes = [l.parte for l in seg.lineas]
                    self.assertEqual(partes[0], "intro")
                    self.assertEqual("cierre" in partes, nivel == 3)

    def test_un_formato_por_nivel_en_orden_al_azar(self):
        ordenes = set()
        for semilla in range(60):
            formatos = rep.formatos(semilla)
            self.assertEqual(sorted(formatos), [1, 2, 3])
            self.assertEqual(sorted(formatos.values()), sorted(rep.ORDEN))      # los 3, sin repetir
            self.assertEqual(formatos, rep.formatos(semilla))                   # misma semilla, mismo orden
            ordenes.add(tuple(formatos.values()))
        self.assertEqual(len(ordenes), 6)                                       # salen las 6 permutaciones

    def test_cada_texto_cabe_en_un_cuadro_y_la_fuente_lo_tiene(self):
        for camino in CAMINOS:
            for seg in (s for n in (1, 2, 3) for s in rep.guion(camino[:n], JEFES, OPINION)):
                for linea in seg.lineas:
                    self.assertEqual(len(paginas(linea.texto)), 1, linea.texto)
                    self.assertLessEqual(len(paginas(linea.texto)[0]), LINEAS_POR_CUADRO)
                    faltan = {c for c in linea.texto.upper() if c not in _G and c not in _ACENTOS}
                    self.assertFalse(faltan, f"{faltan} en {linea.texto!r}")

    def test_nombra_al_jefe_de_cada_nivel_con_contracciones(self):
        camino = [LIBERAR, CAPTURAR, EXTRADITAR]
        textos = [" ".join(l.texto for l in rep.guion(camino[:n], JEFES, OPINION)[0].lineas) for n in (1, 2, 3)]
        self.assertIn("libre al JAGUAR DEL MONTE", textos[0])
        self.assertIn("DON CONCRETO", textos[1])
        self.assertNotIn("JAGUAR", textos[1])                  # cada reportaje habla de su jefe
        self.assertIn("LA SOMBRA DE LA RAYA", textos[2])
        for camino in CAMINOS:
            for seg in (s for n in (1, 2, 3) for s in rep.guion(camino[:n], JEFES, OPINION)):
                for linea in seg.lineas:
                    self.assertNotRegex(linea.texto.upper(), r"\b(A|DE) EL ")

    def test_contraer(self):
        self.assertEqual(contraer("lo de EL JAGUAR"), "lo del JAGUAR")
        self.assertEqual(contraer("a DON CONCRETO"), "a DON CONCRETO")

    def test_el_camino_cambia_el_comentario(self):
        normal = rep.comentario(MEDIOS, [CAPTURAR, LIBERAR], 2)
        reincidente = rep.comentario(MEDIOS, [LIBERAR, LIBERAR], 2)
        self.assertEqual(reincidente, rep.ESPECIALES[MEDIOS]["reincidente"])
        self.assertEqual(normal, rep.COMENTARIOS[MEDIOS][LIBERAR][2])
        self.assertEqual(rep.comentario(PUEBLO, [LIBERAR, CAPTURAR], 2), rep.ESPECIALES[PUEBLO]["rectifica"])
        self.assertEqual(rep.comentario(INFLUENCERS, [EXTRADITAR] * 3, 3), rep.ESPECIALES[INFLUENCERS]["racha"])

    def test_el_cierre_depende_de_la_opinion_final(self):
        self.assertEqual(rep.banda(rep.ALTA), "alta")
        self.assertEqual(rep.banda(50), "media")
        self.assertEqual(rep.banda(rep.BAJA), "baja")
        alta = rep.guion([CAPTURAR] * 3, JEFES, {"medios": 90, "influencers": 90, "pueblo": 90})
        baja = rep.guion([CAPTURAR] * 3, JEFES, {"medios": 10, "influencers": 10, "pueblo": 10})
        for a, b in zip(alta, baja):
            self.assertNotEqual(a.lineas[-1].texto + a.lineas[-2].texto, b.lineas[-1].texto + b.lineas[-2].texto)

    def test_la_pestana_no_cruza_el_texto(self):
        """El texto del nombre (9 px + 1 de sombra) queda dentro del borde gris de la pestaña,
        sin tocarlo, y termina antes del borde del cuadro."""
        from scenes.reportaje import CAJA, geometria_pestana
        from render.texto import fuente
        nombres = [f"{h.nombre} - {h.cargo}" for h in rep.HABLANTES.values()]
        nombres += [f"{c} - CHAT" for c in rep.CHAT.values()]
        for texto in nombres:
            for lado in ("izquierda", "derecha"):
                rect, (tx, ty) = geometria_pestana(texto, lado)
                ancho, alto = fuente(1).size(texto)
                letras = pygame.Rect(tx, ty, ancho + 1, alto + 1)              # con la sombra
                interior = pygame.Rect(rect.x + 3, rect.y + 3, rect.w - 6, CAJA.y - rect.y - 3)
                self.assertTrue(interior.contains(letras), (texto, lado, letras, interior))
                self.assertTrue(CAJA.contains(pygame.Rect(rect.x, CAJA.y, rect.w, 1)), (texto, lado))

    def test_sprites_propios_reemplazan_al_dibujo(self):
        import tempfile
        with tempfile.TemporaryDirectory() as carpeta:
            original, personajes.RUTA_PROPIOS = personajes.RUTA_PROPIOS, carpeta
            try:
                grande = pygame.Surface((176, 232), pygame.SRCALPHA)        # el doble: se reduce
                grande.fill((255, 0, 0, 255))
                pygame.image.save(grande, os.path.join(carpeta, "analista.png"))
                abierta = pygame.Surface((44, 58), pygame.SRCALPHA)          # la mitad: se duplica
                abierta.fill((0, 255, 0, 255))
                pygame.image.save(abierta, os.path.join(carpeta, "analista_habla2.png"))
                personajes._cache.clear()
                cerrada = personajes.retrato("analista")
                self.assertEqual(cerrada.get_size(), personajes.LIENZO)
                self.assertEqual(tuple(cerrada.get_at((10, 10)))[:3], (255, 0, 0))
                self.assertEqual(tuple(personajes.retrato("analista", boca=2).get_at((10, 10)))[:3], (0, 255, 0))
                self.assertEqual(tuple(personajes.retrato("analista", boca=1).get_at((10, 10)))[:3], (0, 255, 0))
                self.assertEqual(tuple(personajes.retrato("analista", parpadeo=True).get_at((10, 10)))[:3],
                                 (255, 0, 0))                                   # sin parpadeo propio: la cerrada
                self.assertNotEqual(tuple(personajes.retrato("carmen").get_at((10, 10)))[:3], (255, 0, 0))
                self.assertEqual(personajes.retrato("carmen").get_size(), personajes.LIENZO)   # el dibujo, x2
            finally:
                personajes.RUTA_PROPIOS = original
                personajes._cache.clear()

    def test_cada_personaje_tiene_aspecto_y_se_dibuja(self):
        for clave in rep.HABLANTES:
            self.assertIn(clave, personajes.ASPECTOS)
            for boca in (0, 1, 2):
                imagen = personajes.dibujar(personajes.ASPECTOS[clave], boca, parpadeo=boca == 1)
                self.assertEqual(imagen.get_size(), (personajes.ANCHO, personajes.ALTO))
                self.assertGreater(imagen.get_bounding_rect().h, 50)


class TestEscape(unittest.TestCase):
    """El jefe que escapa (se acabó el reloj) se comenta como escape en los tres formatos."""

    def test_cada_formato_comenta_el_escape(self):
        for nivel in (1, 2, 3):
            camino = [LIBERAR] * nivel
            for categoria in (MEDIOS, INFLUENCERS, PUEBLO):
                seg, = rep.guion(camino, JEFES, OPINION, categorias=[categoria], escapes=[nivel])
                decision = [l for l in seg.lineas if l.parte == "decision"]
                self.assertTrue(all(l.escapo for l in decision))
                self.assertEqual(decision[1].texto, rep.COMENTARIOS_ESCAPE[categoria][nivel])
                for l in seg.lineas:                               # caben en un cuadro y la fuente las tiene
                    self.assertEqual(len(paginas(l.texto)), 1, l.texto)
                    self.assertFalse({c for c in l.texto.upper() if c not in _G and c not in _ACENTOS})

    def test_un_escape_anterior_no_hace_reincidente(self):
        self.assertEqual(rep.comentario(MEDIOS, [LIBERAR, LIBERAR], 2, escapes=[1]),
                         rep.COMENTARIOS[MEDIOS][LIBERAR][2])
        self.assertEqual(rep.comentario(MEDIOS, [LIBERAR, LIBERAR], 2), rep.ESPECIALES[MEDIOS]["reincidente"])

    def test_la_partida_guarda_el_escape_y_lo_olvida_al_revocar(self):
        from core.partida import Partida
        p = Partida()
        p.decidir(LIBERAR, escapo=True)
        self.assertTrue(p.escapo_en(1))
        self.assertEqual(Partida.from_dict(p.to_dict()).escapes, [1])
        p.nivel = 2
        p.decidir(CAPTURAR)
        self.assertEqual(p.escapes, [1])
        p.revocar()                                                # revocar el nivel 2 no toca el 1
        self.assertEqual(p.escapes, [1])

    def test_si_se_acaba_el_reloj_la_partida_lo_registra(self):
        import settings
        juego = Juego(headless=True)
        juego.nueva_partida()
        juego.escenas.cambiar("decision", jefe="EL JAGUAR DEL MONTE", tipo_jefe=1)
        for _ in range(int((settings.TIEMPO_DECISION + 6) * 60)):
            juego.frame()
            if type(juego.escenas.actual).__name__ != "DecisionScene":
                break
        self.assertTrue(juego.partida.escapo_en(1))
        self.assertEqual(type(juego.escenas.actual).__name__, "PhoneScene")
        self.assertTrue(juego.escenas.actual.escapo)
        self.assertNotIn("corazon_blando", juego.logros.desbloqueados)   # "deja libre a un jefe"


class TestArteProcesado(unittest.TestCase):
    """Los PNG de assets/reportajes/ que genera tools/procesar_reportajes.py."""
    ESTADOS = ("", "_habla1", "_habla2", "_parpadeo")

    @classmethod
    def setUpClass(cls):
        import json
        pygame.init()
        with open(os.path.join("assets", "paleta.json"), encoding="utf-8") as f:
            cls.paleta = {tuple(c) for c in json.load(f)["colores"]}

    def colores(self, imagen):
        w, h = imagen.get_size()
        return {tuple(imagen.get_at((x, y)))[:3] for y in range(h) for x in range(w) if imagen.get_at((x, y)).a}

    def test_bustos_alineados_por_la_boca_y_con_la_paleta(self):
        claves = [c for c in rep.HABLANTES if personajes.tiene_propio(c)]
        if not claves:
            self.skipTest("no hay sprites propios en assets/reportajes/")
        for clave in claves:
            siluetas = []
            for estado in self.ESTADOS:
                ruta = os.path.join(personajes.RUTA_PROPIOS, f"{clave}{estado}.png")
                self.assertTrue(os.path.isfile(ruta), ruta)
                imagen = pygame.image.load(ruta)
                self.assertEqual(imagen.get_size(), personajes.LIENZO, ruta)
                self.assertTrue(imagen.get_at(personajes.BOCA_LIENZO).a, f"{ruta}: la boca cae fuera de la cara")
                self.assertLessEqual(self.colores(imagen), self.paleta, ruta)
                siluetas.append(bytes(pygame.surfarray.array_alpha(imagen).ravel() > 0))
            self.assertEqual(len(set(siluetas)), 1, f"{clave}: los estados no tienen la misma silueta")

    def test_ningun_busto_esta_estirado(self):
        """El busto termina donde termina el dibujo: ninguna fila de abajo se repite."""
        for clave in [c for c in rep.HABLANTES if personajes.tiene_propio(c)]:
            imagen = pygame.image.load(os.path.join(personajes.RUTA_PROPIOS, f"{clave}.png"))
            abajo = imagen.get_bounding_rect().bottom
            filas = [bytes(pygame.image.tobytes(imagen.subsurface((0, y, imagen.get_width(), 1)), "RGBA"))
                     for y in range(abajo - 4, abajo)]
            self.assertGreater(len(set(filas)), 1, f"{clave}: las últimas filas se repiten (estirado)")

    def test_no_quedan_fondos_procesados(self):
        """El usuario prefirió los fondos por código: el juego ya no carga fondo_*.png."""
        sobrantes = [f for f in os.listdir(personajes.RUTA_PROPIOS) if f.startswith("fondo_")]
        self.assertEqual(sobrantes, [])


class TestEncuadre(unittest.TestCase):
    """Los bustos nunca muestran su corte de abajo: lo tapa el escritorio o el cuadro de diálogo."""

    def setUp(self):
        self.juego = Juego(headless=True)

    def test_el_corte_de_cada_busto_queda_tapado(self):
        from render import reportajes as esc
        from levels import cargar_nivel
        ambientes = {n: cargar_nivel(n)["ambiente"] for n in (1, 2, 3)}
        sprites = ["jefe1", "jefe2", "jefe3"]
        escenarios = [esc.Noticiero(self.juego, sprites, 50, ["X"]), esc.EnVivo(self.juego, sprites, 50),
                      esc.Calle(self.juego, sprites, 50, ambientes)]
        for escenario in escenarios:
            tapa = getattr(escenario, "MESA_Y", None) or esc.ESCENA_ALTO        # escritorio o diálogo
            for camino in ([CAPTURAR], [CAPTURAR, LIBERAR], [LIBERAR, LIBERAR, LIBERAR]):
                for seg in rep.guion(camino, JEFES, OPINION, categorias=[escenario.categoria]):
                    for linea in seg.lineas:
                        for clave, (cx, y, voltear) in escenario.posiciones(linea).items():
                            abajo = y - 1 + esc.alto_busto(clave)              # -1: el balanceo al hablar
                            self.assertGreaterEqual(abajo, tapa, f"{type(escenario).__name__}/{clave}")


class TestChatFijado(unittest.TestCase):
    """En el directo, la pregunta del chat queda fijada mientras el influencer la responde."""

    def setUp(self):
        from render import reportajes as esc
        self.juego = Juego(headless=True)
        self.esc = esc

    def test_la_pregunta_queda_fija_durante_la_respuesta_y_luego_se_suelta(self):
        vivo = self.esc.EnVivo(self.juego, ["jefe1", "jefe2", "jefe3"], 50)
        seg, = rep.guion([CAPTURAR, LIBERAR, EXTRADITAR], JEFES, OPINION, categorias=[INFLUENCERS])
        pregunta = next(l for l in seg.lineas if l.hablante.startswith("@"))
        for linea in seg.lineas:
            for _ in range(600):                                  # 10 s: llegan muchos mensajes
                vivo.actualizar(linea, 1 / 60)
            if linea.parte == "decision":
                self.assertEqual(vivo.fijado, (pregunta.nombre, pregunta.texto.upper()), linea.texto)
            elif linea.parte == "cierre":
                self.assertIsNone(vivo.fijado)
        self.assertGreater(vivo.i_chat, 10)                       # el chat siguió corriendo

    def test_el_fijado_cabe_en_el_chat_y_deja_lugar_a_otros(self):
        vivo = self.esc.EnVivo(self.juego, ["jefe1", "jefe2", "jefe3"], 50)
        for camino in CAMINOS:
            for n in (1, 2, 3):
                seg, = rep.guion(camino[:n], JEFES, OPINION, categorias=[INFLUENCERS])
                for linea in seg.lineas:
                    if linea.hablante.startswith("@"):
                        vivo.fijado = (linea.nombre, linea.texto.upper())
                        caja = vivo.caja_fijado()
                        self.assertTrue(vivo.CHAT.contains(caja), linea.texto)
                        self.assertGreaterEqual(vivo.CHAT.bottom - caja.bottom, 2 * vivo.ALTO_LINEA_CHAT + 6)


class TestEscena(unittest.TestCase):
    def setUp(self):
        self.juego = Juego(headless=True)

    def escena(self):
        return type(self.juego.escenas.actual).__name__

    def ir(self, camino):
        """Partida con `camino` ya decidido, en el reportaje del último nivel de ese camino."""
        partida = self.juego.nueva_partida()
        for nivel, decision in enumerate(camino, start=1):
            partida.nivel = nivel
            partida.decidir(decision)
        self.juego.escenas.cambiar("reportaje")
        self.juego.frame()

    def pulsar(self, accion, frames=2):
        self.juego.entrada.simular(accion)
        for _ in range(1 + frames):
            self.juego.frame()

    def test_el_telefono_de_cada_nivel_lleva_a_su_reportaje(self):
        for nivel in (1, 2, 3):
            self.ir([CAPTURAR] * nivel)
            self.juego.escenas.cambiar("telefono", decision=CAPTURAR)
            self.juego.frame()
            self.juego.escenas.actual.continuar()
            self.juego.frame()
            self.assertEqual(self.escena(), "ReportajeScene")
            self.assertEqual(self.juego.escenas.actual.nivel, nivel)
            self.assertEqual(len(self.juego.escenas.actual.segmentos), 1)

    def test_sale_un_solo_formato_y_en_la_partida_salen_los_tres(self):
        self.juego.nueva_partida()
        semilla = self.juego.partida.semilla
        vistos = []
        camino = [EXTRADITAR, CAPTURAR, LIBERAR]
        for nivel in (1, 2, 3):
            partida = self.juego.partida
            partida.nivel = nivel
            partida.decidir(camino[nivel - 1])
            self.juego.escenas.cambiar("reportaje")
            self.juego.frame()
            escena = self.juego.escenas.actual
            self.assertEqual(len(escena.segmentos), 1)
            self.assertEqual(escena.formato, rep.formatos(semilla)[nivel])
            vistos.append(escena.segmento.escenario)
            for _ in range(80):                                # lo recorre todo dibujando cada cuadro
                if self.escena() != "ReportajeScene":
                    break
                self.pulsar(im.CONFIRMAR)
                self.pulsar(im.CONFIRMAR)
            self.assertEqual(self.escena(), "EndingScene" if nivel == 3 else "HistoriaScene")
        self.assertEqual(sorted(vistos), ["calle", "en_vivo", "noticiero"])

    def test_no_se_puede_saltar(self):
        """ESC / B no hacen nada: el reportaje solo avanza con ENTER / A."""
        self.ir([EXTRADITAR])
        escena = self.juego.escenas.actual
        for _ in range(5):
            self.pulsar(im.CANCELAR)
        self.assertIs(self.juego.escenas.actual, escena)
        self.assertEqual((escena.i_segmento, escena.i_linea), (0, 0))

    def test_cada_formato_se_dibuja_en_cada_nivel(self):
        """Los 3 escenarios con cada línea de cada nivel (intro, pregunta, comentario y cierre)."""
        from scenes.reportaje import ReportajeScene
        for nivel in (1, 2, 3):
            self.ir([CAPTURAR, LIBERAR, LIBERAR][:nivel])
            escena = self.juego.escenas.actual
            for formato in rep.ORDEN:
                escena.segmentos = rep.guion(self.juego.partida.arbol.camino(), JEFES, OPINION, nivel, [formato])
                escena._empezar_segmento(0)
                for i in range(len(escena.segmento.lineas)):
                    escena._empezar_linea(i)
                    for _ in range(3):
                        escena.update(1 / 60, self.juego.entrada.consumir())
                        escena.draw(self.juego.lienzo)
            self.assertIsInstance(escena, ReportajeScene)

    def test_el_texto_sale_letra_por_letra(self):
        self.ir([CAPTURAR])
        escena = self.juego.escenas.actual
        self.assertFalse(escena.escrito)
        self.pulsar(im.CONFIRMAR)                              # el primer toque solo completa el texto
        self.assertTrue(escena.escrito)
        self.assertEqual(escena.i_linea, 0)
        self.pulsar(im.CONFIRMAR)
        self.assertEqual(escena.i_linea, 1)


if __name__ == "__main__":
    unittest.main()
