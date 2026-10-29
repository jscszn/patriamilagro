"""Fondos con parallax, decoración animada y terreno, generados por código desde los datos.

ambiente["capas"]       capas de parallax (montañas, colinas, árboles, edificios, cactus, lianas)
ambiente["decoracion"]  adornos según el nivel:
    astro        sol o luna fijos en el cielo
    nubes        nubes que se desplazan solas
    animales     aves | buitres | helicoptero
    particulas   luciernagas | rodadoras
    neones       carteles luminosos que parpadean en los edificios
    adornos      objetos sobre el suelo (pasto, flor, helecho, farol, hidrante, basurero,
                 roca, cactus_chico, craneo). Son solo decorado: no chocan con nada.
    rayos        haces de sol entre los árboles (selva)
    calor        el aire caliente ondula el horizonte (desierto)
    lluvia       llovizna con salpicaduras en la calle (ciudad)
ambiente["estilo"]      cómo se pinta el suelo: selva | ciudad | desierto (render/terreno.py)

Las capas lejanas se funden con el cielo (neblina en su base): así se lee la profundidad.
"""
from __future__ import annotations

import math

import numpy as np
import pygame

from render import paisajes, terreno
from render.texto import dibujar_texto
from render.ui import superficie_opaca

import settings

ANCHO_CAPA = 512   # cada capa se repite cada 512 píxeles


def _ruido(i: int) -> float:
    """Pseudoaleatorio determinista en [0, 1) (el mismo fondo siempre)."""
    return (math.sin(i * 12.9898) * 43758.5453) % 1.0


def _capa(tipo: str, color, base: int, alto: int) -> pygame.Surface:
    sup = pygame.Surface((ANCHO_CAPA, settings.ALTO), pygame.SRCALPHA)
    if tipo == "montanas":
        puntos = [(0, settings.ALTO)]
        for i in range(9):
            x = i * 64
            puntos += [(x, base), (x + 32, base - int(alto * (0.5 + _ruido(i) * 0.5)))]
        puntos += [(ANCHO_CAPA, base), (ANCHO_CAPA, settings.ALTO)]
        pygame.draw.polygon(sup, color, puntos)
    elif tipo == "colinas":
        puntos = [(0, settings.ALTO)]
        for x in range(0, ANCHO_CAPA + 1, 4):
            ang = x / ANCHO_CAPA * math.tau
            y = base - alto * (0.5 + 0.3 * math.sin(ang * 2) + 0.2 * math.sin(ang * 5))
            puntos.append((x, int(y)))
        puntos.append((ANCHO_CAPA, settings.ALTO))
        pygame.draw.polygon(sup, color, puntos)
    elif tipo == "arboles":
        oscuro = tuple(max(0, c - 12) for c in color)
        pygame.draw.rect(sup, oscuro, (0, base - 10, ANCHO_CAPA, settings.ALTO))
        for i in range(16):
            x = i * 32 + int(_ruido(i) * 16)
            h = int(alto * (0.6 + _ruido(i + 50) * 0.4))
            pygame.draw.rect(sup, oscuro, (x + 6, base - h + 10, 4, h))           # tronco
            for j in range(3):                                                    # copa
                r = 10 + int(_ruido(i * 3 + j) * 6)
                pygame.draw.circle(sup, color, (x + 8 + (j - 1) * 9, base - h + 8 + (j % 2) * 4), r)
            for k in range(-2, 3):                                                 # hojas de palma
                pygame.draw.line(sup, color, (x + 8, base - h + 6), (x + 8 + k * 9, base - h + 14 + abs(k) * 3), 2)
    elif tipo == "edificios":
        for i in range(12):
            x = i * 44 + int(_ruido(i) * 10)
            h = int(alto * (0.4 + _ruido(i + 7) * 0.6))
            pygame.draw.rect(sup, color, (x, base - h, 36, h + 40))
            luz = tuple(min(255, c + 60) for c in color)
            for wy in range(base - h + 6, base, 10):
                for wx in range(x + 4, x + 32, 8):
                    if _ruido(wx * 7 + wy) > 0.55:
                        pygame.draw.rect(sup, luz, (wx, wy, 4, 5))
    elif tipo == "lianas":
        # Lianas que cuelgan desde arriba, con hojas
        for i in range(14):
            x = i * 37 + int(_ruido(i + 90) * 20)
            largo = int(alto * (0.5 + _ruido(i + 91) * 0.5))
            for y in range(base, base + largo):
                dx = int(math.sin((y + i * 7) / 9) * 2)
                sup.set_at((x + dx, y), color)
                if (y + i) % 9 == 0:                                     # hojitas
                    pygame.draw.ellipse(sup, color, (x + dx - 3 + ((y // 9) % 2) * 4, y - 1, 4, 3))
    elif tipo == "cactus":
        pygame.draw.rect(sup, color, (0, base, ANCHO_CAPA, settings.ALTO))
        for i in range(10):
            x = i * 52 + int(_ruido(i) * 20)
            h = int(alto * (0.5 + _ruido(i + 3) * 0.5))
            pygame.draw.rect(sup, color, (x, base - h, 6, h))
            pygame.draw.rect(sup, color, (x - 6, base - h + 10, 6, 3))
            pygame.draw.rect(sup, color, (x - 6, base - h + 2, 3, 10))
            pygame.draw.rect(sup, color, (x + 6, base - h + 16, 6, 3))
            pygame.draw.rect(sup, color, (x + 9, base - h + 8, 3, 10))
    return sup


class Fondo:
    """Cielo + capas de parallax + terreno de un nivel."""

    def __init__(self, datos_nivel: dict):
        amb = datos_nivel["ambiente"]
        self.amb = amb
        # Cielo en degradado
        self.cielo = superficie_opaca((settings.ANCHO, settings.ALTO))
        arriba, abajo = amb["cielo"]
        for y in range(settings.ALTO):
            t = y / settings.ALTO
            color = [int(arriba[i] + (abajo[i] - arriba[i]) * t) for i in range(3)]
            pygame.draw.line(self.cielo, color, (0, y), (settings.ANCHO, y))
        # Paisaje pintado (render/paisajes.py) o, si el nivel no tiene, capas simples
        self.paisaje = paisajes.crear(amb)
        self.capas = [] if self.paisaje else \
            [(self._neblina(_capa(c["tipo"], c["color"], c["base"], c["alto"]), c), c["factor"])
             for c in amb.get("capas", [])]
        self.deco = amb.get("decoracion", {})
        self.nubes = self._capa_nubes(self.deco["nubes"]) if "nubes" in self.deco else None
        self.adornos = self._repartir_adornos(datos_nivel)
        self.suelo = datos_nivel["suelo"]
        self.datos = datos_nivel
        self._terreno = None                       # se pinta la primera vez que se dibuja
        self._terreno_de = None
        self.rayos = self._capa_rayos() if self.deco.get("rayos") else None
        if Fondo._luz is None:
            Fondo._luz = pygame.Surface((settings.ANCHO, settings.ALTO), pygame.SRCALPHA)

    def _color_cielo(self, y: float):
        arriba, abajo = self.amb["cielo"]
        t = max(0.0, min(1.0, y / settings.ALTO))
        return [arriba[i] + (abajo[i] - arriba[i]) * t for i in range(3)]

    def _neblina(self, capa: pygame.Surface, conf: dict) -> pygame.Surface:
        """Funde la capa con el color del cielo: un poco toda (más si está lejos) y mucho más
        cerca de su base, como neblina al pie de los cerros o de los edificios."""
        lejania = max(0.0, 1.0 - conf["factor"] / 0.6)            # 1 = la más lejana; 0 = la más cerca
        if lejania <= 0.02:
            return capa
        rgb = pygame.surfarray.pixels3d(capa)
        alfa = pygame.surfarray.pixels_alpha(capa)
        filas = np.arange(settings.ALTO, dtype=np.float32)
        cima = conf["base"] - conf["alto"]
        rampa = np.clip((filas - cima) / max(1, conf["base"] - cima), 0, 1) ** 1.6
        mezcla = np.clip(0.22 * lejania + 0.45 * lejania * rampa, 0, 0.75)    # por fila
        cielo = np.array([self._color_cielo(y) for y in range(settings.ALTO)], np.float32)   # (alto, 3)
        visible = alfa > 0
        nuevo = rgb * (1 - mezcla[None, :, None]) + cielo[None, :, :] * mezcla[None, :, None]
        rgb[visible] = nuevo[visible].astype(np.uint8)
        del rgb, alfa
        return capa

    def _capa_rayos(self) -> pygame.Surface:
        """Haces de luz diagonales que bajan entre las copas (se mueven poco con la cámara)."""
        sup = pygame.Surface((ANCHO_CAPA, settings.ALTO), pygame.SRCALPHA)
        for i in range(5):
            x = i * 104 + int(_ruido(i + 70) * 50)
            ancho = 10 + int(_ruido(i + 71) * 14)
            for k, alfa in ((0, 14), (3, 12), (6, 10)):
                pygame.draw.polygon(sup, (255, 250, 200, alfa), [(x + k, 40), (x + ancho - k, 40),
                                                                 (x + ancho + 60 - k, 200), (x + 60 + k, 200)])
        return sup

    # --- Preparación ---------------------------------------------------------------------
    @staticmethod
    def _capa_nubes(conf) -> pygame.Surface:
        """Nubes pixeladas (grupos de óvalos con base plana), en una franja que se repite."""
        sup = pygame.Surface((ANCHO_CAPA, 60), pygame.SRCALPHA)
        sombra = tuple(max(0, c - 40) for c in conf["color"])
        for i in range(5):
            x, y = i * 104 + int(_ruido(i + 30) * 40), 10 + int(_ruido(i + 31) * 30)
            ancho = 30 + int(_ruido(i + 32) * 26)
            for j in range(4):
                bx = x + j * ancho // 4
                pygame.draw.ellipse(sup, sombra, (bx, y + 2, ancho // 2, 12))
                pygame.draw.ellipse(sup, conf["color"], (bx, y - (j % 2) * 4, ancho // 2, 11))
            pygame.draw.rect(sup, sombra, (x + 2, y + 9, ancho, 3))
        return sup

    def _repartir_adornos(self, datos):
        """Objetos decorativos repartidos sobre cada tramo de suelo, siempre en el mismo lugar."""
        tipos = self.deco.get("adornos", [])
        if not tipos:
            return []
        adornos, i = [], 0
        for x0, x1, y in datos["suelo"]:
            x = x0 + 12
            while x < x1 - 12:
                adornos.append((x, y, tipos[i % len(tipos)] if _ruido(i + 3) > 0.25 else tipos[0]))
                x += 28 + int(_ruido(i + 7) * 60)
                i += 1
        return adornos

    def dibujar_fondo(self, sup: pygame.Surface, camara_x: float, tiempo: float = 0.0) -> None:
        if self.paisaje is not None:
            self.paisaje.dibujar(sup, camara_x, tiempo)
            animal = self.deco.get("animales")
            if animal:
                {"aves": self._aves, "buitres": self._buitres, "helicoptero": self._helicoptero}[animal](sup, tiempo)
            if self.rayos is not None:
                self.rayos.set_alpha(int(170 + 50 * math.sin(tiempo * 0.6)))
                d = -int(camara_x * 0.25) % ANCHO_CAPA
                sup.blit(self.rayos, (d - ANCHO_CAPA, 0))
                sup.blit(self.rayos, (d, 0))
            self._clima(sup, camara_x, tiempo)
            return
        sup.blit(self.cielo, (0, 0))
        if "astro" in self.deco:
            self._astro(sup, self.deco["astro"])
        if self.nubes is not None:
            conf = self.deco["nubes"]
            desplazamiento = -int(camara_x * 0.08 + tiempo * conf.get("velocidad", 5)) % ANCHO_CAPA
            for x in (desplazamiento - ANCHO_CAPA, desplazamiento):
                sup.blit(self.nubes, (x, conf.get("y", 40)))
        animal = self.deco.get("animales")
        for n, (imagen, factor) in enumerate(self.capas):
            if n == 1 and animal:                    # los animales vuelan entre las capas lejanas
                {"aves": self._aves, "buitres": self._buitres, "helicoptero": self._helicoptero}[animal](sup, tiempo)
            desplazamiento = -int(camara_x * factor) % ANCHO_CAPA
            sup.blit(imagen, (desplazamiento - ANCHO_CAPA, 0))
            sup.blit(imagen, (desplazamiento, 0))
            if n == 1 and "neones" in self.deco:     # carteles sobre los edificios del medio
                self._neones(sup, camara_x * factor, tiempo)
            if n == 1 and self.rayos is not None:    # haces de sol, delante de la capa del medio
                self.rayos.set_alpha(int(200 + 55 * math.sin(tiempo * 0.6)))
                d = -int(camara_x * 0.25) % ANCHO_CAPA
                sup.blit(self.rayos, (d - ANCHO_CAPA, 0))
                sup.blit(self.rayos, (d, 0))
        self._clima(sup, camara_x, tiempo)

    def _clima(self, sup, camara_x, tiempo):
        if self.deco.get("calor"):
            self._calor(sup, tiempo)
        if self.deco.get("lluvia"):
            self._lluvia(sup, camara_x, tiempo)

    @staticmethod
    def _calor(sup, tiempo):
        """Ondulación del aire caliente: las filas del horizonte se corren 1 px y vuelven."""
        zona = pygame.Rect(0, 120, settings.ANCHO, 72)
        copia = sup.subsurface(zona).copy()
        for fila in range(0, zona.h, 2):
            dx = int(round(math.sin(tiempo * 2.6 + fila * 0.45) * 1.2 * (fila / zona.h)))
            if dx:
                sup.blit(copia, (dx, zona.y + fila), pygame.Rect(0, fila, zona.w, 2))

    def _lluvia(self, sup, camara_x, tiempo):
        """Llovizna: gotas en diagonal y salpicaduras de 1 px en la calle."""
        color = (120, 132, 176)
        for i in range(26):
            vel = 150 + _ruido(i + 200) * 60
            x = int((_ruido(i + 201) * 300 - camara_x * 0.5 - tiempo * 40) % 300) - 20
            y = int((_ruido(i + 202) * 230 + tiempo * vel) % 230) - 6
            pygame.draw.line(sup, color, (x, y), (x - 1, y + 3))
        for i in range(8):
            fase = (tiempo * 3 + _ruido(i + 220)) % 1.0
            if fase < 0.25:
                x = int((_ruido(i + 221 + int(tiempo * 3)) * 256))
                altura = self._altura_suelo(x + camara_x)
                if altura is not None:
                    sup.set_at((x - 1, int(altura) - 1), color)
                    sup.set_at((x + 1, int(altura) - 1), color)
                    sup.set_at((x, int(altura) - 2), (190, 205, 235))

    # --- Decoración animada ------------------------------------------------------------------
    @staticmethod
    def _astro(sup, conf):
        x, y, r, color = conf["x"], conf["y"], conf["radio"], conf["color"]
        clave = (r, tuple(color))
        if clave not in _HALOS_ASTRO:
            halo = pygame.Surface((r * 4, r * 4), pygame.SRCALPHA)
            for radio, alfa in ((1.95, 22), (1.6, 34), (1.3, 40)):
                pygame.draw.circle(halo, (*color, alfa), (r * 2, r * 2), int(r * radio))
            _HALOS_ASTRO[clave] = halo
        sup.blit(_HALOS_ASTRO[clave], (x - r * 2, y - r * 2))
        pygame.draw.circle(sup, color, (x, y), r)
        if conf["tipo"] == "sol":                   # franjas horizontales del atardecer
            for i, fy in enumerate(range(y + 4, y + r, 6)):
                pygame.draw.rect(sup, tuple(max(0, c - 70) for c in color), (x - r, fy, r * 2, 1 + i // 2))
        else:                                       # cráteres de la luna
            sombra = tuple(max(0, c - 40) for c in color)
            for cx, cy, cr in ((-4, -3, 3), (3, 2, 2), (-1, 5, 2)):
                pygame.draw.circle(sup, sombra, (x + cx, y + cy), cr)

    @staticmethod
    def _aves(sup, tiempo):
        """Bandada en V que cruza el cielo batiendo las alas."""
        base = (tiempo * 22) % (256 + 120) - 60
        for i in range(5):
            x = int(base - abs(i - 2) * 9)
            y = int(60 + abs(i - 2) * 5 + math.sin(tiempo * 2 + i) * 2)        # forma de V
            ala = 2 if int(tiempo * 6 + i) % 2 else -1
            pygame.draw.line(sup, (30, 40, 40), (x - 3, y + ala), (x, y), 1)
            pygame.draw.line(sup, (30, 40, 40), (x, y), (x + 3, y + ala), 1)

    @staticmethod
    def _buitres(sup, tiempo):
        """Buitres que giran en círculos sobre el desierto."""
        for i in range(3):
            ang = tiempo * 0.8 + i * math.tau / 3
            x = int(170 + math.cos(ang) * (28 + i * 6))
            y = int(62 + math.sin(ang) * 10)
            ala = 2 if int(tiempo * 3 + i) % 2 else 0
            pygame.draw.line(sup, (60, 30, 30), (x - 5, y + ala), (x, y), 2)
            pygame.draw.line(sup, (60, 30, 30), (x, y), (x + 5, y + ala), 2)

    _luz = None                                   # superficie del reflector (se reutiliza)

    @staticmethod
    def _helicoptero(sup, tiempo):
        """Helicóptero lejano con reflector que barre la ciudad."""
        x = int(300 - (tiempo * 14) % 420)
        y = 58 + int(math.sin(tiempo) * 3)
        luz = Fondo._luz
        luz.fill((0, 0, 0, 0))
        barrido = math.sin(tiempo * 0.7) * 30
        pygame.draw.polygon(luz, (255, 255, 200, 40), [(x, y + 3), (x + barrido - 18, 200), (x + barrido + 18, 200)])
        sup.blit(luz, (0, 0))
        pygame.draw.ellipse(sup, (20, 20, 30), (x - 6, y - 2, 12, 6))
        pygame.draw.line(sup, (20, 20, 30), (x + 5, y), (x + 13, y - 1))
        if int(tiempo * 8) % 2:
            pygame.draw.line(sup, (40, 40, 50), (x - 9, y - 4), (x + 9, y - 4))
        if int(tiempo * 2) % 2:
            sup.set_at((x + 13, y - 1), (255, 40, 40))

    @staticmethod
    def _neones(sup, desplazamiento_capa, tiempo):
        """Carteles luminosos que parpadean (en la capa de edificios del medio)."""
        textos = [("BAR", (255, 60, 180)), ("24H", (60, 255, 220)), ("HOTEL", (255, 220, 60)),
                  ("TACOS", (120, 255, 80)), ("RADIO", (255, 120, 60))]
        for i, (texto, color) in enumerate(textos):
            x = int(i * 104 + 30 - desplazamiento_capa) % ANCHO_CAPA - 40
            if not -40 < x < 256:
                continue
            y = 112 + int(_ruido(i + 60) * 30)
            encendido = (int(tiempo * 3 + i * 1.7) % 7) != 0          # se apaga a ratos
            ancho = len(texto) * 6 + 4
            pygame.draw.rect(sup, (20, 16, 30), (x, y, ancho, 11))
            pygame.draw.rect(sup, color if encendido else (60, 50, 70), (x, y, ancho, 11), 1)
            if encendido:
                dibujar_texto(sup, texto, (x + 3, y), color, sombra=False)

    def dibujar_adornos(self, sup: pygame.Surface, camara_x: float, tiempo: float) -> None:
        """Objetos del suelo, partículas y rodadoras. Van delante del terreno y detrás de los
        personajes. (En alto contraste no se dibujan, para no distraer.)"""
        cam = int(camara_x)
        for x, y, tipo in self.adornos:
            sx = x - cam
            if -20 < sx < 276:
                _ADORNOS[tipo](sup, sx, y, tiempo + x)
        particulas = self.deco.get("particulas")
        if particulas == "luciernagas":
            for i in range(14):
                px = int((_ruido(i + 40) * 300 - camara_x * 0.9 + math.sin(tiempo * 0.7 + i) * 12) % 290) - 17
                py = int(120 + _ruido(i + 41) * 60 + math.sin(tiempo * 1.3 + i * 2) * 6)
                if int(tiempo * 2 + i) % 3:
                    sup.blit(_HALO_LUCIERNAGA, (px - 2, py - 2), special_flags=pygame.BLEND_RGB_ADD)
                    sup.set_at((px, py), (240, 255, 160))
        elif particulas == "rodadoras":
            for i in range(2):
                sx = int(300 - (tiempo * (38 + i * 12) + i * 170) % 360)
                altura = self._altura_suelo(sx + cam)
                if altura is None:
                    continue
                salto = abs(math.sin(tiempo * 4 + i)) * 6
                _rodadora(sup, sx, altura - 6 - int(salto), tiempo * 6 + i)

    def _altura_suelo(self, x: float):
        for x0, x1, y in self.suelo:
            if x0 <= x < x1:
                return y
        return None

    def dibujar_terreno(self, sup: pygame.Surface, geometria, camara_x: float, alto_contraste: bool = False) -> None:
        """Suelo, bloques y plataformas: un recorte del terreno pintado al cargar el nivel
        (render/terreno.py). En alto contraste, además, una línea blanca sobre cada borde."""
        cam = int(camara_x)
        # Fondo de los precipicios: oscuro, para que se lean como peligro
        for i, y in enumerate(range(194, settings.ALTO, 3)):
            pygame.draw.rect(sup, (max(0, 22 - i * 3), max(0, 26 - i * 3), max(0, 24 - i * 3)), (0, y, settings.ANCHO, 3))
        if self._terreno is None or self._terreno_de is not geometria:
            self._terreno = terreno.pintar(self.datos, geometria)
            if pygame.display.get_surface() is not None:          # blit más rápido en cada cuadro
                self._terreno = self._terreno.convert_alpha()
            self._terreno_de = geometria
        sup.blit(self._terreno, (0, 0), pygame.Rect(cam, 0, settings.ANCHO, settings.ALTO))
        if alto_contraste:
            self._bordes_contraste(sup, geometria, cam)

    @staticmethod
    def _bordes_contraste(sup, geometria, cam: int) -> None:
        vista = pygame.Rect(cam, 0, settings.ANCHO, settings.ALTO)
        for r in list(geometria.solidos) + list(geometria.plataformas):
            if r.colliderect(vista):
                pygame.draw.line(sup, (255, 255, 255), (r.left - cam, r.top), (r.right - 1 - cam, r.top))


# =============================================================================
# Adornos del suelo (pixel art con primitivas). (x, y) = punto de apoyo sobre el suelo.
# =============================================================================
def _pasto(sup, x, y, t):
    for i, (dx, alto) in enumerate(((-2, 4), (0, 6), (2, 5), (4, 3))):
        mecer = int(math.sin(t * 2 + i) * 1)
        pygame.draw.line(sup, (40, 140, 40) if i % 2 else (90, 190, 60), (x + dx, y), (x + dx + mecer, y - alto))


def _flor(sup, x, y, t):
    colores = [(230, 60, 60), (250, 210, 60), (200, 90, 220)]
    color = colores[int(abs(x)) % 3]
    pygame.draw.line(sup, (40, 130, 40), (x, y), (x, y - 6))
    pygame.draw.rect(sup, color, (x - 1, y - 8, 3, 3))
    sup.set_at((x, y - 7), (255, 255, 200))


def _helecho(sup, x, y, t):
    for i in range(-3, 4):
        pygame.draw.line(sup, (30, 110, 50), (x, y), (x + i * 2, y - 7 + abs(i)))


def _farol(sup, x, y, t):
    # Haz de luz en degradado: varios conos superpuestos, más intensos cerca de la lámpara
    luz = pygame.Surface((34, 34), pygame.SRCALPHA)
    for ancho, alfa in ((16, 18), (11, 22), (6, 30)):
        pygame.draw.polygon(luz, (255, 214, 110, alfa), [(22, 2), (22 - ancho, 33), (22 + ancho, 33)])
    pygame.draw.ellipse(luz, (255, 220, 120, 50), (8, 29, 28, 5))          # charco de luz en el suelo
    sup.blit(luz, (x - 17, y - 34))
    pygame.draw.line(sup, (60, 60, 70), (x, y), (x, y - 34), 2)
    pygame.draw.line(sup, (60, 60, 70), (x, y - 34), (x + 5, y - 34), 2)
    pygame.draw.rect(sup, (255, 240, 180), (x + 3, y - 33, 5, 2))


def _hidrante(sup, x, y, t):
    pygame.draw.rect(sup, (200, 40, 40), (x - 2, y - 7, 5, 7))
    pygame.draw.rect(sup, (230, 70, 70), (x - 3, y - 5, 7, 2))
    pygame.draw.rect(sup, (150, 30, 30), (x - 1, y - 9, 3, 2))


def _basurero(sup, x, y, t):
    pygame.draw.rect(sup, (90, 100, 90), (x - 3, y - 8, 7, 8))
    pygame.draw.rect(sup, (120, 130, 120), (x - 4, y - 9, 9, 2))
    pygame.draw.line(sup, (60, 70, 60), (x - 1, y - 6), (x - 1, y - 1))
    pygame.draw.line(sup, (60, 70, 60), (x + 1, y - 6), (x + 1, y - 1))


def _roca(sup, x, y, t):
    pygame.draw.ellipse(sup, (120, 100, 80), (x - 4, y - 4, 9, 5))
    pygame.draw.ellipse(sup, (160, 140, 110), (x - 3, y - 4, 4, 2))


def _cactus_chico(sup, x, y, t):
    pygame.draw.rect(sup, (60, 120, 60), (x - 1, y - 10, 3, 10))
    pygame.draw.rect(sup, (60, 120, 60), (x - 4, y - 7, 3, 2))
    pygame.draw.rect(sup, (60, 120, 60), (x - 4, y - 9, 2, 3))
    pygame.draw.rect(sup, (60, 120, 60), (x + 2, y - 5, 3, 2))
    pygame.draw.rect(sup, (60, 120, 60), (x + 3, y - 7, 2, 3))


def _craneo(sup, x, y, t):
    pygame.draw.rect(sup, (235, 225, 200), (x - 3, y - 3, 6, 3))
    pygame.draw.line(sup, (235, 225, 200), (x - 5, y - 4), (x - 3, y - 3))
    pygame.draw.line(sup, (235, 225, 200), (x + 4, y - 4), (x + 2, y - 3))
    sup.set_at((x - 1, y - 2), (60, 40, 30))
    sup.set_at((x + 1, y - 2), (60, 40, 30))


def _rodadora(sup, x, y, giro):
    color = (150, 110, 60)
    pygame.draw.circle(sup, color, (x, y), 6, 1)
    for i in range(4):
        ang = giro + i * math.pi / 4
        dx, dy = math.cos(ang) * 5, math.sin(ang) * 5
        pygame.draw.line(sup, color, (x - dx, y - dy), (x + dx, y + dy))


_HALOS_ASTRO = {}
_HALO_LUCIERNAGA = pygame.Surface((5, 5), pygame.SRCALPHA)
pygame.draw.circle(_HALO_LUCIERNAGA, (60, 80, 20, 255), (2, 2), 2)
_HALO_LUCIERNAGA.set_at((2, 2), (110, 140, 40))

_ADORNOS = {"pasto": _pasto, "flor": _flor, "helecho": _helecho, "farol": _farol, "hidrante": _hidrante,
            "basurero": _basurero, "roca": _roca, "cactus_chico": _cactus_chico, "craneo": _craneo}
