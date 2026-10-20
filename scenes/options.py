"""Opciones: accesibilidad, volumen, tutorial y remapeo del control."""
from __future__ import annotations

import pygame

import input_manager as im
import settings
from audio import gestor as audio
from render.texto import dibujar_texto
from render.ui import ListaOpciones, dibujar_marco
from scenes.base import Scene

C = settings.COLORES


class OptionsScene(Scene):
    ITEMS = ["alto_contraste", "daltonismo", "volumen_musica", "volumen_efectos",
             "tutorial", "control", "volver"]

    def __init__(self, juego, **datos):
        super().__init__(juego, **datos)
        self.lista = ListaOpciones(self.ITEMS)

    def _textos(self):
        o = self.juego.opciones
        si_no = lambda v: "SÍ" if v else "NO"
        return [
            f"Alto contraste: {si_no(o['alto_contraste'])}",
            f"Daltonismo: {o['daltonismo'].upper()}",
            f"Música: {o['volumen_musica']}",
            f"Efectos: {o['volumen_efectos']}",
            f"Tutorial: {si_no(o['tutorial'])}",
            "Configurar control",
            "Volver",
        ]

    def _cambiar_valor(self, item: str, paso: int) -> None:
        """Modifica la opción seleccionada con IZQUIERDA/DERECHA o CONFIRMAR."""
        o = self.juego.opciones
        if item in ("alto_contraste", "tutorial"):
            o[item] = not o[item]
        elif item == "daltonismo":
            modos = settings.MODOS_DALTONISMO
            o[item] = modos[(modos.index(o[item]) + paso) % len(modos)]
        elif item.startswith("volumen"):
            o[item] = max(0, min(10, o[item] + paso))
        self.juego.aplicar_opciones()          # volumen y filtros se ven y oyen al momento
        audio.efecto("mover")

    def update(self, dt, acciones):
        entrada = acciones[settings.JUGADOR_LOCAL]
        item = self.lista.seleccion
        confirmo = self.lista.update(dt, entrada)
        if entrada.pulso(im.DERECHA):
            self._cambiar_valor(item, +1)
        elif entrada.pulso(im.IZQUIERDA):
            self._cambiar_valor(item, -1)
        elif confirmo:
            if item == "control":
                self.juego.escenas.cambiar("remapeo")
            elif item == "volver":
                self._salir()
            else:
                self._cambiar_valor(item, +1)
        if entrada.pulso(im.CANCELAR) and not entrada.pulso(im.CONFIRMAR):
            self._salir()

    def _salir(self):
        settings.guardar_opciones(self.juego.opciones)
        self.juego.aplicar_opciones()
        self.juego.escenas.cambiar("menu")

    def draw(self, sup):
        sup.fill((8, 8, 32))
        dibujar_marco(sup, pygame.Rect(16, 16, 224, 192))
        dibujar_texto(sup, "OPCIONES", (128, 24), C["amarillo"], 2, centrado=True)
        self.lista.draw(sup, 128, 56, separacion=18, textos=self._textos())
        dibujar_texto(sup, "< > cambiar   Esc: guardar y volver", (128, 192), C["gris"], 1, centrado=True)


class RemapScene(Scene):
    """Pide al jugador presionar el botón deseado para cada acción y lo guarda en gamepad.json."""

    def __init__(self, juego, **datos):
        super().__init__(juego, **datos)
        self.paso = 0
        self.mensaje = ""
        self.terminado = False
        self.espera = 0.0  # pausa breve entre botones para no registrar dos veces

    @property
    def accion_actual(self):
        return im.ACCIONES_REMAPEABLES[self.paso]

    def handle_events(self, eventos):
        # Aquí sí se leen eventos crudos: necesitamos el ID físico del botón.
        entrada = self.juego.entrada
        for e in eventos:
            if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
                entrada.config = im.cargar_config(entrada.ruta_config)  # descarta cambios
                self.juego.escenas.cambiar("opciones")
                return
            if self.terminado or self.espera > 0 or not entrada.hay_control:
                continue
            if e.type == pygame.JOYBUTTONDOWN:
                entrada.asignar_boton(self.accion_actual, e.button)
                self.mensaje = f"{self.accion_actual} = botón {e.button}"
                self.paso += 1
                self.espera = 0.25
                if self.paso >= len(im.ACCIONES_REMAPEABLES):
                    entrada.guardar()
                    self.terminado = True

    def update(self, dt, acciones):
        self.espera = max(0.0, self.espera - dt)
        if self.terminado and self.espera == 0 and acciones[settings.JUGADOR_LOCAL].pulso(im.CONFIRMAR):
            self.juego.escenas.cambiar("opciones")

    def draw(self, sup):
        sup.fill((8, 8, 32))
        dibujar_marco(sup, pygame.Rect(16, 16, 224, 192))
        dibujar_texto(sup, "CONFIGURAR CONTROL", (128, 24), C["amarillo"], 2, centrado=True)
        entrada = self.juego.entrada
        if not entrada.hay_control:
            dibujar_texto(sup, "Conecta un control USB...", (128, 80), C["blanco"], 1, centrado=True)
            dibujar_texto(sup, "(el teclado siempre funciona)", (128, 98), C["gris"], 1, centrado=True)
        elif self.terminado:
            dibujar_texto(sup, "Guardado en config/gamepad.json", (128, 80), C["verde"], 1, centrado=True)
            dibujar_texto(sup, "Presiona A / Enter", (128, 100), C["blanco"], 1, centrado=True)
        else:
            dibujar_texto(sup, entrada.nombre_control()[:30], (128, 46), C["cian"], 1, centrado=True)
            dibujar_texto(sup, "Presiona el botón para:", (128, 74), C["blanco"], 1, centrado=True)
            dibujar_texto(sup, self.accion_actual, (128, 94), C["amarillo"], 2, centrado=True)
        # Mapeo actual
        y = 130
        for accion in im.ACCIONES_REMAPEABLES:
            boton = entrada.config["botones"].get(accion)
            dibujar_texto(sup, f"{accion:<9} botón {boton}", (70, y), C["gris"], 1)
            y += 12
        if self.mensaje:
            dibujar_texto(sup, self.mensaje, (128, 180), C["verde"], 1, centrado=True)
        dibujar_texto(sup, "Esc: cancelar", (128, 194), C["gris"], 1, centrado=True)
