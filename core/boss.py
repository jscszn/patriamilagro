"""Jefes de nivel. Cada patrón de ataque es una pequeña MÁQUINA DE ESTADOS.

Una máquina es un diccionario {nombre_estado: función}. Cada función recibe
(jefe, dt, mundo) y devuelve el nombre del siguiente estado, o None para quedarse.
El estado actual es solo un texto (jefe.estado), así el jefe se puede serializar.

  Jefe 1  esperar -> rafaga (ametralladora horizontal alta o baja) | saltar | barrido
          (abanico que barre de arriba abajo, con huecos para pasar) -> esperar
  Jefe 2  esperar -> abanico (3 balas) | preparar -> embestida -> aturdido -> esperar
  Jefe 3  esperar -> dirigido (balas al jugador) | onda (onda de choque) | invocar (2 sicarios)

Con la mitad de la vida entra en "fase 2": todo ocurre más rápido.
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Callable, Dict, Optional

import settings
from core.bullet import Bala
from core.fisica import Cuerpo


@dataclass
class Jefe(Cuerpo):
    tipo: int = 1
    vida: int = 1
    vida_max: int = 1
    estado: str = "entrada"
    t_estado: float = 0.0
    contador: int = 0             # disparos hechos en el estado actual
    ciclo: int = 0                # cuántos ataques lleva (para alternarlos)
    mirando: int = -1
    t_golpe: float = 0.0          # parpadeo al recibir un impacto
    arena_x0: float = 0.0
    arena_x1: float = 256.0

    @property
    def stats(self) -> dict:
        return settings.JEFES[self.tipo]

    @property
    def nombre(self) -> str:
        return self.stats["nombre"]

    @property
    def vivo(self) -> bool:
        return self.vida > 0

    @property
    def fase2(self) -> bool:
        return self.vida <= self.vida_max // 2

    def ritmo(self, normal: float, rapido: float) -> float:
        """Duración según la fase."""
        return rapido if self.fase2 else normal

    # --- Ciclo de vida -----------------------------------------------------------
    @classmethod
    def crear(cls, tipo: int, x: float, y: float, arena_x0: float, arena_x1: float) -> "Jefe":
        s = settings.JEFES[tipo]
        return cls(x=x, y=y, ancho=s["ancho"], alto=s["alto"], tipo=tipo, vida=s["vida"],
                   vida_max=s["vida"], arena_x0=arena_x0, arena_x1=arena_x1)

    def cambiar(self, estado: str) -> None:
        self.estado, self.t_estado, self.contador = estado, 0.0, 0
        # Jefe 2: agachado desde que se prepara hasta que se le pasa el aturdimiento (la embestida
        # se puede saltar, y al chocar no se levanta de golpe debajo de quien lo acaba de saltar)
        bajo = self.stats.get("alto_embestida")
        if bajo:
            pie = self.pie
            self.alto = bajo if estado in ("preparar", "embestida", "aturdido") else self.stats["alto"]
            self.y = pie - self.alto

    def update(self, dt: float, mundo) -> None:
        self.t_estado += dt
        self.t_golpe = max(0.0, self.t_golpe - dt)
        objetivo = mundo.jugador_mas_cercano(self.centro[0])
        if objetivo is not None and self.estado not in ("embestida", "saltar"):
            self.mirando = 1 if objetivo.centro[0] > self.centro[0] else -1

        maquina = MAQUINAS[self.tipo]
        siguiente = maquina.get(self.estado, _entrada)(self, dt, mundo)
        if siguiente:
            self.cambiar(siguiente)

        mundo.geometria.mover(self, dt)
        # Muros invisibles de la arena
        if self.x < self.arena_x0:
            self.x, self.choco_pared = self.arena_x0, True
        elif self.x + self.ancho > self.arena_x1:
            self.x, self.choco_pared = self.arena_x1 - self.ancho, True

    def recibir_dano(self, dano: int, mundo) -> None:
        if self.estado == "entrada" or not self.vivo:
            return
        self.vida = max(0, self.vida - dano)
        self.t_golpe = 0.08
        if not self.vivo:
            mundo.evento("jefe_derrotado", x=self.centro[0], y=self.centro[1])

    # --- Ayudas para los patrones ---------------------------------------------------
    def boca(self):
        """Posición de la boca del arma según settings.JEFES[tipo]["arma"]."""
        adelante, abajo = self.stats["arma"]
        return self.centro[0] + self.mirando * adelante, self.y + abajo

    def disparar(self, mundo, x: float, y: float, angulo: float, velocidad: Optional[float] = None,
                 dano: Optional[int] = None) -> None:
        v = velocidad or self.stats["vel_bala"]
        vx, vy = round(math.cos(angulo) * v, 6), round(math.sin(angulo) * v, 6)   # sen(pi) no da 0 exacto
        mundo.agregar_bala(Bala(x, y, vx, vy, del_jugador=False,
                                dano=dano or self.stats["dano_bala"], tipo="jefe", radio=3))
        mundo.evento("disparo_jefe", x=x, y=y)

    def angulo_hacia(self, objetivo, desde_y: float) -> float:
        if objetivo is None:
            return math.pi if self.mirando < 0 else 0.0
        ox, oy = objetivo.centro
        return math.atan2(oy - desde_y, ox - self.boca()[0])


Estado = Callable[[Jefe, float, object], Optional[str]]


def _entrada(jefe: Jefe, dt: float, mundo) -> Optional[str]:
    """Pausa dramática mientras aparece el nombre del jefe (es invulnerable)."""
    jefe.vx = 0.0
    return "esperar" if jefe.t_estado >= 1.5 else None


# =============================================================================
# JEFE 1 - El Jaguar del Monte: ráfagas horizontales, saltos y barrido en abanico
# =============================================================================
# Ángulos del barrido respecto a la horizontal (negativo = hacia arriba). Entre bala y bala
# quedan 16 grados: a media arena el hueco mide más que el presidente, así que se puede pasar.
BARRIDO_J1 = (-40, -24, -8, 8, 24)
BARRIDO_J1_FASE2 = (-48, -32, -16, 0, 16, 32)


def _j1_esperar(jefe, dt, mundo):
    jefe.vx = 0.0
    if jefe.t_estado >= jefe.ritmo(0.9, 0.5):
        jefe.ciclo += 1
        if jefe.ciclo % 2:
            return "rafaga" if (jefe.ciclo // 2) % 2 == 0 else "barrido"
        return "saltar"
    return None


def _j1_barrido(jefe, dt, mundo):
    """Abre fuego en VARIAS DIRECCIONES: un abanico que barre de arriba hacia abajo, una bala
    cada vez. Avisa 0,45 s antes (apunta al cielo) y sus balas son más lentas y quitan 1 corazón."""
    jefe.vx = 0.0
    angulos = BARRIDO_J1_FASE2 if jefe.fase2 else BARRIDO_J1
    intervalo = jefe.ritmo(0.16, 0.12)
    if jefe.t_estado >= 0.45 + jefe.contador * intervalo and jefe.contador < len(angulos):
        x, y = jefe.boca()
        grados = angulos[jefe.contador]
        angulo = math.radians(grados) if jefe.mirando > 0 else math.pi - math.radians(grados)
        jefe.disparar(mundo, x, y, angulo, velocidad=jefe.stats["vel_bala"] * 0.75, dano=1)
        jefe.contador += 1
    if jefe.contador >= len(angulos) and jefe.t_estado >= 0.45 + len(angulos) * intervalo + 0.35:
        return "esperar"
    return None


def _j1_rafaga(jefe, dt, mundo):
    """Ametralladora horizontal. Alterna ráfagas ALTAS desde el fusil (pasan sobre la cabeza:
    no saltes) y BAJAS a ras del suelo (salta)."""
    jefe.vx = 0.0
    intervalo = jefe.ritmo(0.14, 0.10)
    total = 6 if not jefe.fase2 else 9
    if jefe.t_estado >= 0.3 + jefe.contador * intervalo and jefe.contador < total:
        alta = (jefe.ciclo // 4) % 2 == 0
        x, y = jefe.boca()
        if not alta:
            x, y = jefe.centro[0] + jefe.mirando * (jefe.ancho // 2 + 4), jefe.pie - 10
        jefe.disparar(mundo, x, y, 0.0 if jefe.mirando > 0 else math.pi)
        jefe.contador += 1
    if jefe.contador >= total and jefe.t_estado >= 0.3 + total * intervalo + 0.3:
        return "esperar"
    return None


def _j1_saltar(jefe, dt, mundo):
    """Salta hacia donde está el jugador y aterriza sacudiendo el suelo."""
    if jefe.contador == 0:
        objetivo = mundo.jugador_mas_cercano(jefe.centro[0])
        destino = objetivo.centro[0] if objetivo else jefe.centro[0]
        jefe.vy = -300.0
        jefe.vx = max(-120.0, min(120.0, (destino - jefe.centro[0]) / 0.95))
        jefe.contador = 1
        mundo.evento("jefe_salta")
    elif jefe.en_suelo and jefe.t_estado > 0.15:
        jefe.vx = 0.0
        mundo.evento("temblor", fuerza=3)
        return "esperar"
    return None


# =============================================================================
# JEFE 2 - Don Concreto: abanico de 3 balas y embestida
# =============================================================================
def _j2_esperar(jefe, dt, mundo):
    jefe.vx = 0.0
    if jefe.t_estado >= jefe.ritmo(0.8, 0.45):
        jefe.ciclo += 1
        return "abanico" if jefe.ciclo % 2 else "preparar"
    return None


def _j2_abanico(jefe, dt, mundo):
    jefe.vx = 0.0
    descargas = 3 if not jefe.fase2 else 4
    intervalo = jefe.ritmo(0.55, 0.4)
    if jefe.t_estado >= 0.25 + jefe.contador * intervalo and jefe.contador < descargas:
        x, y = jefe.boca()
        base = jefe.angulo_hacia(mundo.jugador_mas_cercano(jefe.centro[0]), y)
        for desvio in (-0.32, 0.0, 0.32):
            jefe.disparar(mundo, x, y, base + desvio)
        jefe.contador += 1
    if jefe.contador >= descargas and jefe.t_estado >= 0.25 + descargas * intervalo:
        return "esperar"
    return None


def _j2_preparar(jefe, dt, mundo):
    """Se agacha y tiembla (aviso) antes de embestir."""
    jefe.vx = 0.0
    return "embestida" if jefe.t_estado >= jefe.ritmo(0.7, 0.45) else None


def _j2_embestida(jefe, dt, mundo):
    jefe.vx = jefe.mirando * jefe.ritmo(170.0, 210.0)
    if jefe.choco_pared and jefe.t_estado > 0.05:
        mundo.evento("temblor", fuerza=4)
        return "aturdido"
    return None


def _j2_aturdido(jefe, dt, mundo):
    jefe.vx = 0.0
    return "esperar" if jefe.t_estado >= jefe.ritmo(1.0, 0.7) else None


# =============================================================================
# JEFE 3 - La Sombra de la Raya: balas dirigidas + poder especial
# =============================================================================
def _j3_esperar(jefe, dt, mundo):
    jefe.vx = 0.0
    if jefe.t_estado >= jefe.ritmo(0.7, 0.4):
        jefe.ciclo += 1
        if jefe.ciclo % 2:
            return "dirigido"
        return "onda" if (jefe.ciclo // 2) % 2 else "invocar"
    return None


def _j3_dirigido(jefe, dt, mundo):
    """Balas rápidas apuntadas directamente al jugador."""
    jefe.vx = 0.0
    total = 5 if not jefe.fase2 else 7
    intervalo = jefe.ritmo(0.32, 0.22)
    if jefe.t_estado >= 0.2 + jefe.contador * intervalo and jefe.contador < total:
        x, y = jefe.boca()
        angulo = jefe.angulo_hacia(mundo.jugador_mas_cercano(jefe.centro[0]), y)
        jefe.disparar(mundo, x, y, angulo)
        jefe.contador += 1
    if jefe.contador >= total and jefe.t_estado >= 0.2 + total * intervalo + 0.2:
        return "esperar"
    return None


def _j3_onda(jefe, dt, mundo):
    """Salta en el sitio y al caer lanza dos ondas de choque por el suelo (hay que saltarlas)."""
    if jefe.contador == 0:
        jefe.vx, jefe.vy = 0.0, -280.0
        jefe.contador = 1
    elif jefe.contador == 1 and jefe.en_suelo and jefe.t_estado > 0.15:
        suelo = jefe.pie
        for direccion in (-1, 1):
            mundo.agregar_bala(Bala(jefe.centro[0], suelo, direccion * 130.0, 0.0, del_jugador=False,
                                    dano=jefe.stats["dano_bala"], tipo="onda", alto=12))
        mundo.evento("temblor", fuerza=5)
        mundo.evento("onda_choque", x=jefe.centro[0], y=suelo)
        jefe.contador = 2
    elif jefe.contador == 2 and jefe.t_estado > 0.8:
        return "esperar"
    return None


def _j3_invocar(jefe, dt, mundo):
    """Pide refuerzos: aparecen 2 sicarios rasos en los bordes de la arena."""
    jefe.vx = 0.0
    if jefe.contador == 0 and jefe.t_estado >= 0.5:
        if mundo.cantidad_sicarios() < 4:
            mundo.invocar_sicario(jefe.arena_x0 + 4, 1)
            mundo.invocar_sicario(jefe.arena_x1 - 14, -1)
            mundo.evento("invocacion", x=jefe.centro[0], y=jefe.y)
        jefe.contador = 1
    return "esperar" if jefe.t_estado >= 1.1 else None


MAQUINAS: Dict[int, Dict[str, Estado]] = {
    1: {"entrada": _entrada, "esperar": _j1_esperar, "rafaga": _j1_rafaga, "saltar": _j1_saltar,
        "barrido": _j1_barrido},
    2: {"entrada": _entrada, "esperar": _j2_esperar, "abanico": _j2_abanico, "preparar": _j2_preparar,
        "embestida": _j2_embestida, "aturdido": _j2_aturdido},
    3: {"entrada": _entrada, "esperar": _j3_esperar, "dirigido": _j3_dirigido, "onda": _j3_onda,
        "invocar": _j3_invocar},
}


def jefe_to_dict(jefe: Optional[Jefe]) -> Optional[dict]:
    return asdict(jefe) if jefe else None


def jefe_from_dict(d: Optional[dict]) -> Optional[Jefe]:
    return Jefe(**d) if d else None
