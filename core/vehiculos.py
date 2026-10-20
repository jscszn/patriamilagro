"""Refuerzos aleatorios: DRON, MOTO y CAMIONETA BLINDADA.

Los tres son la misma clase (Vehiculo) con una máquina de estados por clase, igual que los
jefes: un diccionario {estado: función}. Así se serializan con asdict y viajan por la red.

  Dron       aviso -> volar (se pone sobre el jugador y suelta balas hacia abajo) -> huir
  Moto       aviso -> correr (cruza la pantalla disparando al frente; salta huecos y escalones)
  Camioneta  aviso -> entrar (avanza hasta quedar a distancia) -> plantada (el tirador del
             techo dispara ráfagas apuntadas). Está blindada: hay que destruirla para pasar.

Cuándo y dónde aparecen lo decide core/director.py; aquí solo está cómo se comportan.
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Callable, Dict, Optional

import settings
from core.bullet import Bala
from core.datos_sprites import boca_sprite
from core.fisica import Cuerpo

V = settings.VEHICULOS


@dataclass
class Vehiculo(Cuerpo):
    clase: str = "dron"              # dron | moto | camioneta
    direccion: int = -1              # hacia dónde avanza: -1 = viene de frente, 1 = por detrás
    vida: int = 1
    vida_max: int = 1
    estado: str = "aviso"
    t_estado: float = 0.0
    recarga: float = 1.0             # tiempo que falta para poder disparar
    contador: int = 0                # balas de la ráfaga actual (camioneta)
    altura: float = 70.0             # dron: altura de vuelo (y de la caja)
    premio: str = ""                 # camioneta: suministro que suelta al explotar
    t_anim: float = 0.0
    t_golpe: float = 0.0

    @property
    def stats(self) -> dict:
        return V[self.clase]

    @property
    def vivo(self) -> bool:
        return self.vida > 0

    @property
    def activo(self) -> bool:
        """Ya entró en juego: se le puede disparar y hace daño al tocarlo."""
        return self.vivo and self.estado != "aviso"

    @classmethod
    def crear(cls, clase: str, x: float, y: float, direccion: int = -1, vida: Optional[int] = None,
              altura: float = 70.0, premio: str = "") -> "Vehiculo":
        s = V[clase]
        vida = vida or s["vida"]
        return cls(x=x, y=y, ancho=s["caja"][0], alto=s["caja"][1], clase=clase, direccion=direccion,
                   vida=vida, vida_max=vida, recarga=s["cadencia"] * 0.6, altura=altura, premio=premio)

    def cambiar(self, estado: str) -> None:
        self.estado, self.t_estado, self.contador = estado, 0.0, 0

    def update(self, dt: float, mundo) -> None:
        self.t_anim += dt
        self.t_estado += dt
        self.t_golpe = max(0.0, self.t_golpe - dt)
        self.recarga = max(0.0, self.recarga - dt)
        siguiente = MAQUINAS[self.clase][self.estado](self, dt, mundo)
        if siguiente:
            self.cambiar(siguiente)

    def recibir_dano(self, dano: int, mundo) -> None:
        if not self.activo:
            return
        self.vida = max(0, self.vida - dano)
        self.t_golpe = 0.08
        if not self.vivo:
            mundo.evento("vehiculo_muere", clase=self.clase, x=self.centro[0], y=self.centro[1])

    # --- Ayudas para los estados ------------------------------------------------------------
    def boca(self):
        """De dónde salen las balas. Si el sprite trae su boca (el fusil del tirador del techo
        de la camioneta), sale de ahí; si no, de settings.VEHICULOS[clase]["arma"]."""
        del_sprite = boca_sprite(self.clase)
        if del_sprite is not None:                       # relativa al ancla: centro de la base
            return self.centro[0] + self.direccion * del_sprite[0], self.pie + del_sprite[1]
        adelante, abajo = self.stats["arma"]
        return self.centro[0] + self.direccion * adelante, self.y + abajo

    def disparar(self, mundo, angulo: float) -> None:
        x, y = self.boca()
        v = self.stats["vel_bala"]
        vx, vy = round(math.cos(angulo) * v, 6), round(math.sin(angulo) * v, 6)   # sen(pi) no da 0 exacto
        mundo.agregar_bala(Bala(x, y, vx, vy, del_jugador=False, dano=self.stats["dano_bala"]))
        mundo.evento("disparo_enemigo", x=x, y=y)
        self.recarga = self.stats["cadencia"]

    def avanzar_por_el_suelo(self, dt: float, mundo, velocidad: float) -> bool:
        """Rueda con gravedad. Devuelve False si adelante no hay suelo (precipicio)."""
        frente = self.centro[0] + self.direccion * (self.ancho / 2 + 6)
        hay_suelo = mundo.geometria.altura_suelo(frente) <= settings.ALTO
        self.vx = self.direccion * velocidad
        mundo.geometria.mover(self, dt)
        return hay_suelo


Estado = Callable[[Vehiculo, float, object], Optional[str]]


def _aviso(siguiente: str) -> Estado:
    """Espera fuera de la pantalla mientras suena el aviso (el HUD muestra por dónde viene)."""
    def estado(v: Vehiculo, dt: float, mundo) -> Optional[str]:
        return siguiente if v.t_estado >= v.stats["aviso"] * mundo.factor_aviso() else None
    return estado


# --- Dron -------------------------------------------------------------------------------------
def _dron_volar(v: Vehiculo, dt: float, mundo) -> Optional[str]:
    s = v.stats
    objetivo = mundo.jugador_mas_cercano(v.centro[0])
    destino = objetivo.centro[0] if objetivo is not None else v.centro[0] + v.direccion * 40
    dx = destino - v.centro[0]
    v.x += max(-s["velocidad"], min(s["velocidad"], dx * 2.0)) * dt
    v.y = v.altura + math.sin(v.t_anim * 3.0) * 4.0
    if objetivo is not None and v.recarga <= 0 and abs(dx) < s["alcance"] and mundo.en_pantalla(v.rect):
        bx, by = v.boca()
        angulo = math.atan2(objetivo.centro[1] - by, objetivo.centro[0] - bx)
        # Solo dispara hacia abajo, en un cono de 50 grados a cada lado de la vertical
        angulo = max(math.radians(40), min(math.radians(140), angulo))
        v.disparar(mundo, angulo)
    return "huir" if v.t_estado >= s["duracion"] else None


def _dron_huir(v: Vehiculo, dt: float, mundo) -> Optional[str]:
    v.y -= 70 * dt
    v.x += v.direccion * 40 * dt
    if v.y < -30:
        v.vida = 0                    # se fue: desaparece sin dar puntos
    return None


# --- Moto -------------------------------------------------------------------------------------
def _moto_correr(v: Vehiculo, dt: float, mundo) -> Optional[str]:
    s = v.stats
    hay_suelo = v.avanzar_por_el_suelo(dt, mundo, s["velocidad"])
    if v.en_suelo and (not hay_suelo or v.choco_pared):
        v.vy = -s["vel_salto"]        # salta el hueco o el escalón como por una rampa
    objetivo = mundo.jugador_mas_cercano(v.centro[0])
    if objetivo is not None and v.recarga <= 0 and mundo.en_pantalla(v.rect):
        adelante = (objetivo.centro[0] - v.centro[0]) * v.direccion
        if 20 < adelante < s["alcance"]:
            v.disparar(mundo, 0.0 if v.direccion > 0 else math.pi)
    return None


# --- Camioneta blindada -----------------------------------------------------------------------
def _camioneta_entrar(v: Vehiculo, dt: float, mundo) -> Optional[str]:
    s = v.stats
    objetivo = mundo.jugador_mas_cercano(v.centro[0])
    cerca = objetivo is not None and abs(objetivo.centro[0] - v.centro[0]) <= s["distancia"]
    dentro = mundo.en_pantalla(v.rect.inflate(-v.ancho, 0), -8)     # el centro ya se ve
    if not v.avanzar_por_el_suelo(dt, mundo, s["velocidad"]) or v.choco_pared or (dentro and cerca) \
            or v.t_estado > 5.0:
        v.vx = 0.0
        return "plantada"
    return None


def _camioneta_plantada(v: Vehiculo, dt: float, mundo) -> Optional[str]:
    s = v.stats
    v.vx = 0.0
    mundo.geometria.mover(v, dt)
    objetivo = mundo.jugador_mas_cercano(v.centro[0])
    if objetivo is None or not mundo.en_pantalla(v.rect):
        return None
    v.direccion = 1 if objetivo.centro[0] > v.centro[0] else -1
    if v.recarga <= 0:
        bx, by = v.boca()
        v.disparar(mundo, math.atan2(objetivo.centro[1] - by, objetivo.centro[0] - bx))
        v.contador += 1
        if v.contador < s["rafaga"]:
            v.recarga = 0.28          # siguiente bala de la misma ráfaga
        else:
            v.contador = 0
    return None


MAQUINAS: Dict[str, Dict[str, Estado]] = {
    "dron": {"aviso": _aviso("volar"), "volar": _dron_volar, "huir": _dron_huir},
    "moto": {"aviso": _aviso("correr"), "correr": _moto_correr},
    "camioneta": {"aviso": _aviso("entrar"), "entrar": _camioneta_entrar, "plantada": _camioneta_plantada},
}


def vehiculo_to_dict(v: Vehiculo) -> dict:
    return asdict(v)


def vehiculo_from_dict(d: dict) -> Vehiculo:
    return Vehiculo(**d)
