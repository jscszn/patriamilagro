"""Reportaje al final de cada nivel: el país comenta la decisión sobre el jefe de ese nivel.

Va después del teléfono. Sale UNO de los tres formatos, según el orden al azar de la partida
(core/reportajes.formatos): NOTICIERO (medios), EN VIVO (influencers) o LA CALLE (pueblo).
core/reportajes.py arma el guion y render/reportajes.py lo dibuja. Cada línea sale en un cuadro
de diálogo, letra por letra, con el nombre de quien habla en una pestaña de su lado.

Controles: CONFIRMAR completa el texto o pasa al siguiente cuadro. No se puede saltar: el
reportaje se lee entero (es la consecuencia de la decisión).
Al terminar el último segmento sigue el informe del nivel siguiente (o la pantalla final).
"""
from __future__ import annotations

from typing import List, Optional

import pygame

import input_manager as im
import settings
from audio import gestor as audio
from core import reportajes as rep
from core.news import MEDIOS, NOTICIAS, _formatear
from levels import ULTIMO_NIVEL, cargar_nivel
from render import reportajes as esc
from render.texto import dibujar_texto, envolver, fuente
from render.ui import dibujar_marco
from scenes.base import Scene

C = settings.COLORES
CAJA = pygame.Rect(4, esc.ESCENA_ALTO + 4, 248, 56)
MARGEN = 7
ANCHO_TEXTO = CAJA.w - 2 * MARGEN - 6         # deja lugar para la flecha de "seguir"
LINEAS_POR_CUADRO = 4
LETRAS_POR_SEGUNDO = 45.0


def paginas(texto: str) -> List[List[str]]:
    """El texto partido en cuadros de LINEAS_POR_CUADRO líneas (sin cortar palabras)."""
    lineas = envolver(texto.upper(), 1, ANCHO_TEXTO)
    return [lineas[i:i + LINEAS_POR_CUADRO] for i in range(0, len(lineas), LINEAS_POR_CUADRO)] or [[""]]


class ReportajeScene(Scene):
    def __init__(self, juego, **datos):
        super().__init__(juego, **datos)
        self.partida = juego.partida
        arbol = self.partida.arbol
        camino = arbol.camino()
        self.nivel = len(camino)                       # el reportaje comenta la última decisión
        numeros = [cargar_nivel(n)["jefe"] for n in range(1, len(camino) + 1)]
        jefes = [settings.JEFES[k]["nombre"] for k in numeros]
        opinion = arbol.opinion()
        self.formato = rep.formatos(self.partida.semilla)[self.nivel]
        self.segmentos = rep.guion(camino, jefes, opinion, self.nivel, [self.formato],
                                   escapes=self.partida.escapes)
        sprites = [f"jefe{k}" for k in numeros]
        titulares = [_formatear((NOTICIAS[d]["escapo"] if self.partida.escapo_en(i + 1) else NOTICIAS[d]["normal"])
                                [MEDIOS][0], jefes[i], i + 1)
                     for i, d in reversed(list(enumerate(camino)))]            # lo más nuevo primero
        ambientes = {n: cargar_nivel(n)["ambiente"] for n in (1, 2, 3)}
        self.escenarios = {
            "noticiero": lambda: esc.Noticiero(juego, sprites, opinion["medios"], titulares),
            "en_vivo": lambda: esc.EnVivo(juego, sprites, opinion["influencers"]),
            "calle": lambda: esc.Calle(juego, sprites, opinion["pueblo"], ambientes),
        }
        self.i_segmento = 0
        self.escenario = None
        self._empezar_segmento(0)
        audio.musica("noticias")

    # --- Estado ------------------------------------------------------------------------------
    @property
    def segmento(self) -> rep.Segmento:
        return self.segmentos[self.i_segmento]

    @property
    def linea(self) -> rep.Linea:
        return self.segmento.lineas[self.i_linea]

    @property
    def cuadro(self) -> List[str]:
        return self.paginas[self.i_pagina]

    @property
    def escrito(self) -> bool:
        return self.t_texto * LETRAS_POR_SEGUNDO >= sum(len(l) + 1 for l in self.cuadro)

    def _empezar_segmento(self, i: int) -> None:
        self.i_segmento = i
        self.escenario = self.escenarios[self.segmento.escenario]()
        self.t_segmento = 0.0
        self._empezar_linea(0)

    def _empezar_linea(self, i: int, anterior: Optional[rep.Linea] = None) -> None:
        self.i_linea = i
        self.paginas = paginas(self.linea.texto)
        self.i_pagina = 0
        self.t_texto = 0.0
        self.t_linea = 0.0
        if self.escenario.al_cambiar(anterior, self.linea):
            self.juego.iniciar_transicion()

    def siguiente(self) -> None:
        """Siguiente cuadro, línea o segmento; después del último, la pantalla final."""
        if self.i_pagina + 1 < len(self.paginas):
            self.i_pagina += 1
            self.t_texto = 0.0
        elif self.i_linea + 1 < len(self.segmento.lineas):
            self._empezar_linea(self.i_linea + 1, self.linea)
        else:
            self.terminar_segmento()

    def terminar_segmento(self) -> None:
        if self.i_segmento + 1 < len(self.segmentos):
            self._empezar_segmento(self.i_segmento + 1)
            self.juego.iniciar_transicion()
        else:
            self.continuar()

    def continuar(self) -> None:
        """Lo que antes hacía el teléfono: el informe del nivel siguiente o la pantalla final."""
        p = self.partida
        if p.nivel >= ULTIMO_NIVEL:
            self.juego.escenas.cambiar("final")
        else:
            p.avanzar()
            self.juego.escenas.cambiar("historia", numero=p.nivel, puntaje=p.puntaje, vidas=p.vidas)

    # --- Bucle -------------------------------------------------------------------------------
    def update(self, dt, acciones):
        self.t_segmento += dt
        self.t_linea += dt
        antes = int(self.t_texto * LETRAS_POR_SEGUNDO)
        self.t_texto += dt
        if not self.escrito and int(self.t_texto * LETRAS_POR_SEGUNDO) // 3 != antes // 3:
            audio.efecto("mover")                                  # tecleo, como en el informe
        if hasattr(self.escenario, "actualizar"):
            self.escenario.actualizar(self.linea, dt)
        entrada = acciones[settings.JUGADOR_LOCAL]
        if entrada.pulso(im.CONFIRMAR):
            if not self.escrito:
                self.t_texto = 999.0
            else:
                audio.efecto("confirmar")
                self.siguiente()

    def draw(self, sup):
        sup.fill((0, 0, 0))
        hablando = not self.escrito
        self.escenario.dibujar(sup, self.linea, hablando, self.t_segmento, self.t_linea)
        self._cuadro(sup)

    # --- Cuadro de diálogo -------------------------------------------------------------------
    def _cuadro(self, sup):
        pygame.draw.rect(sup, (0, 0, 0), (0, esc.ESCENA_ALTO, settings.ANCHO, settings.ALTO - esc.ESCENA_ALTO))
        dibujar_marco(sup, CAJA, fondo=(0, 0, 40))
        alto = fuente(1).get_linesize()
        quedan = int(self.t_texto * LETRAS_POR_SEGUNDO)
        x, y = CAJA.x + MARGEN, CAJA.y + MARGEN - 1
        for i, linea in enumerate(self.cuadro):
            if quedan <= 0:
                break
            dibujar_texto(sup, linea[:quedan], (x, y + i * alto), C["blanco"])
            quedan -= len(linea) + 1
        if self.escrito and int(self.t_linea * 3) % 2 == 0:            # flecha de "seguir"
            px, py = CAJA.right - 10, CAJA.bottom - 9
            pygame.draw.polygon(sup, C["amarillo"], [(px - 3, py), (px + 3, py), (px, py + 3)])
        self._pestana(sup)

    def _pestana(self, sup):
        """La pestaña con el nombre (y el cargo) de quien habla, del lado en que está. Va entera
        ENCIMA del cuadro y abierta por abajo: sus bordes bajan hasta los del cuadro y ninguna
        línea cruza el texto (ver geometria_pestana)."""
        linea = self.linea
        hablante = rep.HABLANTES.get(linea.hablante)
        cargo = hablante.cargo if hablante else "CHAT"
        rect, (tx, ty) = geometria_pestana(f"{linea.nombre} - {cargo}", self.escenario.lado(linea))
        fondo, blanco, gris = (0, 0, 40), C["blanco"], C["gris"]
        pygame.draw.rect(sup, fondo, (rect.x, rect.y, rect.w, CAJA.y + 3 - rect.y))   # tapa el borde del cuadro
        # Borde exterior (blanco) e interior (gris) arriba y a los lados, hasta unirse con el cuadro
        pygame.draw.line(sup, blanco, rect.topleft, (rect.right - 1, rect.y))
        pygame.draw.line(sup, blanco, rect.topleft, (rect.x, CAJA.y))
        pygame.draw.line(sup, blanco, (rect.right - 1, rect.y), (rect.right - 1, CAJA.y))
        pygame.draw.line(sup, gris, (rect.x + 2, rect.y + 2), (rect.right - 3, rect.y + 2))
        pygame.draw.line(sup, gris, (rect.x + 2, rect.y + 2), (rect.x + 2, CAJA.y + 2))
        pygame.draw.line(sup, gris, (rect.right - 3, rect.y + 2), (rect.right - 3, CAJA.y + 2))
        pygame.draw.line(sup, gris, (rect.x, CAJA.y + 2), (rect.x + 2, CAJA.y + 2))         # empalme con
        pygame.draw.line(sup, gris, (rect.right - 3, CAJA.y + 2), (rect.right, CAJA.y + 2))  # el borde gris
        color = esc.COLORES_OPINION[self.segmento.categoria]
        dibujar_texto(sup, linea.nombre, (tx, ty), color)
        dibujar_texto(sup, f" - {cargo}", (tx + fuente(1).size(linea.nombre)[0], ty), gris)


PESTANA_ALTO = 16        # 2 de bordes + 1 de aire + 9 del texto (con tildes) + 1 de sombra + 1 de aire + 2


def geometria_pestana(texto: str, lado: str):
    """Rectángulo de la pestaña (desde su borde de arriba hasta el borde del cuadro) y dónde va
    el texto. El texto (9 px de alto, 10 con la sombra) queda entre el borde gris de arriba y el
    borde del cuadro, sin tocar ninguno."""
    ancho = fuente(1).size(texto)[0] + 14
    rect = pygame.Rect(0, CAJA.y - PESTANA_ALTO + 2, ancho, PESTANA_ALTO - 2)
    if lado == "derecha":
        rect.right = CAJA.right - 6
    else:
        rect.x = CAJA.x + 6
    return rect, (rect.x + 7, rect.y + 4)
