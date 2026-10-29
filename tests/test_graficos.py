"""Pruebas de las mejoras de imagen y sonido: animación por código, terreno pintado, efectos,
transición, filtro CRT, créditos y partituras."""
import os
import random
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import numpy as np  # noqa: E402
import pygame  # noqa: E402

pygame.init()
pygame.display.set_mode((256, 224))

import input_manager as im  # noqa: E402
import settings  # noqa: E402
from audio import musica_datos, sintesis  # noqa: E402
from core.fisica import Geometria  # noqa: E402
from levels import NIVELES  # noqa: E402
from main import Juego  # noqa: E402
from render import animacion, efectos, mapa_colombia, paisajes, terreno  # noqa: E402
from render.filtros import mascara_crt  # noqa: E402
from render.sprites import GestorSprites  # noqa: E402
from render.transiciones import Transicion  # noqa: E402
from scenes import creditos  # noqa: E402


class TestAnimacion(unittest.TestCase):
    def setUp(self):
        self.sprites = GestorSprites()

    def test_los_jefes_nunca_se_deforman(self):
        """Los jefes solo se mueven enteros: cada cuadro es el dibujo original, corrido."""
        for nombre in ("jefe1", "jefe2", "jefe3"):
            if not self.sprites.tiene_png(nombre):
                continue
            anims = self.sprites.animaciones(nombre)
            original = pygame.mask.from_surface(anims["quieto"][0])
            for anim, cuadros in anims.items():
                if anim == "agachado":
                    continue
                for cuadro in cuadros:
                    with self.subTest(jefe=nombre, anim=anim):
                        self.assertEqual(pygame.mask.from_surface(cuadro).count(), original.count())

    def test_el_sicario_camina_y_respira(self):
        for nombre in ("sicario",):
            if not self.sprites.tiene_png(nombre):
                continue
            with self.subTest(sprite=nombre):
                anims = self.sprites.animaciones(nombre)
                self.assertEqual(len(anims["correr"]), 4)
                self.assertGreater(len(anims["quieto"]), 1)
                quieto = anims["quieto"][0]
                for cuadro in anims["correr"]:          # mismo lienzo: el ancla sigue valiendo
                    self.assertEqual(cuadro.get_size(), quieto.get_size())
                # Los pies siguen apoyados en el mismo suelo
                self.assertEqual(animacion.caja_visible(anims["correr"][1]).bottom,
                                 animacion.caja_visible(quieto).bottom)

    def test_el_paso_mueve_las_piernas_y_no_la_cabeza(self):
        if not self.sprites.tiene_png("sicario"):
            self.skipTest("sin PNG del sicario")
        quieto = self.sprites.animaciones("sicario")["quieto"][0]
        paso = self.sprites.animaciones("sicario")["correr"][0]
        cadera, _ = animacion.medidas(quieto, 0.66)
        cabeza = pygame.Rect(0, 0, quieto.get_width(), 8)
        piernas = pygame.Rect(0, cadera + 4, quieto.get_width(), quieto.get_height() - cadera - 4)

        def pixeles(sup, rect):
            return pygame.surfarray.array_alpha(sup.subsurface(rect))
        # La cabeza solo baja 1 px (el rebote del paso); las piernas cambian de verdad
        self.assertTrue(np.array_equal(pixeles(quieto, cabeza)[:, :7], pixeles(paso, cabeza)[:, 1:8]))
        self.assertFalse(np.array_equal(pixeles(quieto, piernas), pixeles(paso, piernas)))

    def test_lo_dibujado_a_mano_manda(self):
        """Si el PNG trae una animación, no se reemplaza por la generada."""
        anims = {"quieto": [pygame.Surface((10, 20), pygame.SRCALPHA)],
                 "correr": [pygame.Surface((10, 20), pygame.SRCALPHA) for _ in range(2)]}
        propia = anims["correr"]
        animacion.completar("sicario", anims, propias={"quieto", "correr"})
        self.assertIs(anims["correr"], propia)

    def test_el_jugador_corre_apuntando(self):
        self.assertEqual(animacion.anim_correr_jugador("diag_arriba"), "correr_diag_arriba")
        self.assertIsNone(animacion.anim_correr_jugador("quieto"))


class TestPaisajes(unittest.TestCase):
    def test_cada_nivel_tiene_su_paisaje_y_se_dibuja(self):
        vistos = set()
        for numero, datos in NIVELES.items():
            with self.subTest(nivel=numero):
                p = paisajes.crear(datos["ambiente"])
                self.assertIsNotNone(p)
                vistos.add(p.nombre)
                for capa, factor in p.capas:
                    self.assertEqual(capa.get_width(), paisajes.ANCHO)
                    self.assertTrue(0 < factor < 1)
                sup = pygame.Surface((settings.ANCHO, settings.ALTO))
                for t in (0.0, 3.3, 9.7):                  # se dibuja en distintos momentos y lugares
                    p.dibujar(sup, camara_x=t * 300, t=t)
        self.assertEqual(vistos, {"vichada", "medellin", "guajira"})

    def test_las_capas_empalman_al_repetirse(self):
        """Lo que se sale por un borde entra por el otro: no hay costura cada 512 px."""
        lienzo = paisajes.Lienzo()
        pygame.draw.rect(lienzo.sup, (255, 0, 0, 255), (paisajes.MARGEN + paisajes.ANCHO - 5, 50, 10, 4))
        capa = lienzo.cerrar()
        self.assertEqual(tuple(capa.get_at((paisajes.ANCHO - 1, 51)))[:3], (255, 0, 0))
        self.assertEqual(tuple(capa.get_at((2, 51)))[:3], (255, 0, 0))     # la otra mitad, al principio


class TestMapaColombia(unittest.TestCase):
    def setUp(self):
        self.m = mapa_colombia.mapa(122, 170)

    def color(self, lon, lat):
        x, y = self.m.proy.a_pixel(lon, lat)
        return tuple(self.m.imagen.get_at((int(x), int(y))))[:3]

    def test_contornos_reales(self):
        self.assertEqual(len(self.m.nombres), 33)
        for lon, lat in ((-74.08, 4.60), (-75.57, 6.25), (-69.5, 3.5), (-72.24, 11.38)):
            x, y = self.m.proy.a_pixel(lon, lat)
            self.assertTrue(self.m.colombia[int(x), int(y)], (lon, lat))      # las zonas caen en Colombia
        self.assertFalse(self.m.colombia[tuple(int(v) for v in self.m.proy.a_pixel(-77.0, 12.0))])

    def test_colores_de_atlas(self):
        r, g, b = self.color(-76.5, 12.0)                     # mar Caribe: azul
        self.assertGreater(b, r + 60)
        r, g, b = self.color(-72.0, 12.0)                     # alta Guajira: desierto amarillo
        self.assertGreater(r, 180)
        self.assertGreater(g, 150)
        self.assertLess(b, 150)
        r, g, b = self.color(-71.0, -1.0)                     # Amazonía: verde oscuro
        self.assertGreater(g, r + 40)
        self.assertGreater(g, b + 30)
        self.assertGreater(sum(self.color(-73.70, 10.85)), 600)   # nieve en la Sierra Nevada

    def test_zoom_sobre_las_zonas_de_cada_pantalla(self):
        """El informe del nivel 1 se acerca mucho más que el país entero, y todas las zonas de la
        pantalla quedan dentro del recuadro."""
        from core.mapa import Mapa
        from render import grafo_visual
        m = Mapa(con_retenes=False)
        area = pygame.Rect(12, 27, 232, 69)
        zonas = sorted({z for r in m.rutas(1).values() for z in r["camino"]})
        mapa, _ = grafo_visual._encuadre(m, area, zonas)
        self.assertGreater(mapa.proy.escala, 2.5 * self.m.proy.escala)
        for z in zonas:
            self.assertTrue(area.collidepoint(grafo_visual._punto(m, z, area, zonas)), z)

    def test_los_nombres_no_tapan_zonas_ni_se_enciman(self):
        """En las dos páginas del informe de cada nivel, con varias semillas: ningún nombre tapa
        una zona que se ve ni pisa otro nombre, y todos quedan dentro del recuadro."""
        from core.mapa import Mapa
        from render.grafo_visual import dibujar_mapa
        sup = pygame.Surface((256, 224))
        area = pygame.Rect(10, 25, 236, 69)
        for semilla in range(6):
            m = Mapa(semilla)
            for nivel in (1, 2, 3):
                rutas = m.rutas(nivel)
                otra = rutas.get("corta", {}).get("camino", ())
                pantallas = [dict(olas=m.influencia(nivel), olas_visibles=3,
                                  enfoque=[z for ola in m.influencia(nivel)[:2] for z in ola]),
                             dict(ruta=rutas["segura"]["camino"], tramos_ruta=9, ruta_alterna=otra,
                                  enfoque=sorted({z for r in rutas.values() for z in r["camino"]}))]
                for datos in pantallas:
                    with self.subTest(semilla=semilla, nivel=nivel, rutas="ruta" in datos):
                        r = dibujar_mapa(sup, m, area, nivel, simple=True, **datos)
                        cajas = list(r["nombres"].items())
                        for i, (zona, caja) in enumerate(cajas):
                            self.assertTrue(area.contains(caja), zona)
                            for otra_zona, otra_caja in cajas[i + 1:]:
                                self.assertFalse(caja.colliderect(otra_caja), (zona, otra_zona))
                            for z, punto in r["zonas"].items():
                                if z != zona:
                                    self.assertFalse(caja.collidepoint(punto), (zona, "tapa", z))

    def test_el_grafo_se_dibuja_sobre_el_mapa(self):
        from core.mapa import Mapa
        from render.grafo_visual import dibujar_mapa
        sup = pygame.Surface((256, 224))
        m = Mapa(semilla=3)
        area = pygame.Rect(4, 22, 122, 176)
        dibujar_mapa(sup, m, area, 2, ruta=m.rutas(2)["segura"]["camino"], tramos_ruta=9,
                     ruta_alterna=m.rutas(2)["corta"]["camino"], simple=True, recorrido=[m.rutas(1)["segura"]["camino"]])
        dibujar_mapa(sup, m, area, tiempo=1.0)                  # modo completo, con todos los pesos


class TestTerreno(unittest.TestCase):
    def test_cada_nivel_se_pinta_entero(self):
        for numero, datos in NIVELES.items():
            with self.subTest(nivel=numero):
                geo = Geometria(datos)
                sup = terreno.pintar(datos, geo)
                self.assertEqual(sup.get_size(), (datos["largo"], settings.ALTO))
                # Donde hay suelo hay color; sobre el suelo, en el aire, no
                x0, x1, y = datos["suelo"][0]
                self.assertGreater(sup.get_at((x0 + 20, y + 8)).a, 0)
                self.assertEqual(sup.get_at((x0 + 20, y - 40)).a, 0)

    def test_estilos_distintos(self):
        estilos = {datos["ambiente"]["estilo"] for datos in NIVELES.values()}
        self.assertEqual(estilos, {"selva", "ciudad", "desierto"})


class TestEfectos(unittest.TestCase):
    def test_todo_se_apaga_solo(self):
        fx = efectos.Efectos(random.Random(1))
        fx.explosion(100, 100, 2.0)
        fx.casquillo(50, 100, 1, 150)
        fx.polvo(60, 150, 5)
        fx.flotante(70, 90, "+100")
        img = pygame.Surface((10, 10), pygame.SRCALPHA)
        fx.cuerpo(img, img, 40, 40, 1)
        sup = pygame.Surface((256, 224))
        for _ in range(240):                             # 4 segundos
            fx.update(1 / 60)
            fx.dibujar_detras(sup, 0)
            fx.dibujar(sup, 0)
        self.assertEqual((fx.particulas, fx.bolas, fx.casquillos, fx.cuerpos, fx.flotantes, fx.anillos),
                         ([], [], [], [], [], []))

    def test_casquillos_tienen_tope(self):
        fx = efectos.Efectos(random.Random(2))
        for _ in range(200):
            fx.casquillo(0, 0, 1, 10)
        self.assertLessEqual(len(fx.casquillos), efectos.MAX_CASQUILLOS)

    def test_sombra_sobre_el_suelo_y_no_en_el_vacio(self):
        geo = Geometria(NIVELES[1])
        x0, x1, y = NIVELES[1]["suelo"][0]
        self.assertEqual(efectos.suelo_debajo(geo, x0 + 10, y - 30), y)
        hueco = x1 + 2                                   # justo después del primer tramo hay un precipicio
        if not any(r.left <= hueco < r.right for r in geo.solidos + geo.plataformas):
            self.assertIsNone(efectos.suelo_debajo(geo, hueco, y - 30))

    def test_el_halo_no_suma_fuera_del_circulo(self):
        halo = efectos.Efectos().halo(6, (255, 200, 100), 80)
        self.assertEqual(tuple(halo.get_at((0, 0)))[:3], (0, 0, 0))   # esquina: no aclara nada
        self.assertGreater(sum(tuple(halo.get_at((6, 6)))[:3]), 0)


class TestLienzoSinAlfa(unittest.TestCase):
    """En macOS la ventana tiene canal alfa y un Surface sin máscara lo hereda. Entonces una
    capa transparente deja el alfa del lienzo en 0 y una imagen con set_alpha() encima se
    mezcla contra ese 0: sale NEGRO (la selva negra). El lienzo del juego no lleva alfa."""

    ARGB = (0xFF0000, 0x00FF00, 0x0000FF, 0xFF000000)

    def pintar(self, destino):
        destino.fill((76, 148, 92))
        capa = pygame.Surface((40, 40), pygame.SRCALPHA)          # una capa con partes transparentes
        capa.fill((0, 0, 0, 0))
        pygame.draw.rect(capa, (0, 0, 0, 0), (0, 0, 40, 40))
        destino.blit(capa, (0, 0))
        haz = pygame.Surface((40, 40), pygame.SRCALPHA)           # un haz de luz que pulsa
        pygame.draw.rect(haz, (255, 255, 210, 20), (0, 0, 40, 40))
        haz.set_alpha(220)
        destino.blit(haz, (0, 0))
        return tuple(destino.get_at((10, 10)))[:3]

    def test_el_lienzo_del_juego_no_tiene_alfa(self):
        from render.ui import superficie_opaca
        juego = Juego(headless=True)
        self.assertEqual(juego.lienzo.get_masks()[3], 0)
        r, g, b = self.pintar(superficie_opaca((40, 40)))
        self.assertGreater(g, r + 30)                             # verde apenas aclarado: ni negro ni opaco
        self.assertGreater(g, 120)
        r, g, b = self.pintar(pygame.Surface((40, 40), 0, 32, self.ARGB))   # así fallaba en macOS
        self.assertFalse(g > r + 30 and g > 120)

    def test_la_selva_no_sale_negra_en_un_lienzo_sin_alfa(self):
        from render.ui import superficie_opaca
        p = paisajes.crear(NIVELES[1]["ambiente"])
        lienzo = superficie_opaca((settings.ANCHO, settings.ALTO))
        p.dibujar(lienzo, 0, 1.0)
        oscuros = sum(1 for x in range(0, 256, 8) for y in range(40, 190, 8) if sum(tuple(lienzo.get_at((x, y)))[:3]) < 60)
        self.assertLess(oscuros, 10)


class TestPantalla(unittest.TestCase):
    def test_transicion_tapa_y_destapa(self):
        t = Transicion(0.4)
        anterior = pygame.Surface((256, 224))
        anterior.fill((200, 0, 0))
        t.iniciar(anterior)
        sup = pygame.Surface((256, 224))
        sup.fill((0, 200, 0))
        t.avanzar(0.199)
        t.dibujar(sup)
        self.assertLess(sum(tuple(sup.get_at((128, 112)))[:3]), 30)     # a la mitad: casi todo negro
        for _ in range(30):
            t.avanzar(1 / 60)
        self.assertFalse(t.activa)
        sup.fill((0, 200, 0))
        t.dibujar(sup)
        self.assertEqual(tuple(sup.get_at((128, 112)))[:3], (0, 200, 0))

    def test_mascara_crt(self):
        m = mascara_crt(768, 672, 3)
        self.assertEqual(m.get_size(), (768, 672))
        self.assertLess(m.get_at((384, 2))[0], m.get_at((384, 1))[0])        # línea de barrido
        self.assertLess(m.get_at((0, 0))[0], m.get_at((384, 337))[0])        # esquinas más oscuras

    def test_creditos_llegan_al_menu(self):
        juego = Juego(headless=True, escena_inicial="creditos")
        self.assertIn("JOSE CASTRO", [t for t, _, _ in creditos.LINEAS])
        for _ in range(60):
            juego.frame()
        juego.entrada.simular(im.CONFIRMAR)
        for _ in range(3):
            juego.frame()
        self.assertEqual(type(juego.escenas.actual).__name__, "MenuScene")

    def test_crt_en_opciones_y_ventana(self):
        juego = Juego(headless=True)
        juego.opciones["crt"] = True
        for _ in range(5):
            juego.frame()                                  # escala y aplica la máscara sin fallar
        self.assertIn("crt", settings.OPCIONES_POR_DEFECTO)


class TestPartituras(unittest.TestCase):
    def test_cada_compas_suma_cuatro_tiempos(self):
        for grupo in (musica_datos.TEMAS, musica_datos.JINGLES):
            for nombre, tema in grupo.items():
                for sec_nombre, sec in tema["secciones"].items():
                    n = len(sec["acordes"])
                    self.assertEqual(len(sec["melodia"]), n, (nombre, sec_nombre))
                    self.assertEqual(len(sec["bateria"]), n, (nombre, sec_nombre))
                    for voz in ("melodia", "bajo"):
                        for i, compas in enumerate(sec.get(voz) or []):
                            with self.subTest(tema=nombre, seccion=sec_nombre, voz=voz, compas=i):
                                self.assertEqual(sum(d for _, d in sintesis.leer_secuencia(compas)), 16)
                    for patron in sec["bateria"]:
                        self.assertEqual(len(musica_datos.PATRONES[patron]), 16)
                    for acorde in sec["acordes"]:
                        for nombre_acorde in acorde.split():
                            sintesis.leer_acorde(nombre_acorde)

    def test_musica_estereo_y_sin_saturar(self):
        datos = sintesis.tema("nivel1")
        self.assertEqual(datos.shape[1], 2)
        self.assertLessEqual(float(np.abs(datos).max()), 1.0)
        self.assertLess(abs(float(datos.mean())), 0.01)                     # sin componente continua
        izquierda, derecha = datos[:, 0], datos[:, 1]
        self.assertFalse(np.allclose(izquierda, derecha))                    # el eco abre el estéreo

    def test_fanfarrias(self):
        victoria = sintesis.jingle("victoria")
        self.assertLess(len(victoria) / sintesis.SR, 3.4)    # cabe antes de la pantalla de decisión
        self.assertLess(float(np.abs(victoria[-50:]).max()), 0.05)          # termina sin clic
        self.assertGreater(len(sintesis.jingle("game_over")) / sintesis.SR, 3)

    def test_ondas_de_banda_limitada(self):
        """El pulso PolyBLEP tiene mucho menos aliasing que el pulso ingenuo."""
        f = 3520.0
        n = sintesis.SR
        t = np.arange(n) / sintesis.SR
        ingenua = np.where((t * f) % 1 < 0.5, 1.0, -1.0)
        limpia = sintesis.cuadrada(f, 1.0)
        espectro = lambda x: np.abs(np.fft.rfft(x[:n]))
        frec = np.fft.rfftfreq(n, 1 / sintesis.SR)
        armonicos = np.zeros_like(frec, dtype=bool)
        for k in range(1, int(sintesis.SR / 2 / f) + 1):
            armonicos |= np.abs(frec - k * f) < 3
        ruido_ingenua = espectro(ingenua)[~armonicos].sum()
        ruido_limpia = espectro(limpia)[~armonicos].sum()
        self.assertLess(ruido_limpia, ruido_ingenua * 0.5)

    def test_variantes_de_tono(self):
        base = sintesis.efectos()["disparo_jugador"]
        vs = sintesis.variantes(base, 3)
        self.assertEqual(len(vs), 3)
        self.assertNotEqual(len(vs[0]), len(vs[2]))


if __name__ == "__main__":
    unittest.main()
