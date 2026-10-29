"""Refuerzos aleatorios (dron, moto, camioneta), armas, suministros y el director que los reparte."""
import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame  # noqa: E402

import input_manager as im  # noqa: E402
import settings  # noqa: E402
from core import director  # noqa: E402
from core.game_state import EstadoJuego, PowerUp  # noqa: E402
from core.player import Jugador  # noqa: E402
from core.vehiculos import Vehiculo  # noqa: E402
from levels import NIVELES, ULTIMO_NIVEL  # noqa: E402
from tests.bot import Bot  # noqa: E402
from tests.test_nivel import DT, NADA, BaseNivel, acc, nivel_prueba  # noqa: E402

LARGOS = {n: NIVELES[n]["largo"] for n in (1, 2, 3)}
ALEATORIO = {n: NIVELES[n]["aleatorio"] for n in (1, 2, 3)}       # la dificultad vive en levels/


class TestDirector(unittest.TestCase):
    def test_misma_semilla_mismo_plan(self):
        self.assertEqual(director.planear(2, LARGOS[2], 77), director.planear(2, LARGOS[2], 77))

    def test_cada_partida_es_distinta(self):
        planes = {str(director.planear(2, LARGOS[2], s)) for s in range(20)}
        self.assertGreater(len(planes), 15)

    def test_respeta_los_rangos_de_cada_nivel(self):
        for nivel, conf in ALEATORIO.items():
            for semilla in range(40):
                cuenta = director.resumen(director.planear(nivel, LARGOS[nivel], semilla))
                for tipo in ("dron", "moto", "camioneta"):
                    with self.subTest(nivel=nivel, semilla=semilla, tipo=tipo):
                        self.assertGreaterEqual(cuenta[tipo], 0)
                        self.assertLessEqual(cuenta[tipo], conf[tipo][1])
                self.assertLessEqual(cuenta["suministro"], conf["suministro"][1] + len(conf["fijos"]))
                self.assertGreaterEqual(cuenta["suministro"], len(conf["fijos"]))

    def test_el_nivel_1_no_tiene_camionetas_y_el_3_es_el_mas_duro(self):
        def promedio(nivel):
            total = 0
            for semilla in range(60):
                c = director.resumen(director.planear(nivel, LARGOS[nivel], semilla))
                total += c["dron"] + c["moto"] + c["camioneta"]
            return total / 60
        for semilla in range(60):
            self.assertEqual(director.resumen(director.planear(1, LARGOS[1], semilla))["camioneta"], 0)
        self.assertLess(promedio(1), promedio(2))
        self.assertLess(promedio(2), promedio(3))

    def test_los_niveles_2_y_3_garantizan_suministros_a_mitad_de_camino(self):
        for nivel in (2, 3):
            mitad = (LARGOS[nivel] - settings.ANCHO) / 2
            for semilla in range(20):
                plan = director.planear(nivel, LARGOS[nivel], semilla)
                centrales = [a for a in plan if a["tipo"] == "suministro" and abs(a["x"] - mitad) < 400]
                with self.subTest(nivel=nivel, semilla=semilla):
                    self.assertTrue(any(a["clase"] == "vida" for a in centrales))   # una vida extra, siempre
        clases = [f["clase"] for f in ALEATORIO[3]["fijos"]]
        self.assertEqual(sorted(clases), ["rapida", "vida"])                        # vida y un arma

    def test_sin_motos_por_la_espalda_en_los_primeros_15_segundos(self):
        """15 s corriendo son unos 1080 px: antes de "detras_desde" ninguna moto entra por detrás."""
        self.assertGreaterEqual(ALEATORIO[3]["detras_desde"], 15 * settings.JUGADOR["velocidad"])
        por_detras = 0
        for nivel in (2, 3):
            for semilla in range(80):
                for a in director.planear(nivel, LARGOS[nivel], semilla):
                    if a["tipo"] == "moto" and a["lado"] == "izquierda":
                        por_detras += 1
                        self.assertGreaterEqual(a["x"], ALEATORIO[nivel]["detras_desde"])
        self.assertGreater(por_detras, 10)                                          # pero después sí aparecen

    def test_el_nivel_3_quedo_mas_suave_pero_sigue_siendo_el_mas_duro(self):
        self.assertEqual(ALEATORIO[3]["dron"], (4, 5))          # antes (5, 7): -25 %
        self.assertEqual(ALEATORIO[3]["moto"], (3, 4))          # antes (4, 5): -25 %
        self.assertEqual(ALEATORIO[3]["camioneta"], (1, 2))     # antes (2, 3): una menos
        self.assertEqual(ALEATORIO[3]["vida_camioneta"], 8)     # antes 10
        self.assertEqual(settings.JEFES[3]["vida"], 60)         # antes 70: -15 %
        self.assertGreater(settings.JEFES[3]["vida"], settings.JEFES[2]["vida"])
        for tipo in ("dron", "moto", "camioneta"):
            self.assertGreaterEqual(ALEATORIO[3][tipo][1], ALEATORIO[2][tipo][1])
            self.assertGreaterEqual(ALEATORIO[2][tipo][1], ALEATORIO[1][tipo][1])

    def test_el_peligro_suma_refuerzos(self):
        def enemigos(peligro):
            c = director.resumen(director.planear(3, LARGOS[3], 5, peligro))
            return c["dron"] + c["moto"] + c["camioneta"]
        self.assertGreaterEqual(enemigos(3), enemigos(0) + 2)   # alguno puede no caber por la separación

    def test_posiciones_separadas_y_fuera_de_la_arena(self):
        for nivel in (1, 2, 3):
            plan = director.planear(nivel, LARGOS[nivel], 9, peligro=3)
            xs = [a["x"] for a in plan]
            self.assertEqual(xs, sorted(xs))
            self.assertGreaterEqual(xs[0], ALEATORIO[nivel]["desde"])
            self.assertLess(xs[-1], LARGOS[nivel] - settings.ANCHO)
            al_azar = [a["x"] for a in plan if a["tipo"] != "suministro"]
            for a, b in zip(al_azar, al_azar[1:]):               # los refuerzos no caen todos juntos
                self.assertGreaterEqual(b - a, settings.SEPARACION_ALEATORIA)

    def test_sin_semilla_no_hay_azar(self):
        pygame.init()
        self.assertEqual(EstadoJuego.nuevo(1, [Jugador()]).plan, [])
        self.assertTrue(EstadoJuego.nuevo(1, [Jugador()], semilla=3).plan)


class TestArmas(BaseNivel):
    def disparos_en(self, segundos):
        self.estado.eventos.clear()
        self.pasos(int(segundos / DT), acc(im.DISPARAR))
        return sum(1 for e in self.estado.eventos if e["tipo"] == "disparo_jugador")

    def test_arma_rapida_dispara_mucho_mas_rapido(self):
        self.nuevo()
        normales = self.disparos_en(2)
        self.jugador.arma = "rapida"
        rapidos = self.disparos_en(2)
        self.assertGreater(rapidos, normales * 1.8)

    def test_recoger_las_armas(self):
        for tipo in ("triple", "rapida"):
            with self.subTest(arma=tipo):
                self.nuevo(powerups=[{"x": 40, "y": 176, "tipo": tipo}])
                self.pasos(60, acc(im.DERECHA))
                self.assertEqual(self.jugador.arma, tipo)
                self.jugador.morir(self.estado)
                self.assertEqual(self.jugador.arma, "normal")    # el arma se pierde al morir

    def test_suministro_baja_y_se_queda_en_el_suelo(self):
        self.nuevo()
        self.estado.powerups.append(PowerUp(200, -14.0, "rapida", cayendo=True))
        self.pasos(int(5 / DT))
        p = self.estado.powerups[0]
        self.assertFalse(p.cayendo)
        self.assertAlmostEqual(p.y + 12, 192, delta=2)           # apoyado en el suelo (y=192)
        self.assertLessEqual(192 - p.y, settings.JUGADOR["alto"])   # se toca caminando

    def test_suministro_sobre_un_precipicio_se_pierde(self):
        self.nuevo(suelo=[[0, 100, 192], [200, 512, 192]])
        self.estado.powerups.append(PowerUp(140, -14.0, "vida", cayendo=True))
        self.pasos(int(6 / DT))
        self.assertEqual(self.estado.powerups, [])


class TestVehiculos(BaseNivel):
    def con(self, clase, x, direccion=-1, **datos):
        self.nuevo(largo=1024, suelo=[[0, 1024, 192]])
        stats = settings.VEHICULOS[clase]
        y = datos.pop("y", 192 - stats["caja"][1])
        v = Vehiculo.crear(clase, x, y, direccion, **datos)
        self.estado.vehiculos.append(v)
        return v

    def balas_enemigas(self):
        return [b for b in self.estado.balas if not b.del_jugador]

    def test_aviso_antes_de_entrar(self):
        v = self.con("moto", 300)
        self.assertEqual(v.estado, "aviso")
        self.assertFalse(v.activo)                              # durante el aviso no daña ni recibe daño
        v.recibir_dano(5, self.estado)
        self.assertEqual(v.vida, settings.VEHICULOS["moto"]["vida"])
        self.pasos(int((settings.VEHICULOS["moto"]["aviso"] + 0.1) / DT))
        self.assertEqual(v.estado, "correr")

    def test_dron_se_pone_encima_y_dispara_hacia_abajo(self):
        v = self.con("dron", 230, y=70, altura=70)
        vistas = []
        for _ in range(int(5 / DT)):
            self.jugador.invulnerable = 1.0
            self.estado.update(DT, {1: NADA})
            vistas += [b for b in self.balas_enemigas() if b not in vistas]
        self.assertLess(abs(v.centro[0] - self.jugador.centro[0]), 20)   # llegó sobre el jugador
        self.assertLess(v.pie, self.jugador.y)                            # vuela por encima
        self.assertTrue(vistas)
        self.assertTrue(all(b.vy > 0 for b in vistas))                    # siempre hacia abajo

    def test_dron_se_va_si_nadie_lo_derriba(self):
        self.con("dron", 230, y=70, altura=70)
        for _ in range(int(16 / DT)):
            self.jugador.invulnerable = 1.0
            self.estado.update(DT, {1: NADA})
        self.assertEqual(self.estado.vehiculos, [])
        self.assertEqual(self.jugador.puntaje, 0)                         # irse no da puntos

    def test_moto_cruza_rapido_y_agacharse_esquiva_su_bala(self):
        v = self.con("moto", 250)
        self.pasos(int((settings.VEHICULOS["moto"]["aviso"] + 0.1) / DT))
        x0 = v.x
        balas = []
        for _ in range(int(1.0 / DT)):
            self.pasos(1, acc(im.ABAJO))
            balas += [b for b in self.balas_enemigas() if b not in balas]
        self.assertLess(v.x, x0 - 80)                                     # más de 80 px/s
        self.assertGreater(settings.VEHICULOS["moto"]["velocidad"], settings.JUGADOR["velocidad"])
        self.assertTrue(balas)
        self.assertTrue(all(b.vy == 0 for b in balas))                    # dispara al frente
        salud = self.jugador.salud
        while self.balas_enemigas():                                      # agachado, las balas pasan
            self.estado.vehiculos.clear()
            self.pasos(1, acc(im.ABAJO))
        self.assertEqual(self.jugador.salud, salud)

    def test_de_pie_se_le_da_a_la_moto_y_a_la_camioneta(self):
        """La bala de pie (sale a ~27 px del suelo) tiene que dar en lo que se ve del vehículo."""
        for clase in ("moto", "camioneta"):
            with self.subTest(clase=clase):
                v = self.con(clase, 200)
                for _ in range(int(4 / DT)):
                    self.jugador.invulnerable = 1.0
                    self.estado.update(DT, acc(im.DISPARAR))
                    if not v.vivo:
                        break
                self.assertFalse(v.vivo)

    def test_la_moto_se_puede_saltar(self):
        alto_salto = settings.JUGADOR["vel_salto"] ** 2 / (2 * settings.GRAVEDAD)
        self.assertGreater(alto_salto, settings.VEHICULOS["moto"]["caja"][1] + 10)

    def test_moto_salta_los_precipicios(self):
        self.nuevo(largo=1024, suelo=[[0, 200, 192], [250, 1024, 192]])
        self.jugador.x = 60
        v = Vehiculo.crear("moto", 420, 192 - settings.VEHICULOS["moto"]["caja"][1], -1)
        self.estado.vehiculos.append(v)
        for _ in range(int((settings.VEHICULOS["moto"]["aviso"] + 3.0) / DT)):
            self.jugador.invulnerable = 1.0
            self.estado.update(DT, {1: NADA})
            if v not in self.estado.vehiculos:
                break
            self.assertLess(v.y, settings.ALTO)                           # nunca cae al vacío
        self.assertLess(v.x, 200)                                         # cruzó el hueco de 50 px

    def test_camioneta_se_planta_y_el_tirador_apunta(self):
        v = self.con("camioneta", 280, vida=8)
        self.jugador.x = 40
        balas = []
        for _ in range(int(7 / DT)):
            self.jugador.invulnerable = 1.0
            self.estado.update(DT, {1: NADA})
            balas += [b for b in self.balas_enemigas() if b not in balas]
        self.assertEqual(v.estado, "plantada")
        self.assertEqual(v.vx, 0.0)
        self.assertGreater(v.x - self.jugador.x, 40)                      # se queda a distancia
        self.assertTrue(balas)
        b = balas[-1]
        self.assertLess(b.vx, 0)                                          # hacia el jugador (a su izquierda)
        self.assertGreater(b.vy, 0)                                       # desde el techo, hacia abajo

    def test_camioneta_es_blindada_y_suelta_un_arma(self):
        v = self.con("camioneta", 150, vida=8, premio="rapida")
        v.cambiar("plantada")
        impactos = 0
        for _ in range(int(8 / DT)):
            self.jugador.invulnerable = 1.0
            self.estado.eventos.clear()
            self.estado.update(DT, acc(im.DISPARAR))
            impactos += sum(1 for e in self.estado.eventos if e["tipo"] == "chispa")
            if not v.vivo:
                break
        self.assertFalse(v.vivo)
        self.assertGreaterEqual(impactos, 8)                              # aguanta 8 balas; un sicario, 1
        self.assertEqual(self.jugador.puntaje, settings.VEHICULOS["camioneta"]["puntos"])
        self.assertEqual([p.tipo for p in self.estado.powerups], ["rapida"])

    def test_tocar_un_vehiculo_hace_dano(self):
        v = self.con("camioneta", 60, vida=8)
        v.cambiar("plantada")
        self.pasos(30, acc(im.DERECHA))
        self.assertLess(self.jugador.salud, settings.JUGADOR["salud"])

    def test_serializacion(self):
        self.con("dron", 200, y=64, altura=64)
        self.estado.vehiculos.append(Vehiculo.crear("camioneta", 300, 164, -1, vida=10, premio="triple"))
        self.pasos(90, acc(im.DISPARAR))
        datos = self.estado.to_dict()
        self.assertEqual(EstadoJuego.from_dict(datos).to_dict(), datos)


class TestNivelConAzar(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()

    def recorrer(self, nivel, semilla, peligro=0):
        estado = EstadoJuego.nuevo(nivel, [Jugador()], semilla=semilla, peligro=peligro)
        j, bot = estado.jugadores[0], Bot()
        clases, avisos, suministros = set(), 0, 0
        for paso in range(int(260 / DT)):
            j.invulnerable = 1.0
            direccion = 1 if not estado.arena_activa or (paso // 90) % 2 == 0 else -1
            estado.update(DT, bot.acciones(estado, j, direccion))
            for e in estado.extraer_eventos():
                avisos += e["tipo"] == "aviso_vehiculo"
                suministros += e["tipo"] == "suministro"
            clases |= {v.clase for v in estado.vehiculos}
            if estado.victoria:
                break
        return estado, clases, avisos, suministros

    def test_el_bot_completa_cada_nivel_con_refuerzos(self):
        for nivel in range(1, ULTIMO_NIVEL + 1):
            with self.subTest(nivel=nivel):
                estado, clases, avisos, suministros = self.recorrer(nivel, semilla=11, peligro=1)
                self.assertTrue(estado.victoria, f"nivel {nivel}: el bot no terminó")
                cuenta = director.resumen(estado.plan)
                self.assertGreaterEqual(avisos, cuenta["dron"])           # aparecieron de verdad
                self.assertGreaterEqual(suministros, 1)
                if nivel == 1:
                    self.assertNotIn("camioneta", clases)
                else:
                    self.assertIn("camioneta", clases)

    def test_dos_partidas_con_la_misma_semilla_son_iguales(self):
        a, *_ = self.recorrer(1, semilla=21)
        b, *_ = self.recorrer(1, semilla=21)
        self.assertEqual(a.to_dict(), b.to_dict())                        # determinista: sirve para la red

    def test_en_la_arena_no_entran_refuerzos(self):
        estado = EstadoJuego.nuevo(2, [Jugador()], en_arena=True, semilla=4)
        for _ in range(300):
            estado.update(DT, {1: NADA})
        self.assertTrue(estado.arena_activa)
        self.assertEqual(estado.vehiculos, [])


class TestSimulador(unittest.TestCase):
    """tools/simular_partidas.py: partidas con semilla jugadas por un jugador automático."""

    @classmethod
    def setUpClass(cls):
        pygame.init()
        import sys
        sys.path.insert(0, os.path.join(settings.RUTA_BASE, "tools"))
        import simular_partidas
        cls.sim = simular_partidas

    def test_una_partida_es_reproducible(self):
        a, b = self.sim.jugar(1, 5), self.sim.jugar(1, 5)
        self.assertEqual(a, b)                                 # misma semilla, mismo resultado
        self.assertEqual(set(a), {"supero", "vidas_perdidas", "segundos", "llego_al_jefe", "vidas_al_jefe",
                                  "avance", "vida_jefe"})
        self.assertTrue(0 <= a["avance"] <= 1 and 0 <= a["vidas_perdidas"] <= settings.JUGADOR["vidas"])

    def test_el_nivel_3_se_puede_recorrer_con_3_vidas(self):
        """Con los refuerzos suavizados, el jugador automático llega al jefe del nivel 3 en buena
        parte de las partidas (antes del ajuste llegaba en 2 de cada 10) y a veces lo vence."""
        r = self.sim.simular(3, 12, semilla=1)
        self.assertGreaterEqual(r["llegan_al_jefe"], 0.35)
        self.assertGreater(r["superacion"], 0.0)
        self.assertEqual(r["partidas"], 12)

    def test_el_nivel_1_es_el_recorrido_mas_facil(self):
        uno, tres = self.sim.simular(1, 8, semilla=1), self.sim.simular(3, 8, semilla=1)
        self.assertGreater(uno["llegan_al_jefe"], tres["llegan_al_jefe"])
        self.assertGreater(uno["vidas_al_jefe"], tres["vidas_al_jefe"])


class TestRoles(BaseNivel):
    def test_cada_rol_empieza_distinto(self):
        general = Jugador.con_rol(2, "general")
        self.assertEqual((general.salud, general.arma), (4, "triple"))
        periodista = Jugador.con_rol(3, "periodista")
        self.assertEqual(periodista.arma, "rapida")
        self.assertEqual(Jugador.con_rol(4, "influencer").salud, 2)
        self.assertEqual({r["voto"] for r in settings.ROLES.values()}, {1, 2})

    def test_el_rol_conserva_su_arma_y_su_salud_al_reaparecer(self):
        general = Jugador.con_rol(1, "general")
        self.estado = EstadoJuego.nuevo(nivel_prueba(), [general])
        self.pasos(5)
        general.arma = "rapida"
        general.morir(self.estado)
        self.pasos(int(1.5 / DT))
        self.assertEqual((general.arma, general.salud), ("triple", 4))

    def test_velocidad_y_puntos_por_rol(self):
        periodista, influencer = Jugador.con_rol(1, "periodista"), Jugador.con_rol(2, "influencer")
        self.estado = EstadoJuego.nuevo(nivel_prueba(), [periodista, influencer])
        self.pasos(5)
        x0 = periodista.x
        self.pasos(60, {1: im.EstadoAcciones(frozenset([im.DERECHA]))})
        self.assertAlmostEqual(periodista.x - x0, settings.JUGADOR["velocidad"] * 1.12, delta=2)
        self.estado._sumar_puntos(2, 100)
        self.estado._sumar_puntos(1, 100)
        self.assertEqual((influencer.puntaje, periodista.puntaje), (150, 100))

    def test_el_periodista_avisa_las_emboscadas_con_el_doble_de_tiempo(self):
        def segundos_de_aviso(rol):
            self.estado = EstadoJuego.nuevo(nivel_prueba(), [Jugador.con_rol(1, rol)])
            self.pasos(5)
            v = Vehiculo.crear("moto", 300, 170, -1)
            self.estado.vehiculos.append(v)
            pasos = 0
            while v.estado == "aviso":
                self.pasos(1)
                pasos += 1
            return pasos * DT
        normal, periodista = segundos_de_aviso("presidente"), segundos_de_aviso("periodista")
        self.assertAlmostEqual(normal, settings.VEHICULOS["moto"]["aviso"], delta=0.05)
        self.assertAlmostEqual(periodista, normal * 2, delta=0.05)

    def test_varios_jugadores_comparten_el_nivel(self):
        a, b = Jugador.con_rol(1, "presidente"), Jugador.con_rol(2, "general")
        self.estado = EstadoJuego.nuevo(nivel_prueba(), [a, b])
        self.pasos(30, {1: im.EstadoAcciones(frozenset([im.DERECHA])), 2: NADA})
        self.assertGreater(a.x, b.x)                                      # cada uno con sus botones
        b.vidas = 0
        self.pasos(5)
        self.assertFalse(self.estado.game_over)                           # sigue mientras quede uno
        a.vidas = 0
        self.pasos(5)
        self.assertTrue(self.estado.game_over)


if __name__ == "__main__":
    unittest.main()
