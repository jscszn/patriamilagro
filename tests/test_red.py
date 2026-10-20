"""Modo multijugador: protocolo, reglas de la sesión (sin sockets) y una partida por sockets reales."""
import os
import socket
import time
import unittest

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
import pygame  # noqa: E402

import input_manager as im  # noqa: E402
import settings  # noqa: E402
from core.decision_tree import CAPTURAR, EXTRADITAR, LIBERAR  # noqa: E402
from net import sesion as ss  # noqa: E402
from net.cliente import Cliente  # noqa: E402
from net.protocolo import CABECERA, Canal, empaquetar  # noqa: E402
from net.servidor import Servidor  # noqa: E402
from net.sesion import Sesion  # noqa: E402

DT = settings.DT


class TestProtocolo(unittest.TestCase):
    def setUp(self):
        a, b = socket.socketpair()
        self.a, self.b = Canal(a), Canal(b)

    def tearDown(self):
        self.a.cerrar()
        self.b.cerrar()

    def test_ida_y_vuelta_con_tildes(self):
        self.a.enviar({"t": "hola", "nombre": "ÑANDÚ ¡sí!"})
        self.assertEqual(self.b.recibir(), [{"t": "hola", "nombre": "ÑANDÚ ¡sí!"}])

    def test_varios_mensajes_pegados_se_separan(self):
        for i in range(5):
            self.a.enviar({"n": i})
        self.assertEqual([m["n"] for m in self.b.recibir()], [0, 1, 2, 3, 4])

    def test_un_mensaje_partido_espera_al_resto(self):
        datos = empaquetar({"t": "estado", "x": list(range(50))})
        self.a.sock.send(datos[:7])                           # llega la cabecera y un pedazo
        self.assertEqual(self.b.recibir(), [])
        self.a.sock.send(datos[7:])
        self.assertEqual(self.b.recibir()[0]["x"], list(range(50)))

    def test_mensaje_grande(self):
        grande = {"t": "estado", "mundo": ["x" * 100] * 3000}  # ~300 KB: más que el búfer del sistema
        self.a.enviar(grande)
        recibidos = []
        for _ in range(200):
            self.a.vaciar()
            recibidos += self.b.recibir()
            if recibidos:
                break
        self.assertEqual(recibidos, [grande])

    def test_detecta_el_cierre_del_otro_lado(self):
        self.a.cerrar()
        self.b.recibir()
        self.assertFalse(self.b.abierto)

    def test_basura_cierra_el_canal(self):
        self.a.sock.send(CABECERA.pack(5) + b"\xff\xfe{{{")
        self.assertEqual(self.b.recibir(), [])
        self.assertFalse(self.b.abierto)


class BaseSesion(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()

    def sesion(self, jugadores=2, semilla=7, en_arena=True):
        s = Sesion(semilla=semilla, en_arena=en_arena)
        ids = [s.unir(f"j{i}") for i in range(jugadores)]
        return s, ids

    def pasos(self, s, n):
        for _ in range(n):
            s.paso(DT)

    def empezar(self, s, ids):
        for i in ids:
            s.recibir(i, {"t": "listo"})
        s.recibir(s.anfitrion, {"t": "empezar"})

    def hasta_votacion(self, s, ids):
        self.empezar(s, ids)
        for i in ids:
            s.recibir(i, {"t": "listo"})
        self.pasos(s, 2)
        self.assertEqual(s.fase, ss.NIVEL)
        self.pasos(s, 150)                                    # entra a la arena y aparece el jefe
        s.estado.jefe.recibir_dano(999, s.estado)
        s.estado._jefe_derrotado()
        self.pasos(s, 200)
        self.assertEqual(s.fase, ss.VOTACION)


class TestSala(BaseSesion):
    def test_de_2_a_4_jugadores_con_roles_distintos(self):
        s, ids = self.sesion(4)
        self.assertEqual(ids, [1, 2, 3, 4])
        self.assertEqual([s.jugadores[i]["rol"] for i in ids], list(settings.ORDEN_ROLES))
        self.assertIsNone(s.unir("quinto"))                   # máximo 4
        self.assertEqual(s.anfitrion, 1)

    def test_no_empieza_con_un_solo_jugador(self):
        s, ids = self.sesion(1)
        self.empezar(s, ids)
        self.assertEqual(s.fase, ss.SALA)
        self.assertIn("MÍNIMO 2", s.aviso)

    def test_no_empieza_si_alguien_no_esta_listo(self):
        s, ids = self.sesion(3)
        s.recibir(1, {"t": "listo"})
        s.recibir(1, {"t": "empezar"})
        self.assertEqual(s.fase, ss.SALA)

    def test_solo_el_anfitrion_empieza(self):
        s, ids = self.sesion(2)
        for i in ids:
            s.recibir(i, {"t": "listo"})
        s.recibir(2, {"t": "empezar"})
        self.assertEqual(s.fase, ss.SALA)
        s.recibir(1, {"t": "empezar"})
        self.assertEqual(s.fase, ss.INFORME)

    def test_elegir_rol_sin_repetir(self):
        s, _ = self.sesion(2)
        s.recibir(2, {"t": "rol", "rol": "presidente"})        # ocupado: pasa al siguiente libre
        self.assertEqual(s.jugadores[2]["rol"], "general")
        s.recibir(2, {"t": "rol", "rol": "influencer"})
        self.assertEqual(s.jugadores[2]["rol"], "influencer")
        s.recibir(2, {"t": "rol", "rol": "inventado"})
        self.assertEqual(len({j["rol"] for j in s.jugadores.values()}), 2)

    def test_salir_de_la_sala_libera_el_lugar_y_pasa_el_anfitrion(self):
        s, _ = self.sesion(3)
        s.salir(1)
        self.assertEqual(sorted(s.jugadores), [2, 3])
        self.assertEqual(s.anfitrion, 2)
        self.assertEqual(s.unir("nuevo"), 1)

    def test_no_se_entra_con_la_partida_en_curso(self):
        s, ids = self.sesion(2)
        self.empezar(s, ids)
        self.assertIsNone(s.unir("tarde"))


class TestPartidaEnRed(BaseSesion):
    def test_informe_trae_la_historia_y_la_ruta(self):
        s, ids = self.sesion(2)
        self.empezar(s, ids)
        d = s.instantanea()["datos"]
        self.assertEqual(d["nivel"], 1)
        self.assertEqual(len(d["paginas"]), 2)
        self.assertEqual(set(d["rutas"]), {"segura", "corta"})
        self.assertEqual(d["clave"], "segura")
        for ruta in d["rutas"].values():
            self.assertEqual((ruta["camino"][0], ruta["camino"][-1]), ("capital", "selva"))
        self.assertNotIn("rng", d["mapa"])                     # liviano: sin el estado del azar
        self.pasos(s, 5)
        self.assertEqual(s.fase, ss.INFORME)                   # espera a que todos estén listos

    def test_el_anfitrion_elige_la_ruta_y_eso_cambia_el_nivel(self):
        resultados = {}
        for clave in ("segura", "corta"):
            s, ids = self.sesion(2)
            self.empezar(s, ids)
            s.recibir(2, {"t": "ruta", "clave": "corta"})          # no es el anfitrión: se ignora
            self.assertEqual(s.datos["clave"], "segura")
            s.recibir(1, {"t": "ruta", "clave": clave})
            s.recibir(1, {"t": "ruta", "clave": "inventada"})      # ruta que no existe: se ignora
            self.assertEqual(s.datos["clave"], clave)
            self.assertIn("SEGURA" if clave == "segura" else "CORTA", s.datos["paginas"][1])
            for i in ids:
                s.recibir(i, {"t": "listo"})
            self.pasos(s, 2)
            self.assertEqual(s.partida.rutas[1]["clave"], clave)
            resultados[clave] = (s.estado.peligro, s.estado.opinion["pueblo"])
        self.assertGreater(resultados["corta"][0], resultados["segura"][0])   # más refuerzos
        self.assertLess(resultados["segura"][1], resultados["corta"][1])      # llegar tarde cuesta opinión

    def test_el_servidor_simula_con_los_botones_de_cada_cliente(self):
        s, ids = self.sesion(2, en_arena=False)
        self.empezar(s, ids)
        for i in ids:
            s.recibir(i, {"t": "listo"})
        self.pasos(s, 2)
        a, b = s.estado.jugadores
        self.assertEqual((a.rol, b.rol), ("presidente", "general"))
        s.recibir(1, {"t": "acciones", "m": [im.DERECHA], "p": []})
        s.recibir(2, {"t": "acciones", "m": [], "p": [im.SALTAR]})
        xa, xb = a.x, b.x
        self.pasos(s, 10)
        self.assertGreater(a.x, xa)                            # 1 camina
        self.assertEqual(b.x, xb)
        self.assertLess(b.vy, 0)                               # 2 saltó: la pulsación llegó una vez
        m = s.instantanea()
        self.assertEqual(len(m["mundo"]["jugadores"]), 2)
        self.assertTrue(any(e["tipo"] == "salto" for e in m["eventos"]))
        self.assertEqual(s.instantanea()["eventos"], [])       # los eventos se envían una sola vez

    def test_dos_pulsaciones_seguidas_no_se_pierden(self):
        s, ids = self.sesion(2)
        self.empezar(s, ids)
        for i in ids:
            s.recibir(i, {"t": "listo"})
        self.pasos(s, 2)
        s.recibir(1, {"t": "acciones", "m": [], "p": [im.SALTAR]})
        s.recibir(1, {"t": "acciones", "m": [], "p": []})      # llega otro mensaje antes del paso
        self.assertTrue(s.acciones[1].pulso(im.SALTAR))

    def test_el_voto_del_presidente_vale_doble(self):
        s, ids = self.sesion(3)
        self.hasta_votacion(s, ids)
        s.recibir(1, {"t": "voto", "decision": CAPTURAR})      # presidente: 2
        s.recibir(2, {"t": "voto", "decision": LIBERAR})       # 1
        s.recibir(3, {"t": "voto", "decision": LIBERAR})       # 1  -> empate 2 a 2: decide el presidente
        self.pasos(s, 2)
        self.assertEqual(s.fase, ss.RESULTADO)
        self.assertEqual(s.datos["decision"], CAPTURAR)
        self.assertEqual(s.partida.arbol.camino(), [CAPTURAR])
        self.assertEqual(s.datos["votos"], {"1": CAPTURAR, "2": LIBERAR, "3": LIBERAR})
        self.assertEqual(s.datos["opinion"], s.partida.arbol.opinion())      # la opinión sale del árbol
        self.assertNotEqual(s.datos["opinion"], s.datos["opinion_antes"])

    def test_la_mayoria_le_gana_al_presidente(self):
        s, ids = self.sesion(4)
        self.hasta_votacion(s, ids)
        s.recibir(1, {"t": "voto", "decision": CAPTURAR})
        for i in (2, 3, 4):
            s.recibir(i, {"t": "voto", "decision": EXTRADITAR})
        self.pasos(s, 2)
        self.assertEqual(s.datos["decision"], EXTRADITAR)

    def test_si_nadie_vota_el_jefe_escapa(self):
        s, ids = self.sesion(2)
        self.hasta_votacion(s, ids)
        self.pasos(s, int(settings.TIEMPO_DECISION / DT) + 5)
        self.assertEqual(s.fase, ss.RESULTADO)
        self.assertTrue(s.datos["escapo"])
        self.assertEqual(s.partida.arbol.camino(), [LIBERAR])

    def test_partida_completa_con_puntaje_individual_y_resultado_general(self):
        s, ids = self.sesion(2)
        self.empezar(s, ids)
        for nivel in (1, 2, 3):
            for i in ids:
                s.recibir(i, {"t": "listo"})
            self.pasos(s, 2)
            self.assertEqual((s.fase, s.partida.nivel), (ss.NIVEL, nivel))
            self.pasos(s, 150)
            s.estado.jugador(2).puntaje += 100 * nivel         # el jugador 2 hace más puntos
            s.estado.jefe.recibir_dano(999, s.estado)
            s.estado._jefe_derrotado()
            self.pasos(s, 200)
            for i in ids:
                s.recibir(i, {"t": "voto", "decision": EXTRADITAR})
            self.pasos(s, 2)
            self.assertEqual(s.fase, ss.RESULTADO)             # de la votación directo al resultado
            for i in ids:
                s.recibir(i, {"t": "listo"})
            self.pasos(s, 2)
        self.assertEqual(s.fase, ss.FINAL)
        d = s.datos
        self.assertFalse(d["derrota"])
        self.assertEqual(d["camino"], [EXTRADITAR] * 3)
        self.assertEqual(d["tabla"][0]["id"], 2)               # tabla ordenada por puntaje individual
        self.assertEqual(d["tabla"][0]["puntaje"], 600)
        self.assertEqual(len(d["jefes"]), 3)
        s.recibir(2, {"t": "sala"})                            # solo el anfitrión vuelve a la sala
        self.assertEqual(s.fase, ss.FINAL)
        s.recibir(1, {"t": "sala"})
        self.assertEqual(s.fase, ss.SALA)
        self.assertEqual(s.jugadores[2]["puntaje"], 0)

    def test_el_resultado_sigue_solo_si_nadie_marca_listo(self):
        s, ids = self.sesion(2)
        self.hasta_votacion(s, ids)
        for i in ids:
            s.recibir(i, {"t": "voto", "decision": CAPTURAR})
        self.pasos(s, 2)
        self.assertEqual(s.fase, ss.RESULTADO)
        self.pasos(s, int(ss.ESPERA_RESULTADO / DT) + 5)
        self.assertEqual((s.fase, s.partida.nivel), (ss.INFORME, 2))

    def test_el_influencer_amplifica_la_decision_del_grupo(self):
        opiniones = []
        for rol in ("general", "influencer"):
            s, ids = self.sesion(2)
            s.recibir(2, {"t": "rol", "rol": rol})
            self.hasta_votacion(s, ids)
            for i in ids:
                s.recibir(i, {"t": "voto", "decision": CAPTURAR})
            self.pasos(s, 2)
            opiniones.append(s.datos["opinion"]["pueblo"])
        self.assertGreater(opiniones[1], opiniones[0])

    def test_game_over_de_todos_termina_en_derrota(self):
        s, ids = self.sesion(2)
        self.empezar(s, ids)
        for i in ids:
            s.recibir(i, {"t": "listo"})
        self.pasos(s, 2)
        for j in s.estado.jugadores:
            j.vidas = 0
        self.pasos(s, 2)
        self.assertEqual(s.fase, ss.FINAL)
        self.assertTrue(s.datos["derrota"])

    def test_desconexion_en_medio_del_nivel(self):
        s, ids = self.sesion(2)
        self.empezar(s, ids)
        for i in ids:
            s.recibir(i, {"t": "listo"})
        self.pasos(s, 2)
        s.salir(1)
        self.assertFalse(s.jugadores[1]["conectado"])
        self.assertTrue(s.estado.jugador(1).eliminado)
        self.assertEqual(s.anfitrion, 2)
        self.pasos(s, 5)
        self.assertEqual(s.fase, ss.NIVEL)                     # el otro sigue jugando
        s.salir(2)
        self.assertEqual((s.fase, s.jugadores), (ss.SALA, {}))  # sin nadie, vuelve a la sala


class TestSockets(unittest.TestCase):
    """Servidor y dos clientes reales hablando por TCP en este mismo equipo."""

    @classmethod
    def setUpClass(cls):
        pygame.init()

    def setUp(self):
        try:
            self.servidor = Servidor(puerto=0, anfitrion="127.0.0.1", sesion=Sesion(semilla=7, en_arena=True))
        except OSError as error:
            self.skipTest(f"no se pueden abrir sockets aquí: {error}")
        self.a, self.b = Cliente(), Cliente()
        self.assertTrue(self.a.conectar("127.0.0.1", "ana", self.servidor.puerto))
        self.assertTrue(self.b.conectar("127.0.0.1", "beto", self.servidor.puerto))

    def tearDown(self):
        self.a.cerrar()
        self.b.cerrar()
        self.servidor.detener()

    def vueltas(self, n, hasta=None):
        for _ in range(n):
            self.servidor.vuelta()
            self.a.actualizar()
            self.b.actualizar()
            if hasta is not None and hasta():
                return True
            time.sleep(0.0005)
        return hasta is None

    def test_partida_por_tcp(self):
        self.assertTrue(self.vueltas(300, lambda: self.a.id and self.b.id and self.b.estado))
        self.assertEqual({self.a.id, self.b.id}, {1, 2})
        self.assertEqual(self.b.estado["fase"], ss.SALA)
        self.a.enviar("listo")
        self.b.enviar("listo")
        self.vueltas(12)
        self.a.enviar("empezar")
        self.assertTrue(self.vueltas(300, lambda: self.b.estado["fase"] == ss.INFORME))
        self.a.enviar("listo")
        self.b.enviar("listo")
        self.assertTrue(self.vueltas(300, lambda: "mundo" in self.b.estado))
        x0 = self.a.estado["mundo"]["jugadores"][1]["x"]
        self.b.enviar("acciones", m=[im.IZQUIERDA, im.DISPARAR], p=[])
        self.vueltas(60)
        # Los DOS clientes ven lo mismo: el servidor es la única fuente de verdad
        self.assertLess(self.a.estado["mundo"]["jugadores"][1]["x"], x0)
        self.assertEqual(self.a.estado["mundo"]["jugadores"], self.b.estado["mundo"]["jugadores"])
        self.assertTrue(any(e["tipo"] == "disparo_jugador" for e in self.a.eventos))

    def test_tercer_cliente_rechazado_con_la_partida_en_curso(self):
        self.vueltas(20)
        self.a.enviar("listo")
        self.b.enviar("listo")
        self.vueltas(12)
        self.a.enviar("empezar")
        self.vueltas(12)
        tarde = Cliente()
        self.assertTrue(tarde.conectar("127.0.0.1", "tarde", self.servidor.puerto))
        for _ in range(60):
            self.servidor.vuelta()
            tarde.actualizar()
            time.sleep(0.001)
        self.assertIn("SALA LLENA", tarde.error)
        tarde.cerrar()

    def test_el_servidor_nota_cuando_un_cliente_se_va(self):
        self.vueltas(20)
        self.b.cerrar()
        self.assertTrue(self.vueltas(400, lambda: len(self.servidor.sesion.jugadores) == 1))
        self.vueltas(12)                                        # llega la instantánea siguiente
        self.assertEqual(len(self.a.estado["jugadores"]), 1)

    def test_cliente_sin_servidor_no_se_cuelga(self):
        nadie = Cliente()
        libre = socket.socket()
        libre.bind(("127.0.0.1", 0))
        puerto = libre.getsockname()[1]
        libre.close()
        self.assertFalse(nadie.conectar("127.0.0.1", "x", puerto, espera=0.5))
        self.assertIn("NO SE PUDO CONECTAR", nadie.error)

    def test_servidor_en_un_hilo(self):
        self.servidor.iniciar_en_hilo()
        fin = time.time() + 3
        while time.time() < fin and not (self.a.estado and self.a.id):
            self.a.actualizar()
            time.sleep(0.01)
        self.assertEqual(self.a.estado["fase"], ss.SALA)
        self.servidor.detener()
        self.assertFalse(self.servidor.hilo.is_alive())


if __name__ == "__main__":
    unittest.main()
