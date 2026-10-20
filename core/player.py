"""El jugador: el Presidente A. Milagro."""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass

import input_manager as im
import settings
from core.bullet import Bala
from core.datos_sprites import boca_jugador
from core.fisica import Cuerpo, _se_solapan

J = settings.JUGADOR


@dataclass
class Jugador(Cuerpo):
    id_jugador: int = 1
    ancho: int = J["ancho"]
    alto: int = J["alto"]
    mirando: int = 1                 # 1 = derecha, -1 = izquierda
    apunte_x: int = 1                # dirección del arma (-1, 0, 1)
    apunte_y: int = 0                # -1 arriba, 1 abajo
    agachado: bool = False
    vidas: int = J["vidas"]
    salud: int = J["salud"]
    invulnerable: float = 0.0
    cooldown: float = 0.0
    arma: str = "normal"             # normal | triple | rapida
    rol: str = "presidente"          # settings.ROLES (en un jugador siempre es el presidente)
    puntaje: int = 0
    t_reaparecer: float = 0.0        # > 0 mientras espera reaparecer tras morir
    t_atravesar: float = 0.0         # > 0 mientras baja de una plataforma
    t_disparo: float = 0.0           # para la pose de disparo
    t_herido: float = 0.0            # > 0 justo después de recibir un golpe (pose "herido")
    t_anim: float = 0.0

    @classmethod
    def con_rol(cls, id_jugador: int, rol: str, **datos) -> "Jugador":
        """Jugador con la salud y el arma iniciales de su rol (modo multijugador)."""
        stats = settings.ROLES[rol]
        return cls(id_jugador=id_jugador, rol=rol, salud=stats["salud"], arma=stats["arma"], **datos)

    # --- Estado -----------------------------------------------------------------
    @property
    def stats_rol(self) -> dict:
        return settings.ROLES[self.rol]

    @property
    def salud_max(self) -> int:
        return self.stats_rol["salud"]

    @property
    def activo(self) -> bool:
        """Está en juego (no esperando reaparecer ni eliminado)."""
        return self.t_reaparecer <= 0 and self.vidas > 0

    @property
    def eliminado(self) -> bool:
        return self.vidas <= 0

    # --- Actualización -------------------------------------------------------------
    def update(self, dt: float, acciones: im.EstadoAcciones, mundo) -> None:
        if self.eliminado:
            return
        if self.t_reaparecer > 0:
            self.t_reaparecer -= dt
            if self.t_reaparecer <= 0:
                self._reaparecer(mundo)
            return

        self.t_anim += dt
        self.invulnerable = max(0.0, self.invulnerable - dt)
        self.cooldown = max(0.0, self.cooldown - dt)
        self.t_atravesar = max(0.0, self.t_atravesar - dt)
        self.t_disparo = max(0.0, self.t_disparo - dt)
        self.t_herido = max(0.0, self.t_herido - dt)

        h = int(acciones.mantiene(im.DERECHA)) - int(acciones.mantiene(im.IZQUIERDA))
        v = int(acciones.mantiene(im.ABAJO)) - int(acciones.mantiene(im.ARRIBA))

        # Acostarse: solo en el suelo y sin moverse a los lados.
        self._set_agachado(self.en_suelo and v == 1 and h == 0, mundo.geometria)

        if h:
            self.mirando = h
        self.vx = 0.0 if self.agachado else h * J["velocidad"] * self.stats_rol["velocidad"]

        # Salto (ABAJO + SALTAR sobre una plataforma = bajarse de ella)
        if acciones.pulso(im.SALTAR) and self.en_suelo:
            if v == 1 and mundo.geometria.sobre_plataforma(self):
                self.t_atravesar = 0.25
                self._set_agachado(False)
            else:
                self._set_agachado(False)
                self.vy = -J["vel_salto"]
                mundo.evento("salto")
        # Salto variable: si suelta el botón subiendo, el salto se corta.
        if not acciones.mantiene(im.SALTAR) and self.vy < 0:
            self.vy = max(self.vy, -J["vel_salto"] * J["corte_salto"])

        mundo.geometria.mover(self, dt, atravesar_plataformas=self.t_atravesar > 0)

        # Apuntar en 8 direcciones
        self._calcular_apunte(h, v)
        if acciones.mantiene(im.DISPARAR) and self.cooldown <= 0:
            self._disparar(mundo)

    def _set_agachado(self, agachado: bool, geometria=None) -> None:
        """Cambia la caja de colisión (de pie / acostado) manteniendo los pies en el suelo y el
        centro en su lugar. Acostado es más ancho: si junto a una pared no cabe, se corre lo
        justo para caber; si ni así cabe, sigue de pie."""
        if agachado == self.agachado:
            return
        pie, centro = self.pie, self.x + self.ancho / 2
        antes = (self.x, self.y, self.ancho, self.alto)
        self.agachado = agachado
        self.ancho = J["ancho_agachado"] if agachado else J["ancho"]
        self.alto = J["alto_agachado"] if agachado else J["alto"]
        self.x, self.y = centro - self.ancho / 2, pie - self.alto
        if agachado and geometria is not None and not self._caber(geometria):
            self.agachado = False
            self.x, self.y, self.ancho, self.alto = antes

    def _caber(self, geometria) -> bool:
        """Corre la caja a un lado si choca con un sólido. False si no hay lugar."""
        for solido in geometria.solidos:
            if _se_solapan(self, solido):
                centro = self.x + self.ancho / 2
                self.x = solido.right if centro > solido.centerx else solido.left - self.ancho
        return not any(_se_solapan(self, s) for s in geometria.solidos)

    def _calcular_apunte(self, h: int, v: int) -> None:
        if self.agachado:
            self.apunte_x, self.apunte_y = self.mirando, 0
        elif h == 0 and v == 0:
            self.apunte_x, self.apunte_y = self.mirando, 0
        elif v == 1 and self.en_suelo and h == 0:
            self.apunte_x, self.apunte_y = self.mirando, 0
        else:
            self.apunte_x, self.apunte_y = h, v

    # --- Pose (qué dibujo corresponde al estado; también decide de dónde sale la bala) ---
    def pose(self) -> str:
        """quieto, disparar, correr, saltar, agachado, arriba, diag_arriba, diag_abajo, abajo o herido."""
        return "herido" if self.t_herido > 0 else self.pose_arma()

    def pose_arma(self, disparando: bool = False) -> str:
        """Pose según cómo sostiene el arma (sin contar el golpe). De pie y quieto: "quieto"
        (fusil bajo) o "disparar" (al frente) si está disparando o disparó hace un momento."""
        if self.agachado:
            return "agachado"
        if self.apunte_y < 0:
            return "arriba" if self.apunte_x == 0 else "diag_arriba"
        if self.apunte_y > 0:
            return "abajo" if self.apunte_x == 0 else "diag_abajo"
        if not self.en_suelo:
            return "saltar"
        if abs(self.vx) > 1:
            return "correr"
        return "disparar" if disparando or self.t_disparo > 0 else "quieto"

    def punto_disparo(self):
        """Dónde sale la bala: la punta del arma de la pose actual (de sprites.json) o,
        si no hay PNG, un punto genérico según la dirección de apunte."""
        cx = self.x + self.ancho / 2
        boca = boca_jugador(self.pose_arma(disparando=True), self.t_anim)
        if boca is not None:
            return cx + self.mirando * boca[0], self.pie + boca[1]
        if self.agachado:
            return cx + self.mirando * 20, self.pie - 5
        return cx + self.apunte_x * 9, self.y + self.alto * 0.3 + self.apunte_y * 9

    def _disparar(self, mundo) -> None:
        angulo = math.atan2(self.apunte_y, self.apunte_x)
        angulos = [angulo]
        if self.arma == "triple":
            a = J["apertura_triple"]
            angulos = [angulo - a, angulo, angulo + a]
        x, y = self.punto_disparo()
        for ang in angulos:
            mundo.agregar_bala(Bala(x, y, math.cos(ang) * J["vel_bala"], math.sin(ang) * J["vel_bala"],
                                    del_jugador=True, dueno=self.id_jugador))
        self.cooldown = J["cadencia_rapida"] if self.arma == "rapida" else J["cadencia"]
        self.t_disparo = 0.2
        mundo.evento("disparo_jugador", x=x + math.cos(angulo) * 3, y=y + math.sin(angulo) * 3)

    # --- Daño y vidas --------------------------------------------------------------
    def recibir_dano(self, dano: int, mundo) -> None:
        if not self.activo or self.invulnerable > 0:
            return
        self.salud -= dano
        if self.salud <= 0:
            self.morir(mundo)
        else:
            self.invulnerable = J["invulnerable"] / 2
            self.t_herido = 0.35
            mundo.evento("jugador_herido", x=self.centro[0], y=self.centro[1])

    def morir(self, mundo) -> None:
        if not self.activo:
            return
        self.vidas -= 1
        self.arma = self.stats_rol["arma"]         # pierde el arma recogida; conserva la de su rol
        self.t_reaparecer = 1.2
        mundo.evento("jugador_muere", x=self.centro[0], y=self.centro[1], id=self.id_jugador)

    def _reaparecer(self, mundo) -> None:
        self.x, self.y = mundo.punto_reaparicion(self)
        self.vx = self.vy = 0.0
        self.salud = self.salud_max
        self._set_agachado(False)
        self.invulnerable = J["invulnerable"]

    # --- Serialización ----------------------------------------------------------------
    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Jugador":
        return cls(**d)
