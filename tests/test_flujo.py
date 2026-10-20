"""Integración: una partida completa en modo headless, de menú a menú, pasando por el árbol."""
import os
import unittest

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import input_manager as im  # noqa: E402
from core.decision_tree import CAPTURAR, EXTRADITAR, LIBERAR, final_de  # noqa: E402
from main import Juego  # noqa: E402

# Cuántas veces pulsar DERECHA en la escena de decisión para cada opción
POSICION = {CAPTURAR: 0, EXTRADITAR: 1, LIBERAR: 2}


class TestFlujoCompleto(unittest.TestCase):
    def setUp(self):
        self.juego = Juego(headless=True, arena=True)

    def escena(self):
        return type(self.juego.escenas.actual).__name__

    def frames(self, n):
        for _ in range(n):
            self.juego.frame()

    def pulsar(self, accion, despues=3):
        self.juego.entrada.simular(accion)
        self.frames(1 + despues)

    def saltar_historia(self):
        """Informe antes del nivel: un toque completa el texto y otro pasa la página (2 páginas)."""
        for _ in range(6):
            if self.escena() != "HistoriaScene":
                break
            self.pulsar(im.CONFIRMAR)

    def vencer_jefe(self):
        self.saltar_historia()
        self.assertEqual(self.escena(), "LevelScene")
        estado = self.juego.escenas.actual.estado
        self.frames(150)                                    # entra a la arena y termina la presentación
        self.assertIsNotNone(estado.jefe)
        estado.jefe.recibir_dano(999, estado)
        estado._jefe_derrotado()
        self.frames(200)                                    # 3 s de explosiones
        self.assertEqual(self.escena(), "DecisionScene")

    def decidir(self, decision):
        self.frames(40)                                     # espera inicial anti-pulsación accidental
        for _ in range(POSICION[decision]):
            self.pulsar(im.DERECHA)
        self.pulsar(im.CONFIRMAR)
        self.frames(80)                                     # animación del sello
        self.pulsar(im.CONFIRMAR)                           # no revoca: sigue sin esperar la ventana
        self.assertEqual(self.escena(), "PhoneScene")
        self.frames(int(3.1 * 60))                           # se puede saltar desde los 3 s
        self.pulsar(im.CONFIRMAR)

    def test_partida_completa(self):
        self.pulsar(im.CONFIRMAR)                           # menú: JUGAR
        camino = [EXTRADITAR, LIBERAR, LIBERAR]
        for nivel, decision in enumerate(camino, start=1):
            self.assertEqual(self.juego.partida.nivel, nivel)
            self.vencer_jefe()
            self.decidir(decision)
        arbol = self.juego.partida.arbol
        self.assertEqual(arbol.camino(), camino)
        self.assertTrue(arbol.terminado)
        self.assertEqual(len(self.juego.partida.jefes_derrotados), 3)
        self.assertEqual(self.escena(), "EndingScene")
        self.assertEqual(self.juego.escenas.actual.final.clave, final_de(arbol.actual).clave)
        self.assertEqual(self.juego.escenas.actual.final.clave, "cuestionado")
        self.frames(100)
        self.pulsar(im.CONFIRMAR)
        self.assertEqual(self.escena(), "MenuScene")
        self.assertIsNone(self.juego.partida)

    def test_la_opinion_del_hud_viene_del_arbol(self):
        self.pulsar(im.CONFIRMAR)
        self.vencer_jefe()
        self.decidir(LIBERAR)
        self.saltar_historia()
        estado = self.juego.escenas.actual.estado         # ya en el nivel 2
        self.assertEqual(estado.opinion, self.juego.partida.arbol.opinion())
        self.assertLess(estado.opinion["pueblo"], 50)

    def test_telefono_no_se_salta_antes_de_3_segundos_y_avanza_solo(self):
        self.pulsar(im.CONFIRMAR)
        self.vencer_jefe()
        self.frames(40)
        self.pulsar(im.CONFIRMAR)
        self.frames(80)
        self.frames(int(2.6 * 60))                          # pasa sola la ventana para revocar
        self.assertEqual(self.escena(), "PhoneScene")
        self.pulsar(im.CONFIRMAR)                           # antes de 3 s: se ignora
        self.assertEqual(self.escena(), "PhoneScene")
        self.frames(int(10 * 60))                           # a los 10 s sigue solo al informe del nivel 2
        self.assertEqual(self.escena(), "HistoriaScene")
        self.assertEqual(self.juego.partida.nivel, 2)

    def test_pulsar_al_entrar_no_decide(self):
        self.pulsar(im.CONFIRMAR)
        self.vencer_jefe()
        self.pulsar(im.CONFIRMAR, despues=0)                # durante la espera inicial: se ignora
        self.assertEqual(self.juego.partida.arbol.camino(), [])


if __name__ == "__main__":
    unittest.main()


class TestTelefonoManual(unittest.TestCase):
    """El jugador puede desplazar el feed y leer a su ritmo."""

    def setUp(self):
        self.juego = Juego(headless=True)
        partida = self.juego.nueva_partida()
        partida.arbol.decidir(CAPTURAR)
        partida.jefes_derrotados = ["EL JAGUAR DEL MONTE"]
        self.juego.escenas.cambiar("telefono", decision=CAPTURAR)
        self.juego.escenas.aplicar_cambios()
        self.escena = self.juego.escenas.actual

    def paso(self, *mantenidas, pulsadas=()):
        self.escena.update(1 / 60, {1: im.EstadoAcciones(frozenset(mantenidas), frozenset(pulsadas))})
        self.juego.escenas.aplicar_cambios()

    def test_abajo_y_arriba_desplazan(self):
        for _ in range(30):
            self.paso(im.ABAJO)
        bajado = self.escena.desplazamiento
        self.assertGreater(bajado, 30)
        self.assertTrue(self.escena.manual)
        for _ in range(20):
            self.paso(im.ARRIBA)
        self.assertLess(self.escena.desplazamiento, bajado)
        for _ in range(200):
            self.paso(im.ARRIBA)
        self.assertEqual(self.escena.desplazamiento, 0)       # no se pasa del inicio

    def test_en_modo_manual_no_avanza_solo(self):
        self.paso(im.ABAJO)
        for _ in range(int(15 * 60)):                       # más que DURACION
            self.paso()
        self.assertIs(self.juego.escenas.actual, self.escena)
        auto = self.escena.desplazamiento
        for _ in range(120):
            self.paso()
        self.assertEqual(self.escena.desplazamiento, auto)  # sin toques automáticos
        self.paso(pulsadas=[im.CONFIRMAR])
        self.assertEqual(type(self.juego.escenas.actual).__name__, "HistoriaScene")


class TestPulgarTelefono(TestTelefonoManual):
    """El pulgar: extendido en reposo, flexionado al desplazar, base fija y cortada abajo."""

    def test_presiona_al_desplazar_y_suelta_tras_100_ms(self):
        self.assertEqual(self.escena.anim_pulgar, "quieto")
        self.paso(im.ABAJO)
        self.assertEqual(self.escena.anim_pulgar, "presionando")
        for _ in range(5):                                  # 83 ms después de soltar: sigue presionando
            self.paso()
        self.assertEqual(self.escena.anim_pulgar, "presionando")
        for _ in range(2):                                  # pasados ~100 ms: vuelve al extendido
            self.paso()
        self.assertEqual(self.escena.anim_pulgar, "quieto")

    def test_yema_en_el_punto_de_contacto_y_base_fuera_de_pantalla(self):
        from scenes.phone import CONTACTO, FEED
        bx, by = self.escena.base_pulgar
        dx, dy = self.escena.yema("presionando")
        self.assertEqual((bx + dx, by + dy), CONTACTO)      # la yema presionando toca el contacto
        self.assertTrue(FEED.collidepoint(CONTACTO))         # ...dentro del feed
        self.assertGreater(by, 224)                          # la base sale por el borde inferior
        self.paso(im.ABAJO)
        self.assertEqual(self.escena.base_pulgar, (bx, by))  # la base no se mueve al presionar
