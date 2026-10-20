"""El único enemigo común: el SICARIO RASO (idéntico en los 3 niveles).

IA en dos estados:
  correr  -> PERSIGUE al jugador más cercano (se da la vuelta si lo pasa). Si quedó atrás
             (el jugador le lleva más de distancia_alcance px), corre más rápido para alcanzarlo.
             Salta los escalones.
             Cuando su recarga termina y está en pantalla, pasa a apuntar.
  apuntar -> se detiene un instante (aviso visual) y dispara una bala lenta en línea recta.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

import settings
from core.bullet import Bala
from core.fisica import Cuerpo

S = settings.SICARIO


@dataclass
class Sicario(Cuerpo):
    ancho: int = S["ancho"]
    alto: int = S["alto"]
    direccion: int = -1
    estado: str = "correr"           # correr | apuntar
    t_estado: float = 0.0
    recarga: float = S["cadencia"]   # tiempo que falta para poder disparar
    vida: int = S["vida"]
    t_giro: float = 0.0              # tiempo que falta para poder volver a girar
    t_anim: float = 0.0

    @property
    def vivo(self) -> bool:
        return self.vida > 0

    def update(self, dt: float, mundo) -> None:
        self.t_anim += dt
        self.t_estado += dt
        self.t_giro = max(0.0, self.t_giro - dt)
        objetivo = mundo.jugador_mas_cercano(self.centro[0])

        if self.estado == "correr":
            self._perseguir(objetivo)
            # Atrás = el jugador avanzó y le lleva ventaja (la cámara solo avanza a la derecha).
            # Los que vienen de frente no aceleran: la dificultad del nivel no cambia.
            atras = objetivo is not None and objetivo.centro[0] - self.centro[0] > S["distancia_alcance"]
            self.vx = self.direccion * (S["velocidad_alcance"] if atras and self.direccion > 0 else S["velocidad"])
            self.recarga -= dt
            if self.recarga <= 0 and objetivo is not None and mundo.en_pantalla(self.rect):
                self.estado, self.t_estado = "apuntar", 0.0
                self.direccion = 1 if objetivo.centro[0] > self.centro[0] else -1
        elif self.estado == "apuntar":
            self.vx = 0.0
            if self.t_estado >= S["apuntar"]:
                self._disparar(mundo)
                self.estado, self.t_estado = "correr", 0.0
                self.recarga = S["cadencia"]
                if objetivo is not None:  # vuelve a correr hacia el jugador
                    self.direccion = 1 if objetivo.centro[0] > self.centro[0] else -1

        mundo.geometria.mover(self, dt)
        if self.choco_pared and self.en_suelo:
            self.vy = -S["vel_salto"]          # sube el escalón en vez de darse la vuelta

    def _perseguir(self, objetivo) -> None:
        """Gira hacia el jugador si quedó del otro lado (con margen y tiempo mínimo entre giros)."""
        if objetivo is None or self.t_giro > 0:
            return
        dx = objetivo.centro[0] - self.centro[0]
        if abs(dx) > S["margen_giro"] and (1 if dx > 0 else -1) != self.direccion:
            self.direccion = -self.direccion
            self.t_giro = S["giro_min"]

    def _disparar(self, mundo) -> None:
        x = self.centro[0] + self.direccion * S["arma"][0]
        y = self.y + S["arma"][1]
        mundo.agregar_bala(Bala(x, y, self.direccion * S["vel_bala"], 0.0,
                                del_jugador=False, dano=S["dano_bala"]))
        mundo.evento("disparo_enemigo", x=x, y=y)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Sicario":
        return cls(**d)
