"""Escenarios de los reportajes del final: NOTICIERO, EN VIVO y LA CALLE (todo por código).

Cada escenario dibuja el ESCENARIO (de y = 0 hasta ESCENA_ALTO; debajo va el cuadro de diálogo)
con sus personajes. La parte fija se pinta una sola vez en una superficie y lo que se mueve
(bocas, parpadeos, cintillo, chat, corazones) se dibuja encima en cada cuadro.

Estilo: el de los fondos del juego (degradados por bandas, luces con halo, pixel art sin
suavizado) y los colores de categoría del HUD: medios cian, influencers magenta, pueblo amarillo.
Los fondos tienen pocos elementos y dejan el protagonismo a los personajes (bustos de 88 x 116,
assets/reportajes/), que se integran con la luz de cada escena (Luz: filo de luz, tono ambiente
y sombra en la pared). Los bustos nunca se estiran: el escritorio o el cuadro de diálogo tapan
su corte de abajo.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np
import pygame

import settings
from core.decision_tree import CAPTURAR, EXTRADITAR, LIBERAR
from core.reportajes import CANAL, VECINOS, Linea
from render import personajes as per
from render import paisajes
from render.hud import COLORES_OPINION
from render.paisajes import degradado
from render.texto import dibujar_texto, envolver, fuente
from render.ui import superficie_opaca

C = settings.COLORES
ANCHO = settings.ANCHO
ESCENA_ALTO = 160                       # de aquí para abajo: el cuadro de diálogo
SELLOS = {CAPTURAR: "¡CAPTURADO!", EXTRADITAR: "¡EXTRADITADO!", LIBERAR: "¡LIBRE!"}
COLOR_SELLO = {CAPTURAR: C["verde"], EXTRADITAR: C["cian"], LIBERAR: C["rojo"]}
ROJO_CANAL = (188, 27, 31)


def _halo(radio: int, color, alfa: int) -> pygame.Surface:
    """Círculo de luz que se desvanece hacia afuera (por anillos, como en render/paisajes.py)."""
    sup = pygame.Surface((radio * 2, radio * 2), pygame.SRCALPHA)
    for r in range(radio, 0, -2):
        a = int(alfa * (1 - r / radio) ** 1.5)
        pygame.draw.circle(sup, (*color, a), (radio, radio), r)
    return sup


def _cono(ancho_arriba: int, ancho_abajo: int, alto: int, alfa: int) -> pygame.Surface:
    """Haz de luz de un reflector."""
    sup = pygame.Surface((ancho_abajo, alto), pygame.SRCALPHA)
    centro = ancho_abajo // 2
    for i in range(4):
        k = 1 - i * 0.22
        arriba, abajo = ancho_arriba * k / 2, ancho_abajo * k / 2
        pygame.draw.polygon(sup, (255, 250, 220, alfa), [(centro - arriba, 0), (centro + arriba, 0),
                                                        (centro + abajo, alto), (centro - abajo, alto)])
    return sup


@dataclass(frozen=True)
class Luz:
    """Cómo ilumina una escena a sus personajes (para integrarlos con el fondo):
    borde: color del filo de luz; lados: de dónde viene ("izquierda", "derecha", "arriba");
    ambiente: tono que tiñe todo el personaje y fuerza (0..1) cuánto lo tiñe;
    sombra: desplazamiento (dx, dy) de la sombra en la pared, o None si no hay pared cerca."""
    borde: Tuple[int, int, int]
    lados: Tuple[str, ...]
    ambiente: Tuple[int, int, int] = (255, 255, 255)
    fuerza: float = 0.0
    sombra: Optional[Tuple[int, int]] = None


_integrados: Dict[tuple, pygame.Surface] = {}
_sombras: Dict[int, pygame.Surface] = {}


def integrar(imagen: pygame.Surface, luz: Luz) -> pygame.Surface:
    """El personaje con el tono ambiental de la escena y un filo de luz de 1 px del lado de la
    luz (el primer píxel de color junto al contorno negro). Cacheado."""
    clave = (id(imagen), luz)
    hecho = _integrados.get(clave)
    if hecho is not None:
        return hecho
    rgb = pygame.surfarray.array3d(imagen).astype(np.float64)       # (ancho, alto, 3)
    alfa = pygame.surfarray.array_alpha(imagen)
    opaco = alfa > 0
    vacio = ~opaco
    contorno = opaco & (rgb.sum(-1) < 45)
    color = opaco & ~contorno
    if luz.fuerza:
        tinte = np.array(luz.ambiente, np.float64) / max(luz.ambiente)
        rgb[color] = rgb[color] * (1 - luz.fuerza + luz.fuerza * tinte)
    desplazamientos = {"izquierda": (2, 0), "derecha": (-2, 0), "arriba": (0, 2)}
    borde = np.zeros_like(opaco)
    for lado in luz.lados:
        dx, dy = desplazamientos[lado]
        lejos = np.ones_like(vacio)                                   # fuera del lienzo = vacío
        w, h = vacio.shape
        lejos[max(dx, 0):w + min(dx, 0), max(dy, 0):h + min(dy, 0)] = \
            vacio[max(-dx, 0):w + min(-dx, 0), max(-dy, 0):h + min(-dy, 0)]
        borde |= color & lejos
    rgb[borde] = rgb[borde] * 0.5 + np.array(luz.borde, np.float64) * 0.5
    hecho = pygame.Surface(imagen.get_size(), pygame.SRCALPHA)
    pygame.surfarray.blit_array(hecho, np.clip(rgb, 0, 255).astype(np.uint8))
    pygame.surfarray.pixels_alpha(hecho)[:] = alfa
    if pygame.display.get_surface() is not None:
        hecho = hecho.convert_alpha()
    _integrados[clave] = hecho
    return hecho


def sombra_de(imagen: pygame.Surface) -> pygame.Surface:
    """La silueta del personaje en negro translúcido (su sombra en la pared)."""
    hecha = _sombras.get(id(imagen))
    if hecha is None:
        hecha = pygame.Surface(imagen.get_size(), pygame.SRCALPHA)
        hecha.fill((6, 4, 16, 0))
        pygame.surfarray.pixels_alpha(hecha)[:] = (pygame.surfarray.array_alpha(imagen) > 0) * 70
        _sombras[id(imagen)] = hecha
    return hecha


def busto(sup: pygame.Surface, clave: str, centro_x: int, y: int, hablando: bool, t: float,
          voltear: bool = False, luz: Luz = None) -> None:
    """Dibuja un personaje: centro_x = centro del lienzo (88 px), y = su borde de arriba. Si
    habla, mueve la boca y se balancea un píxel. Nunca se estira: las escenas tapan el corte de
    abajo del busto con el escritorio o con el cuadro de diálogo."""
    desfase = (sum(map(ord, clave)) % 17) / 5
    boca = per.boca_al_hablar(t) if hablando else 0
    imagen = per.retrato(clave, boca, per.parpadea(t, desfase), voltear)
    if hablando and int(t * 4) % 2:
        y -= 1
    x = centro_x - per.LIENZO[0] // 2
    if luz is not None:
        if luz.sombra:
            sup.blit(sombra_de(imagen), (x + luz.sombra[0], y + luz.sombra[1]))
        imagen = integrar(imagen, luz)
    sup.blit(imagen, (x, y))


def boca_de(centro_x: int, y: int, voltear: bool = False) -> Tuple[int, int]:
    """Dónde está la boca de un busto dibujado con busto(...)."""
    bx = per.BOCA_LIENZO[0] if not voltear else per.LIENZO[0] - 1 - per.BOCA_LIENZO[0]
    return centro_x - per.LIENZO[0] // 2 + bx, y + per.BOCA_LIENZO[1]


def alto_busto(clave: str) -> int:
    """Hasta qué fila llega el dibujo del busto (igual en todos sus estados)."""
    return per.retrato(clave).get_bounding_rect().bottom


def velo(tam: Tuple[int, int], color, alfa: int) -> pygame.Surface:
    capa = pygame.Surface(tam, pygame.SRCALPHA)
    capa.fill((*color, alfa))
    return capa


def medidor(sup: pygame.Surface, rect: pygame.Rect, categoria: str, valor: int, titulo: str) -> None:
    """La opinión final de una categoría, grande (para la intro y el cierre)."""
    color = COLORES_OPINION[categoria]
    dibujar_texto(sup, titulo, (rect.centerx, rect.y + 6), C["blanco"], centrado=True)
    dibujar_texto(sup, str(valor), (rect.centerx, rect.y + 18), color, 3, centrado=True)
    barra = pygame.Rect(rect.x + 8, rect.bottom - 14, rect.w - 16, 6)
    pygame.draw.rect(sup, (40, 40, 52), barra)
    pygame.draw.rect(sup, color, (barra.x, barra.y, round(barra.w * valor / 100), barra.h))
    pygame.draw.rect(sup, C["negro"], barra, 1)


# =============================================================================================
class Escenario:
    """Base. posiciones(): {clave: (centro_x, y, voltear)} de quienes están en cuadro;
    luz_de(clave, linea): cómo los ilumina la escena."""
    categoria = ""

    def __init__(self, juego, jefes_sprite: List[str], opinion: int):
        self.juego = juego
        self.jefes_sprite = jefes_sprite          # nombre del sprite del jefe de cada nivel
        self.opinion = opinion                    # opinión final de la categoría
        self.fondo = superficie_opaca((ANCHO, ESCENA_ALTO))
        self.rng = random.Random(self.categoria)
        self.pintar_fondo()

    def luz_de(self, clave: str, linea: Linea) -> Optional[Luz]:
        return None

    _velo_contraste: Optional[pygame.Surface] = None

    def _velar(self, s: pygame.Surface) -> None:
        """Alto contraste (Opciones): oscurece el FONDO como en los niveles (velo negro de 170),
        para que resalten los personajes y los textos. Se llama justo después del fondo."""
        if not self.juego.opciones.get("alto_contraste", False):
            return
        if Escenario._velo_contraste is None:
            Escenario._velo_contraste = velo((ANCHO, ESCENA_ALTO), (0, 0, 0), 170)
        s.blit(Escenario._velo_contraste, (0, 0))

    def pintar_fondo(self) -> None:
        raise NotImplementedError

    def posiciones(self, linea: Linea) -> Dict[str, Tuple[int, int, bool]]:
        raise NotImplementedError

    def lado(self, linea: Linea) -> str:
        """De qué lado de la pantalla está quien habla (para la pestaña del nombre)."""
        pos = self.posiciones(linea).get(linea.hablante)
        return "derecha" if pos and pos[0] > ANCHO // 2 else "izquierda"

    def al_cambiar(self, anterior: Optional[Linea], linea: Linea) -> bool:
        """True si el cambio de línea merece cortina (p. ej. otro lugar del país)."""
        return False

    def dibujar(self, sup: pygame.Surface, linea: Linea, hablando: bool, t: float, t_linea: float) -> None:
        raise NotImplementedError

    def _personajes(self, sup, linea: Linea, hablando: bool, t: float) -> None:
        for clave, (cx, y, voltear) in self.posiciones(linea).items():
            busto(sup, clave, cx, y, hablando and clave == linea.hablante, t, voltear, self.luz_de(clave, linea))


# =============================================================================================
class Noticiero(Escenario):
    """Estudio de VENTANA 7 TV en plano medio: la presentadora a la izquierda y el analista a la
    derecha, cada uno delante de una columna de luz; entre ellos, la pantalla con el jefe del que
    se habla; delante, el escritorio (tapa el corte de los bustos). Arriba, el cintillo."""
    categoria = "medios"
    PANTALLA = pygame.Rect(90, 20, 76, 58)
    MESA_Y = 122                                 # borde de arriba del escritorio
    PRESENTADORA = (46, 40)                      # (centro del lienzo, borde de arriba)
    ANALISTA = (210, 40)
    COLUMNAS = (pygame.Rect(14, 14, 64, 108), pygame.Rect(178, 14, 64, 108))
    CIAN = (120, 200, 255)

    def __init__(self, juego, jefes_sprite, opinion, titulares: List[str]):
        self.titulares = titulares
        super().__init__(juego, jefes_sprite, opinion)
        self._jefes: Dict[int, pygame.Surface] = {}
        self._lineas = None
        self.cinta = "   +++   ".join(t.upper() for t in titulares) + "   +++   "
        self._mesa_sup = self._pintar_mesa()

    def pintar_fondo(self):
        s = self.fondo
        degradado(s, 0, ESCENA_ALTO, [(8, 11, 28), (16, 24, 52), (24, 38, 78), (12, 18, 40)], 14)
        # Columnas de luz detrás de cada presentador: separan a los personajes del fondo
        for col in self.COLUMNAS:
            for i in range(col.w // 2):
                k = (i / (col.w / 2)) ** 1.6                              # más claro al centro
                c = tuple(int(a + (b - a) * k) for a, b in zip((16, 24, 52), (40, 70, 130)))
                pygame.draw.line(s, c, (col.x + i, col.y), (col.x + i, col.bottom))
                pygame.draw.line(s, c, (col.right - 1 - i, col.y), (col.right - 1 - i, col.bottom))
            pygame.draw.line(s, (70, 140, 210), (col.x, col.y), (col.x, col.bottom))
            pygame.draw.line(s, (70, 140, 210), (col.right - 1, col.y), (col.right - 1, col.bottom))
            pygame.draw.line(s, self.CIAN, (col.x, col.y), (col.right - 1, col.y))
        # Línea del horizonte del set (zócalo con luz)
        pygame.draw.rect(s, (10, 14, 32), (0, self.MESA_Y - 10, ANCHO, 10))
        pygame.draw.line(s, (40, 90, 150), (0, self.MESA_Y - 10), (ANCHO, self.MESA_Y - 10))
        # Halo y marco de la pantalla (soportes al techo)
        p = self.PANTALLA
        s.blit(_halo(60, self.CIAN, 40), (p.centerx - 60, p.centery - 60))
        for x in (p.x + 14, p.right - 15):
            pygame.draw.line(s, (60, 70, 90), (x, 11), (x, p.y - 4))
        marco = p.inflate(8, 8)
        pygame.draw.rect(s, (13, 9, 10), marco.inflate(2, 2))
        pygame.draw.rect(s, (52, 58, 70), marco)
        pygame.draw.line(s, (117, 131, 141), marco.topleft, (marco.right - 1, marco.y))
        pygame.draw.line(s, (117, 131, 141), marco.topleft, (marco.x, marco.bottom - 1))
        pygame.draw.line(s, (30, 32, 40), (marco.x, marco.bottom - 1), (marco.right - 1, marco.bottom - 1))
        pygame.draw.rect(s, (13, 9, 10), p.inflate(2, 2))
        s.set_at((marco.right - 4, marco.bottom - 3), (110, 230, 120))      # piloto de encendido

    def _pintar_mesa(self) -> pygame.Surface:
        """El escritorio (delante de los personajes), pintado una vez."""
        m = pygame.Surface((ANCHO, ESCENA_ALTO - self.MESA_Y + 2), pygame.SRCALPHA)
        # Cubierta brillante con reflejo
        pygame.draw.rect(m, (13, 9, 10), (0, 0, ANCHO, 8))
        degradado(m, 1, 7, [(240, 240, 240), (180, 191, 199), (117, 131, 141)], 3)
        for x in range(30, ANCHO, 64):
            pygame.draw.line(m, (255, 255, 255), (x, 2), (x + 18, 2))
        # Frente azul con franja roja y el logo del canal
        degradado(m, 8, m.get_height(), [(32, 51, 99), (19, 29, 55)], 6)
        pygame.draw.line(m, (13, 9, 10), (0, 8), (ANCHO, 8))
        pygame.draw.rect(m, ROJO_CANAL, (0, 14, ANCHO, 3))
        pygame.draw.line(m, (13, 9, 10), (0, 17), (ANCHO, 17))
        for x in (64, 192):                                                 # paneles
            pygame.draw.line(m, (13, 9, 10), (x, 9), (x, m.get_height()))
            pygame.draw.line(m, (52, 74, 130), (x + 1, 9), (x + 1, m.get_height()))
        logo = pygame.Rect(0, 0, 72, 13)
        logo.center = (ANCHO // 2, 16)            # por encima de la pestaña del nombre (y ~ 150)
        pygame.draw.rect(m, (13, 9, 10), logo.inflate(2, 2))
        pygame.draw.rect(m, ROJO_CANAL, logo)
        pygame.draw.line(m, (230, 80, 70), logo.topleft, (logo.right - 1, logo.y))
        dibujar_texto(m, CANAL, (logo.centerx, logo.y + 2), C["blanco"], centrado=True)
        return m

    def posiciones(self, linea):
        return {"presentadora": (*self.PRESENTADORA, False), "analista": (*self.ANALISTA, True)}

    def luz_de(self, clave, linea):
        """La luz de la pantalla (del centro) y la de su columna (por detrás): filo cian hacia el
        centro y arriba; la sombra cae en la pared, hacia afuera."""
        izquierda = clave == "presentadora"
        return Luz(self.CIAN, ("derecha" if izquierda else "izquierda", "arriba"), (190, 210, 255), 0.12,
                   (-4, 2) if izquierda else (4, 2))

    def _jefe(self, nivel: int) -> pygame.Surface:
        if nivel not in self._jefes:
            imagen = self.juego.sprites.frame(self.jefes_sprite[nivel - 1], "quieto", 0, voltear=True)
            alto = min(imagen.get_height(), self.PANTALLA.h - 14)        # de la cintura para arriba
            self._jefes[nivel] = imagen.subsurface((0, 0, imagen.get_width(), alto)).copy()
        return self._jefes[nivel]

    _velos_cinta: Dict[int, pygame.Surface] = {}

    def _velo_cinta(self, alfa: int) -> pygame.Surface:
        if alfa not in self._velos_cinta:
            self._velos_cinta[alfa] = velo((1, 11), (13, 9, 10), alfa)
        return self._velos_cinta[alfa]

    def _barrido(self) -> pygame.Surface:
        if self._lineas is None:
            self._lineas = pygame.Surface(self.PANTALLA.size, pygame.SRCALPHA)
            for y in range(0, self.PANTALLA.h, 3):
                pygame.draw.line(self._lineas, (0, 0, 0, 70), (0, y), (self.PANTALLA.w, y))
        return self._lineas

    def _pantalla(self, s, linea: Linea, t: float, t_linea: float):
        p = self.PANTALLA
        anterior = s.get_clip()
        s.set_clip(p)
        if linea.decision is None:                                        # intro o cierre
            degradado(s, p.top, p.bottom, [(19, 29, 55), (7, 51, 147)], 6)
            medidor(s, p, "medios", self.opinion, "MEDIOS")
        else:
            color = COLOR_SELLO[linea.decision]
            degradado(s, p.top, p.bottom, [(13, 9, 10), tuple(v // 3 for v in color)], 6)
            for i in range(-2, 8):                                        # rayas que avanzan
                x = p.x + i * 16 + int(t * 12) % 16
                pygame.draw.line(s, tuple(v // 4 + 10 for v in color), (x, p.bottom), (x + 30, p.top))
            jefe = self._jefe(linea.nivel)
            s.blit(jefe, jefe.get_rect(midbottom=(p.centerx + 6, p.bottom - 12)))
            dibujar_texto(s, f"NIVEL {linea.nivel}", (p.x + 3, p.y + 2), C["blanco"])
            banda = pygame.Rect(p.x, p.bottom - 13, p.w, 13)
            pygame.draw.rect(s, (13, 9, 10), banda)
            if t_linea > 0.25 or int(t_linea * 16) % 2:                   # el sello parpadea al aparecer
                sello = "¡ESCAPÓ!" if linea.escapo else SELLOS[linea.decision]
                dibujar_texto(s, sello, (banda.centerx, banda.y + 3), color, centrado=True)
        s.blit(self._barrido(), p.topleft)                                 # líneas de barrido
        s.set_clip(anterior)

    def _cintillo(self, s, t: float):
        """ÚLTIMA HORA arriba: logo V7 y los titulares corriendo; EN VIVO debajo."""
        pygame.draw.rect(s, (13, 9, 10), (0, 0, ANCHO, 11))
        pygame.draw.rect(s, ROJO_CANAL, (0, 0, 22, 11))
        dibujar_texto(s, "V7", (11, 1), C["blanco"], centrado=True, sombra=False)
        anterior = s.get_clip()
        inicio = 27                                             # 5 px de aire después del logo
        s.set_clip(pygame.Rect(inicio, 0, ANCHO - inicio, 11))
        ancho_cinta = fuente(1).size(self.cinta)[0]
        x = inicio - int(t * 30) % ancho_cinta
        while x < ANCHO:
            dibujar_texto(s, self.cinta, (x, 1), C["blanco"], sombra=False)
            x += ancho_cinta
        s.set_clip(anterior)
        for i, alfa in enumerate((220, 150, 80)):                # el texto entra difuminado
            s.blit(self._velo_cinta(alfa), (inicio + i, 0))
        pygame.draw.rect(s, (13, 9, 10), (3, 13, fuente(1).size("EN VIVO")[0] + 15, 11))
        if int(t * 1.5) % 2 == 0:
            pygame.draw.circle(s, C["rojo"], (8, 18), 2)
        dibujar_texto(s, "EN VIVO", (13, 13), C["blanco"], sombra=False)

    def dibujar(self, s, linea, hablando, t, t_linea):
        s.blit(self.fondo, (0, 0))
        self._velar(s)
        self._pantalla(s, linea, t, t_linea)
        self._personajes(s, linea, hablando, t)
        s.blit(self._mesa_sup, (0, self.MESA_Y))
        self._cintillo(s, t)


# =============================================================================================
class EnVivo(Escenario):
    """El cuarto de @NICOVIRAL transmitiendo, en plano medio: el aro de luz detrás de su cabeza,
    la silla, la tira de LED y el neón; delante, el escritorio con el teclado (tapa el corte del
    busto). Encima, la interfaz del directo (EN VIVO, espectadores, chat y corazones)."""
    categoria = "influencers"
    CHAT = pygame.Rect(162, 18, 90, 126)      # termina antes de la pestaña del nombre (y = 150)
    INFLUENCER = (88, 42)                           # (centro del lienzo, borde de arriba)
    ARO = (86, 64, 40)                        # centro y radio: rodea la cabeza (4 px libres del neón)
    MESA_Y = 130
    ROSA = (255, 130, 235)
    MENSAJES = {
        None: [("@LUCHO_FIT", "HOLAAA"), ("@MAFE.23", "PRIMERA"), ("@TIOMEMES", "JAJAJA"),
               ("@KEVIN", "SALUDOS DESDE CALI"), ("@ANITA", "TE AMO NICO")],
        CAPTURAR: [("@LUCHO_FIT", "MANO DURA"), ("@ANITA", "#JUSTICIAYA"), ("@KEVIN", "POR FIN"),
                   ("@MAFE.23", "QUE LO GRABEN")],
        EXTRADITAR: [("@KEVIN", "Y EL AVION?"), ("@ANITA", "ELEGANTE"), ("@MAFE.23", "MUY DIPLOMATICO"),
                     ("@LUCHO_FIT", "Y LOS JUECES?")],
        LIBERAR: [("@KEVIN", "QUEEEE"), ("@ANITA", "#NIUNCAPOLIBRE"), ("@MAFE.23", "NOOO"),
                  ("@LUCHO_FIT", "RENUNCIE")],
    }
    ETIQUETAS = {CAPTURAR: "#JUSTICIAYA", EXTRADITAR: "#EXTRADITADOYA", LIBERAR: "#NIUNCAPOLIBRE"}
    COLORES_AUTOR = [(60, 188, 252), (246, 217, 104), (110, 230, 120), (252, 152, 56), (228, 92, 220)]

    def __init__(self, juego, jefes_sprite, opinion):
        super().__init__(juego, jefes_sprite, opinion)
        self.chat: List[Tuple[str, str]] = []
        self.fijado: Optional[Tuple[str, str]] = None   # la pregunta que el influencer responde
        self.t_chat = 0.0
        self.i_chat = 0
        self.ultima: Optional[Linea] = None
        self.corazones: List[List[float]] = []
        self.espectadores = 1200

    def pintar_fondo(self):
        s = self.fondo
        degradado(s, 0, ESCENA_ALTO, [(22, 8, 34), (46, 18, 64), (34, 14, 50)], 14)
        # Tira de LED arriba, con su resplandor sobre la pared
        s.blit(_cono(ANCHO, ANCHO, 46, 9), (0, 0))
        pygame.draw.rect(s, (228, 92, 220), (0, 0, ANCHO, 2))
        for x in range(2, ANCHO, 6):
            s.set_at((x, 0), (255, 210, 250))
        # Neón "NICO" arriba a la izquierda: entre la fila de rótulos y el aro, sin tocar a nadie
        s.blit(_halo(30, (228, 92, 220), 60), (0, 2))
        dibujar_texto(s, "NICO", (4, 24), (255, 170, 245), 2, sombra=False)
        # Respaldo de la silla gamer
        cx, cy, r = self.ARO
        silla = pygame.Rect(0, 0, 60, 90)
        silla.midtop = (cx, cy - 18)
        pygame.draw.rect(s, (13, 9, 10), silla.inflate(2, 2), border_radius=12)
        pygame.draw.rect(s, (36, 18, 46), silla, border_radius=12)
        for dx in (8, silla.w - 12):
            pygame.draw.rect(s, (200, 70, 190), (silla.x + dx, silla.y + 8, 4, silla.h - 8))
        # Aro de luz con su halo
        s.blit(_halo(r + 22, (255, 230, 250), 70), (cx - r - 22, cy - r - 22))
        pygame.draw.circle(s, (13, 9, 10), (cx, cy), r + 1, 7)
        pygame.draw.circle(s, (245, 230, 245), (cx, cy), r, 5)
        pygame.draw.circle(s, (255, 255, 255), (cx, cy), r - 1, 2)
        pygame.draw.line(s, (13, 9, 10), (cx, cy + r + 1), (cx, self.MESA_Y))   # el pie del aro

    def _mesa(self, s, t: float):
        """Escritorio delante: madera oscura, teclado con luces y una lata."""
        y = self.MESA_Y
        pygame.draw.rect(s, (13, 9, 10), (0, y, self.CHAT.x - 2, ESCENA_ALTO - y))
        degradado(s, y + 1, ESCENA_ALTO, [(88, 68, 39), (51, 42, 33), (30, 24, 20)], 5)
        pygame.draw.line(s, (175, 142, 98), (0, y + 1), (self.CHAT.x - 3, y + 1))
        kx = self.INFLUENCER[0] - 36                                   # teclado centrado frente a él
        pygame.draw.rect(s, (13, 9, 10), (kx, y - 4, 72, 8))
        pygame.draw.rect(s, (74, 79, 82), (kx + 1, y - 3, 70, 6))
        for x in range(kx + 3, kx + 69, 4):
            pygame.draw.rect(s, ((228, 92, 220), (60, 188, 252))[(x // 4 + int(t * 6)) % 2], (x, y - 1, 2, 1))
        lx = self.INFLUENCER[0] + 48                                   # la lata, a su derecha
        pygame.draw.rect(s, (13, 9, 10), (lx, y - 13, 9, 15))
        pygame.draw.rect(s, (110, 230, 120), (lx + 1, y - 12, 7, 13))
        pygame.draw.rect(s, (240, 240, 240), (lx + 1, y - 8, 7, 3))

    def posiciones(self, linea):
        return {"influencer": (*self.INFLUENCER, False)}

    def lado(self, linea):
        return "derecha" if linea.hablante.startswith("@") else "izquierda"

    def luz_de(self, clave, linea):
        """El aro y el LED por detrás: filo rosado arriba y a los dos lados, tono violeta."""
        return Luz(self.ROSA, ("izquierda", "derecha", "arriba"), (230, 190, 255), 0.14)

    def _nuevo_mensaje(self, linea: Linea) -> None:
        pool = self.MENSAJES[linea.decision if linea else None]
        if linea is None:
            self.chat.append(pool[len(self.chat) % len(pool)])
            return
        autor, texto = pool[self.i_chat % len(pool)]
        self.i_chat += 1
        self.chat.append((autor, texto))
        self.chat = self.chat[-12:]

    def actualizar(self, linea: Linea, dt: float) -> None:
        if not self.chat:                                        # el directo ya venía andando
            for _ in range(4):
                self._nuevo_mensaje(None)
            for _ in range(2):
                self._nuevo_mensaje(linea)
        if linea is not self.ultima:
            if linea.hablante.startswith("@"):
                # La pregunta llega por el chat y queda FIJADA arriba mientras el influencer la
                # responde; los demás mensajes siguen llegando debajo
                self.fijado = (linea.nombre, linea.texto.upper())
                self.t_chat = -1.0
            elif linea.parte != "decision":                          # respondida: se suelta
                self.fijado = None
            self.ultima = linea
        self.t_chat += dt
        if self.t_chat > 1.1:
            self.t_chat = 0.0
            self._nuevo_mensaje(linea)
            self.espectadores += self.rng.randint(5, 60)
        if self.rng.random() < dt * (5 if linea.decision == CAPTURAR else 2):
            self.corazones.append([self.CHAT.x - 14 + self.rng.uniform(-6, 6), self.MESA_Y - 10, 0.0])
        for c in self.corazones:
            c[1] -= 28 * dt
            c[2] += dt
        self.corazones = [c for c in self.corazones if c[2] < 2.5]

    def _corazon(self, s, x, y, color):
        pygame.draw.rect(s, color, (x, y + 1, 7, 3))
        pygame.draw.rect(s, color, (x + 1, y, 2, 1))
        pygame.draw.rect(s, color, (x + 4, y, 2, 1))
        pygame.draw.rect(s, color, (x + 1, y + 4, 5, 1))
        pygame.draw.rect(s, color, (x + 2, y + 5, 3, 1))

    @staticmethod
    def _pastilla(s, x: int, texto: str, fondo, color, y: int = 4, icono: str = None) -> int:
        """Rótulo de 11 px de alto de la interfaz del directo, con un ícono opcional a la izquierda
        ("punto", "punto_apagado" u "ojo"). El texto (7 px de mayúsculas) queda centrado.
        Devuelve la x donde termina."""
        ancho_icono = {"ojo": 9, "punto": 6, "punto_apagado": 6}.get(icono, 0)
        rect = pygame.Rect(x, y, fuente(1).size(texto)[0] + 8 + ancho_icono, 11)
        pygame.draw.rect(s, fondo, rect)
        ix = rect.x + 4
        if icono == "ojo":
            pygame.draw.ellipse(s, color, (ix, y + 3, 7, 5), 1)
            pygame.draw.rect(s, color, (ix + 3, y + 5, 1, 1))
        elif icono == "punto":
            pygame.draw.circle(s, color, (ix + 1, y + 5), 2)
        dibujar_texto(s, texto, (ix + ancho_icono, y), color, sombra=False)
        return rect.right

    ALTO_LINEA_CHAT = 10

    def _mensaje(self, s, x: int, y: int, autor: str, lineas: List[str], color_autor) -> None:
        dibujar_texto(s, autor, (x, y), color_autor, sombra=False)
        for i, linea in enumerate(lineas):
            dibujar_texto(s, linea, (x, y + self.ALTO_LINEA_CHAT * (i + 1)), C["blanco"], sombra=False)

    @staticmethod
    def _chincheta(s, x: int, y: int, color) -> None:
        """Ícono de mensaje fijado (5 x 7)."""
        pygame.draw.rect(s, color, (x + 1, y, 3, 1))
        pygame.draw.rect(s, color, (x, y + 1, 5, 3))
        pygame.draw.rect(s, color, (x + 2, y + 4, 1, 3))

    def caja_fijado(self) -> Optional[pygame.Rect]:
        """Dónde va el mensaje fijado (justo bajo el encabezado del chat), o None si no hay."""
        if not self.fijado:
            return None
        lineas = envolver(self.fijado[1], 1, self.CHAT.w - 10)
        return pygame.Rect(self.CHAT.x + 2, self.CHAT.y + 13, self.CHAT.w - 4,
                           self.ALTO_LINEA_CHAT * (1 + len(lineas)) + 4)

    def _panel_chat(self, s):
        p = self.CHAT
        velo_chat = pygame.Surface(p.size, pygame.SRCALPHA)
        velo_chat.fill((10, 6, 18, 200))
        s.blit(velo_chat, p.topleft)
        pygame.draw.rect(s, (228, 92, 220), p, 1)
        pygame.draw.rect(s, (228, 92, 220), (p.x, p.y, p.w, 11))
        dibujar_texto(s, "CHAT", (p.x + 4, p.y + 2), C["blanco"], sombra=False)
        tope = p.y + 13                                   # hasta dónde pueden subir los mensajes
        caja = self.caja_fijado()
        if caja is not None:                              # la pregunta fijada, arriba y quieta
            autor, texto = self.fijado
            pygame.draw.rect(s, (90, 40, 10), caja)
            pygame.draw.rect(s, C["amarillo"], caja, 1)
            self._mensaje(s, caja.x + 3, caja.y + 2, autor, envolver(texto, 1, p.w - 10), C["amarillo"])
            self._chincheta(s, caja.right - 8, caja.y + 3, C["amarillo"])
            tope = caja.bottom + 3
        # Los demás, de abajo hacia arriba (lo más nuevo abajo). Un mensaje que no cabe entero no
        # se dibuja: nada queda cortado a la mitad ni tapa al fijado.
        y = p.bottom - 3
        for autor, texto in reversed(self.chat):
            lineas = envolver(texto, 1, p.w - 10)
            y -= self.ALTO_LINEA_CHAT * (1 + len(lineas)) + 3
            if y < tope:
                break
            self._mensaje(s, p.x + 5, y, autor, lineas, self.COLORES_AUTOR[sum(map(ord, autor)) % 5])

    def dibujar(self, s, linea, hablando, t, t_linea):
        s.blit(self.fondo, (0, 0))
        self._velar(s)
        self._personajes(s, linea, hablando, t)
        self._mesa(s, t)
        # Interfaz del directo: una fila de pastillas de 11 px (el texto, de 7 px, centrado)
        x = 4
        x = self._pastilla(s, x, "EN VIVO", C["rojo"], C["blanco"],
                           icono="punto" if int(t * 1.5) % 2 == 0 else "punto_apagado")
        x = self._pastilla(s, x + 3, f"{self.espectadores / 1000:.1f}K", (13, 9, 10), C["blanco"], icono="ojo")
        if linea.decision is not None:                           # la tendencia del momento
            etiqueta = "#SEVOLÓ" if linea.escapo else self.ETIQUETAS[linea.decision]
            self._pastilla(s, x + 3, etiqueta, (13, 9, 10), (255, 170, 245))
        else:                                                    # intro o cierre: la opinión
            color = COLORES_OPINION["influencers"]
            fin = self._pastilla(s, x + 3, f"INFLUENCERS {self.opinion}", (13, 9, 10), color)
            pygame.draw.rect(s, (40, 40, 52), (x + 3, 15, fin - x - 3, 2))
            pygame.draw.rect(s, color, (x + 3, 15, round((fin - x - 3) * self.opinion / 100), 2))
        self._panel_chat(s)
        for x, y, edad in self.corazones:
            color = (228, 92, 220) if int(x) % 2 else (188, 27, 31)
            self._corazon(s, int(x + math.sin(edad * 4) * 3), int(y), color)


# =============================================================================================
class Calle(Escenario):
    """Entrevista en la calle, en plano medio, delante del paisaje del nivel del que se habla (la
    selva, la ciudad, la frontera), un poco velado para que resalten los personajes: la reportera
    con su micrófono y el vecino de ese lugar. El cuadro de diálogo tapa el corte de los bustos.
    Encima, el visor de la cámara (REC, esquinas, hora y batería)."""
    categoria = "pueblo"
    REPORTERA_X, VECINO_X = 82, 176              # centro del lienzo de cada uno
    PIE = 163             # el borde de abajo de cada busto queda aquí, bajo el cuadro de diálogo
    SUELO_Y = 132
    # Luz de cada lugar: filo, de dónde viene, tono ambiente y su fuerza
    LUCES = {
        1: Luz((235, 245, 170), ("izquierda", "arriba"), (200, 240, 190), 0.12),   # selva: sol filtrado
        2: Luz((255, 150, 190), ("izquierda", "arriba"), (230, 170, 210), 0.18),   # Medellín: neón de noche
        3: Luz((255, 225, 150), ("derecha", "arriba"), (255, 230, 190), 0.12),     # La Guajira: sol a la derecha
    }
    VELO = {1: (30, 60, 30), 2: (30, 12, 40), 3: (120, 90, 60)}   # aire entre los personajes y el fondo

    def __init__(self, juego, jefes_sprite, opinion, ambientes: Dict[int, dict]):
        self.ambientes = ambientes
        super().__init__(juego, jefes_sprite, opinion)
        self._paisajes: Dict[int, object] = {}
        self._velos: Dict[int, pygame.Surface] = {}
        # Sin sprite propio, la reportera no trae micrófono: el juego le dibuja uno en la mano
        self.mic_dibujado = not per.tiene_propio("reportera")

    def pintar_fondo(self):
        pass                                                     # el fondo es el paisaje del nivel

    @staticmethod
    def nivel_vista(linea: Linea) -> int:
        """El lugar que se ve: el del nivel del reportaje."""
        return linea.nivel or 1

    @classmethod
    def vecino(cls, linea: Linea) -> str:
        return "carmen" if linea.parte == "cierre" else VECINOS[cls.nivel_vista(linea)]

    def posiciones(self, linea):
        """Cada busto apoyado por su borde de abajo en PIE (los dibujos terminan a distinta
        altura): nunca se ve su corte y no se estiran."""
        vecino = self.vecino(linea)
        return {"reportera": (self.REPORTERA_X, self.PIE - alto_busto("reportera"), False),
                vecino: (self.VECINO_X, self.PIE - alto_busto(vecino), True)}

    def luz_de(self, clave, linea):
        return self.LUCES.get(self.nivel_vista(linea))

    def al_cambiar(self, anterior, linea):
        """Cortina cuando cambia el lugar o el entrevistado."""
        return anterior is not None and (self.nivel_vista(anterior), self.vecino(anterior)) != \
            (self.nivel_vista(linea), self.vecino(linea))

    def _paisaje(self, nivel: int):
        if nivel not in self._paisajes:
            self._paisajes[nivel] = paisajes.crear(self.ambientes[nivel])
        return self._paisajes[nivel]

    def _velo(self, nivel: int) -> pygame.Surface:
        """Velo en degradado (más denso abajo, donde están los personajes): da profundidad."""
        if nivel not in self._velos:
            capa = pygame.Surface((ANCHO, ESCENA_ALTO), pygame.SRCALPHA)
            color = self.VELO.get(nivel, (20, 20, 30))
            for y in range(ESCENA_ALTO):
                pygame.draw.line(capa, (*color, int(30 + 50 * y / ESCENA_ALTO)), (0, y), (ANCHO, y))
            self._velos[nivel] = capa
        return self._velos[nivel]

    def _suelo(self, s, nivel: int):
        amb = self.ambientes[nivel]
        borde, suelo = amb.get("suelo_borde", (150, 146, 156)), amb.get("suelo", (74, 64, 74))
        y = self.SUELO_Y
        pygame.draw.rect(s, suelo, (0, y, ANCHO, ESCENA_ALTO - y))
        pygame.draw.rect(s, borde, (0, y, ANCHO, 2))
        pygame.draw.line(s, (13, 9, 10), (0, y + 2), (ANCHO, y + 2))

    def _microfono(self, s, linea: Linea, t: float):
        """Solo si la reportera es el dibujo por código: un micrófono en su mano, bajo la boca."""
        bx, by = boca_de(self.REPORTERA_X, self.PIE - alto_busto("reportera"))
        mano = (bx + 6, by + 22 + int(math.sin(t * 2)))
        cabeza = (bx + 8, by + 8)
        pygame.draw.line(s, (13, 9, 10), mano, cabeza, 4)
        pygame.draw.circle(s, (13, 9, 10), cabeza, 5)
        pygame.draw.circle(s, (158, 165, 173), cabeza, 4)
        cubo = pygame.Rect(0, 0, 8, 6)
        cubo.center = ((mano[0] + cabeza[0]) // 2, (mano[1] + cabeza[1]) // 2 + 2)
        pygame.draw.rect(s, (13, 9, 10), cubo.inflate(2, 2))
        pygame.draw.rect(s, ROJO_CANAL, cubo)

    def _visor(self, s, t: float, linea: Linea):
        blanco = C["blanco"]
        for x, y, dx, dy in ((4, 4, 1, 1), (ANCHO - 5, 4, -1, 1), (4, ESCENA_ALTO - 5, 1, -1),
                             (ANCHO - 5, ESCENA_ALTO - 5, -1, -1)):
            pygame.draw.line(s, blanco, (x, y), (x + 8 * dx, y))
            pygame.draw.line(s, blanco, (x, y), (x, y + 8 * dy))
        if int(t * 1.5) % 2 == 0:
            pygame.draw.circle(s, C["rojo"], (14, 14), 3)
        dibujar_texto(s, "REC", (20, 9), blanco)
        segundos = int(t)
        dibujar_texto(s, f"00:{segundos // 60:02d}:{segundos % 60:02d}", (ANCHO - 12, 9), blanco, derecha=True)
        pygame.draw.rect(s, blanco, (ANCHO - 26, 21, 12, 7), 1)                  # batería
        pygame.draw.rect(s, blanco, (ANCHO - 14, 23, 2, 3))
        pygame.draw.rect(s, (110, 230, 120), (ANCHO - 24, 23, 8, 3))
        nivel = self.nivel_vista(linea)
        lugar = {1: "VICHADA", 2: "MEDELLÍN", 3: "LA GUAJIRA"}.get(nivel, "")
        dibujar_texto(s, lugar, (12, 20), C["amarillo"])
        if linea.decision is None:                               # intro o cierre: la opinión
            texto = f"PUEBLO {self.opinion}"
            dibujar_texto(s, texto, (12, 31), COLORES_OPINION["pueblo"])
            ancho = fuente(1).size(texto)[0]
            pygame.draw.rect(s, (40, 40, 52), (12, 42, ancho, 3))
            pygame.draw.rect(s, COLORES_OPINION["pueblo"], (12, 42, round(ancho * self.opinion / 100), 3))

    def dibujar(self, s, linea, hablando, t, t_linea):
        nivel = self.nivel_vista(linea)
        anterior = s.get_clip()
        s.set_clip(pygame.Rect(0, 0, ANCHO, ESCENA_ALTO))
        paisaje = self._paisaje(nivel)
        if paisaje is not None:
            paisaje.dibujar(s, 40 + t * 6, t)
        else:
            s.fill((40, 40, 60))
        self._suelo(s, nivel)
        s.blit(self._velo(nivel), (0, 0))
        self._velar(s)
        self._personajes(s, linea, hablando, t)
        if self.mic_dibujado:
            self._microfono(s, linea, t)
        self._visor(s, t, linea)
        s.set_clip(anterior)
