"""Efectos visuales de los niveles: explosiones, humo, casquillos, polvo, cuerpos que salen
despedidos, puntos que flotan y sombras en el suelo.

Son solo dibujo: nada de aquí cambia la lógica del juego. La escena de nivel los crea a partir
de los eventos del estado (core.game_state) y los avanza con su propio reloj. Todo el azar sale
de un random.Random de la escena, así que tampoco toca la semilla de la partida.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import pygame

import settings
from render.texto import dibujar_texto

C = settings.COLORES

# Rampa de la bola de fuego: de blanco a humo (por fracción de vida)
RAMPA_FUEGO = [(0.10, (255, 255, 240)), (0.25, (255, 236, 120)), (0.45, (252, 168, 48)),
               (0.62, (216, 72, 24)), (0.78, (110, 52, 40)), (1.01, (70, 62, 66))]
MAX_CASQUILLOS = 40
MAX_PARTICULAS = 500


def _color_fuego(p: float):
    for limite, color in RAMPA_FUEGO:
        if p < limite:
            return color
    return RAMPA_FUEGO[-1][1]


def _aclarar(color, k: int = 50):
    return tuple(min(255, c + k) for c in color)


@dataclass
class Particula:
    x: float
    y: float
    vx: float
    vy: float
    vida: float
    color: tuple
    tam: int = 2
    gravedad: float = 0.0
    edad: float = 0.0


@dataclass
class Bola:
    """Una bola de la explosión: crece, cambia de color y termina como humo que sube."""
    x: float
    y: float
    radio: float
    vida: float
    retraso: float = 0.0
    edad: float = 0.0
    sube: float = 18.0


@dataclass
class Casquillo:
    x: float
    y: float
    vx: float
    vy: float
    suelo: float
    vida: float = 1.4
    rebotes: int = 0


@dataclass
class Cuerpo:
    """Enemigo abatido: sale despedido hacia arriba y atrás, parpadea y cae fuera del suelo."""
    imagen: pygame.Surface
    blanca: pygame.Surface
    x: float
    y: float
    vx: float
    vy: float
    edad: float = 0.0
    giro: float = 0.0


@dataclass
class Flotante:
    x: float
    y: float
    texto: str
    color: tuple
    edad: float = 0.0


@dataclass
class Anillo:
    x: float
    y: float
    radio: float
    vida: float
    color: tuple
    edad: float = 0.0


class Efectos:
    def __init__(self, rng: Optional[random.Random] = None):
        self.rng = rng or random.Random(0)
        self.particulas: List[Particula] = []
        self.bolas: List[Bola] = []
        self.casquillos: List[Casquillo] = []
        self.cuerpos: List[Cuerpo] = []
        self.flotantes: List[Flotante] = []
        self.anillos: List[Anillo] = []
        self.destellos: List[list] = []               # [x, y, radio, segundos]: luz breve del estallido
        self._halos: Dict[Tuple[int, tuple], pygame.Surface] = {}

    # --- Creación --------------------------------------------------------------------------
    def chispas(self, x, y, cantidad, colores, velocidad=90.0, gravedad=200.0, vida=(0.25, 0.6)):
        r = self.rng
        for _ in range(cantidad):
            ang = r.uniform(0, math.tau)
            v = r.uniform(0.3, 1.0) * velocidad
            self.particulas.append(Particula(x, y, math.cos(ang) * v, math.sin(ang) * v - 20,
                                             r.uniform(*vida), r.choice(colores), r.choice((1, 2, 2, 3)), gravedad))

    def explosion(self, x: float, y: float, tam: float = 1.0) -> None:
        """Bola de fuego con núcleo blanco, humo que sube, escombros y onda expansiva.
        tam: 1 = sicario o dron; 2 = camioneta; 3 = jefe."""
        r = self.rng
        n = int(3 + 3 * tam)
        for i in range(n):
            dist = 0 if i == 0 else r.uniform(2, 7) * tam
            ang = r.uniform(0, math.tau)
            self.bolas.append(Bola(x + math.cos(ang) * dist, y + math.sin(ang) * dist * 0.7,
                                   r.uniform(4, 7) * (0.7 + 0.3 * tam) * (1.3 if i == 0 else 1.0),
                                   r.uniform(0.35, 0.6) * (0.8 + 0.2 * tam), retraso=i * 0.025 * r.uniform(0.5, 1.5)))
        self.chispas(x, y, int(6 + 6 * tam), [C["amarillo"], C["naranja"], (255, 255, 220)],
                     velocidad=80 + 30 * tam, gravedad=260)
        self.chispas(x, y, int(3 * tam), [(60, 50, 50), (90, 80, 70)], velocidad=70 + 20 * tam,
                     gravedad=380, vida=(0.5, 0.9))                       # escombros oscuros
        self.anillos.append(Anillo(x, y, 10 + 8 * tam, 0.22 + 0.05 * tam, (255, 230, 170)))
        self.destellos.append([x, y, 18 + 10 * tam, 0.09])

    def humo(self, x: float, y: float, radio: float = 2.5) -> None:
        """Bocanada de humo gris (escape de la moto, camioneta herida): una bola que nace ya
        en la parte de humo de la rampa."""
        self.bolas.append(Bola(x, y, radio, 0.5, edad=0.62 * 0.5, sube=14))

    def impacto(self, x: float, y: float, color=None) -> None:
        """Bala que pega: chispas cortas y un aro pequeño."""
        self.chispas(x, y, 3, [color or C["amarillo"], C["blanco"]], velocidad=60, gravedad=150, vida=(0.1, 0.25))
        self.anillos.append(Anillo(x, y, 5, 0.1, (255, 255, 220)))

    def casquillo(self, x: float, y: float, mirando: int, suelo: float) -> None:
        r = self.rng
        if len(self.casquillos) >= MAX_CASQUILLOS:
            self.casquillos.pop(0)
        self.casquillos.append(Casquillo(x, y, -mirando * r.uniform(30, 70), -r.uniform(70, 120), suelo))

    def polvo(self, x: float, y: float, cantidad: int = 5, color=(170, 150, 120), hacia: int = 0) -> None:
        """Nube baja de polvo (al saltar, caer o derrapar). hacia: -1/1 para empujarla de lado."""
        r = self.rng
        for i in range(cantidad):
            lado = hacia or (1 if i % 2 else -1)
            self.particulas.append(Particula(x + r.uniform(-3, 3), y - 1, lado * r.uniform(15, 45),
                                             -r.uniform(5, 20), r.uniform(0.25, 0.45), color,
                                             r.choice((1, 2, 2)), -10.0))

    def cuerpo(self, imagen: pygame.Surface, blanca: pygame.Surface, x: float, y: float, golpe: int) -> None:
        """x, y: esquina superior izquierda del sprite en el mundo. golpe: hacia dónde lo empuja la bala."""
        self.cuerpos.append(Cuerpo(imagen, blanca, x, y, golpe * self.rng.uniform(50, 75), -self.rng.uniform(120, 150)))

    def flotante(self, x: float, y: float, texto: str, color=None) -> None:
        self.flotantes.append(Flotante(x, y, texto, color or C["blanco"]))

    # --- Avance ------------------------------------------------------------------------------
    def update(self, dt: float) -> None:
        for p in self.particulas:
            p.x += p.vx * dt
            p.y += p.vy * dt
            p.vy += p.gravedad * dt
            p.vida -= dt
            p.edad += dt
        self.particulas = [p for p in self.particulas if p.vida > 0][-MAX_PARTICULAS:]
        for b in self.bolas:
            b.edad += dt
            if b.edad > b.retraso:
                b.y -= b.sube * dt * max(0.0, (b.edad - b.retraso) / b.vida)
        self.bolas = [b for b in self.bolas if b.edad - b.retraso < b.vida]
        for c in self.casquillos:
            c.vida -= dt
            if c.rebotes < 2:
                c.vy += 520 * dt
                c.x += c.vx * dt
                c.y += c.vy * dt
                if c.y >= c.suelo and c.vy > 0:              # rebota una vez y se queda quieto
                    c.y = c.suelo
                    c.vy *= -0.35
                    c.vx *= 0.5
                    c.rebotes += 1
        self.casquillos = [c for c in self.casquillos if c.vida > 0]
        for c in self.cuerpos:
            c.edad += dt
            c.x += c.vx * dt
            c.y += c.vy * dt
            c.vy += 430 * dt
        self.cuerpos = [c for c in self.cuerpos if c.edad < 0.9]
        for f in self.flotantes:
            f.edad += dt
        self.flotantes = [f for f in self.flotantes if f.edad < 0.8]
        for a in self.anillos:
            a.edad += dt
        self.anillos = [a for a in self.anillos if a.edad < a.vida]
        for d in self.destellos:
            d[3] -= dt
        self.destellos = [d for d in self.destellos if d[3] > 0]

    # --- Dibujo ------------------------------------------------------------------------------
    def halo(self, radio: int, color, intensidad: int = 70) -> pygame.Surface:
        """Círculo de luz para sumar con BLEND_RGB_ADD (con caché). Los colores van ya
        multiplicados por la intensidad: el negro no suma nada, así que no hace falta alfa."""
        clave = (radio, tuple(color) + (intensidad,))
        if clave not in self._halos:
            sup = pygame.Surface((radio * 2 + 1, radio * 2 + 1))
            sup.fill((0, 0, 0))
            for r, k in ((radio, 0.5), (max(1, int(radio * 0.6)), 1.0)):
                pygame.draw.circle(sup, tuple(int(c * intensidad / 255 * k) for c in color), (radio, radio), r)
            self._halos[clave] = sup
        return self._halos[clave]

    def dibujar_detras(self, sup: pygame.Surface, cam: float) -> None:
        """Casquillos en el suelo (detrás de los personajes)."""
        for c in self.casquillos:
            if c.vida < 0.3 and int(c.vida * 20) % 2:
                continue
            x, y = int(c.x - cam), int(c.y)
            color = (232, 188, 72) if c.rebotes == 0 or int(c.vida * 6) % 2 else (180, 130, 50)
            sup.fill(color, (x, y - 1, 2, 1))
            sup.set_at((x, y - 2), (255, 236, 150))

    def dibujar(self, sup: pygame.Surface, cam: float) -> None:
        for x, y, radio, t in self.destellos:
            sup.blit(self.halo(int(radio), (255, 220, 150), 90), (int(x - cam - radio), int(y - radio)),
                     special_flags=pygame.BLEND_RGB_ADD)
        for c in self.cuerpos:
            # Gira en el aire de a 90° (pixel art: sin rotaciones raras) y parpadea al final
            if c.edad > 0.55 and int(c.edad * 20) % 2:
                continue
            imagen = c.blanca if c.edad < 0.08 else c.imagen
            pasos = int(c.edad / 0.18) % 4 if c.edad > 0.25 else 0
            if pasos:
                imagen = pygame.transform.rotate(imagen, -90 * pasos * (1 if c.vx > 0 else -1))
            sup.blit(imagen, (int(c.x - cam), int(c.y)))
        for b in self.bolas:
            edad = b.edad - b.retraso
            if edad < 0:
                continue
            p = edad / b.vida
            crece = 1 - (1 - min(1.0, p * 2.2)) ** 2
            radio = b.radio * (0.45 + 0.55 * crece) * (1.0 if p < 0.7 else 1.0 - (p - 0.7) * 1.2)
            if radio < 1:
                continue
            x, y = int(b.x - cam), int(b.y)
            color = _color_fuego(p)
            pygame.draw.circle(sup, color, (x, y), int(radio))
            if p < 0.6:                                        # núcleo más claro, corrido hacia arriba
                pygame.draw.circle(sup, _aclarar(color, 45), (x - 1, y - 1), max(1, int(radio * 0.55)))
            elif p < 0.9:                                      # sombra del humo abajo
                pygame.draw.circle(sup, tuple(max(0, k - 18) for k in color), (x + 1, y + 1),
                                   max(1, int(radio * 0.6)))
        for a in self.anillos:
            p = a.edad / a.vida
            pygame.draw.circle(sup, a.color, (int(a.x - cam), int(a.y)), max(1, int(a.radio * (0.3 + 0.7 * p))), 1)
        for p in self.particulas:
            color = p.color
            if p.vida < 0.12 and p.tam > 1:                     # se apagan al final
                color = tuple(max(0, k - 70) for k in color)
            sup.fill(color, (int(p.x - cam), int(p.y), p.tam, p.tam))
        for f in self.flotantes:
            if f.edad > 0.6 and int(f.edad * 20) % 2:
                continue
            subida = int(min(1.0, f.edad / 0.4) * 12)
            dibujar_texto(sup, f.texto, (int(f.x - cam), int(f.y) - subida), f.color, centrado=True)


# --- Sombras en el suelo ----------------------------------------------------------------------
_sombras: Dict[int, pygame.Surface] = {}


def sombra(ancho: int) -> pygame.Surface:
    """Elipse oscura y semitransparente para poner bajo los pies (con caché por ancho)."""
    ancho = max(4, ancho)
    if ancho not in _sombras:
        alto = max(3, ancho // 5)
        sup = pygame.Surface((ancho, alto), pygame.SRCALPHA)
        pygame.draw.ellipse(sup, (0, 0, 0, 55), (0, 0, ancho, alto))
        pygame.draw.ellipse(sup, (0, 0, 0, 70), (ancho // 4, 1, ancho // 2, max(1, alto - 2)))
        _sombras[ancho] = sup
    return _sombras[ancho]


def suelo_debajo(geometria, x: float, desde_y: float) -> Optional[float]:
    """Altura del primer suelo o plataforma bajo el punto (x, desde_y), o None si hay vacío."""
    mejor = None
    for r in list(geometria.solidos) + list(geometria.plataformas):
        if r.left <= x < r.right and r.top >= desde_y - 2:
            if mejor is None or r.top < mejor:
                mejor = r.top
    return mejor


def dibujar_sombra(sup: pygame.Surface, geometria, centro_x: float, pie: float, ancho: int, cam: float) -> None:
    """Sombra que se achica y aclara cuando el cuerpo está en el aire."""
    suelo = suelo_debajo(geometria, centro_x, pie)
    if suelo is None:
        return
    altura = suelo - pie
    if altura > 90:
        return
    w = int(ancho * (1 - min(0.6, altura / 120)))
    imagen = sombra(w)
    sup.blit(imagen, (int(centro_x - cam - w / 2), int(suelo - imagen.get_height() // 2 - 1)))
