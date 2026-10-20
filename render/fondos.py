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
"""
from __future__ import annotations

import math

import pygame

from render.texto import dibujar_texto

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
        self.cielo = pygame.Surface((settings.ANCHO, settings.ALTO))
        arriba, abajo = amb["cielo"]
        for y in range(settings.ALTO):
            t = y / settings.ALTO
            color = [int(arriba[i] + (abajo[i] - arriba[i]) * t) for i in range(3)]
            pygame.draw.line(self.cielo, color, (0, y), (settings.ANCHO, y))
        self.capas = [(_capa(c["tipo"], c["color"], c["base"], c["alto"]), c["factor"]) for c in amb["capas"]]
        self.baldosa = self._baldosa()
        self.deco = amb.get("decoracion", {})
        self.nubes = self._capa_nubes(self.deco["nubes"]) if "nubes" in self.deco else None
        self.adornos = self._repartir_adornos(datos_nivel)
        self.suelo = datos_nivel["suelo"]

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

    def _baldosa(self) -> pygame.Surface:
        """Baldosa de 16x16 para rellenar el suelo."""
        sup = pygame.Surface((16, 16))
        sup.fill(self.amb["suelo"])
        for i in range(6):
            x, y = int(_ruido(i) * 15), int(_ruido(i + 20) * 15)
            sup.fill(self.amb["suelo_detalle"], (x, y, 2, 2))
        return sup

    def dibujar_fondo(self, sup: pygame.Surface, camara_x: float, tiempo: float = 0.0) -> None:
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

    # --- Decoración animada ------------------------------------------------------------------
    @staticmethod
    def _astro(sup, conf):
        x, y, r, color = conf["x"], conf["y"], conf["radio"], conf["color"]
        halo = pygame.Surface((r * 4, r * 4), pygame.SRCALPHA)
        pygame.draw.circle(halo, (*color, 50), (r * 2, r * 2), int(r * 1.8))
        sup.blit(halo, (x - r * 2, y - r * 2))
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

    @staticmethod
    def _helicoptero(sup, tiempo):
        """Helicóptero lejano con reflector que barre la ciudad."""
        x = int(300 - (tiempo * 14) % 420)
        y = 58 + int(math.sin(tiempo) * 3)
        luz = pygame.Surface((256, 224), pygame.SRCALPHA)
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
                    halo = pygame.Surface((5, 5), pygame.SRCALPHA)
                    pygame.draw.circle(halo, (220, 255, 120, 90), (2, 2), 2)
                    sup.blit(halo, (px - 2, py - 2))
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
        """Suelo (baldosas con borde) y plataformas."""
        cam = int(camara_x)
        vista = pygame.Rect(cam, 0, settings.ANCHO, settings.ALTO)
        # Fondo de los precipicios: oscuro, para que se lean como peligro
        pygame.draw.rect(sup, (8, 12, 10), (0, 198, settings.ANCHO, settings.ALTO - 198))
        for solido in geometria.solidos:
            if not solido.colliderect(vista):
                continue
            r = solido.move(-cam, 0)
            sup.set_clip(r.clip(sup.get_rect()))
            # Baldosas alineadas al mundo para que no "resbalen" al mover la cámara
            x0 = r.left - (solido.left % 16)
            for x in range(x0, r.right, 16):
                for y in range(r.top, r.bottom, 16):
                    sup.blit(self.baldosa, (x, y))
            sup.set_clip(None)
            pygame.draw.rect(sup, self.amb["suelo_borde"], (r.left, r.top, r.width, 4))
            if alto_contraste:
                pygame.draw.line(sup, (255, 255, 255), (r.left, r.top), (r.right - 1, r.top))
            for x in range(r.left + ((-solido.left) % 6), r.right, 6):   # pasto / borde irregular
                sup.set_at((x, r.top + 4), self.amb["suelo_borde"])
        for p in geometria.plataformas:
            if not p.colliderect(vista):
                continue
            r = p.move(-cam, 0)
            pygame.draw.rect(sup, self.amb["plataforma"], (r.left, r.top, r.width, 5))
            if alto_contraste:
                pygame.draw.line(sup, (255, 255, 255), (r.left, r.top), (r.right - 1, r.top))
            oscuro = tuple(max(0, c - 40) for c in self.amb["plataforma"])
            pygame.draw.line(sup, oscuro, (r.left, r.top + 4), (r.right - 1, r.top + 4))
            for x in range(r.left + 2, r.right, 12):
                pygame.draw.line(sup, oscuro, (x, r.top + 1), (x, r.top + 3))


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


_ADORNOS = {"pasto": _pasto, "flor": _flor, "helecho": _helecho, "farol": _farol, "hidrante": _hidrante,
            "basurero": _basurero, "roca": _roca, "cactus_chico": _cactus_chico, "craneo": _craneo}
