"""Pantalla de LOGROS (desde el menú): cuáles se ganaron y cuáles faltan."""
from __future__ import annotations

import pygame

import input_manager as im
import settings
from core.logros import LOGROS, SICARIOS_CAZADOR
from render.texto import dibujar_texto
from render.ui import dibujar_marco
from scenes.base import Scene

C = settings.COLORES
POR_PAGINA = 6


class LogrosScene(Scene):
    def __init__(self, juego, **datos):
        super().__init__(juego, **datos)
        self.pagina = 0
        self.paginas = (len(LOGROS) + POR_PAGINA - 1) // POR_PAGINA

    def update(self, dt, acciones):
        entrada = acciones[settings.JUGADOR_LOCAL]
        if entrada.pulso(im.DERECHA):
            self.pagina = min(self.pagina + 1, self.paginas - 1)
        if entrada.pulso(im.IZQUIERDA):
            self.pagina = max(self.pagina - 1, 0)
        if entrada.pulso(im.CANCELAR) or entrada.pulso(im.CONFIRMAR):
            self.juego.escenas.cambiar("menu")

    def draw(self, sup):
        sup.fill((8, 8, 32))
        dibujar_marco(sup, pygame.Rect(8, 6, 240, 212))
        gestor = self.juego.logros
        progreso = gestor.progreso()
        dibujar_texto(sup, f"LOGROS {progreso['desbloqueados']}/{progreso['total']}", (128, 12), C["amarillo"], 2,
                      centrado=True)
        y = 36
        for logro in LOGROS[self.pagina * POR_PAGINA:(self.pagina + 1) * POR_PAGINA]:
            ganado = logro.clave in gestor.desbloqueados
            # Medalla: llena si se ganó, vacía si no
            if ganado:
                pygame.draw.circle(sup, C["amarillo"], (24, y + 8), 6)
                pygame.draw.circle(sup, C["naranja"], (24, y + 8), 6, 1)
            else:
                pygame.draw.circle(sup, C["gris_oscuro"], (24, y + 8), 6, 1)
            dibujar_texto(sup, logro.titulo, (36, y), C["blanco"] if ganado else C["gris"])
            descripcion = logro.descripcion
            if logro.clave == "cazador" and not ganado:
                descripcion += f" ({gestor.sicarios}/{SICARIOS_CAZADOR})"
            dibujar_texto(sup, descripcion, (36, y + 10), C["cian"] if ganado else C["gris_oscuro"])
            y += 27
        dibujar_texto(sup, f"< {self.pagina + 1}/{self.paginas} >   ENTER/ESC: VOLVER", (128, 202), C["gris"],
                      centrado=True)
