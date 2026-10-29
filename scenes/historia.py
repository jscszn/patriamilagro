"""Informe de inteligencia antes de cada nivel: la historia de los daños del jefe y la ruta.

Detrás del texto se ve al jefe del nivel, grande y desvanecido: es el villano de la historia.

Página 1, LOS DAÑOS: el texto de core/historia.py y, en el mapa, las zonas que sufren al jefe,
que aparecen por olas (BFS desde su zona).
Página 2, LA RUTA: el jugador ELIGE con izquierda/derecha entre la ruta segura (Dijkstra: menos
peligro) y la ruta corta (BFS: menos tramos). La elegida se resalta en el mapa y tiene efecto:
refuerzos enemigos en el nivel y opinión del pueblo (core/partida.py -> elegir_ruta).
"""
from __future__ import annotations

import pygame

import input_manager as im
import settings
from audio import gestor as audio
from core import historia
from core.mapa import CORTA, NOMBRE_RUTA, SEGURA, ZONA_NIVEL
from levels import cargar_nivel
from render.grafo_visual import COLOR_CORTA, COLOR_OLA, COLOR_RUTA_ALTERNA, COLOR_SEGURA, dibujar_mapa
from render.texto import dibujar_texto, envolver, fuente
from render.ui import dibujar_marco
from scenes.base import Scene

C = settings.COLORES
AREA_MAPA = pygame.Rect(8, 23, 240, 90)
CAJA_TEXTO = pygame.Rect(8, 115, 240, 95)
# En LA RUTA el texto es más corto (5 líneas): el mapa crece para que las dos rutas se separen
AREA_MAPA_RUTA = pygame.Rect(8, 23, 240, 114)
CAJA_TEXTO_RUTA = pygame.Rect(8, 139, 240, 72)
# Cada ruta tiene siempre su color; la elegida va gruesa y la otra punteada
COLOR_RUTA = {SEGURA: COLOR_SEGURA, CORTA: COLOR_CORTA}
MARGEN_TEXTO = 5               # entre el borde del recuadro y el texto
ANCHO_TEXTO = CAJA_TEXTO.w - 12
OPACIDAD_JEFE = 105            # 0..255: el jefe detrás del texto
OPACIDAD_VELO = 120            # capa oscura sobre el jefe para que el texto se lea
LETRAS_POR_SEGUNDO = 45.0
SEGUNDOS_POR_OLA = 0.9
SEGUNDOS_POR_TRAMO = 0.7
TITULOS = ("LOS DAÑOS", "LA RUTA")


class HistoriaScene(Scene):
    def __init__(self, juego, numero: int = 1, puntaje: int = 0, vidas: int = None, **datos):
        super().__init__(juego, **datos)
        self.numero = numero
        self.siguiente = {"numero": numero, "puntaje": puntaje, "vidas": vidas}
        if juego.partida is None:
            juego.nueva_partida().nivel = numero
        self.partida = juego.partida
        self.mapa = self.partida.mapa
        self.datos_nivel = cargar_nivel(numero)
        self.jefe = settings.JEFES[self.datos_nivel["jefe"]]["nombre"]
        self.opciones = self.partida.opciones_ruta(numero)     # rutas que ofrece el grafo
        self.claves = list(self.opciones)
        self.clave = SEGURA
        self.ya_elegida = numero in self.partida.rutas          # se volvió al informe: no se re-elige
        if self.ya_elegida:
            self.clave = self.partida.rutas[numero]["clave"]
        self.paginas = historia.informe(numero, self.partida.arbol.camino(), self.mapa, self.clave)
        self.olas = self.mapa.influencia(numero)
        self.pagina = 0
        self.t_pagina = 0.0
        self.tiempo = 0.0
        self._villano = None            # sprite del jefe ampliado (se prepara al dibujar)
        self.t_ruta = 0.0               # segundos desde que se empezó a trazar la ruta elegida
        audio.musica("decision")

    @property
    def texto(self) -> str:
        return self.paginas[self.pagina]

    @property
    def ruta(self) -> list:
        """Zonas de la ruta elegida."""
        return self.opciones[self.clave]["camino"]

    def cambiar_ruta(self, paso: int) -> None:
        if self.ya_elegida or len(self.claves) < 2:
            return
        self.clave = self.claves[(self.claves.index(self.clave) + paso) % len(self.claves)]
        self.paginas[1] = historia.pagina_ruta(self.numero, self.mapa, self.clave)
        self.t_pagina = 999.0                                  # el texto de la otra ruta sale completo
        self.t_ruta = 0.0                                      # y la ruta se vuelve a trazar
        audio.efecto("mover")

    # --- Medidas del texto (reales, según la fuente) ---------------------------------------------
    @staticmethod
    def alto_linea() -> int:
        return fuente(1).get_linesize()

    @classmethod
    def alto_encabezado(cls) -> int:
        """La primera línea del recuadro es el nombre del jefe."""
        return cls.alto_linea() + 2

    @classmethod
    def lineas_que_caben(cls, caja: pygame.Rect = CAJA_TEXTO) -> int:
        """Cuántas líneas de texto entran de verdad en el recuadro, debajo del encabezado."""
        libre = caja.h - 2 * MARGEN_TEXTO - cls.alto_encabezado()
        return libre // cls.alto_linea()

    @classmethod
    def alto_texto(cls, texto: str) -> int:
        """Alto en píxeles que ocupa `texto` ya partido en líneas (con el encabezado)."""
        ultima = fuente(1).size("A")[1]                       # la última línea no lleva interlineado
        lineas = len(envolver(texto, 1, ANCHO_TEXTO))
        return cls.alto_encabezado() + (lineas - 1) * cls.alto_linea() + ultima

    @property
    def area_mapa(self) -> pygame.Rect:
        return AREA_MAPA_RUTA if self.pagina == 1 else AREA_MAPA

    @property
    def caja_texto(self) -> pygame.Rect:
        return CAJA_TEXTO_RUTA if self.pagina == 1 else CAJA_TEXTO

    @property
    def escrito(self) -> bool:
        return self.t_pagina * LETRAS_POR_SEGUNDO >= len(self.texto)

    def update(self, dt, acciones):
        self.tiempo += dt
        antes = int(self.t_pagina * LETRAS_POR_SEGUNDO)
        self.t_pagina += dt
        if not self.escrito and int(self.t_pagina * LETRAS_POR_SEGUNDO) // 3 != antes // 3:
            audio.efecto("mover")                               # tecleo de la máquina de escribir
        self.t_ruta += dt
        entrada = acciones[settings.JUGADOR_LOCAL]
        if self.pagina == 1:                                    # izquierda/derecha: elegir la ruta
            paso = int(entrada.pulso(im.DERECHA)) - int(entrada.pulso(im.IZQUIERDA))
            if paso:
                self.cambiar_ruta(paso)
        if entrada.pulso(im.AYUDA):
            self.juego.escenas.apilar("ayuda", superpuesta=True)
        elif entrada.pulso(im.CONFIRMAR):
            if not self.escrito:                                # primer toque: completa el texto
                self.t_pagina = 999.0
            elif self.pagina + 1 < len(self.paginas):
                self.pagina, self.t_pagina, self.t_ruta = self.pagina + 1, 0.0, 0.0
                audio.efecto("confirmar")
            else:
                audio.efecto("confirmar")
                self.partida.elegir_ruta(self.numero, self.clave)   # grafo -> refuerzos y opinión
                self.juego.escenas.cambiar("nivel", **self.siguiente)
        elif entrada.pulso(im.CANCELAR) and self.pagina > 0:
            self.pagina, self.t_pagina = self.pagina - 1, 999.0

    def draw(self, sup):
        sup.fill((10, 12, 26))
        dibujar_texto(sup, "INFORME DE INTELIGENCIA", (8, 3), C["gris"])
        dibujar_texto(sup, f"{self.pagina + 1}/{len(self.paginas)} {TITULOS[self.pagina]}", (248, 3), C["cian"],
                      derecha=True)
        dibujar_texto(sup, f"NIVEL {self.numero}: {self.datos_nivel['nombre']}", (8, 13), C["amarillo"])

        dibujar_marco(sup, self.area_mapa, fondo=(16, 20, 40))
        interior = self.area_mapa.inflate(-4, -4)
        interior.h -= 13                                        # abajo, la leyenda
        # Lo que ya viajó el presidente en los niveles anteriores (en blanco)
        recorrido = [self.partida.rutas[n]["camino"] for n in sorted(self.partida.rutas)
                     if n < self.numero and "camino" in self.partida.rutas[n]]
        if self.pagina == 0:        # BFS: las olas de daño salen de la zona del jefe
            visibles = 1 + int(self.t_pagina / SEGUNDOS_POR_OLA)
            enfoque = [z for ola in self.olas[:2] for z in ola]      # el jefe y sus vecinos
            dibujar_mapa(sup, self.mapa, interior, self.numero, olas=self.olas, olas_visibles=visibles,
                         tiempo=self.tiempo, simple=True, enfoque=enfoque)
        else:                       # la ruta elegida avanza tramo por tramo; la otra va punteada
            otra = next((c for c in self.claves if c != self.clave), None)
            enfoque = {z for r in self.opciones.values() for z in r["camino"]}
            dibujar_mapa(sup, self.mapa, interior, self.numero, ruta=self.ruta,
                         tramos_ruta=self.t_ruta / SEGUNDOS_POR_TRAMO, tiempo=self.tiempo,
                         ruta_alterna=self.opciones[otra]["camino"] if otra else (), simple=True,
                         color_ruta=COLOR_RUTA[self.clave],
                         color_alterna=COLOR_RUTA[otra] if otra else COLOR_RUTA_ALTERNA,
                         recorrido=recorrido, enfoque=sorted(enfoque))
        self._leyenda(sup)

        dibujar_marco(sup, self.caja_texto)
        self._dibujar_villano(sup)
        x, y = self.caja_texto.x + 6, self.caja_texto.y + MARGEN_TEXTO
        dibujar_texto(sup, self.jefe, (x, y), C["naranja"])
        y += self.alto_encabezado()
        # Se parte el texto completo en líneas y se van destapando letras (las palabras no saltan)
        quedan = int(self.t_pagina * LETRAS_POR_SEGUNDO)
        for i, linea in enumerate(envolver(self.texto, 1, ANCHO_TEXTO)[:self.lineas_que_caben(self.caja_texto)]):
            if quedan <= 0:
                break
            dibujar_texto(sup, linea[:quedan], (x, y + i * self.alto_linea()), C["blanco"])
            quedan -= len(linea) + 1

        if self.escrito and int(self.tiempo * 2) % 2 == 0:
            ultimo = self.pagina + 1 == len(self.paginas)
            dibujar_texto(sup, "ENTER: ¡A LA MISIÓN!" if ultimo else "ENTER: SEGUIR", (248, 212), C["blanco"],
                          derecha=True)
        if self.pagina == 1 and len(self.claves) > 1 and not self.ya_elegida:
            dibujar_texto(sup, "< > CAMBIAR DE RUTA", (8, 212), C["cian"])

    def _dibujar_villano(self, sup):
        """El jefe del nivel al doble de tamaño, a baja opacidad, DETRÁS del texto; encima va
        una capa oscura semitransparente para que el texto siga legible. El mapa no se toca."""
        interior = self.caja_texto.inflate(-6, -6)
        if self._villano is None:
            imagen = self.juego.sprites.frame(f"jefe{self.datos_nivel['jefe']}", "quieto", 0, voltear=True)
            self._villano = pygame.transform.scale_by(imagen, 2).convert_alpha()
            self._villano.set_alpha(OPACIDAD_JEFE)
        anterior = sup.get_clip()
        sup.set_clip(interior)
        sup.blit(self._villano, self._villano.get_rect(topright=(interior.right - 2, interior.y - 6)))
        velo = pygame.Surface(interior.size, pygame.SRCALPHA)
        velo.fill((0, 0, 30, OPACIDAD_VELO))
        sup.blit(velo, interior.topleft)
        sup.set_clip(anterior)

    def _leyenda(self, sup):
        """Qué significan los colores del mapa en la página actual."""
        x, y = self.area_mapa.x + 6, self.area_mapa.bottom - 14
        pygame.draw.rect(sup, (12, 14, 28), (self.area_mapa.x + 2, y - 2, self.area_mapa.w - 4, 12))
        if self.pagina == 0:
            for i, texto in enumerate(("JEFE", "1 SALTO", "2 SALTOS")):
                pygame.draw.rect(sup, COLOR_OLA[i], (x, y + 2, 5, 5))
                dibujar_texto(sup, texto, (x + 8, y), C["gris"], sombra=False)
                x += 14 + len(texto) * 6
        else:                       # las dos rutas con su peligro; la elegida en blanco
            dibujar_texto(sup, "PELIGRO", (x, y), C["gris"], sombra=False)
            x += 48
            for clave in self.claves:
                color = COLOR_RUTA[clave]
                if clave == self.clave:
                    pygame.draw.rect(sup, color, (x, y + 3, 8, 3))
                else:
                    for dx in (0, 5):
                        pygame.draw.rect(sup, color, (x + dx, y + 3, 3, 2))
                texto = f"{NOMBRE_RUTA[clave].replace('RUTA ', '')} {self.opciones[clave]['peligro']}"
                dibujar_texto(sup, texto, (x + 11, y), C["blanco"] if clave == self.clave else C["gris"],
                              sombra=False)
                x += 11 + len(texto) * 6 + 10
            if self.mapa.retenes:
                dibujar_texto(sup, "RETÉN", (self.area_mapa.right - 6, y), C["rojo"], derecha=True, sombra=False)

    @property
    def zona(self) -> str:
        return ZONA_NIVEL[self.numero]
