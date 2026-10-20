"""Estado completo de una partida en un nivel y su función update(dt, acciones_por_jugador).

Aquí NO se dibuja nada: este módulo solo contiene datos y reglas. La escena de nivel
lee el estado para dibujarlo y consume `eventos` para sonidos, partículas y temblores.
Todo el estado es serializable (to_dict/from_dict) para el futuro modo en red.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Dict, List, Optional

import pygame

import settings
from core import director
from core.boss import Jefe, jefe_from_dict, jefe_to_dict
from core.bullet import Bala
from core.enemy import Sicario
from core.fisica import Geometria
from core.player import Jugador
from core.vehiculos import Vehiculo, vehiculo_from_dict, vehiculo_to_dict
from input_manager import EstadoAcciones
from levels import cargar_nivel

SIN_ACCIONES = EstadoAcciones()
MARGEN_BALAS = 24
CAMARA_ADELANTE = 100   # el jugador va a ~100 px del borde izquierdo


@dataclass
class PowerUp:
    x: float
    y: float
    tipo: str               # triple | rapida | vida
    vivo: bool = True
    cayendo: bool = False   # True: es un suministro que baja en paracaídas hasta tocar suelo

    @property
    def rect(self) -> pygame.Rect:
        return pygame.Rect(int(self.x), int(self.y), 12, 12)

    def update(self, dt: float, geometria: Geometria) -> None:
        if not self.cayendo:
            return
        self.y += settings.VEL_SUMINISTRO * dt
        fondo = pygame.Rect(int(self.x), int(self.y) + 12, 12, 3)
        if any(fondo.colliderect(r) for r in geometria.solidos + geometria.plataformas):
            self.cayendo = False
        elif self.y > settings.ALTO + 16:        # cayó a un precipicio
            self.vivo = False


@dataclass
class EstadoJuego:
    numero_nivel: int
    jugadores: List[Jugador] = field(default_factory=list)
    sicarios: List[Sicario] = field(default_factory=list)
    balas: List[Bala] = field(default_factory=list)
    powerups: List[PowerUp] = field(default_factory=list)
    vehiculos: List[Vehiculo] = field(default_factory=list)   # refuerzos aleatorios
    jefe: Optional[Jefe] = None
    camara_x: float = 0.0
    siguiente_enemigo: int = 0          # índice en la lista de apariciones del nivel
    semilla: Optional[int] = None       # None = sin apariciones aleatorias (pruebas de lógica)
    peligro: int = 0                    # refuerzos extra por el peligro de la ruta (core/mapa.py)
    siguiente_aleatorio: int = 0        # índice en el plan aleatorio
    arena_activa: bool = False
    tiempo: float = 0.0
    t_victoria: float = 0.0             # cuenta tras derrotar al jefe
    victoria: bool = False
    game_over: bool = False
    opinion: Dict[str, int] = field(default_factory=lambda: {"medios": 50, "influencers": 50, "pueblo": 50})
    eventos: List[dict] = field(default_factory=list)   # transitorios, no se serializan

    def __post_init__(self):
        self.datos = cargar_nivel(self.numero_nivel)          # datos estáticos del nivel
        self.geometria = Geometria(self.datos)
        self.arena_x = self.datos["largo"] - settings.ANCHO   # la arena es la última pantalla
        self._apariciones = sorted(self.datos["enemigos"], key=lambda e: e["x"])
        # Plan aleatorio del nivel: sale entero de la semilla, por eso no hace falta serializarlo
        self.plan = [] if self.semilla is None else \
            director.planear(self.numero_nivel, self.datos["largo"], self.semilla, self.peligro)

    # --- Creación ------------------------------------------------------------------
    @classmethod
    def nuevo(cls, numero_nivel: int, jugadores: List[Jugador], opinion: Dict[str, int] = None,
              en_arena: bool = False, semilla: Optional[int] = None, peligro: int = 0) -> "EstadoJuego":
        """Estado inicial del nivel. en_arena=True (desarrollo) pone al jugador frente al jefe.
        semilla: activa los refuerzos y suministros aleatorios (core/director.py)."""
        estado = cls(numero_nivel=numero_nivel, jugadores=jugadores, semilla=semilla, peligro=peligro)
        if opinion:
            estado.opinion = dict(opinion)
        inicio = estado.arena_x + 32 if en_arena else 32
        if en_arena:
            estado.camara_x = float(estado.arena_x)
        for i, j in enumerate(estado.jugadores):
            j.x = inicio + 14.0 * i
            j.y = estado.geometria.altura_suelo(j.x + j.ancho / 2) - j.alto
        estado.powerups = [PowerUp(p["x"], p["y"], p["tipo"]) for p in estado.datos.get("powerups", [])]
        return estado

    # --- Utilidades que usan las entidades ----------------------------------------------
    def evento(self, tipo: str, **datos) -> None:
        self.eventos.append(dict(tipo=tipo, **datos))

    def extraer_eventos(self) -> List[dict]:
        eventos, self.eventos = self.eventos, []
        return eventos

    def agregar_bala(self, bala: Bala) -> None:
        self.balas.append(bala)

    def jugadores_activos(self) -> List[Jugador]:
        return [j for j in self.jugadores if j.activo]

    def jugador_mas_cercano(self, x: float) -> Optional[Jugador]:
        activos = self.jugadores_activos()
        return min(activos, key=lambda j: abs(j.centro[0] - x)) if activos else None

    def en_pantalla(self, rect: pygame.Rect, margen: int = 0) -> bool:
        return rect.right > self.camara_x - margen and rect.left < self.camara_x + settings.ANCHO + margen

    def cantidad_sicarios(self) -> int:
        return len(self.sicarios)

    def factor_aviso(self) -> float:
        """Cuánto se alarga el aviso antes de que entre un refuerzo: con un PERIODISTA en pie,
        las emboscadas se anuncian con el doble de tiempo."""
        return max([j.stats_rol["aviso"] for j in self.jugadores_activos()] or [1.0])

    def jugador(self, id_jugador: int) -> Optional[Jugador]:
        for j in self.jugadores:
            if j.id_jugador == id_jugador:
                return j
        return None

    def invocar_sicario(self, x: float, direccion: int, pie: Optional[float] = None) -> None:
        """Crea un sicario con los pies en `pie` (o sobre el suelo de esa columna)."""
        s = Sicario(x=x, direccion=direccion)
        s.y = (pie if pie is not None else self.geometria.altura_suelo(x + 5)) - s.alto
        self.sicarios.append(s)

    def suelo_firme_cerca(self, x: float, alcance: int = 120):
        """Columna con suelo más cercana a x (primero hacia atrás, luego hacia adelante), para no
        hacer aparecer un sicario sobre un precipicio. None si no hay suelo cerca."""
        for distancia in range(0, alcance, 4):
            for candidato in (x - distancia, x + distancia):
                if self.geometria.altura_suelo(candidato + 5) <= settings.ALTO:
                    return candidato
        return None

    def punto_reaparicion(self, jugador: Jugador):
        """Reaparece cayendo desde arriba sobre la primera columna con suelo firme."""
        x = self.camara_x + 32
        while x < self.camara_x + settings.ANCHO - 16 and self.geometria.altura_suelo(x + 5) > settings.ALTO:
            x += 8
        return x, 0.0

    @property
    def puntaje_total(self) -> int:
        return sum(j.puntaje for j in self.jugadores)

    # --- Paso de simulación ------------------------------------------------------
    def update(self, dt: float, acciones: Dict[int, EstadoAcciones]) -> None:
        """Avanza la partida un paso fijo dt. acciones = {id_jugador: EstadoAcciones}."""
        if self.game_over:
            return
        self.tiempo += dt

        for j in self.jugadores:
            j.update(dt, acciones.get(j.id_jugador, SIN_ACCIONES), self)
        self._actualizar_camara(dt)
        self._limitar_jugadores()
        self._aparecer_enemigos()
        self._aparecer_aleatorios()

        for s in self.sicarios:
            s.update(dt, self)
        for v in self.vehiculos:
            v.update(dt, self)
        for p in self.powerups:
            p.update(dt, self.geometria)
        if self.jefe is not None and self.jefe.vivo:
            self.jefe.update(dt, self)
        for b in self.balas:
            b.update(dt)

        self._colisiones()
        self._limpiar()

        if self.jefe is not None and not self.jefe.vivo:
            self.t_victoria += dt
            if self.t_victoria >= 3.0:
                self.victoria = True
        if all(j.eliminado for j in self.jugadores):
            self.game_over = True
            self.evento("game_over")

    def _actualizar_camara(self, dt: float) -> None:
        """La cámara solo avanza (como en Super C) y se bloquea en la arena del jefe."""
        activos = self.jugadores_activos()
        if activos and not self.arena_activa:
            objetivo = max(j.x for j in activos) - CAMARA_ADELANTE
            self.camara_x = max(self.camara_x, min(objetivo, self.arena_x))
        if not self.arena_activa and self.camara_x >= self.arena_x:
            self._activar_arena()

    def _activar_arena(self) -> None:
        self.arena_activa = True
        self.camara_x = float(self.arena_x)
        tipo = self.datos["jefe"]
        stats = settings.JEFES[tipo]
        x = self.arena_x + settings.ANCHO - 48
        y = self.geometria.altura_suelo(x) - stats["alto"] - 40   # cae desde arriba
        self.jefe = Jefe.crear(tipo, x, y, self.arena_x, self.arena_x + settings.ANCHO)
        # Los sicarios que quedaban atrás se retiran: el duelo es contra el jefe.
        self.sicarios = [s for s in self.sicarios if s.x >= self.arena_x]
        self.vehiculos = []
        self.evento("arena", nombre=self.jefe.nombre)

    def _limitar_jugadores(self) -> None:
        """Muros de la cámara y muerte por caída al precipicio."""
        for j in self.jugadores_activos():
            izquierda = self.camara_x
            derecha = self.camara_x + settings.ANCHO - j.ancho
            j.x = max(izquierda, min(j.x, derecha))
            if j.y > settings.ALTO + 16:
                j.morir(self)

    def _aparecer_enemigos(self) -> None:
        """Crea los sicarios definidos en el nivel cuando la cámara llega a su posición."""
        borde = self.camara_x + settings.ANCHO
        while self.siguiente_enemigo < len(self._apariciones) and \
                self._apariciones[self.siguiente_enemigo]["x"] <= borde + 8:
            datos = self._apariciones[self.siguiente_enemigo]
            self.siguiente_enemigo += 1
            if self.arena_activa:
                continue
            if datos.get("lado") == "izquierda":       # aparece por detrás del jugador
                x = self.suelo_firme_cerca(self.camara_x - 10)
                if x is not None:
                    self.invocar_sicario(x, 1, datos.get("y"))
            else:
                self.invocar_sicario(datos["x"], -1, datos.get("y"))

    def _aparecer_aleatorios(self) -> None:
        """Refuerzos y suministros del plan aleatorio, cuando la cámara llega a su posición."""
        borde = self.camara_x + settings.ANCHO
        while self.siguiente_aleatorio < len(self.plan) and self.plan[self.siguiente_aleatorio]["x"] <= borde:
            a = self.plan[self.siguiente_aleatorio]
            self.siguiente_aleatorio += 1
            if self.arena_activa:
                continue
            if a["tipo"] == "suministro":
                x = self.suelo_firme_cerca(self.camara_x + settings.ANCHO - 70)
                if x is not None:
                    self.powerups.append(PowerUp(x, -14.0, a["clase"], cayendo=True))
                    self.evento("suministro", x=x)
            elif a["tipo"] == "dron":
                lado = 1 if a["x"] % 8 else -1                # entra por un lado u otro
                x = self.camara_x + (settings.ANCHO + 20 if lado > 0 else -40)
                self.vehiculos.append(Vehiculo.crear("dron", x, a["altura"], -lado, altura=a["altura"]))
                self.evento("aviso_vehiculo", clase="dron", lado=lado)
            else:
                self._aparecer_rodando(a)

    def _aparecer_rodando(self, a: dict) -> None:
        """Moto o camioneta: entra rodando por un borde, sobre suelo firme."""
        stats = settings.VEHICULOS[a["tipo"]]
        lado = -1 if a.get("lado") == "izquierda" else 1       # 1 = entra por la derecha
        borde = self.camara_x + settings.ANCHO + 24 if lado > 0 else self.camara_x - 24 - stats["caja"][0]
        x = self.suelo_firme_cerca(borde, 160)
        if x is None:
            return
        y = self.geometria.altura_suelo(x + stats["caja"][0] / 2) - stats["caja"][1]
        self.vehiculos.append(Vehiculo.crear(a["tipo"], x, y, -lado, vida=a.get("vida"),
                                             premio=a.get("premio", "")))
        self.evento("aviso_vehiculo", clase=a["tipo"], lado=lado)

    def _colisiones(self) -> None:
        for b in self.balas:
            if not b.vivo:
                continue
            rb = b.rect
            if b.del_jugador:
                for s in self.sicarios:
                    if s.vivo and rb.colliderect(s.rect):
                        s.vida -= 1
                        b.vivo = False
                        self._sumar_puntos(b.dueno, settings.SICARIO["puntos"])
                        self.evento("sicario_muere", x=s.centro[0], y=s.centro[1])
                        break
                for v in self.vehiculos:
                    if b.vivo and v.activo and rb.colliderect(v.rect):
                        b.vivo = False
                        v.recibir_dano(1, self)
                        self.evento("chispa", x=b.x, y=b.y)
                        if not v.vivo:
                            self._sumar_puntos(b.dueno, v.stats["puntos"])
                            if v.premio:                   # la camioneta suelta su carga
                                self.powerups.append(PowerUp(v.centro[0] - 6, v.y, v.premio, cayendo=True))
                if b.vivo and self.jefe is not None and self.jefe.vivo and rb.colliderect(self.jefe.rect):
                    b.vivo = False
                    self.jefe.recibir_dano(1, self)
                    self.evento("impacto_jefe", x=b.x, y=b.y)
                    if not self.jefe.vivo:
                        self._sumar_puntos(b.dueno, self.jefe.stats["puntos"])
                        self._jefe_derrotado()
            else:
                for j in self.jugadores_activos():
                    if rb.colliderect(j.rect) and j.invulnerable <= 0:
                        b.vivo = False
                        j.recibir_dano(b.dano, self)
                        break
            # Las balas normales chocan con el suelo; la onda de choque viaja sobre él.
            if b.vivo and b.tipo != "onda" and any(rb.colliderect(s) for s in self.geometria.solidos):
                b.vivo = False
                self.evento("chispa", x=b.x, y=b.y)

        # Contacto cuerpo a cuerpo y power-ups
        for j in self.jugadores_activos():
            rj = j.rect
            for s in self.sicarios:
                if s.vivo and rj.colliderect(s.rect):
                    j.recibir_dano(settings.SICARIO["dano_contacto"], self)
            for v in self.vehiculos:
                if v.activo and rj.colliderect(v.rect):
                    j.recibir_dano(v.stats["dano_contacto"], self)
            if self.jefe is not None and self.jefe.vivo and rj.colliderect(self.jefe.rect):
                j.recibir_dano(self.jefe.stats["dano_contacto"], self)
            for p in self.powerups:
                if p.vivo and rj.colliderect(p.rect):
                    p.vivo = False
                    self._aplicar_powerup(j, p)

    def _aplicar_powerup(self, j: Jugador, p: PowerUp) -> None:
        if p.tipo in ("triple", "rapida"):
            j.arma = p.tipo
        elif p.tipo == "vida":
            j.vidas += 1
        j.puntaje += settings.POWERUPS[p.tipo]["puntos"]
        self.evento("powerup", clase=p.tipo, x=p.x, y=p.y)

    def _jefe_derrotado(self) -> None:
        """Al caer el jefe: se limpian las balas enemigas y los sicarios huyen... al suelo."""
        for s in self.sicarios:
            if s.vivo:
                s.vida = 0
                self.evento("sicario_muere", x=s.centro[0], y=s.centro[1])
        for v in self.vehiculos:
            v.vida = 0
        for b in self.balas:
            if not b.del_jugador:
                b.vivo = False
        self.evento("temblor", fuerza=8)

    def _sumar_puntos(self, id_jugador: int, puntos: int) -> None:
        j = self.jugador(id_jugador)
        if j is not None:
            j.puntaje += int(puntos * j.stats_rol["puntos"])

    def _limpiar(self) -> None:
        izquierda = self.camara_x - MARGEN_BALAS
        derecha = self.camara_x + settings.ANCHO + MARGEN_BALAS
        self.balas = [b for b in self.balas if b.vivo and izquierda < b.x < derecha
                      and -MARGEN_BALAS < b.y < settings.ALTO + MARGEN_BALAS]
        self.sicarios = [s for s in self.sicarios if s.vivo and s.y < settings.ALTO + 32
                         and s.x > self.camara_x - 64 and s.x < self.camara_x + settings.ANCHO + 64]
        self.vehiculos = [v for v in self.vehiculos if v.vivo and v.y < settings.ALTO + 48
                          and self.camara_x - 140 < v.x < self.camara_x + settings.ANCHO + 200]
        self.powerups = [p for p in self.powerups if p.vivo]

    # --- Serialización -----------------------------------------------------------------
    def to_dict(self) -> dict:
        return {
            "numero_nivel": self.numero_nivel,
            "jugadores": [j.to_dict() for j in self.jugadores],
            "sicarios": [s.to_dict() for s in self.sicarios],
            "balas": [b.to_dict() for b in self.balas],
            "powerups": [asdict(p) for p in self.powerups],
            "vehiculos": [vehiculo_to_dict(v) for v in self.vehiculos],
            "jefe": jefe_to_dict(self.jefe),
            "camara_x": self.camara_x,
            "siguiente_enemigo": self.siguiente_enemigo,
            "semilla": self.semilla,
            "peligro": self.peligro,
            "siguiente_aleatorio": self.siguiente_aleatorio,
            "arena_activa": self.arena_activa,
            "tiempo": self.tiempo,
            "t_victoria": self.t_victoria,
            "victoria": self.victoria,
            "game_over": self.game_over,
            "opinion": dict(self.opinion),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "EstadoJuego":
        return cls(
            numero_nivel=d["numero_nivel"],
            jugadores=[Jugador.from_dict(j) for j in d["jugadores"]],
            sicarios=[Sicario.from_dict(s) for s in d["sicarios"]],
            balas=[Bala.from_dict(b) for b in d["balas"]],
            powerups=[PowerUp(**p) for p in d["powerups"]],
            vehiculos=[vehiculo_from_dict(v) for v in d.get("vehiculos", [])],
            jefe=jefe_from_dict(d["jefe"]),
            camara_x=d["camara_x"],
            siguiente_enemigo=d["siguiente_enemigo"],
            semilla=d.get("semilla"),
            peligro=d.get("peligro", 0),
            siguiente_aleatorio=d.get("siguiente_aleatorio", 0),
            arena_activa=d["arena_activa"],
            tiempo=d["tiempo"],
            t_victoria=d["t_victoria"],
            victoria=d["victoria"],
            game_over=d["game_over"],
            opinion=dict(d["opinion"]),
        )
