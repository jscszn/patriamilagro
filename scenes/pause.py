"""Menú de pausa superpuesto al nivel."""
from __future__ import annotations

import input_manager as im
import settings
from render.texto import dibujar_texto
from render.ui import ListaOpciones, oscurecer
from scenes.base import Scene

C = settings.COLORES


class PauseScene(Scene):
    transparente = True

    def __init__(self, juego, **datos):
        super().__init__(juego, **datos)
        self.lista = ListaOpciones(["CONTINUAR", "AYUDA", "SALIR AL MENÚ"])

    def update(self, dt, acciones):
        entrada = acciones[settings.JUGADOR_LOCAL]
        if entrada.pulso(im.AYUDA):
            self.juego.escenas.apilar("ayuda", superpuesta=True)
            return
        if entrada.pulso(im.CANCELAR):
            self.juego.escenas.desapilar()
            return
        if self.lista.update(dt, entrada):
            if self.lista.seleccion == "CONTINUAR":
                self.juego.escenas.desapilar()
            elif self.lista.seleccion == "AYUDA":
                self.juego.escenas.apilar("ayuda", superpuesta=True)
            else:
                self.juego.escenas.cambiar("menu")

    def draw(self, sup):
        oscurecer(sup)
        dibujar_texto(sup, "PAUSA", (128, 70), C["amarillo"], 3, centrado=True)
        self.lista.draw(sup, 128, 110)
