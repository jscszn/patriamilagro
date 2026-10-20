"""Validación de los datos de los 3 niveles y prueba de que cada uno se puede completar."""
import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame  # noqa: E402

import settings  # noqa: E402
from core.game_state import EstadoJuego  # noqa: E402
from core.player import Jugador  # noqa: E402
from levels import NIVELES, ULTIMO_NIVEL  # noqa: E402
from tests.bot import Bot  # noqa: E402

ALTURA_SALTO = settings.JUGADOR["vel_salto"] ** 2 / (2 * settings.GRAVEDAD)   # ~48 px
PRECIPICIO_MAX = 48     # huecos que se cruzan saltando sin plataforma
# Solo los niveles reales: otras pruebas registran niveles temporales en NIVELES.
REALES = {n: NIVELES[n] for n in range(1, ULTIMO_NIVEL + 1)}


def salto_posible(origen, destino) -> bool:
    """¿Un salto desde la superficie origen (tipo, x0, x1, y) cae sobre destino?
    Usa la física real: velocidad horizontal, impulso de salto y gravedad de settings."""
    _, a0, a1, ya = origen
    _, b0, b1, yb = destino
    subida = ya - yb                                   # positivo = destino más alto
    v, g = settings.JUGADOR["vel_salto"], settings.GRAVEDAD
    if subida > ALTURA_SALTO - 2:
        return False
    # Tiempo hasta pasar por la altura del destino bajando (o el apex si es la misma altura)
    t = (v + (v * v - 2 * g * max(subida, 0)) ** 0.5) / g
    alcance = settings.JUGADOR["velocidad"] * t
    hueco = max(b0 - a1, a0 - b1, 0)                   # distancia horizontal entre superficies
    return hueco <= alcance - settings.JUGADOR["ancho"]


def superficies_bajo(datos, x0, x1):
    """Alturas de suelo/bloques/plataformas que hay debajo del tramo [x0, x1)."""
    alturas = [y for a, b, y in datos["suelo"] if a < x1 and b > x0]
    alturas += [y for bx, y, w, h in datos.get("bloques", []) if bx < x1 and bx + w > x0]
    alturas += [y for px, y, w in datos.get("plataformas", []) if px < x1 and px + w > x0]
    return alturas


class TestDatosNiveles(unittest.TestCase):
    def test_hay_tres_niveles_con_su_jefe(self):
        self.assertEqual(sorted(REALES), [1, 2, 3])
        for n, datos in REALES.items():
            self.assertEqual(datos["jefe"], n)
            self.assertNotIn("PROVISIONAL", datos["nombre"])

    def test_la_dificultad_sube_con_la_cantidad_de_sicarios(self):
        cantidades = [len(REALES[n]["enemigos"]) for n in (1, 2, 3)]
        por_detras = [sum(e.get("lado") == "izquierda" for e in REALES[n]["enemigos"]) for n in (1, 2, 3)]
        self.assertEqual(cantidades, sorted(cantidades))
        self.assertLess(cantidades[0], cantidades[2])
        self.assertEqual(por_detras, sorted(por_detras))

    def test_arena_plana_y_sin_enemigos(self):
        for n, datos in REALES.items():
            arena = datos["largo"] - settings.ANCHO
            with self.subTest(nivel=n):
                self.assertEqual(set(superficies_bajo(datos, arena, datos["largo"])), {192})
                self.assertTrue(all(e["x"] < arena for e in datos["enemigos"]))

    def test_suelo_ordenado_y_precipicios_saltables(self):
        for n, datos in REALES.items():
            tramos = datos["suelo"]
            for (a0, a1, _), (b0, b1, _) in zip(tramos, tramos[1:]):
                with self.subTest(nivel=n, hueco=(a1, b0)):
                    self.assertLessEqual(a1, b0)
                    hueco = b0 - a1
                    puente = any(px <= a1 and px + w >= b0 for px, _, w in datos.get("plataformas", []))
                    self.assertTrue(hueco <= PRECIPICIO_MAX or puente, f"hueco de {hueco} px sin puente")

    def test_escalones_y_plataformas_alcanzables(self):
        """Grafo de superficies (suelo, bloques, plataformas): hay arista si un salto real llega
        de una a otra. Con BFS desde el suelo, TODAS las plataformas deben ser alcanzables."""
        for n, datos in REALES.items():
            tramos = datos["suelo"]
            for (_, a1, ya), (b0, _, yb) in zip(tramos, tramos[1:]):
                if a1 == b0:
                    with self.subTest(nivel=n, escalon=a1):
                        self.assertLess(ya - yb, ALTURA_SALTO - 6)     # subir el escalón saltando
            superficies = [("suelo", a, b, y) for a, b, y in tramos]
            superficies += [("bloque", x, x + w, y) for x, y, w, h in datos.get("bloques", [])]
            superficies += [("plataforma", x, x + w, y) for x, y, w in datos.get("plataformas", [])]
            alcanzadas = {i for i, s in enumerate(superficies) if s[0] == "suelo"}
            cola = list(alcanzadas)
            while cola:
                origen = superficies[cola.pop(0)]
                for i, destino in enumerate(superficies):
                    if i not in alcanzadas and salto_posible(origen, destino):
                        alcanzadas.add(i)
                        cola.append(i)
            for i, s in enumerate(superficies):
                with self.subTest(nivel=n, superficie=s):
                    self.assertIn(i, alcanzadas, "no se puede llegar saltando")

    def test_sicarios_sobre_plataformas_estan_sobre_una(self):
        for n, datos in REALES.items():
            for e in datos["enemigos"]:
                if "y" in e:
                    with self.subTest(nivel=n, enemigo=e):
                        self.assertTrue(any(px <= e["x"] and e["x"] + 12 <= px + w and py == e["y"]
                                            for px, py, w in datos["plataformas"]))

    def test_powerups_alcanzables(self):
        for n, datos in REALES.items():
            for p in datos["powerups"]:
                with self.subTest(nivel=n, powerup=p):
                    debajo = [y for y in superficies_bajo(datos, p["x"], p["x"] + 12) if y >= p["y"] + 12]
                    self.assertTrue(debajo)
                    self.assertLessEqual(min(debajo) - p["y"], settings.JUGADOR["alto"] + 4)   # se toca de pie


class TestNivelesCompletables(unittest.TestCase):
    """Un bot invencible recorre cada nivel real y derrota al jefe."""

    @classmethod
    def setUpClass(cls):
        pygame.init()

    def test_bot_completa_cada_nivel(self):
        for n in range(1, ULTIMO_NIVEL + 1):
            with self.subTest(nivel=n):
                estado = EstadoJuego.nuevo(n, [Jugador()])
                j, bot = estado.jugadores[0], Bot()
                for paso in range(int(240 / settings.DT)):
                    j.invulnerable = 1.0
                    direccion = 1 if not estado.arena_activa or (paso // 90) % 2 == 0 else -1
                    estado.update(settings.DT, bot.acciones(estado, j, direccion))
                    if estado.victoria:
                        break
                self.assertTrue(estado.arena_activa, f"nivel {n}: el bot no llegó a la arena")
                self.assertTrue(estado.victoria, f"nivel {n}: el bot no venció al jefe")
