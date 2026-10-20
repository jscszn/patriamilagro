"""Menú principal: Jugar, Ayuda, Opciones, Logros, Salir.

Composición "épica": atardecer con un sol rayado detrás del presidente (busto con contraluz
que se disuelve en píxeles sobre la bandera), rayos de luz girando y el título a la derecha.
"""
from __future__ import annotations

import math

import pygame

import input_manager as im
import settings
from audio import gestor as audio
from render.texto import dibujar_texto, fuente
from render.ui import ListaOpciones
from scenes.base import Scene

C = settings.COLORES
SOL = (88, 158)                # centro del sol (asoma por detrás del presidente y su fusil)
COLUMNA = 184                  # centro de la columna derecha (título y opciones)
INTRO = 0.9                    # segundos de la animación de entrada
CIELO = [(0, (8, 6, 34)), (70, (54, 24, 84)), (130, (190, 70, 70)), (175, (250, 160, 70))]


def _suavizar(t: float) -> float:
    """0..1 con frenado al final (ease-out cúbico)."""
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 3


def _color_cielo(y: int):
    """Interpola el degradado del atardecer en la fila y."""
    for (y0, c0), (y1, c1) in zip(CIELO, CIELO[1:]):
        if y <= y1:
            t = max(0.0, (y - y0) / (y1 - y0))
            return [int(c0[i] + (c1[i] - c0[i]) * t) for i in range(3)]
    return CIELO[-1][1]


class MenuScene(Scene):
    OPCIONES = ["JUGAR", "AYUDA", "OPCIONES", "LOGROS", "SALIR"]

    def __init__(self, juego, **datos):
        super().__init__(juego, **datos)
        self.lista = ListaOpciones(self.OPCIONES)
        self.tiempo = 0.0
        self.fondo = self._pintar_fondo()
        self.busto = juego.sprites.frame("presidente_menu", "quieto", 0)
        self.contraluz = self._contraluz(self.busto)
        self.titulos = [self._titulo("PATRIA", C["amarillo"]), self._titulo("MILAGRO", C["rojo"])]
        # Primero "Bienvenido a la Patria Milagro"; el himno arranca cuando termina la frase
        audio.presentar("bienvenida", "menu")

    # --- Lógica ---------------------------------------------------------------------------
    def update(self, dt, acciones):
        self.tiempo += dt
        entrada = acciones[settings.JUGADOR_LOCAL]
        if entrada.pulso(im.AYUDA):
            self.juego.escenas.cambiar("ayuda")
            return
        if self.lista.update(dt, entrada):
            eleccion = self.lista.seleccion
            if eleccion == "JUGAR":
                partida = self.juego.nueva_partida()
                self.juego.escenas.cambiar("historia", numero=1, puntaje=partida.puntaje, vidas=partida.vidas)
            elif eleccion == "AYUDA":
                self.juego.escenas.cambiar("ayuda")
            elif eleccion == "OPCIONES":
                self.juego.escenas.cambiar("opciones")
            elif eleccion == "LOGROS":
                self.juego.escenas.cambiar("logros")
            elif eleccion == "SALIR":
                self.juego.salir()

    # --- Elementos pre-dibujados ----------------------------------------------------------
    @staticmethod
    def _pintar_fondo() -> pygame.Surface:
        """Cielo de atardecer, sol rayado y cerros en silueta (se dibujan una sola vez)."""
        sup = pygame.Surface((settings.ANCHO, settings.ALTO))
        for y in range(settings.ALTO):
            pygame.draw.line(sup, _color_cielo(y), (0, y), (settings.ANCHO, y))
        # Sol con halo y franjas (estilo retro)
        halo = pygame.Surface((160, 160), pygame.SRCALPHA)
        for r, a in ((78, 30), (64, 45), (54, 60)):
            pygame.draw.circle(halo, (255, 190, 90, a), (80, 80), r)
        sup.blit(halo, (SOL[0] - 80, SOL[1] - 80))
        pygame.draw.circle(sup, (255, 210, 100), SOL, 44)
        for i, y in enumerate(range(SOL[1] - 4, SOL[1] + 44, 7)):
            pygame.draw.rect(sup, (232, 120, 80), (SOL[0] - 44, y, 88, 1 + i // 2))
        # Cerros lejanos y cercanos
        for color, base, alto, paso, semilla in (((96, 40, 70), 178, 30, 32, 1), ((48, 20, 46), 190, 22, 22, 7)):
            puntos = [(0, settings.ALTO)]
            for x in range(0, settings.ANCHO + paso, paso):
                h = alto * (0.5 + 0.5 * math.sin(x * 0.07 + semilla) * math.cos(x * 0.031 + semilla))
                puntos.append((x, int(base - abs(h))))
            puntos.append((settings.ANCHO, settings.ALTO))
            pygame.draw.polygon(sup, color, puntos)
        return sup

    @staticmethod
    def _contraluz(imagen: pygame.Surface, hasta: float = 0.58) -> pygame.Surface:
        """Borde naranja alrededor del busto, como si el sol lo iluminara por detrás. Solo en la
        parte de arriba: la parte disuelta en píxeles no lleva borde (si no, se ensucia)."""
        silueta = pygame.mask.from_surface(imagen).to_surface(setcolor=(255, 170, 70, 255),
                                                              unsetcolor=(0, 0, 0, 0))
        corte = int(imagen.get_height() * hasta)
        silueta.fill((0, 0, 0, 0), pygame.Rect(0, corte, imagen.get_width(), imagen.get_height() - corte))
        borde = pygame.Surface((imagen.get_width() + 4, imagen.get_height() + 4), pygame.SRCALPHA)
        for dx, dy, alfa in ((-2, 0, 90), (2, 0, 90), (0, -2, 110), (-1, -1, 200), (1, -1, 200),
                             (-1, 0, 200), (1, 0, 200), (0, -1, 220)):
            capa = silueta.copy()
            capa.set_alpha(alfa)
            borde.blit(capa, (2 + dx, 2 + dy))
        return borde

    @staticmethod
    def _titulo(texto: str, color) -> pygame.Surface:
        """Texto grande con contorno grueso negro y la parte de arriba más clara (volumen)."""
        f = fuente(3)
        ancho, alto = f.size(texto)
        sup = pygame.Surface((ancho + 4, alto + 4), pygame.SRCALPHA)
        negro = f.render(texto, False, C["negro"])
        for dx in range(5):
            for dy in range(5):
                sup.blit(negro, (dx, dy))
        sup.blit(f.render(texto, False, color), (2, 2))
        claro = tuple(min(255, c + 70) for c in color)
        sup.blit(f.render(texto, False, claro), (2, 2), pygame.Rect(0, 0, ancho, 12))
        return sup

    # --- Dibujo ---------------------------------------------------------------------------
    def draw(self, sup):
        sup.blit(self.fondo, (0, 0))
        self._estrellas(sup)
        self._rayos(sup)
        # Busto: sube desde abajo al entrar y "respira" despacio
        subida = int((1 - _suavizar(self.tiempo / INTRO)) * 50)
        respiro = int(math.sin(self.tiempo * 1.6) * 1.2)
        x, y = 4, 196 - self.busto.get_height() + subida + respiro
        sup.blit(self.contraluz, (x - 2, y - 2))
        sup.blit(self.busto, (x, y))
        self._bandera(sup)
        self._dibujar_titulo(sup)
        if self.tiempo > INTRO * 0.6:
            self.lista.draw(sup, COLUMNA, 94, separacion=12)
        control = self.juego.entrada.nombre_control()
        estado = f"CONTROL: {control[:20]}" if control else "FLECHAS, Z, X, ENTER"
        dibujar_texto(sup, estado, (COLUMNA, 168), (210, 200, 220), centrado=True)

    def _estrellas(self, sup):
        for i in range(36):
            x, y = (i * 97 + 13) % 256, (i * 53) % 70
            if (i + int(self.tiempo * 2)) % 9:
                sup.set_at((x, y), (200, 200, 230) if i % 3 else (255, 255, 255))

    def _rayos(self, sup):
        """Rayos de luz que salen del sol y giran lentamente."""
        capa = pygame.Surface((settings.ANCHO, settings.ALTO), pygame.SRCALPHA)
        for i in range(10):
            ang = self.tiempo * 0.12 + i * math.tau / 10
            puntos = [SOL] + [(SOL[0] + math.cos(a) * 260, SOL[1] + math.sin(a) * 260) for a in (ang - 0.09, ang + 0.09)]
            pygame.draw.polygon(capa, (255, 220, 140, 22), puntos)
        sup.blit(capa, (0, 0))

    def _bandera(self, sup):
        """Bandera tricolor ondeando sobre la parte baja (disuelta) del busto."""
        franjas = [(C["amarillo"], 12), (C["azul"], 6), (C["rojo"], 6)]
        for x in range(0, settings.ANCHO, 2):
            y = 186 + int(math.sin(self.tiempo * 3 + x * 0.05) * 3)
            for color, alto in franjas:
                pygame.draw.rect(sup, color, (x, y, 2, alto))
                y += alto
        dibujar_texto(sup, "LA CRUZADA DEL PRESIDENTE A. MILAGRO", (128, 214), C["blanco"], centrado=True)

    def _dibujar_titulo(self, sup):
        bajada = int((1 - _suavizar(self.tiempo / INTRO)) * -70)       # cae desde arriba al entrar
        for i, (titulo, y) in enumerate(zip(self.titulos, (14, 44))):
            rect = titulo.get_rect(midtop=(COLUMNA, y + bajada))
            sup.blit(titulo, rect)
            # Destello: una franja blanca diagonal que cruza el título cada 5 segundos
            fase = (self.tiempo % 5.0) / 0.8
            if fase < 1:
                brillo = pygame.mask.from_surface(titulo, 200).to_surface(setcolor=(255, 255, 255, 200),
                                                                         unsetcolor=(0, 0, 0, 0))
                franja_x = int(rect.x - 20 + fase * (rect.w + 40)) + i * 6
                sup.set_clip(pygame.Rect(franja_x, rect.y, 6, rect.h))
                sup.blit(brillo, rect)
                sup.set_clip(None)
        dibujar_texto(sup, "¡POR LA PATRIA!", (COLUMNA, 78 + bajada), C["naranja"], centrado=True)
