"""Simula partidas con un jugador automático y reporta la tasa de superación de cada nivel.

    python tools/simular_partidas.py                 # 40 partidas por nivel
    python tools/simular_partidas.py -n 100 --nivel 3
    python tools/simular_partidas.py --semilla 500   # otras 40 partidas (semillas 500 a 539)

Cada partida usa una semilla distinta (refuerzos y suministros distintos) y empieza el nivel
con las vidas normales. Sirve para COMPARAR: si se cambia la dificultad en levels/ o en
settings.py, la tasa debe moverse en la dirección esperada.

Ojo: el jugador automático NO es una persona. Esquiva balas, salta motos y huecos, apunta a
los drones y se aleja de los jefes, pero no aprende sus patrones: contra los jefes 1 y 2 pierde
casi siempre (una persona los vence). Por eso el reporte separa:
  - nivel completo: de principio a fin con 3 vidas (lo más exigente para el autómata);
  - recorrido: cuántas partidas llegan al jefe y con cuántas vidas (mide refuerzos y sicarios);
  - jefe solo: empezando en la arena con 3 vidas; si pierde, cuánta vida le quedaba al jefe.
Las cifras sirven para comparar niveles y versiones entre sí, no como dificultad "real".
"""
from __future__ import annotations

import argparse
import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame  # noqa: E402

import input_manager as im  # noqa: E402
import settings  # noqa: E402
from core.game_state import EstadoJuego  # noqa: E402
from core.player import Jugador  # noqa: E402
from levels import ULTIMO_NIVEL  # noqa: E402

DT = settings.DT
LIMITE = 300.0            # segundos de juego por partida antes de darla por perdida
ALTO_AGACHADO = settings.JUGADOR["alto_agachado"]


class JugadorAutomatico:
    """Reglas simples, en orden de urgencia: esquivar, no caer, pelear, avanzar."""

    def __init__(self):
        self.salto = 0                # frames que sigue manteniendo SALTAR (salto alto)
        self.t_camioneta = 0.0        # tiempo plantado frente a una camioneta sin destruirla

    def _jefe(self, e: EstadoJuego, j: Jugador, jefe) -> tuple:
        """Contra el jefe: quedarse en el extremo opuesto de la arena, mirándolo. Si salta o
        embiste hacia el jugador, cruzar al otro lado. Devuelve (dirección, saltar)."""
        cx = j.centro[0]
        dx = jefe.centro[0] - cx
        hacia = 1 if dx > 0 else -1
        izquierda, derecha = e.camara_x + 14, e.camara_x + settings.ANCHO - 26
        centro = (izquierda + derecha) / 2
        refugio = izquierda if jefe.centro[0] > centro else derecha       # el extremo lejano
        en_el_aire = not jefe.en_suelo and jefe.estado in ("saltar", "onda")
        if en_el_aire and abs(dx) < 70:                                   # va a caer encima: salir de ahí
            return (-hacia if abs(j.x - (izquierda if hacia > 0 else derecha)) > 30 else hacia), False
        if jefe.estado == "embestida" and abs(dx) < 80 and (jefe.vx > 0) == (dx < 0):
            return hacia, True                                            # salta hacia él: pasa menos tiempo en su caja
        if abs(cx - refugio) > 10 and abs(dx) < 150:
            return (1 if refugio > cx else -1), False
        return (hacia if j.mirando != hacia else 0), False

    def acciones(self, e: EstadoJuego, j: Jugador) -> dict:
        mantenidas, pulsadas = {im.DISPARAR}, set()
        cx, pie = j.centro[0], j.pie
        jefe = e.jefe if e.jefe is not None and e.jefe.vivo else None
        direccion = 1                                         # por defecto, avanzar
        agacharse = saltar = False

        # 1) Pelea con el jefe
        if jefe is not None:
            direccion, saltar = self._jefe(e, j, jefe)

        # 2) Refuerzos
        frente_a_camioneta = False
        for v in e.vehiculos:
            if not v.activo:
                continue
            dx = v.centro[0] - cx
            if v.clase == "camioneta" and 0 < dx < 120 and jefe is None:
                frente_a_camioneta = True
                if self.t_camioneta > 2.5 or abs(v.pie - pie) > 6:   # no le da de frente: se acerca saltando
                    direccion = 1 if dx > 62 else 0
                    saltar = True
                else:
                    direccion = 0 if j.mirando > 0 else 1         # se planta y le dispara
            elif v.clase == "moto" and abs(dx) < 50 and (dx > 0) == (v.direccion < 0):
                saltar = True
            elif v.clase == "dron" and abs(dx) < 60 and v.pie < j.y:
                mantenidas.add(im.ARRIBA)                     # apunta arriba o en diagonal
                if abs(dx) < 8:
                    direccion = 0
                elif jefe is None:
                    direccion = 1 if dx > 0 else -1
        self.t_camioneta = self.t_camioneta + DT if frente_a_camioneta else 0.0

        # 3) Sicarios encima o por la espalda: darse la vuelta y disparar; si ya tocan, saltar
        if jefe is None:
            cercanos = [s for s in e.sicarios if abs(s.pie - pie) < 30
                        and -85 < s.centro[0] - cx < 46]          # los de atrás corren más: se miran antes
            if cercanos:
                s_cerca = min(cercanos, key=lambda s: abs(s.centro[0] - cx))
                lado = 1 if s_cerca.centro[0] > cx else -1
                if lado < 0 or frente_a_camioneta:
                    direccion = lado if j.mirando != lado else 0
                if abs(s_cerca.centro[0] - cx) < 16:
                    saltar = True

        # 4) Balas: las altas se esquivan agachado; las bajas y las ondas, saltando hacia ellas
        for b in e.balas:
            if b.del_jugador:
                continue
            if b.tipo == "onda":
                if abs(b.x - cx) < 34 and (b.x - cx) * b.vx < 0:
                    saltar = True
                continue
            if abs(b.vx) < 1:
                continue
            t = (cx - b.x) / b.vx
            if not 0 < t < 0.32:
                continue
            y = b.y + b.vy * t
            if pie - settings.JUGADOR["alto"] - 4 <= y <= pie + 2:
                if y < pie - ALTO_AGACHADO - 3 and j.en_suelo and abs(b.vy) < 40:
                    agacharse = True
                else:
                    saltar = True
                    if jefe is not None:                      # contra la ráfaga, saltar hacia el jefe
                        direccion = -1 if b.vx > 0 else 1

        # 5) El terreno: huecos y escalones
        if direccion and j.en_suelo:
            adelante = j.x + (j.ancho + 10 if direccion > 0 else -10)
            suelo = e.geometria.altura_suelo(adelante)
            if suelo > pie + 1 or suelo < pie - 1 or j.choco_pared:
                saltar, agacharse = True, False

        if saltar and j.en_suelo and self.salto == 0:
            pulsadas.add(im.SALTAR)
            self.salto = 22
        if self.salto > 0:
            mantenidas.add(im.SALTAR)
            self.salto -= 1
        if agacharse and not saltar and self.salto == 0:
            mantenidas.discard(im.ARRIBA)
            mantenidas.add(im.ABAJO)                          # quieto y agachado
        elif direccion:
            mantenidas.add(im.DERECHA if direccion > 0 else im.IZQUIERDA)
        return {j.id_jugador: im.EstadoAcciones(frozenset(mantenidas), frozenset(pulsadas))}


def jugar(nivel: int, semilla: int, peligro: int = 0, solo_jefe: bool = False) -> dict:
    """Una partida de un nivel. solo_jefe=True empieza en la arena con las vidas completas."""
    jugador = Jugador()
    estado = EstadoJuego.nuevo(nivel, [jugador], semilla=semilla, peligro=peligro, en_arena=solo_jefe)
    automata = JugadorAutomatico()
    vidas = jugador.vidas
    pasos = 0
    vidas_al_jefe = None
    while pasos * DT < LIMITE and not estado.victoria and not estado.game_over:
        estado.update(DT, automata.acciones(estado, jugador))
        estado.extraer_eventos()
        pasos += 1
        if vidas_al_jefe is None and estado.arena_activa:
            vidas_al_jefe = jugador.vidas
    return {"supero": estado.victoria, "vidas_perdidas": vidas - max(0, jugador.vidas), "segundos": pasos * DT,
            "llego_al_jefe": estado.arena_activa, "vidas_al_jefe": vidas_al_jefe or 0,
            "avance": min(1.0, jugador.x / max(1, estado.arena_x)),
            "vida_jefe": (max(0, estado.jefe.vida) / estado.jefe.vida_max) if estado.jefe else 1.0}


def simular(nivel: int, partidas: int, semilla: int = 1, peligro: int = 0) -> dict:
    """Tasas del nivel completo y, aparte, del jefe solo (empezando en la arena con 3 vidas)."""
    completas = [jugar(nivel, semilla + i, peligro) for i in range(partidas)]
    jefes = [jugar(nivel, semilla + i, peligro, solo_jefe=True) for i in range(partidas)]
    n = len(completas)
    return {"nivel": nivel, "partidas": n,
            "superacion": sum(r["supero"] for r in completas) / n,
            "llegan_al_jefe": sum(r["llego_al_jefe"] for r in completas) / n,
            "vidas_al_jefe": sum(r["vidas_al_jefe"] for r in completas) / n,
            "avance": sum(r["avance"] for r in completas) / n,
            "segundos": sum(r["segundos"] for r in completas) / n,
            "jefe_solo": sum(r["supero"] for r in jefes) / n,
            "vida_jefe": sum(r["vida_jefe"] for r in jefes) / n}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("-n", "--partidas", type=int, default=40, help="partidas por nivel")
    parser.add_argument("--nivel", type=int, choices=range(1, ULTIMO_NIVEL + 1), help="solo ese nivel")
    parser.add_argument("--semilla", type=int, default=1, help="primera semilla")
    parser.add_argument("--peligro", type=int, default=0, help="refuerzos extra (ruta peligrosa o jefes libres)")
    args = parser.parse_args()
    pygame.init()
    niveles = [args.nivel] if args.nivel else range(1, ULTIMO_NIVEL + 1)
    print(f"{args.partidas} partidas por nivel, semillas {args.semilla} a {args.semilla + args.partidas - 1}, "
          f"refuerzos extra: {args.peligro}")
    print("        ------- nivel completo -------   ------ recorrido ------   ---- jefe solo, 3 vidas ----")
    print("nivel   superación   duración             llegan al jefe  vidas     lo vencen  vida que le queda")
    for nivel in niveles:
        r = simular(nivel, args.partidas, args.semilla, args.peligro)
        print(f"  {nivel}       {r['superacion']:6.0%}      {r['segundos']:4.0f} s               {r['llegan_al_jefe']:6.0%}       "
              f"{r['vidas_al_jefe']:4.1f}       {r['jefe_solo']:6.0%}        {r['vida_jefe']:6.0%}")


if __name__ == "__main__":
    main()
