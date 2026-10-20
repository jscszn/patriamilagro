"""Escenas y sonido nuevos: informe del nivel, tiempo límite, red social, voz, himno y multijugador."""
import os
import time
import unittest
import wave

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import numpy as np  # noqa: E402

import input_manager as im  # noqa: E402
import settings  # noqa: E402
from audio import sintesis  # noqa: E402
from core import historia  # noqa: E402
from core.decision_tree import CAPTURAR, DECISIONES, LIBERAR  # noqa: E402
from core.partida import Partida  # noqa: E402
from main import Juego  # noqa: E402
from net.cliente import Cliente  # noqa: E402
from render.texto import envolver  # noqa: E402
from scenes import help as ayuda  # noqa: E402


class BaseJuego(unittest.TestCase):
    def setUp(self):
        self.juego = Juego(headless=True, arena=True)

    def tearDown(self):
        self.juego.cerrar_red()

    def escena(self):
        return type(self.juego.escenas.actual).__name__

    def frames(self, n):
        for _ in range(n):
            self.juego.frame()

    def pulsar(self, accion, despues=3):
        self.juego.entrada.simular(accion)
        self.frames(1 + despues)

    def ir(self, nombre, **datos):
        self.juego.escenas.cambiar(nombre, **datos)
        self.juego.escenas.aplicar_cambios()
        return self.juego.escenas.actual

class TestHistoria(BaseJuego):
    def test_el_texto_cabe_en_el_recuadro_medido_de_verdad(self):
        """Mide el alto real del texto (fuente y partido en líneas reales) contra el recuadro, en
        los 3 niveles, con todas las variantes del jefe anterior y con muchos mapas distintos."""
        from scenes.historia import ANCHO_TEXTO, CAJA_TEXTO, MARGEN_TEXTO, HistoriaScene
        libre = CAJA_TEXTO.h - 2 * MARGEN_TEXTO
        caminos = {1: [[]], 2: [[d] for d in DECISIONES],
                   3: [[a, b] for a in DECISIONES for b in DECISIONES]}
        medidos = 0
        for nivel, variantes in caminos.items():
            for camino in variantes:
                for semilla in range(1, 13):
                    p = Partida(semilla=semilla)
                    for i, decision in enumerate(camino):
                        p.nivel = i + 1
                        p.decidir(decision)
                    paginas = [historia.pagina_danos(nivel, p.arbol.camino())]
                    paginas += [historia.pagina_ruta(nivel, p.mapa, clave) for clave in p.opciones_ruta(nivel)]
                    for pagina in paginas:                     # los daños y CADA ruta que se puede elegir
                        with self.subTest(nivel=nivel, camino=camino, semilla=semilla, texto=pagina[:24]):
                            self.assertLessEqual(HistoriaScene.alto_texto(pagina), libre)
                            self.assertLessEqual(len(envolver(pagina, 1, ANCHO_TEXTO)),
                                                 HistoriaScene.lineas_que_caben())
                            medidos += 1
        self.assertGreaterEqual(medidos, (1 + 3 + 9) * 12 * 2)
        # El recuadro no pisa el pie de página ni el mapa
        from scenes.historia import AREA_MAPA
        self.assertLessEqual(CAJA_TEXTO.bottom, 211)
        self.assertGreaterEqual(CAJA_TEXTO.top, AREA_MAPA.bottom)

    def test_el_jefe_se_ve_detras_del_texto_sin_tapar_el_mapa(self):
        import pygame
        from scenes.historia import AREA_MAPA, CAJA_TEXTO
        self.juego.nueva_partida()
        for nivel in (1, 2, 3):
            e = self.ir("historia", numero=nivel)
            e.t_pagina = 0.0                                   # sin texto todavía: solo fondo y jefe
            lienzo = pygame.Surface((settings.ANCHO, settings.ALTO))
            e.draw(lienzo)
            con_jefe = lienzo.subsurface(CAJA_TEXTO.inflate(-8, -8)).copy()
            e._villano = pygame.Surface((1, 1), pygame.SRCALPHA)        # el mismo dibujo, sin jefe
            sin_jefe = pygame.Surface((settings.ANCHO, settings.ALTO))
            e.draw(sin_jefe)
            distintos = sum(1 for x in range(0, con_jefe.get_width(), 3) for y in range(14, con_jefe.get_height(), 3)
                            if con_jefe.get_at((x, y)) != sin_jefe.subsurface(CAJA_TEXTO.inflate(-8, -8)).get_at((x, y)))
            self.assertGreater(distintos, 60, f"nivel {nivel}: el jefe no se ve")
            self.assertEqual(pygame.image.tobytes(lienzo.subsurface(AREA_MAPA), "RGB"),
                             pygame.image.tobytes(sin_jefe.subsurface(AREA_MAPA), "RGB"))   # mapa despejado
            # Tenue: ningún píxel del jefe llega a ser más claro que el texto blanco
            self.assertLess(max(sum(con_jefe.get_at((x, y))[:3]) for x in range(0, con_jefe.get_width(), 2)
                                for y in range(14, con_jefe.get_height(), 2)), 3 * 150)

    def test_la_historia_depende_del_camino_del_arbol(self):
        self.assertNotEqual(historia.pagina_danos(2, [CAPTURAR]), historia.pagina_danos(2, [LIBERAR]))
        self.assertIn("JAGUAR", historia.pagina_danos(2, [LIBERAR]))
        self.assertEqual(historia.pagina_danos(1, []), historia.DANOS[1])

    def test_dos_paginas_y_luego_el_nivel(self):
        self.pulsar(im.CONFIRMAR)                              # menú: JUGAR
        self.assertEqual(self.escena(), "HistoriaScene")
        e = self.juego.escenas.actual
        self.assertFalse(e.escrito)
        self.pulsar(im.CONFIRMAR)                              # completa el texto
        self.assertTrue(e.escrito)
        self.assertEqual(e.pagina, 0)
        self.pulsar(im.CONFIRMAR)
        self.assertEqual(e.pagina, 1)
        self.assertEqual((e.ruta[0], e.ruta[-1]), ("capital", "selva"))   # la ruta que calculó Dijkstra
        self.pulsar(im.CANCELAR)                               # se puede volver a la página anterior
        self.assertEqual(e.pagina, 0)
        self.pulsar(im.CONFIRMAR)                              # otra vez a la página 2
        self.pulsar(im.CONFIRMAR)                              # completa su texto
        self.pulsar(im.CONFIRMAR)                              # ¡a la misión!
        self.assertEqual(self.escena(), "LevelScene")
        estado = self.juego.escenas.actual.estado
        self.assertEqual(estado.semilla, self.juego.partida.semilla)   # el nivel usa el azar de la partida
        self.assertEqual(estado.peligro, self.juego.partida.peligro(1))

    def test_elegir_la_ruta_con_izquierda_y_derecha(self):
        from core.partida import Partida as P
        self.juego.partida = P(semilla=3)
        e = self.ir("historia", numero=1)
        self.pulsar(im.DERECHA)                                # en la página 1 no hay nada que elegir
        self.assertEqual(e.clave, "segura")
        e.pagina, e.t_pagina = 1, 999.0
        segura = list(e.ruta)
        self.pulsar(im.DERECHA)
        self.assertEqual(e.clave, "corta")
        self.assertNotEqual(e.ruta, segura)                    # en el mapa se resalta la otra ruta
        self.assertIn("RUTA CORTA", e.texto)
        self.pulsar(im.IZQUIERDA)
        self.assertEqual(e.clave, "segura")
        self.pulsar(im.DERECHA)
        self.frames(30)                                        # se dibuja con las dos rutas
        self.pulsar(im.CONFIRMAR)                              # ¡a la misión!
        self.assertEqual(self.escena(), "LevelScene")
        p = self.juego.partida
        self.assertEqual(p.rutas[1]["clave"], "corta")
        self.assertEqual(self.juego.escenas.actual.estado.peligro, p.rutas[1]["refuerzos"])
        self.assertGreaterEqual(p.rutas[1]["refuerzos"], 1)    # la corta es más peligrosa: más refuerzos
        self.assertEqual(p.arbol.opinion()["pueblo"], 50)      # y llega a tiempo: no cuesta opinión

    def test_la_ruta_segura_cuesta_opinion_y_se_ve_en_el_hud(self):
        from core.partida import Partida as P
        self.juego.partida = P(semilla=3)
        e = self.ir("historia", numero=1)
        e.pagina, e.t_pagina = 1, 999.0
        self.pulsar(im.CONFIRMAR)
        self.assertEqual(self.escena(), "LevelScene")
        self.assertLess(self.juego.partida.arbol.opinion()["pueblo"], 50)
        self.assertEqual(self.juego.escenas.actual.estado.opinion, self.juego.partida.arbol.opinion())

    def test_se_dibujan_las_dos_paginas_de_los_tres_niveles(self):
        self.juego.nueva_partida()
        for nivel in (1, 2, 3):
            e = self.ir("historia", numero=nivel)
            self.frames(90)
            e.pagina, e.t_pagina = 1, 0.0
            self.frames(90)


class TestTiempoLimite(BaseJuego):
    def test_si_se_acaba_el_tiempo_el_jefe_escapa(self):
        self.juego.nueva_partida().jefes_derrotados = ["EL JAGUAR DEL MONTE"]
        e = self.ir("decision", jefe="EL JAGUAR DEL MONTE", tipo_jefe=1)
        self.frames(int((settings.TIEMPO_DECISION - 1) * 60))
        self.assertEqual(self.juego.partida.arbol.camino(), [])        # todavía hay tiempo
        self.assertLess(e.restante, 2)
        self.frames(120)
        self.assertTrue(e.escapo)
        self.assertEqual(self.juego.partida.arbol.camino(), [LIBERAR])
        self.frames(90)
        self.assertEqual(self.escena(), "PhoneScene")          # si escapó no hay ventana para revocar

    def test_decidir_a_tiempo_no_escapa(self):
        self.juego.nueva_partida().jefes_derrotados = ["X"]
        e = self.ir("decision", jefe="X", tipo_jefe=2)
        self.frames(60)
        self.pulsar(im.CONFIRMAR)
        self.assertFalse(e.escapo)
        self.assertEqual(self.juego.partida.arbol.camino(), [CAPTURAR])

    def test_la_ayuda_detiene_el_reloj(self):
        self.juego.nueva_partida()
        e = self.ir("decision", jefe="X", tipo_jefe=1)
        self.frames(60)
        self.pulsar(im.AYUDA)
        self.assertEqual(self.escena(), "HelpScene")
        restante = e.restante
        self.frames(300)
        self.assertEqual(e.restante, restante)


class TestRevocar(BaseJuego):
    """Revocar vive en la escena de decisión: elimina el nodo del árbol y se decide de nuevo."""

    def abrir(self):
        from core.partida import Partida as P
        self.juego.partida = P(semilla=6)
        self.juego.partida.jefes_derrotados = ["EL JAGUAR DEL MONTE"]
        e = self.ir("decision", jefe="EL JAGUAR DEL MONTE", tipo_jefe=1)
        self.frames(45)
        return e, self.juego.partida

    def test_revocar_borra_el_nodo_cobra_opinion_y_deja_decidir_otra_vez(self):
        from core.partida import PENALIZACION_REVOCAR
        e, p = self.abrir()
        self.pulsar(im.DERECHA)
        self.pulsar(im.DERECHA)
        self.pulsar(im.CONFIRMAR)                              # DEJAR LIBRE
        self.assertEqual(p.arbol.camino(), [LIBERAR])
        self.assertEqual(p.arbol.cantidad_nodos(), 2)
        self.frames(40)
        self.assertTrue(e.se_puede_revocar)
        self.pulsar(im.CANCELAR)                               # X / B: REVOCAR
        self.assertEqual(self.escena(), "DecisionScene")       # sigue aquí, decidiendo de nuevo
        self.assertTrue(e.revocada)
        self.assertEqual((p.arbol.camino(), p.arbol.cantidad_nodos()), ([], 1))   # nodo eliminado
        self.assertEqual(p.arbol.opinion()["medios"], 50 + PENALIZACION_REVOCAR["medios"])
        self.assertEqual(e.restante, settings.TIEMPO_DECISION)  # el reloj vuelve a empezar
        self.frames(45)
        self.pulsar(im.IZQUIERDA)
        self.pulsar(im.IZQUIERDA)
        self.pulsar(im.CONFIRMAR)                              # ahora CAPTURAR
        self.assertEqual(p.arbol.camino(), [CAPTURAR])
        self.frames(40)
        self.assertFalse(e.se_puede_revocar)                   # una sola vez por partida
        self.pulsar(im.CANCELAR)
        self.assertEqual(p.arbol.camino(), [CAPTURAR])
        self.frames(int(1.2 * 60))
        self.assertEqual(self.escena(), "PhoneScene")          # sin ventana, pasa al teléfono enseguida

    def test_si_no_se_revoca_la_ventana_se_cierra_sola(self):
        e, p = self.abrir()
        self.pulsar(im.CONFIRMAR)                              # CAPTURAR
        self.frames(int(1.2 * 60))
        self.assertEqual(self.escena(), "DecisionScene")       # todavía se puede revocar
        self.frames(int(2.6 * 60))
        self.assertEqual(self.escena(), "PhoneScene")
        self.assertEqual(p.arbol.camino(), [CAPTURAR])


class TestSonidoNuevo(BaseJuego):
    def test_la_voz_suena_al_entrar_al_menu_y_al_ganar(self):
        audio = self.juego.audio
        self.assertEqual(audio.voz_actual, "bienvenida")       # al abrir el juego
        audio.voz_actual = None
        self.ir("opciones")
        self.assertIsNone(audio.voz_actual)
        self.ir("menu")
        self.assertEqual(audio.voz_actual, "bienvenida")       # cada vez que se vuelve al menú
        audio.voz_actual = None
        p = self.juego.nueva_partida()
        for _ in range(3):
            p.arbol.decidir(CAPTURAR)
        p.jefes_derrotados = ["A", "B", "C"]
        self.ir("final")
        self.assertEqual(audio.voz_actual, "bienvenida")       # al ganar
        self.assertEqual((audio.tema_actual, audio.tema_pendiente), (None, "final"))   # la música espera
        self.frames(2)
        self.assertEqual(audio.tema_actual, "final")

    def test_primero_la_voz_y_despues_la_musica(self):
        """Con el mezclador real (salida muda): mientras habla no suena el himno; al terminar, sí."""
        import pygame
        from audio import gestor
        a = gestor.Audio({"volumen_efectos": 8, "volumen_musica": 6})
        if not a.activo:
            self.skipTest("sin mezclador")
        a.presentar("bienvenida", "menu")
        self.assertTrue(a.hablando())
        self.assertFalse(a.canal_musica.get_busy())            # silencio de fondo mientras habla
        a.actualizar()
        self.assertIsNone(a.tema_actual)
        a.canal_voz.stop()                                     # termina la frase
        a.actualizar()
        self.assertEqual(a.tema_actual, "menu")
        self.assertTrue(a.canal_musica.get_busy())
        # Si el tema ya sonaba (volver al menú), no se corta: baja de volumen y luego sube
        a.presentar("bienvenida", "menu")
        self.assertTrue(a.canal_musica.get_busy())
        self.assertAlmostEqual(a.canal_musica.get_volume(), a.vol_musica * settings.VOLUMEN_ATENUADO, delta=0.02)
        a.canal_voz.stop()
        a.actualizar()
        self.assertAlmostEqual(a.canal_musica.get_volume(), a.vol_musica, delta=0.02)
        # Si otra escena pide su música mientras habla, la voz se calla
        a.presentar("bienvenida", "menu")
        a.musica("decision")
        self.assertFalse(a.hablando())
        self.assertEqual(a.tema_actual, "decision")
        pygame.mixer.stop()

    def test_la_voz_es_solo_la_frase(self):
        ruta = os.path.join(settings.RUTA_ASSETS, "sonidos", "bienvenida.wav")
        with wave.open(ruta) as w:
            self.assertLess(w.getnframes() / w.getframerate(), 3.0)     # ~1,9 s de frase + eco, sin pitidos

    def test_el_archivo_de_la_voz_existe_y_es_valido(self):
        ruta = os.path.join(settings.RUTA_ASSETS, "sonidos", "bienvenida.wav")
        with wave.open(ruta) as w:
            self.assertEqual((w.getnchannels(), w.getsampwidth()), (1, 2))
            duracion = w.getnframes() / w.getframerate()
            datos = np.frombuffer(w.readframes(w.getnframes()), np.int16)
        self.assertTrue(1.5 < duracion < 3)
        self.assertGreater(int(np.abs(datos).max()), 20000)             # normalizada, no un susurro
        self.assertLess(int(np.abs(datos[:200]).max()), 3000)           # entra sin "clic"

    def test_el_menu_toca_el_himno_en_estilo_arcade(self):
        h = sintesis.HIMNO
        self.assertIsNotNone(h)
        self.assertEqual(len(h.MELODIA), len(h.BAJO))                    # un bajo por compás
        for compas in h.MELODIA:
            notas = sintesis.leer_compas(compas)
            self.assertTrue(notas)
            fin = 0.0
            for nota, inicio, duracion in notas:
                self.assertGreaterEqual(inicio, fin - 1e-9)              # una sola voz: no se pisan
                fin = inicio + duracion
            self.assertLessEqual(fin, 4.0)                               # caben en el compás de 4 pulsos
        # El coro empieza Sol-Sol-La-Sol-Fa#: "¡Oh glo-ria in-mar-ce...!"
        self.assertEqual([n for n, _, _ in sintesis.leer_compas(h.MELODIA[8])], [79, 79, 81, 79, 78])
        self.assertEqual((sintesis.nota_midi("C4"), sintesis.nota_midi("Bb4"), sintesis.nota_midi("F#5")),
                         (60, 70, 78))
        self.assertEqual((sintesis.nota_midi("C4") + h.TRANSPORTE) % 12, 3)   # suena en Mi bemol mayor
        audio = sintesis.tema("menu")
        self.assertEqual(audio.dtype, np.float32)
        self.assertGreater(len(audio) / sintesis.SR, 40)                 # intro y coro completos
        self.assertLessEqual(float(np.abs(audio).max()), 1.0)
        self.assertEqual(len(audio), len(sintesis.himno()))              # el tema "menu" ES el himno

    def test_el_bajo_del_himno_se_puede_apagar(self):
        con, sin = sintesis.himno(con_bajo=True), sintesis.himno(con_bajo=False)
        self.assertEqual(len(con), len(sin))
        self.assertFalse(np.array_equal(con, sin))
        guardado, settings.HIMNO_CON_BAJO = settings.HIMNO_CON_BAJO, False
        try:
            # Con la constante apagada solo queda la melodía. (Se compara la forma de onda:
            # los dos se normalizan al mismo pico, así que deben ser idénticos.)
            self.assertTrue(np.allclose(sintesis.himno(), sin))
        finally:
            settings.HIMNO_CON_BAJO = guardado

    def test_sin_datos_del_himno_usa_el_tema_generico(self):
        guardado, sintesis.HIMNO = sintesis.HIMNO, None
        try:
            self.assertGreater(len(sintesis.tema("menu", repeticiones=1)), sintesis.SR * 4)
        finally:
            sintesis.HIMNO = guardado

    def test_efectos_nuevos(self):
        efectos = sintesis.efectos()
        for nombre in ("alerta", "suministro", "tic"):
            self.assertIn(nombre, efectos)
        for nombre in ("onda_red", "rumor"):                   # se fueron con la red social
            self.assertNotIn(nombre, efectos)


class TestAyuda(unittest.TestCase):
    def test_explica_indicadores_y_lo_nuevo(self):
        titulos = [t for t, _ in ayuda.PAGINAS]
        for quitado in ("LA RED SOCIAL", "MULTIJUGADOR", "ROLES"):
            self.assertNotIn(quitado, titulos)
        for titulo in ("OPINIÓN POPULAR", "EL MAPA DEL PAÍS",
                       "TIEMPO LÍMITE", "ARMAS Y REFUERZOS", "CÓMO SE GANA", "CONTROLES", "OBJETIVO"):
            self.assertIn(titulo, titulos)
        self.assertIn("REVOCAR", dict(ayuda.PAGINAS)["TIEMPO LÍMITE"])

    def test_las_paginas_caben(self):
        import pygame
        pygame.init()
        for titulo, texto in ayuda.PAGINAS:
            with self.subTest(pagina=titulo):
                self.assertLessEqual(len(envolver(texto, 1, 208)), 12)
                self.assertLessEqual(len(titulo) * 12, 232)


class TestEscenasMultijugador(BaseJuego):
    """El anfitrión (este juego, con el servidor en un hilo) y un segundo cliente."""

    def esperar(self, condicion, segundos=6.0):
        fin = time.time() + segundos
        while time.time() < fin:
            self.juego.frame()
            self.otro.actualizar()
            if condicion():
                return True
            time.sleep(0.003)
        return False

    def fase(self):
        c = self.juego.cliente
        return c.estado["fase"] if c is not None and c.estado else None

    def test_partida_de_dos_por_la_interfaz(self):
        self.otro = Cliente()
        self.ir("sala")                                        # fuera del menú hasta rehacer el modo
        self.assertEqual(self.escena(), "SalaScene")
        self.pulsar(im.CONFIRMAR)                              # CREAR PARTIDA
        sala = self.juego.escenas.actual
        if self.juego.servidor is None:
            self.skipTest(f"no se pudo abrir el servidor: {sala.aviso}")
        self.assertEqual(sala.modo, "sala")
        self.assertTrue(self.otro.conectar("127.0.0.1", "rival"))
        self.assertTrue(self.esperar(lambda: self.fase() == "sala" and len(self.juego.cliente.estado["jugadores"]) == 2))
        self.otro.enviar("rol", rol="influencer")
        self.assertTrue(self.esperar(lambda: self.juego.cliente.estado["jugadores"][1]["rol"] == "influencer"))
        self.pulsar(im.DERECHA)                                # el anfitrión cambia de rol: GENERAL
        self.assertTrue(self.esperar(lambda: [j["rol"] for j in self.juego.cliente.estado["jugadores"]]
                                     == ["general", "influencer"]))
        self.otro.enviar("listo")
        self.pulsar(im.CONFIRMAR)                              # LISTO
        self.assertTrue(self.esperar(lambda: all(j["listo"] for j in self.juego.cliente.estado["jugadores"])))
        self.pulsar(im.ABAJO)
        self.pulsar(im.CONFIRMAR)                              # EMPEZAR PARTIDA
        self.assertTrue(self.esperar(lambda: self.escena() == "PartidaRedScene" and self.fase() == "informe"))
        self.pulsar(im.DERECHA)                                # página de la ruta
        self.assertEqual(self.juego.escenas.actual.pagina, 1)
        hay_corta = "corta" in self.juego.cliente.estado["datos"]["rutas"]   # depende del azar del mapa
        self.pulsar(im.ABAJO)                                  # el anfitrión cambia a la ruta corta
        if hay_corta:
            self.assertTrue(self.esperar(lambda: self.juego.cliente.estado["datos"]["clave"] == "corta"))
        self.frames(30)                                        # pasa la espera anti-pulsación
        self.otro.enviar("listo")
        self.pulsar(im.CONFIRMAR)
        self.assertTrue(self.esperar(lambda: self.fase() == "nivel"))
        escena = self.juego.escenas.actual
        self.assertTrue(self.esperar(lambda: escena.vista is not None))
        self.assertEqual(len(escena.vista.estado.jugadores), 2)
        self.assertEqual(escena.vista.jugador_local().rol, "general")
        self.assertEqual(escena.vista.jugador_local().arma, "triple")
        sesion = self.juego.servidor.sesion
        self.assertTrue(self.esperar(lambda: sesion.estado.jefe is not None and sesion.estado.jefe.estado != "entrada"))
        sesion.estado.jefe.recibir_dano(999, sesion.estado)
        sesion.estado._jefe_derrotado()
        self.assertTrue(self.esperar(lambda: self.fase() == "votacion"))
        self.otro.enviar("voto", decision=LIBERAR)
        self.pulsar(im.CONFIRMAR)                              # el anfitrión vota CAPTURAR
        self.assertTrue(self.esperar(lambda: self.fase() == "resultado"))
        self.assertEqual(self.juego.cliente.estado["datos"]["decision"], CAPTURAR)   # empate: primera en orden
        self.assertEqual(self.juego.servidor.sesion.partida.rutas[1]["clave"], "corta" if hay_corta else "segura")
        self.frames(60)                                        # se dibuja el resultado
        sesion.partida.nivel = 3                               # atajo de la prueba: era el último nivel
        self.otro.enviar("listo")
        self.pulsar(im.CONFIRMAR)
        self.assertTrue(self.esperar(lambda: self.fase() == "final"))
        self.frames(100)
        self.assertEqual(len(self.juego.cliente.estado["datos"]["tabla"]), 2)
        self.pulsar(im.CONFIRMAR)                              # el anfitrión vuelve a la sala
        self.assertTrue(self.esperar(lambda: self.escena() == "SalaScene"))
        self.assertEqual(self.juego.escenas.actual.modo, "sala")
        self.otro.cerrar()

    def test_unirse_sin_servidor_muestra_el_error(self):
        sala = self.ir("sala")
        sala.modo, sala.ip = "ip", "127.0.0.1"
        sala._unirse("127.0.0.1")
        self.assertEqual(sala.modo, "menu")
        self.assertIn("NO SE PUDO CONECTAR", sala.aviso)
        self.assertIsNone(self.juego.cliente)
        self.frames(5)

    def test_si_se_cae_el_servidor_se_vuelve_a_la_sala(self):
        sala = self.ir("sala")
        sala._crear()
        if self.juego.servidor is None:
            self.skipTest(sala.aviso)
        self.frames(30)
        self.juego.servidor.detener()
        for _ in range(200):
            self.juego.frame()
            time.sleep(0.003)
            if sala.modo == "menu":
                break
        self.assertEqual(sala.modo, "menu")
        self.assertTrue(sala.aviso)


if __name__ == "__main__":
    unittest.main()
