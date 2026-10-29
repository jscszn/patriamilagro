"""Carga de sprites desde assets/sprites.json con respaldo a los placeholders de pixelart.py.

Para reemplazar un gráfico: pon la hoja PNG en assets/sprites/ y en sprites.json indica
el archivo, el tamaño de cada cuadro, el ancla (punto de los pies) y qué cuadros forman
cada animación. Cada cuadro puede ser un índice de la hoja ("archivo") o la ruta de un PNG
suelto (así están las poses del presidente). Si no hay PNG, se usa el dibujo por código.

Cuando un sprite SÍ tiene PNG, nunca se mezcla con el placeholder: una animación que falte
usa su base del PNG ("correr_diag_arriba" -> "correr") o, si tampoco está, "quieto".
"agachado" se deriva aplastando "quieto" si el PNG no lo trae.
La lógica del juego no cambia: solo pide (nombre, animación, tiempo).
"""
from __future__ import annotations

import json
import os
from typing import Dict, List, Tuple

import pygame

import settings
from render import animacion
from render.pixelart import GENERADORES

RUTA_JSON = os.path.join(settings.RUTA_ASSETS, "sprites.json")


class GestorSprites:
    def __init__(self, ruta_json: str = RUTA_JSON):
        self.config: Dict[str, dict] = {}
        try:
            with open(ruta_json, encoding="utf-8") as f:
                self.config = {k: v for k, v in json.load(f).items() if not k.startswith("_")}
        except (OSError, ValueError) as error:
            print(f"[sprites] No se pudo leer {ruta_json}: {error}. Se usan placeholders.")
        self._anims: Dict[str, Dict[str, List[pygame.Surface]]] = {}
        self._volteados: Dict[Tuple[str, str, int], pygame.Surface] = {}
        self._siluetas: Dict[Tuple[int, tuple], pygame.Surface] = {}
        self._imagenes: Dict[str, pygame.Surface] = {}
        self._contornos: Dict[Tuple[int, tuple], pygame.Surface] = {}
        self._escaladas: Dict[Tuple[int, tuple], pygame.Surface] = {}

    def _imagen(self, ruta_relativa: str):
        """PNG de assets/ (con caché), o None si no existe."""
        if ruta_relativa not in self._imagenes:
            ruta = os.path.join(settings.RUTA_ASSETS, ruta_relativa)
            if not os.path.isfile(ruta):
                return None
            imagen = pygame.image.load(ruta)
            if pygame.display.get_surface() is not None:
                imagen = imagen.convert_alpha()
            self._imagenes[ruta_relativa] = imagen
        return self._imagenes[ruta_relativa]

    def _cargar(self, nombre: str) -> Dict[str, List[pygame.Surface]]:
        anims = dict(GENERADORES[nombre]()) if nombre in GENERADORES else {}
        conf = self.config.get(nombre)
        if conf and self.tiene_png(nombre):
            hoja = self._imagen(conf["archivo"]) if conf.get("archivo") else None
            ancho, alto = conf["frame"]
            columnas = max(1, hoja.get_width() // ancho) if hoja else 1

            def cuadro(ref):
                if isinstance(ref, str):                       # PNG suelto
                    return self._imagen(ref)
                if hoja is not None:                           # índice en la hoja
                    return hoja.subsurface(((ref % columnas) * ancho, (ref // columnas) * alto, ancho, alto))
                return None

            cargadas = {}
            for anim, refs in conf.get("animaciones", {}).items():
                cuadros = [c for c in (cuadro(r) for r in refs) if c is not None]
                if cuadros:
                    cargadas[anim] = cuadros
            if cargadas:
                quieto = cargadas.get("quieto") or next(iter(cargadas.values()))
                if "agachado" not in cargadas:
                    cargadas["agachado"] = [self._aplastar(quieto[0], 0.6)]
                # Las animaciones que el PNG no trae usan su base del PNG o "quieto",
                # para no mezclar el estilo del PNG con el placeholder.
                propias = set(cargadas)
                for anim in set(anims) | {"quieto", "correr", "saltar", "disparar", "especial", "apuntar"}:
                    if anim not in cargadas:
                        cargadas[anim] = cargadas.get(anim.split("_")[0], quieto)
                # Cuadros generados moviendo partes del dibujo (caminar, respirar...): render/animacion.py
                animacion.completar(nombre, cargadas, propias)
                anims = cargadas
        if not anims:
            anims = {"quieto": [self._caja_error()]}
        return anims

    @staticmethod
    def _aplastar(imagen: pygame.Surface, factor: float) -> pygame.Surface:
        """Reduce la altura con vecino más cercano (pose agachada derivada de 'quieto')."""
        return pygame.transform.scale(imagen, (imagen.get_width(), max(1, round(imagen.get_height() * factor))))

    @staticmethod
    def _caja_error() -> pygame.Surface:
        sup = pygame.Surface((12, 12))
        sup.fill((255, 0, 255))
        return sup

    def animaciones(self, nombre: str) -> Dict[str, List[pygame.Surface]]:
        if nombre not in self._anims:
            self._anims[nombre] = self._cargar(nombre)
        return self._anims[nombre]

    def tiene_png(self, nombre: str) -> bool:
        """¿Existe la hoja o algún PNG suelto de este sprite?"""
        conf = self.config.get(nombre, {})
        rutas = [conf.get("archivo", "")] + [r for refs in conf.get("animaciones", {}).values()
                                              for r in refs if isinstance(r, str)]
        return any(r and os.path.isfile(os.path.join(settings.RUTA_ASSETS, r)) for r in rutas)

    def ancla(self, nombre: str, imagen: pygame.Surface, voltear: bool) -> Tuple[int, int]:
        """Punto de la imagen que se apoya en el suelo. Por defecto: centro de abajo.
        Si la imagen es más baja que el cuadro (p. ej. agachado), el ancla se baja igual."""
        conf = self.config.get(nombre, {})
        if "ancla" in conf and self.tiene_png(nombre):
            ax, ay = conf["ancla"]
            alto_cuadro = conf.get("frame", [0, imagen.get_height()])[1]
            if imagen.get_height() != alto_cuadro:            # cuadro derivado (aplastado)
                ay = round(ay * imagen.get_height() / alto_cuadro)
        else:
            ax, ay = imagen.get_width() // 2, imagen.get_height()
        if voltear:
            ax = imagen.get_width() - 1 - ax
        return ax, ay

    def dato_cuadro(self, nombre: str, anim: str, clave: str, por_defecto=None):
        """Dato del JSON asociado al primer cuadro de una animación (p. ej. "yemas" del pulgar).
        Solo vale si ese cuadro es un PNG que existe; si no, devuelve por_defecto."""
        conf = self.config.get(nombre, {})
        refs = conf.get("animaciones", {}).get(anim) or []
        if refs and isinstance(refs[0], str) and os.path.isfile(os.path.join(settings.RUTA_ASSETS, refs[0])):
            return conf.get(clave, {}).get(refs[0], por_defecto)
        return por_defecto

    def fps(self, nombre: str) -> float:
        return float(self.config.get(nombre, {}).get("fps", 10))

    def frame(self, nombre: str, anim: str, t: float, voltear: bool = False) -> pygame.Surface:
        """Cuadro de la animación en el tiempo t. Si la animación no existe, usa 'quieto'."""
        anims = self.animaciones(nombre)
        frames = anims.get(anim) or anims.get("quieto") or next(iter(anims.values()))
        i = int(t * self.fps(nombre)) % len(frames)
        imagen = frames[i]
        if not voltear:
            return imagen
        clave = (nombre, anim, i)
        if clave not in self._volteados:
            self._volteados[clave] = pygame.transform.flip(imagen, True, False)
        return self._volteados[clave]

    def silueta(self, imagen: pygame.Surface, color=(255, 255, 255)) -> pygame.Surface:
        """Versión de un solo color del sprite (parpadeo al recibir daño)."""
        clave = (id(imagen), tuple(color))
        if clave not in self._siluetas:
            self._siluetas[clave] = pygame.mask.from_surface(imagen).to_surface(
                setcolor=color, unsetcolor=(0, 0, 0, 0))
        return self._siluetas[clave]

    def contorno(self, imagen: pygame.Surface, color) -> pygame.Surface:
        """Silueta engrosada 1 px de un color (modo alto contraste), del tamaño de la imagen + 2."""
        clave = (id(imagen), tuple(color))
        if clave not in self._contornos:
            silueta = self.silueta(imagen, color)
            borde = pygame.Surface((imagen.get_width() + 2, imagen.get_height() + 2), pygame.SRCALPHA)
            for ox, oy in ((0, 1), (2, 1), (1, 0), (1, 2)):
                borde.blit(silueta, (ox, oy))
            self._contornos[clave] = borde
        return self._contornos[clave]

    def dibujar(self, sup: pygame.Surface, nombre: str, anim: str, t: float, centro_x: float, pie_y: float,
                camara_x: float, voltear: bool = False, destello=None, dx: int = 0, contorno=None,
                escala=(1.0, 1.0), tinte=None) -> None:
        """Dibuja el sprite con su ancla (los pies) en (centro_x, pie_y) del mundo.
        destello: color opcional para dibujarlo como silueta (al recibir daño).
        tinte: color que se SUMA al sprite (se aclara sin perder el dibujo: golpe recibido).
        escala: (x, y) para deformarlo (el jefe 2 agazapado), con el ancla en los mismos pies."""
        imagen = self.frame(nombre, anim, t, voltear)
        ax, ay = self.ancla(nombre, imagen, voltear)
        if escala != (1.0, 1.0):
            clave = (id(imagen), escala)
            if clave not in self._escaladas:
                self._escaladas[clave] = pygame.transform.scale(
                    imagen, (round(imagen.get_width() * escala[0]), round(imagen.get_height() * escala[1])))
            imagen = self._escaladas[clave]
            ax, ay = round(ax * escala[0]), round(ay * escala[1])
        x, y = int(centro_x - camara_x) + dx - ax, int(pie_y) - ay
        if contorno:
            sup.blit(self.contorno(imagen, contorno), (x - 1, y - 1))
        if destello:
            imagen = self.silueta(imagen, destello)
        sup.blit(imagen, (x, y))
        if tinte:
            sup.blit(self.silueta(imagen, tinte), (x, y), special_flags=pygame.BLEND_RGB_ADD)
