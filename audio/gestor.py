"""Gestor de audio: reproduce efectos y música con pygame.mixer.

- Los sonidos se sintetizan con audio/sintesis.py la primera vez que se piden.
- Si existe assets/sonidos/<nombre>.wav u .ogg (efecto) o assets/sonidos/musica_<nombre>.ogg
  (tema), se usa ese archivo en su lugar: se pueden reemplazar sin tocar el código.
- Si no hay tarjeta de sonido, el juego sigue funcionando en silencio.
- Los efectos que se repiten mucho (disparos, impactos) tienen variantes de tono y un tope
  de voces a la vez: una ráfaga no tapa todo lo demás.
- Las fanfarrias (victoria, game over) suenan una vez en el canal de la música.
"""
from __future__ import annotations

import os
import random
from typing import Dict, List, Optional

import pygame

import settings
from audio import sintesis

RUTA_SONIDOS = os.path.join(settings.RUTA_ASSETS, "sonidos")
MAX_VOCES = {"disparo_jugador": 3, "disparo_enemigo": 3, "impacto": 3, "explosion": 4, "mover": 1, "tic": 1}


class Audio:
    def __init__(self, opciones: dict, activo: bool = True):
        self.activo = False
        if activo:
            try:
                if not pygame.mixer.get_init():
                    pygame.mixer.init(frequency=sintesis.SR, size=-16, channels=2, buffer=512)
                pygame.mixer.set_num_channels(24)
                pygame.mixer.set_reserved(2)                 # canal 0: música; canal 1: voz
                self.frecuencia, _, self.canales = pygame.mixer.get_init()
                self.canal_musica = pygame.mixer.Channel(0)
                self.canal_voz = pygame.mixer.Channel(1)
                self.activo = True
            except pygame.error as error:
                print(f"[audio] Sin sonido: {error}")
        self._efectos: Dict[str, pygame.mixer.Sound] = {}
        self._variantes: Dict[str, List[pygame.mixer.Sound]] = {}
        self._sonando: Dict[str, List[pygame.mixer.Channel]] = {}
        self._temas: Dict[str, pygame.mixer.Sound] = {}
        self._azar = random.Random(7)
        self._sinteticos: Optional[dict] = None
        self.tema_actual: Optional[str] = None
        self.voz_actual: Optional[str] = None       # última frase pedida (para las pruebas)
        self.tema_pendiente: Optional[str] = None   # música que espera a que termine la frase
        self.atenuada = False                       # hay una frase en curso (música baja o en espera)
        self.vol_efectos = self.vol_musica = 0.0
        self.aplicar_volumen(opciones)

    # --- Volumen ------------------------------------------------------------------------------
    def aplicar_volumen(self, opciones: dict) -> None:
        self.vol_efectos = opciones.get("volumen_efectos", 8) / 10
        self.vol_musica = opciones.get("volumen_musica", 6) / 10 * 0.6
        if self.activo:
            factor = settings.VOLUMEN_ATENUADO if self.atenuada and self.tema_pendiente is None else 1.0
            self.canal_musica.set_volume(self.vol_musica * factor)

    # --- Carga --------------------------------------------------------------------------------
    def _archivo(self, nombre: str) -> Optional[str]:
        for ext in (".wav", ".ogg"):
            ruta = os.path.join(RUTA_SONIDOS, nombre + ext)
            if os.path.isfile(ruta):
                return ruta
        return None

    def _sonido(self, datos) -> pygame.mixer.Sound:
        return pygame.sndarray.make_sound(sintesis.a_int16(datos, self.canales))

    def _efecto(self, nombre: str) -> Optional[pygame.mixer.Sound]:
        if nombre not in self._efectos:
            archivo = self._archivo(nombre)
            if archivo:
                self._efectos[nombre] = pygame.mixer.Sound(archivo)
            else:
                if self._sinteticos is None:
                    self._sinteticos = sintesis.efectos(self.frecuencia)
                if nombre not in self._sinteticos:
                    return None
                datos = self._sinteticos[nombre]
                self._efectos[nombre] = self._sonido(datos)
                if nombre in sintesis.VARIANTES:
                    self._variantes[nombre] = [self._sonido(v) for v in
                                               sintesis.variantes(datos, sintesis.VARIANTES[nombre])]
        return self._efectos[nombre]

    def _tema(self, nombre: str) -> Optional[pygame.mixer.Sound]:
        if nombre not in self._temas:
            archivo = self._archivo("musica_" + nombre)
            if archivo:
                self._temas[nombre] = pygame.mixer.Sound(archivo)
            elif nombre in sintesis.TEMAS:
                self._temas[nombre] = self._sonido(sintesis.tema(nombre, self.frecuencia))
            elif nombre in sintesis.JINGLES:
                self._temas[nombre] = self._sonido(sintesis.jingle(nombre, self.frecuencia))
            else:
                return None
        return self._temas[nombre]

    def precargar(self) -> None:
        """Sintetiza todo al inicio para que no haya tirones al cambiar de escena."""
        if not self.activo:
            return
        for nombre in sintesis.efectos(self.frecuencia):
            self._efecto(nombre)
        for nombre in list(sintesis.TEMAS) + list(sintesis.JINGLES):
            self._tema(nombre)

    # --- Reproducción ------------------------------------------------------------------------
    def efecto(self, nombre: str) -> None:
        if not self.activo or self.vol_efectos <= 0:
            return
        sonido = self._efecto(nombre)
        if sonido is None:
            return
        if self._variantes.get(nombre):
            sonido = self._azar.choice(self._variantes[nombre])
        tope = MAX_VOCES.get(nombre)
        if tope:                                   # corta la voz más vieja si ya hay demasiadas
            vivos = [c for c in self._sonando.get(nombre, []) if c.get_busy()]
            while len(vivos) >= tope:
                vivos.pop(0).fadeout(20)
            self._sonando[nombre] = vivos
        canal = sonido.play()
        if canal is not None:
            canal.set_volume(self.vol_efectos)
            if tope:
                self._sonando[nombre].append(canal)

    def jingle(self, nombre: str) -> None:
        """Fanfarria corta en el canal de la música, sin repetir. Al terminar queda en silencio
        hasta que una escena pida su tema."""
        self.tema_actual = None
        if not self.activo:
            return
        sonido = self._tema(nombre)
        if sonido is not None:
            self.canal_musica.stop()
            self.canal_musica.play(sonido)
            self.canal_musica.set_volume(self.vol_musica)

    def presentar(self, voz: str, tema: Optional[str]) -> None:
        """Primero la frase hablada y DESPUÉS la música: nunca las dos a todo volumen.
        - Si `tema` no estaba sonando, queda en silencio y arranca cuando termina la frase.
        - Si `tema` ya sonaba (p. ej. al volver al menú desde Opciones), no se corta: baja a
          settings.VOLUMEN_ATENUADO mientras dura la frase y luego vuelve a su volumen."""
        self.voz_actual = voz
        ya_sonaba = tema == self.tema_actual and self.tema_pendiente is None
        if not ya_sonaba:
            self.musica(None)
            self.tema_pendiente = tema
        self.atenuada = True
        hay_voz = self.activo and self.vol_efectos > 0 and self._archivo(voz) is not None
        if hay_voz:
            sonido = self._efecto(voz)
            self.canal_voz.play(sonido)
            self.canal_voz.set_volume(self.vol_efectos)
            if ya_sonaba:
                self.canal_musica.set_volume(self.vol_musica * settings.VOLUMEN_ATENUADO)

    def hablando(self) -> bool:
        return self.activo and self.canal_voz.get_busy()

    def actualizar(self) -> None:
        """Una vez por frame: cuando la frase termina, arranca la música pendiente o le
        devuelve su volumen."""
        if not self.atenuada or self.hablando():
            return
        self.atenuada = False
        if self.tema_pendiente is not None:
            pendiente, self.tema_pendiente = self.tema_pendiente, None
            self.musica(pendiente)
        elif self.activo:
            self.canal_musica.set_volume(self.vol_musica)

    def musica(self, nombre: Optional[str]) -> None:
        """Cambia el tema en bucle (None = silencio). Si ya suena ese tema, no lo reinicia.
        Cambiar de tema cancela la frase hablada que estuviera sonando."""
        if self.tema_pendiente is not None or self.atenuada:
            if nombre is not None:                          # otra escena pide su música: se calla la voz
                self.tema_pendiente, self.atenuada = None, False
                if self.activo:
                    self.canal_voz.stop()
                    self.canal_musica.set_volume(self.vol_musica)
        if nombre == self.tema_actual:
            return
        self.tema_actual = nombre
        if not self.activo:
            return
        self.canal_musica.stop()
        tema = self._tema(nombre) if nombre else None
        if tema is not None:
            self.canal_musica.play(tema, loops=-1, fade_ms=300)
            self.canal_musica.set_volume(self.vol_musica)


# Instancia global: la usan las escenas y los componentes de UI. Juego la reemplaza al iniciar.
audio = Audio({}, activo=False)


def iniciar(opciones: dict, activo: bool = True) -> Audio:
    global audio
    audio = Audio(opciones, activo)
    return audio


def efecto(nombre: str) -> None:
    audio.efecto(nombre)


def musica(nombre: Optional[str]) -> None:
    audio.musica(nombre)


def presentar(voz: str, tema: Optional[str]) -> None:
    audio.presentar(voz, tema)


def jingle(nombre: str) -> None:
    audio.jingle(nombre)
