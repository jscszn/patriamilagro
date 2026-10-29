"""Créditos: suben despacio sobre un cielo estrellado, con la bandera ondeando abajo.

ABAJO los acelera; CONFIRMAR o CANCELAR vuelven al menú. Al terminar, vuelven solos.
"""
from __future__ import annotations

import math

import pygame

import input_manager as im
import settings
from audio import gestor as audio
from render.texto import dibujar_texto
from scenes.base import Scene

C = settings.COLORES
VELOCIDAD = 16          # píxeles por segundo
SEPARACION = 12

# (texto, color, escala). "" deja una línea en blanco.
LINEAS = [
    ("PATRIA MILAGRO", C["amarillo"], 2),
    ("LA CRUZADA DEL PRESIDENTE A. MILAGRO", C["blanco"], 1),
    ("", None, 1),
    ("ESTRUCTURA DE DATOS II", C["cian"], 1),
    ("UNIVERSIDAD DEL NORTE", C["cian"], 1),
    ("", None, 1), ("", None, 1),
    ("EQUIPO", C["naranja"], 2),
    ("JOSE CASTRO", C["blanco"], 1),
    ("SANTIAGO GÓMEZ", C["blanco"], 1),
    ("MARIANA GUTIÉRREZ", C["blanco"], 1),
    ("DANIELA IDARRAGA", C["blanco"], 1),
    ("", None, 1), ("", None, 1),
    ("PROGRAMACIÓN Y DISEÑO", C["naranja"], 1),
    ("EL EQUIPO DE PATRIA MILAGRO", C["blanco"], 1),
    ("", None, 1),
    ("ÁRBOL DE DECISIONES Y GRAFO DEL PAÍS", C["naranja"], 1),
    ("HECHOS A MANO, SIN LIBRERÍAS", C["blanco"], 1),
    ("", None, 1),
    ("ARTE", C["naranja"], 1),
    ("PERSONAJES GENERADOS CON IA", C["blanco"], 1),
    ("Y ADAPTADOS A PIXEL ART POR CÓDIGO", C["blanco"], 1),
    ("FONDOS, EFECTOS Y ANIMACIONES", C["blanco"], 1),
    ("DIBUJADOS POR CÓDIGO", C["blanco"], 1),
    ("", None, 1),
    ("MÚSICA Y SONIDO", C["naranja"], 1),
    ("SINTETIZADOS POR CÓDIGO AL ESTILO NES", C["blanco"], 1),
    ("HIMNO NACIONAL: ORESTE SÍNDICI", C["blanco"], 1),
    ("(DOMINIO PÚBLICO), ARREGLO DE 8 BITS", C["gris"], 1),
    ("", None, 1),
    ("HECHO CON", C["naranja"], 1),
    ("PYTHON, PYGAME-CE Y NUMPY", C["blanco"], 1),
    ("", None, 1), ("", None, 1),
    ("PATRIA MILAGRO ES UNA SÁTIRA.", C["gris"], 1),
    ("SU HISTORIA, PERSONAJES, MEDIOS", C["gris"], 1),
    ("Y CRIMINALES SON FICTICIOS.", C["gris"], 1),
    ("", None, 1), ("", None, 1), ("", None, 1),
    ("¡GRACIAS POR JUGAR!", C["amarillo"], 2),
]


def alto_total() -> int:
    return sum(SEPARACION * (2 if escala == 2 else 1) for _, _, escala in LINEAS)


class CreditosScene(Scene):
    def __init__(self, juego, **datos):
        super().__init__(juego, **datos)
        self.tiempo = 0.0
        self.y = float(settings.ALTO)           # posición de la primera línea
        self.velo = pygame.Surface((settings.ANCHO, 24), pygame.SRCALPHA)
        for i in range(24):
            pygame.draw.line(self.velo, (8, 6, 30, int(255 * (1 - i / 24))), (0, i), (settings.ANCHO, i))
        audio.musica("final")

    def update(self, dt, acciones):
        entrada = acciones[settings.JUGADOR_LOCAL]
        self.tiempo += dt
        rapido = 4 if entrada.mantiene(im.ABAJO) else 1
        self.y -= VELOCIDAD * rapido * dt
        if entrada.pulso(im.CONFIRMAR) or entrada.pulso(im.CANCELAR) or entrada.pulso(im.PAUSA) \
                or self.y < -alto_total() + 70:
            self.juego.escenas.cambiar("menu")

    def draw(self, sup):
        for y in range(0, settings.ALTO, 4):                       # cielo de noche en franjas
            t = y / settings.ALTO
            pygame.draw.rect(sup, (int(8 + 30 * t), int(6 + 12 * t), int(30 + 40 * t)), (0, y, settings.ANCHO, 4))
        for i in range(60):                                       # estrellas que titilan
            x, y = (i * 97 + 13) % 256, (i * 53 + int(self.tiempo * (2 + i % 3))) % 200
            if (i + int(self.tiempo * 3)) % 11:
                sup.set_at((x, y), (230, 230, 255) if i % 4 else (255, 240, 180))
        y = self.y
        for texto, color, escala in LINEAS:
            alto = SEPARACION * (2 if escala == 2 else 1)
            if texto and -20 < y < settings.ALTO:
                dibujar_texto(sup, texto, (128, int(y)), color, escala, centrado=True)
            y += alto
        # Bandera ondeando abajo, como en el menú (el texto pasa por detrás)
        pygame.draw.rect(sup, (36, 18, 68), (0, 203, settings.ANCHO, settings.ALTO - 203))
        franjas = [(C["amarillo"], 8), (C["azul"], 4), (C["rojo"], 4)]
        for x in range(0, settings.ANCHO, 2):
            fy = 206 + int(math.sin(self.tiempo * 3 + x * 0.05) * 2)
            for color, alto in franjas:
                pygame.draw.rect(sup, color, (x, fy, 2, alto))
                fy += alto
        sup.blit(self.velo, (0, 0))                               # el texto se desvanece arriba
