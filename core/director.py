"""Director aleatorio: decide qué refuerzos y suministros aparecen en un nivel, y dónde.

A partir de una SEMILLA (distinta en cada partida) arma el PLAN del nivel: una lista de
apariciones ordenadas por x. Con la misma semilla el plan es idéntico, así que:
  - el servidor y los clientes del modo en red ven lo mismo;
  - el estado se puede guardar con solo la semilla;
  - las pruebas son reproducibles.

La dificultad no queda al azar: cada nivel fija en sus datos (levels/nivelN.py, clave
"aleatorio") cuántos refuerzos de cada clase pueden salir (el nivel 1 no tiene camionetas; el 3
tiene más de todo), desde dónde pueden entrar motos por la espalda y qué suministros están
garantizados. `peligro` viene del grafo del país (core/mapa.py): una ruta más peligrosa o un
jefe libre cerca suman refuerzos.
"""
from __future__ import annotations

import random
from typing import List

import settings
from levels import cargar_nivel

CLASES = ("dron", "moto", "camioneta")


def _elegir_con_pesos(rng: random.Random, pesos: dict) -> str:
    claves = sorted(pesos)
    return rng.choices(claves, weights=[pesos[c] for c in claves])[0]


def planear(numero: int, largo: int, semilla: int, peligro: int = 0) -> List[dict]:
    """Plan de apariciones del nivel: [{"x", "tipo", ...}] ordenado por x.

    tipo "dron": altura.   tipo "moto": lado.   tipo "camioneta": vida, premio.
    tipo "suministro": clase (triple | rapida | vida).
    """
    conf = cargar_nivel(numero).get("aleatorio")
    if conf is None:
        return []
    rng = random.Random(semilla * 1000 + numero)
    arena_x = largo - settings.ANCHO
    desde, hasta = conf["desde"], arena_x - 140
    if hasta <= desde:
        return []

    tipos: List[str] = []
    for clase in CLASES:
        tipos += [clase] * rng.randint(*conf[clase])
    # El peligro de la ruta suma refuerzos de las clases que ese nivel permite
    permitidas = [c for c in CLASES if conf[c][1] > 0]
    tipos += [rng.choice(permitidas) for _ in range(max(0, peligro))]
    tipos += ["suministro"] * rng.randint(*conf["suministro"])
    rng.shuffle(tipos)

    # Posiciones al azar, separadas entre sí para que no caiga todo junto
    posiciones: List[int] = []
    for _ in tipos:
        for _intento in range(40):
            x = rng.randrange(desde, hasta, 4)
            if all(abs(x - otra) >= settings.SEPARACION_ALEATORIA for otra in posiciones):
                posiciones.append(x)
                break
    plan = []
    for x, tipo in zip(sorted(posiciones), tipos):
        aparicion = {"x": x, "tipo": tipo}
        if tipo == "dron":
            aparicion["altura"] = rng.randrange(52, 88, 4)
        elif tipo == "moto":
            por_detras = rng.random() < conf["detras"] and x >= conf.get("detras_desde", 0)
            aparicion["lado"] = "izquierda" if por_detras else "derecha"
        elif tipo == "camioneta":
            aparicion["vida"] = conf["vida_camioneta"]
            aparicion["premio"] = rng.choice(("triple", "rapida"))
        else:
            aparicion["clase"] = _elegir_con_pesos(rng, settings.PESOS_SUMINISTRO)
        plan.append(aparicion)
    # Suministros garantizados del nivel (no dependen del azar)
    plan += [{"x": f["x"], "tipo": "suministro", "clase": f["clase"]} for f in conf.get("fijos", [])]
    return sorted(plan, key=lambda a: a["x"])


def resumen(plan: List[dict]) -> dict:
    """Cuántas apariciones hay de cada tipo (para pruebas y para mostrar en pantalla)."""
    cuenta = {"dron": 0, "moto": 0, "camioneta": 0, "suministro": 0}
    for a in plan:
        cuenta[a["tipo"]] += 1
    return cuenta
