"""Pruebas de la lógica del nivel: física, disparo, sicario, jefes, vidas y serialización.

Solo usan core/ (sin dibujar), lo que demuestra que la lógica está separada del render.
"""
import copy
import math
import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame  # noqa: E402

import input_manager as im  # noqa: E402
import settings  # noqa: E402
from core.bullet import Bala  # noqa: E402
from core.enemy import Sicario  # noqa: E402
from core.game_state import EstadoJuego  # noqa: E402
from core.player import Jugador  # noqa: E402
from levels import NIVELES, nivel1  # noqa: E402
from tests.bot import Bot  # noqa: E402

DT = settings.DT
NADA = im.EstadoAcciones()


def acc(*mantenidas, pulsadas=()):
    return {1: im.EstadoAcciones(frozenset(mantenidas), frozenset(pulsadas))}


def nivel_prueba(numero=99, jefe=1, **cambios):
    """Nivel plano de 2 pantallas, sin enemigos, para aislar cada mecánica."""
    datos = copy.deepcopy(nivel1.NIVEL)
    datos.update({"largo": 512, "jefe": jefe, "suelo": [[0, 512, 192]], "plataformas": [],
                  "bloques": [], "enemigos": [], "powerups": [], "tutorial": []})
    datos.update(cambios)
    NIVELES[numero] = datos
    return numero


class BaseNivel(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()

    def nuevo(self, **cambios):
        self.estado = EstadoJuego.nuevo(nivel_prueba(**cambios), [Jugador()])
        self.jugador = self.estado.jugadores[0]
        self.pasos(5)
        return self.estado

    def pasos(self, n, acciones=None):
        for _ in range(n):
            self.estado.update(DT, acciones or {1: NADA})


class TestFisica(BaseNivel):
    def test_queda_quieto_en_el_suelo(self):
        self.nuevo()
        self.pasos(120)
        self.assertTrue(self.jugador.en_suelo)
        self.assertAlmostEqual(self.jugador.pie, 192)

    def test_salto_sube_y_vuelve_al_suelo(self):
        self.nuevo()
        self.estado.update(DT, acc(im.SALTAR, pulsadas=[im.SALTAR]))
        alturas = []
        for _ in range(90):
            self.estado.update(DT, acc(im.SALTAR))
            alturas.append(self.jugador.pie)
        self.assertLess(min(alturas), 192 - 40)       # sube más de 40 px
        self.assertTrue(self.jugador.en_suelo)

    def test_salto_corto_al_soltar(self):
        self.nuevo()
        self.estado.update(DT, acc(im.SALTAR, pulsadas=[im.SALTAR]))
        alturas = [self.jugador.pie]
        for _ in range(60):
            self.estado.update(DT, {1: NADA})
            alturas.append(self.jugador.pie)
        self.assertGreater(min(alturas), 192 - 25)    # soltar pronto = salto bajo

    def test_plataforma_de_una_via(self):
        self.nuevo(plataformas=[[20, 150, 60]])
        self.jugador.x = 40
        self.estado.update(DT, acc(im.SALTAR, pulsadas=[im.SALTAR]))
        self.pasos(60, acc(im.SALTAR))
        self.assertAlmostEqual(self.jugador.pie, 150)  # atravesó desde abajo y quedó encima
        self.estado.update(DT, acc(im.ABAJO, im.SALTAR, pulsadas=[im.SALTAR]))
        self.pasos(60)
        self.assertAlmostEqual(self.jugador.pie, 192)  # ABAJO + SALTAR la atraviesa hacia abajo

    def test_caer_al_precipicio_quita_vida(self):
        self.nuevo(suelo=[[0, 60, 192], [120, 512, 192]])
        self.pasos(120, acc(im.DERECHA))
        self.assertEqual(self.jugador.vidas, settings.JUGADOR["vidas"] - 1)


class TestDisparo(BaseNivel):
    CASOS = {
        (): (1, 0),
        (im.DERECHA,): (1, 0),
        (im.IZQUIERDA,): (-1, 0),
        (im.ARRIBA,): (0, -1),
        (im.ABAJO,): (0, 1),               # solo en el aire
        (im.DERECHA, im.ARRIBA): (1, -1),
        (im.IZQUIERDA, im.ARRIBA): (-1, -1),
        (im.DERECHA, im.ABAJO): (1, 1),
        (im.IZQUIERDA, im.ABAJO): (-1, 1),
    }

    def test_ocho_direcciones(self):
        for direcciones, (ex, ey) in self.CASOS.items():
            with self.subTest(direcciones=direcciones):
                self.nuevo()
                self.jugador.x = 200
                self.jugador.y, self.jugador.en_suelo = 60, False   # en el aire, para apuntar abajo
                self.estado.balas.clear()
                self.estado.update(DT, acc(im.DISPARAR, *direcciones))
                bala = self.estado.balas[0]
                self.assertEqual((int(math.copysign(1, bala.vx)) if abs(bala.vx) > 1 else 0,
                                  int(math.copysign(1, bala.vy)) if abs(bala.vy) > 1 else 0), (ex, ey))

    def test_sin_direccion_dispara_hacia_donde_mira(self):
        self.nuevo()
        self.pasos(10, acc(im.IZQUIERDA))
        self.estado.update(DT, acc(im.DISPARAR))
        self.assertLess(self.estado.balas[-1].vx, 0)

    def test_disparo_triple(self):
        self.nuevo()
        self.jugador.arma = "triple"
        self.estado.update(DT, acc(im.DISPARAR))
        self.assertEqual(len(self.estado.balas), 3)


class TestSicario(BaseNivel):
    def test_muere_de_un_impacto_y_da_puntos(self):
        self.nuevo()
        self.estado.invocar_sicario(150, -1)
        self.pasos(1)
        self.jugador.x = 60
        self.pasos(60, acc(im.DISPARAR))
        self.assertEqual(len(self.estado.sicarios), 0)
        self.assertEqual(self.jugador.puntaje, settings.SICARIO["puntos"])

    def test_corre_hacia_el_jugador_y_dispara_bala_lenta_recta(self):
        self.nuevo()
        self.jugador.x = 30
        self.estado.invocar_sicario(200, 1)        # empieza mirando al lado contrario
        s = self.estado.sicarios[0]
        s.recarga = 0.1
        self.pasos(int(0.6 / DT))
        balas = [b for b in self.estado.balas if not b.del_jugador]
        self.assertEqual(len(balas), 1)
        self.assertAlmostEqual(abs(balas[0].vx), settings.SICARIO["vel_bala"])
        self.assertEqual(balas[0].vy, 0)
        self.pasos(30)
        self.assertLess(s.vx, 0)                   # tras disparar corre hacia el jugador

    def test_agacharse_esquiva_su_bala(self):
        self.nuevo()
        self.jugador.x = 60
        y_arma = 192 - settings.SICARIO["alto"] + settings.SICARIO["arma"][1]   # altura real de su disparo
        self.estado.agregar_bala(Bala(200, y_arma, -70, 0, del_jugador=False))
        self.pasos(int(3 / DT), acc(im.ABAJO))
        self.assertEqual(self.jugador.salud, settings.JUGADOR["salud"])

    def test_un_solo_tipo_de_enemigo_en_los_datos(self):
        for numero, datos in NIVELES.items():
            for e in datos["enemigos"]:
                self.assertLessEqual(set(e), {"x", "y", "lado"}, f"nivel {numero}: {e}")


class TestCamaraYArena(BaseNivel):
    def test_camara_solo_avanza_y_se_bloquea_en_la_arena(self):
        self.nuevo()
        self.pasos(400, acc(im.DERECHA))
        self.assertTrue(self.estado.arena_activa)
        self.assertEqual(self.estado.camara_x, self.estado.arena_x)
        self.assertIsNotNone(self.estado.jefe)
        self.pasos(400, acc(im.IZQUIERDA))
        self.assertEqual(self.estado.camara_x, self.estado.arena_x)
        self.assertGreaterEqual(self.jugador.x, self.estado.arena_x)


class TestJefes(BaseNivel):
    ESPERADOS = {
        1: {"esperar", "rafaga", "saltar", "barrido"},
        2: {"esperar", "abanico", "preparar", "embestida", "aturdido"},
        3: {"esperar", "dirigido", "onda", "invocar"},
    }

    def pelear(self, tipo, segundos=30):
        self.nuevo(jefe=tipo)
        self.pasos(400, acc(im.DERECHA))
        estados, balas, sicarios = set(), [], 0
        for _ in range(int(segundos / DT)):
            self.jugador.invulnerable = 1.0
            self.estado.update(DT, acc(im.ABAJO))
            estados.add(self.estado.jefe.estado)
            balas += [b for b in self.estado.balas if not b.del_jugador and b not in balas]
            sicarios = max(sicarios, len(self.estado.sicarios))
        return estados, balas, sicarios

    def test_maquinas_de_estado_recorren_todos_sus_estados(self):
        for tipo, esperados in self.ESPERADOS.items():
            with self.subTest(jefe=tipo):
                estados, _, _ = self.pelear(tipo)
                self.assertLessEqual(esperados, estados)

    def test_balas_mas_rapidas_y_daninas_que_el_sicario(self):
        for tipo in (1, 2, 3):
            stats = settings.JEFES[tipo]
            self.assertGreater(stats["vel_bala"], settings.SICARIO["vel_bala"])
            self.assertGreater(stats["dano_bala"], settings.SICARIO["dano_bala"])
            self.assertGreater(stats["vida"], settings.SICARIO["vida"])

    def test_jefe1_rafagas_horizontales(self):
        self.nuevo(jefe=1)
        self.pasos(400, acc(im.DERECHA))
        jefe = self.estado.jefe
        jefe.cambiar("rafaga")
        self.estado.balas.clear()
        self.pasos(int(0.6 / DT))
        balas = [b for b in self.estado.balas if not b.del_jugador]
        self.assertTrue(balas)
        self.assertTrue(all(b.vy == 0 for b in balas))

    def test_jefe1_barrido_en_varias_direcciones(self):
        """El barrido sale en abanico: balas hacia arriba y hacia abajo, más lentas y de 1 corazón,
        con un hueco entre bala y bala por el que el presidente cabe."""
        from core.boss import BARRIDO_J1
        self.nuevo(jefe=1, largo=768, suelo=[[0, 768, 192]])
        self.pasos(500, acc(im.DERECHA))
        self.jugador.x = self.estado.arena_x + 20           # lejos, a la izquierda del jefe
        jefe = self.estado.jefe
        jefe.mirando = -1
        jefe.cambiar("barrido")
        self.estado.eventos.clear()
        vistas = {}
        for _ in range(int(1.4 / DT)):
            self.jugador.invulnerable = 1.0
            self.estado.update(DT, {1: NADA})
            for b in self.estado.balas:
                if not b.del_jugador:
                    vistas[round(b.vy, 1)] = b
        self.assertEqual(len(vistas), len(BARRIDO_J1))      # una dirección por bala
        self.assertTrue(any(vy < 0 for vy in vistas) and any(vy > 0 for vy in vistas))
        for b in vistas.values():
            self.assertLess(math.hypot(b.vx, b.vy), settings.JEFES[1]["vel_bala"])
            self.assertEqual(b.dano, 1)
        # A 100 px, dos balas vecinas (16 grados) quedan separadas más que el ancho del jugador
        self.assertGreater(100 * math.tan(math.radians(16)), settings.JUGADOR["ancho"] * 2)

    def test_jefe2_abanico_de_tres(self):
        self.nuevo(jefe=2)
        self.pasos(400, acc(im.DERECHA))
        jefe = self.estado.jefe
        jefe.cambiar("abanico")
        self.estado.eventos.clear()
        self.pasos(int(0.3 / DT))
        disparos = [e for e in self.estado.eventos if e["tipo"] == "disparo_jefe"]
        self.assertEqual(len(disparos), 3)

    def test_jefe2_embiste_agachado_y_se_puede_saltar(self):
        self.nuevo(jefe=2)
        self.pasos(400, acc(im.DERECHA))
        self.pasos(int(2 / DT))                                     # termina la entrada
        jefe = self.estado.jefe
        pie = jefe.pie
        self.jugador.x = jefe.arena_x0 + 80                         # con lugar para caer detrás de él
        jefe.mirando = -1
        jefe.cambiar("embestida")
        self.estado.balas.clear()
        self.jugador.invulnerable = 0.0                             # que un golpe sí cuente
        self.assertEqual(jefe.alto, settings.JEFES[2]["alto_embestida"])
        self.assertAlmostEqual(jefe.pie, pie)
        alto_salto = settings.JUGADOR["vel_salto"] ** 2 / (2 * settings.GRAVEDAD)
        self.assertGreater(alto_salto, jefe.alto + 8)
        salud, salto = self.jugador.salud, False
        for _ in range(int(3 / DT)):
            cerca = abs(jefe.centro[0] - self.jugador.centro[0]) < 68      # ver settings.JEFES[2]
            pulsar = cerca and not salto and self.jugador.en_suelo
            salto = salto or pulsar
            self.estado.update(DT, acc(im.SALTAR, pulsadas=(im.SALTAR,) if pulsar else ()))
            if jefe.estado != "embestida":
                break
        self.assertEqual(jefe.estado, "aturdido")                   # llegó a la pared
        self.assertEqual(jefe.alto, settings.JEFES[2]["alto_embestida"])   # aturdido sigue agachado
        while jefe.estado == "aturdido":
            self.estado.update(DT, {1: NADA})
        self.assertEqual(self.jugador.salud, salud)                 # le pasó por debajo
        self.assertEqual(jefe.alto, settings.JEFES[2]["alto"])      # y después se levanta
        self.assertAlmostEqual(jefe.pie, pie)

    def test_jefe3_onda_e_invocacion(self):
        _, balas, sicarios = self.pelear(3)
        self.assertTrue(any(b.tipo == "onda" for b in balas))
        self.assertGreaterEqual(sicarios, 2)

    def test_derrotar_jefe_da_victoria(self):
        self.nuevo(jefe=1)
        self.pasos(400, acc(im.DERECHA))
        self.pasos(int(2 / DT))                     # termina la entrada
        self.estado.jefe.vida = 1
        self.estado.jefe.recibir_dano(1, self.estado)
        self.estado._jefe_derrotado()
        self.pasos(int(3.1 / DT))
        self.assertTrue(self.estado.victoria)


class TestAcostado(BaseNivel):
    """El presidente acostado boca abajo: caja ancha y baja, centrada donde estaba de pie."""

    def test_caja_ancha_y_baja_sin_saltos(self):
        self.nuevo()
        self.jugador.x = 100
        self.pasos(2)
        centro, pie = self.jugador.centro[0], self.jugador.pie
        self.pasos(2, acc(im.ABAJO))
        self.assertTrue(self.jugador.agachado)
        self.assertEqual((self.jugador.ancho, self.jugador.alto),
                         (settings.JUGADOR["ancho_agachado"], settings.JUGADOR["alto_agachado"]))
        self.assertAlmostEqual(self.jugador.centro[0], centro)     # no se desplaza al acostarse
        self.assertAlmostEqual(self.jugador.pie, pie)              # ni se hunde en el suelo
        self.pasos(2)
        self.assertFalse(self.jugador.agachado)
        self.assertEqual(self.jugador.ancho, settings.JUGADOR["ancho"])
        self.assertAlmostEqual(self.jugador.centro[0], centro)
        self.assertAlmostEqual(self.jugador.pie, pie)

    def test_dispara_en_horizontal_a_ras_de_suelo(self):
        self.nuevo()
        self.pasos(2, acc(im.ABAJO))
        self.estado.balas.clear()
        self.pasos(1, acc(im.ABAJO, im.DISPARAR))
        balas = [b for b in self.estado.balas if b.del_jugador]
        self.assertTrue(balas)
        self.assertEqual(balas[0].vy, 0)
        self.assertGreater(balas[0].vx, 0)
        self.assertLess(self.jugador.pie - balas[0].y, 8)          # a ras de suelo
        self.assertGreater(balas[0].x, self.jugador.centro[0] + 10)   # sale de la punta del fusil

    def test_las_balas_altas_le_pasan_por_encima(self):
        alto = settings.JUGADOR["alto_agachado"]
        altura_sicario = settings.SICARIO["alto"] - settings.SICARIO["arma"][1]
        moto = settings.VEHICULOS["moto"]
        altura_moto = moto["caja"][1] - moto["arma"][1]
        for altura in (altura_sicario, altura_moto):
            self.assertGreater(altura - 2, alto)                   # radio de la bala: 2

    def test_junto_a_una_pared_se_corre_para_caber(self):
        self.nuevo(bloques=[[120, 140, 20, 52]])
        self.jugador.x = 106                                       # pegado a la pared
        self.pasos(2)
        self.pasos(2, acc(im.ABAJO))
        self.assertTrue(self.jugador.agachado)
        self.assertLessEqual(self.jugador.x + self.jugador.ancho, 120)


class TestVidas(BaseNivel):
    def test_game_over_al_perder_todas_las_vidas(self):
        self.nuevo()
        for _ in range(settings.JUGADOR["vidas"]):
            self.jugador.morir(self.estado)
            self.pasos(int(1.5 / DT))
        self.assertTrue(self.estado.game_over)

    def test_invulnerable_tras_golpe(self):
        self.nuevo()
        self.jugador.recibir_dano(1, self.estado)
        self.jugador.recibir_dano(1, self.estado)   # ignorado: invulnerable
        self.assertEqual(self.jugador.salud, settings.JUGADOR["salud"] - 1)

    def test_powerup_vida(self):
        self.nuevo(powerups=[{"x": 40, "y": 176, "tipo": "vida"}])
        self.pasos(60, acc(im.DERECHA))
        self.assertEqual(self.jugador.vidas, settings.JUGADOR["vidas"] + 1)


class TestSerializacion(BaseNivel):
    def test_ida_y_vuelta(self):
        self.nuevo(enemigos=[{"x": 300}])
        self.pasos(200, acc(im.DERECHA, im.DISPARAR))
        datos = self.estado.to_dict()
        self.assertEqual(EstadoJuego.from_dict(datos).to_dict(), datos)


class TestNivel1Completo(BaseNivel):
    def test_bot_completa_el_nivel_1(self):
        """Integración: un bot invencible recorre el nivel 1 real y derrota al jefe."""
        self.estado = EstadoJuego.nuevo(1, [Jugador()])
        j, bot = self.estado.jugadores[0], Bot()
        for paso in range(int(150 / DT)):
            j.invulnerable = 1.0
            direccion = 1 if not self.estado.arena_activa or (paso // 90) % 2 == 0 else -1
            self.estado.update(DT, bot.acciones(self.estado, j, direccion))
            if self.estado.victoria:
                break
        self.assertTrue(self.estado.victoria)


if __name__ == "__main__":
    unittest.main()


class TestPosesJugador(BaseNivel):
    """La pose depende del estado y la bala sale de la punta del arma de esa pose."""
    CASOS = [
        ((), True, "quieto"),
        ((im.DISPARAR,), True, "disparar"),
        ((im.DERECHA,), True, "correr"),
        ((im.ARRIBA,), True, "arriba"),
        ((im.DERECHA, im.ARRIBA), True, "diag_arriba"),
        ((im.DERECHA, im.ABAJO), True, "diag_abajo"),
        ((im.ABAJO,), True, "agachado"),
        ((), False, "saltar"),
        ((im.ABAJO,), False, "abajo"),
    ]

    def test_pose_segun_estado(self):
        for teclas, en_suelo, esperada in self.CASOS:
            with self.subTest(teclas=teclas, en_suelo=en_suelo):
                self.nuevo()
                self.jugador.x = 200
                if not en_suelo:
                    self.jugador.y, self.jugador.en_suelo = 60, False
                self.estado.update(DT, acc(*teclas))
                self.assertEqual(self.jugador.pose(), esperada)

    def test_quieto_vuelve_tras_dejar_de_disparar(self):
        self.nuevo()
        self.estado.update(DT, acc(im.DISPARAR))
        self.assertEqual(self.jugador.pose(), "disparar")
        self.pasos(30)
        self.assertEqual(self.jugador.pose(), "quieto")

    def test_pose_herido(self):
        self.nuevo()
        self.jugador.recibir_dano(1, self.estado)
        self.assertEqual(self.jugador.pose(), "herido")
        self.pasos(30)
        self.assertNotEqual(self.jugador.pose(), "herido")

    def test_bala_sale_de_la_boca_del_sprite(self):
        from core.datos_sprites import boca_jugador
        self.nuevo()
        self.jugador.x = 200
        self.pasos(10, acc(im.IZQUIERDA))                 # mirando a la izquierda: la boca se refleja
        self.estado.balas.clear()
        self.estado.update(DT, acc(im.DISPARAR))
        boca = boca_jugador("disparar", self.jugador.t_anim)
        if boca is None:
            self.skipTest("no hay PNG de las poses")
        bala = self.estado.balas[0]
        origen_x, origen_y = bala.x - bala.vx * DT, bala.y - bala.vy * DT   # ya avanzó un paso
        self.assertAlmostEqual(origen_x, self.jugador.centro[0] - boca[0], delta=0.5)
        self.assertAlmostEqual(origen_y, self.jugador.pie + boca[1], delta=0.5)


class TestSicarioPersigue(BaseNivel):
    """Los sicarios que aparecen por detrás (o a los que el jugador pasa) lo persiguen."""

    def test_el_que_aparece_por_detras_alcanza_al_jugador(self):
        self.nuevo(largo=2000, suelo=[[0, 2000, 192]])
        self.jugador.x = 400
        self.estado.camara_x = 300
        self.estado.invocar_sicario(self.estado.camara_x - 10, -1)   # detrás y mirando al lado contrario
        s = self.estado.sicarios[0]
        for _ in range(int(4 / DT)):                                 # el jugador sigue avanzando
            self.jugador.invulnerable = 1
            self.estado.update(DT, acc(im.DERECHA))
        self.assertIn(s, self.estado.sicarios)                       # no se perdió por detrás
        self.assertEqual(s.direccion, 1)
        self.assertTrue(self.estado.en_pantalla(s.rect))
        self.assertLess(self.jugador.centro[0] - s.centro[0], 150)

    def test_se_da_vuelta_cuando_el_jugador_lo_pasa(self):
        self.nuevo()
        self.jugador.x = 60
        self.estado.invocar_sicario(160, -1)
        s = self.estado.sicarios[0]
        s.recarga = 99                                               # que no se detenga a disparar
        self.jugador.x = 200                                         # el jugador queda del otro lado
        self.pasos(int(0.6 / DT))
        self.assertEqual(s.direccion, 1)
        self.assertGreater(s.vx, 0)

    def test_sube_escalones_en_vez_de_darse_vuelta(self):
        self.nuevo(suelo=[[0, 150, 192], [150, 512, 176]])          # escalón de 16 px
        self.jugador.x = 230                                         # la cámara no avanza: el sicario sigue en juego
        self.estado.invocar_sicario(80, 1)
        s = self.estado.sicarios[0]
        s.recarga = 99
        self.pasos(int(3 / DT))
        self.assertGreater(s.x, 150)                                 # pasó el escalón
        self.assertAlmostEqual(s.pie, 176)


class TestAparicionPorDetras(BaseNivel):
    def test_no_aparece_sobre_un_precipicio(self):
        # Precipicio justo donde caería el que entra por detrás (cámara - 10)
        self.nuevo(largo=2000, suelo=[[0, 270, 192], [330, 2000, 192]], enemigos=[{"x": 600, "lado": "izquierda"}])
        self.jugador.x = 400
        self.pasos(int(1 / DT), acc(im.DERECHA))
        self.assertEqual(len(self.estado.sicarios), 1)
        s = self.estado.sicarios[0]
        self.pasos(30)
        self.assertIn(s, self.estado.sicarios)
        self.assertTrue(s.en_suelo)
