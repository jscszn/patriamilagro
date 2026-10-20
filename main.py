"""Punto de entrada de Patria Milagro.

Uso:
    python main.py                       # juego normal
    python main.py --headless 300        # corre 300 frames sin ventana (pruebas)
    python main.py --arena               # (desarrollo) cada nivel empieza en la arena del jefe
    python main.py --nivel 3 --arena     # (desarrollo) empieza directo en el nivel 3
"""
from __future__ import annotations

import argparse
import os
import sys

import pygame

import settings
from input_manager import InputManager
from render.sprites import GestorSprites
from scenes.base import SceneManager
from core.partida import Partida
from scenes.decision import DecisionScene
from scenes.ending import EndingScene
from scenes.phone import PhoneScene
from audio import gestor as audio
from core.logros import GestorLogros
from render.filtros import aplicar_daltonismo
from render.texto import dibujar_texto
from render.ui import dibujar_marco
from scenes.help import HelpScene
from scenes.historia import HistoriaScene
from scenes.level import LevelScene
from scenes.logros import LogrosScene
from scenes.menu import MenuScene
from scenes.multijugador import PartidaRedScene, SalaScene
from scenes.options import OptionsScene, RemapScene
from scenes.pause import PauseScene


class Juego:
    """Une ventana, entrada y escenas. Simula con paso fijo y dibuja a 256x224 escalado."""

    def __init__(self, headless: bool = False, escena_inicial: str = "menu", arena: bool = False,
                 **datos_escena):
        self.headless = headless
        self.arena = arena            # modo desarrollo: los niveles empiezan frente al jefe
        self.partida = None           # core.partida.Partida mientras se juega
        self.servidor = None          # net.servidor.Servidor si este equipo creó la partida en red
        self.cliente = None           # net.cliente.Cliente mientras se juega en red
        if headless:
            os.environ["SDL_VIDEODRIVER"] = "dummy"
            os.environ["SDL_AUDIODRIVER"] = "dummy"
        pygame.init()
        pygame.display.set_caption(settings.TITULO)
        self.opciones = settings.cargar_opciones()
        tam = (settings.ANCHO * settings.ESCALA_INICIAL, settings.ALTO * settings.ESCALA_INICIAL)
        self.ventana = pygame.display.set_mode(tam, pygame.RESIZABLE)
        self.lienzo = pygame.Surface((settings.ANCHO, settings.ALTO))  # resolución interna
        self.reloj = pygame.time.Clock()
        self.entrada = InputManager()
        self.sprites = GestorSprites()
        # Sonido y logros: en modo headless (pruebas) sin tarjeta de sonido y sin escribir en disco
        self.audio = audio.iniciar(self.opciones, activo=not headless)
        self.audio.precargar()
        self.logros = GestorLogros(None if headless else settings.RUTA_LOGROS)
        self.avisos = []              # [logro, segundos en pantalla] de los logros recién ganados
        self.fundido = 0.0            # > 0: fundido desde negro al cambiar de escena
        self.corriendo = True
        self.frames = 0

        self.escenas = SceneManager(self)
        for nombre, clase in {
            "menu": MenuScene,
            "ayuda": HelpScene,
            "opciones": OptionsScene,
            "remapeo": RemapScene,
            "nivel": LevelScene,
            "pausa": PauseScene,
            "decision": DecisionScene,
            "historia": HistoriaScene,
            "sala": SalaScene,
            "partida_red": PartidaRedScene,
            "telefono": PhoneScene,
            "final": EndingScene,
            "logros": LogrosScene,
        }.items():
            self.escenas.registrar(nombre, clase)
        self.escenas.cambiar(escena_inicial, **datos_escena)
        self.escenas.aplicar_cambios()
        self.aplicar_opciones()
        self._acumulador = 0.0

    def nueva_partida(self) -> Partida:
        """Empieza una partida desde cero (árbol en la raíz, puntaje 0, 3 vidas)."""
        self.partida = Partida()
        return self.partida

    def aplicar_opciones(self) -> None:
        """Aplica volumen al instante. Los filtros (alto contraste y daltonismo) se leen de
        self.opciones al dibujar cada frame, así que no necesitan más."""
        self.audio.aplicar_volumen(self.opciones)

    def cerrar_red(self) -> None:
        """Corta la conexión del modo multijugador y, si este equipo era el anfitrión, el servidor."""
        if self.cliente is not None:
            self.cliente.cerrar()
            self.cliente = None
        if self.servidor is not None:
            self.servidor.detener()
            self.servidor = None

    def salir(self) -> None:
        self.cerrar_red()
        self.corriendo = False

    # --- Bucle principal ---------------------------------------------------------
    def frame(self) -> None:
        """Un frame: eventos -> entrada -> N pasos fijos de simulación -> dibujo."""
        if self.headless:
            dt_real = settings.DT  # en pruebas el tiempo avanza exacto
        else:
            dt_real = min(self.reloj.tick(settings.FPS) / 1000.0, 0.25)

        eventos = pygame.event.get()
        for e in eventos:
            if e.type == pygame.QUIT:
                self.salir()
            elif e.type == pygame.KEYDOWN and e.key == pygame.K_F11:
                pygame.display.toggle_fullscreen()
            self.entrada.procesar_evento(e)
        self.entrada.actualizar()
        self.audio.actualizar()                    # arranca la música cuando termina la frase hablada
        self.escenas.handle_events(eventos)

        # Paso fijo: la lógica siempre avanza en incrementos de DT (determinista).
        self._acumulador += dt_real
        pasos = 0
        while self._acumulador >= settings.DT and pasos < settings.MAX_PASOS_POR_FRAME:
            self.escenas.update(settings.DT, self.entrada.consumir())
            self._actualizar_avisos(settings.DT)
            self._acumulador -= settings.DT
            pasos += 1
        if pasos == settings.MAX_PASOS_POR_FRAME:
            self._acumulador = 0.0

        self.escenas.draw(self.lienzo)
        self._dibujar_avisos(self.lienzo)
        if self.fundido > 0:
            velo = pygame.Surface(self.lienzo.get_size())
            velo.set_alpha(int(255 * self.fundido / settings.DURACION_FUNDIDO))
            self.lienzo.blit(velo, (0, 0))
        aplicar_daltonismo(self.lienzo, self.opciones.get("daltonismo", "ninguno"))
        self._presentar()
        self.frames += 1

    # --- Logros: aviso en pantalla ---------------------------------------------------
    def _actualizar_avisos(self, dt: float) -> None:
        self.fundido = max(0.0, self.fundido - dt)
        for logro in self.logros.extraer_nuevos():
            self.avisos.append([logro, 3.5])
            self.audio.efecto("logro")
        for aviso in self.avisos[:1]:                  # se muestran de a uno
            aviso[1] -= dt
        self.avisos = [a for a in self.avisos if a[1] > 0]

    def _dibujar_avisos(self, sup) -> None:
        if not self.avisos:
            return
        logro, t = self.avisos[0]
        entrada = min(1.0, (3.5 - t) / 0.25, t / 0.25)  # se desliza al entrar y al salir
        caja = pygame.Rect(0, 0, 200, 26)
        caja.midtop = (128, int(-26 + 30 * entrada))
        dibujar_marco(sup, caja, fondo=(40, 30, 0), borde=settings.COLORES["amarillo"])
        dibujar_texto(sup, "¡LOGRO DESBLOQUEADO!", (128, caja.y + 3), settings.COLORES["amarillo"], centrado=True)
        dibujar_texto(sup, logro.titulo, (128, caja.y + 14), settings.COLORES["blanco"], centrado=True)

    def _presentar(self) -> None:
        """Escala el lienzo a la ventana con un factor entero (pixel art nítido) y bandas negras."""
        ancho_v, alto_v = self.ventana.get_size()
        escala = max(1, min(ancho_v // settings.ANCHO, alto_v // settings.ALTO))
        tam = (settings.ANCHO * escala, settings.ALTO * escala)
        self.ventana.fill((0, 0, 0))
        imagen = pygame.transform.scale(self.lienzo, tam)  # vecino más cercano: sin suavizado
        self.ventana.blit(imagen, ((ancho_v - tam[0]) // 2, (alto_v - tam[1]) // 2))
        pygame.display.flip()

    def ejecutar(self, max_frames: int = None) -> None:
        while self.corriendo and (max_frames is None or self.frames < max_frames):
            self.frame()
        pygame.quit()


def main() -> None:
    parser = argparse.ArgumentParser(description="Patria Milagro")
    parser.add_argument("--headless", type=int, metavar="FRAMES",
                        help="corre sin ventana la cantidad de frames indicada y termina")
    parser.add_argument("--arena", action="store_true",
                        help="(desarrollo) cada nivel empieza en la arena del jefe")
    parser.add_argument("--nivel", type=int, choices=(1, 2, 3),
                        help="(desarrollo) empieza directamente en ese nivel")
    args = parser.parse_args()
    if args.nivel:
        juego = Juego(headless=args.headless is not None, arena=args.arena,
                      escena_inicial="nivel", numero=args.nivel)
    else:
        juego = Juego(headless=args.headless is not None, arena=args.arena)
    juego.ejecutar(max_frames=args.headless)
    if args.headless is not None:
        print(f"OK: {juego.frames} frames sin errores")


if __name__ == "__main__":
    sys.exit(main())
