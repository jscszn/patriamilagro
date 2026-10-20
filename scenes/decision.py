"""Escena de decisión: CAPTURAR, EXTRADITAR o DEJAR LIBRE al jefe derrotado.

La escena solo elige; quien registra la decisión es la partida (partida.decidir), que la
inserta en el árbol y la pasa a los grafos.
Hay TIEMPO LÍMITE (settings.TIEMPO_DECISION): si se acaba, el jefe aprovecha la duda y escapa,
que cuenta como DEJAR LIBRE.
REVOCAR (una vez por partida): justo después de sellar la decisión hay unos segundos para
arrepentirse con X / B. Revocar ELIMINA el nodo recién insertado en el árbol, cobra una
penalización de opinión y deja decidir de nuevo.
"""
from __future__ import annotations

import math

import pygame

import input_manager as im
import settings
from audio import gestor as audio
from core.decision_tree import CAPTURAR, CATEGORIAS, EXTRADITAR, LIBERAR
from core.partida import DECISION_POR_TIEMPO
from render.hud import COLORES_OPINION, ETIQUETAS_OPINION
from render.texto import dibujar_parrafo, dibujar_texto
from render.ui import dibujar_marco
from scenes.base import Scene

C = settings.COLORES

OPCIONES = [
    (CAPTURAR, "CAPTURAR",
     "Juicio aquí, en el país. Al pueblo le gusta ver justicia en casa; los medios vigilarán cada paso."),
    (EXTRADITAR, "EXTRADITAR",
     "Lo envías a juicio en el extranjero. Los medios aplauden; parte del pueblo siente que se entrega la justicia."),
    (LIBERAR, "DEJAR LIBRE",
     "Evitas represalias... por ahora. La opinión suele caer, y repetirlo sale cada vez más caro."),
]
SELLOS = {CAPTURAR: "¡CAPTURADO!", EXTRADITAR: "¡EXTRADITADO!", LIBERAR: "LIBERADO..."}
ESPERA_INICIAL = 0.6      # evita que un salto o disparo del nivel confirme sin querer
DURACION_SELLO = 1.2
VENTANA_REVOCAR = 2.5     # segundos extra con el sello en pantalla para poder revocar


class DecisionScene(Scene):
    def __init__(self, juego, jefe: str = "", tipo_jefe: int = 1, revocada: bool = False, **datos):
        super().__init__(juego, **datos)
        self.partida = juego.partida
        self.jefe, self.tipo_jefe = jefe, tipo_jefe
        self.revocada = revocada           # se volvió aquí después de revocar la decisión
        self.indice = 0
        self.tiempo = 0.0
        self.t_sello = 0.0                 # > 0 tras confirmar
        self.restante = settings.TIEMPO_DECISION
        self.escapo = False                # se acabó el tiempo
        self.opinion_antes = self.partida.arbol.opinion()
        audio.musica("decision")

    @property
    def decision(self) -> str:
        return OPCIONES[self.indice][0]

    def update(self, dt, acciones):
        self.tiempo += dt
        entrada = acciones[settings.JUGADOR_LOCAL]
        if self.t_sello > 0:
            self.t_sello += dt
            if self.se_puede_revocar and self.t_sello > 0.4 and entrada.pulso(im.CANCELAR):
                self._revocar()
            elif self.t_sello >= DURACION_SELLO + (VENTANA_REVOCAR if self.se_puede_revocar else 0.0) \
                    or (self.t_sello >= DURACION_SELLO and entrada.pulso(im.CONFIRMAR)):
                self.juego.escenas.cambiar("telefono", decision=self.decision,
                                           opinion_antes=self.opinion_antes)
            return
        if self.tiempo < ESPERA_INICIAL:
            return
        antes = self.restante
        self.restante = max(0.0, self.restante - dt)
        if self.restante <= 5.0 and int(antes) != int(self.restante):
            audio.efecto("tic")                            # los últimos 5 segundos suenan
        if self.restante <= 0:                             # dudó demasiado: el jefe escapa
            self.indice = [o[0] for o in OPCIONES].index(DECISION_POR_TIEMPO)
            self.escapo = True
            self._confirmar(dt)
            return
        if entrada.pulso(im.DERECHA) or entrada.pulso(im.ABAJO):
            self.indice = (self.indice + 1) % len(OPCIONES)
            audio.efecto("mover")
        if entrada.pulso(im.IZQUIERDA) or entrada.pulso(im.ARRIBA):
            self.indice = (self.indice - 1) % len(OPCIONES)
            audio.efecto("mover")
        if entrada.pulso(im.AYUDA):
            self.juego.escenas.apilar("ayuda", superpuesta=True)
        elif entrada.pulso(im.CONFIRMAR):
            self._confirmar(dt)

    @property
    def se_puede_revocar(self) -> bool:
        """Tras sellar: queda una revocación y el jefe no escapó (si escapó, ya no hay a quién)."""
        return self.t_sello > 0 and not self.escapo and self.partida.puede_revocar

    def _confirmar(self, dt: float) -> None:
        self.partida.decidir(self.decision)                # inserción en el árbol + cambios en el mapa
        self.juego.logros.notificar("decision", decision=self.decision)
        audio.efecto("sello")
        self.t_sello = dt

    def _revocar(self) -> None:
        """Elimina del árbol el nodo de la decisión recién tomada y vuelve a preguntar."""
        self.partida.revocar()
        self.revocada = True
        self.t_sello, self.tiempo = 0.0, 0.0               # vuelve la espera inicial anti-pulsación
        self.restante = settings.TIEMPO_DECISION
        self.opinion_antes = self.partida.arbol.opinion()  # ya con la penalización
        audio.efecto("herido")

    # --- Dibujo ---------------------------------------------------------------------
    def draw(self, sup):
        sup.fill((14, 10, 28))
        # Foco de luz sobre el jefe
        pygame.draw.ellipse(sup, (40, 34, 60), (78, 96, 100, 14))
        nivel = self.partida.nivel
        dibujar_texto(sup, f"NIVEL {nivel} SUPERADO", (128, 6), C["gris"], 1, centrado=True)
        dibujar_texto(sup, self.jefe, (128, 18), C["naranja"], 1, centrado=True)
        imagen = self.juego.sprites.frame(f"jefe{self.tipo_jefe}", "quieto", 0)
        sup.blit(imagen, imagen.get_rect(midbottom=(128, 104)))
        dibujar_texto(sup, "¿QUÉ HARÁS CON ÉL?", (128, 110), C["amarillo"], 1, centrado=True)
        self._dibujar_reloj(sup)

        for i, (clave, texto, _) in enumerate(OPCIONES):
            self._dibujar_boton(sup, i, texto)
        _, _, descripcion = OPCIONES[self.indice]
        caja = pygame.Rect(8, 152, 240, 66)
        dibujar_marco(sup, caja)
        dibujar_parrafo(sup, descripcion, (14, 157), 228, C["blanco"], 1, interlineado=1)
        self._dibujar_tendencia(sup, 14, 205)

        if self.t_sello > 0:
            self._dibujar_sello(sup)

    def _dibujar_reloj(self, sup):
        """Tiempo que queda para decidir: barra que se acorta y segundos (rojo al final)."""
        fraccion = self.restante / settings.TIEMPO_DECISION
        urgente = self.restante <= 5.0
        color = C["rojo"] if urgente else C["cian"]
        pygame.draw.rect(sup, C["gris_oscuro"], (8, 32, 60, 5))
        pygame.draw.rect(sup, color, (8, 32, int(60 * fraccion), 5))
        if not urgente or int(self.tiempo * 4) % 2 == 0:
            dibujar_texto(sup, f"TIEMPO {int(self.restante + 0.99):2d}", (8, 40), color)
        if self.revocada and self.t_sello == 0:
            dibujar_texto(sup, "DECISIÓN REVOCADA", (248, 32), C["naranja"], derecha=True)
            dibujar_texto(sup, "DECIDE DE NUEVO", (248, 42), C["naranja"], derecha=True)

    def _dibujar_boton(self, sup, i, texto):
        seleccionado = i == self.indice
        rect = pygame.Rect(8 + i * 82, 124, 76, 22)
        if seleccionado:
            rect.y -= 2 + int(abs(math.sin(self.tiempo * 5)) * 2)
        fondo = (60, 40, 10) if seleccionado else (24, 24, 48)
        borde = C["amarillo"] if seleccionado else C["gris"]
        pygame.draw.rect(sup, fondo, rect)
        pygame.draw.rect(sup, borde, rect, 1 + seleccionado)
        dibujar_texto(sup, texto, (rect.centerx, rect.y + 6), C["amarillo"] if seleccionado else C["blanco"],
                      1, centrado=True)

    def _dibujar_tendencia(self, sup, x, y):
        """Pista de hacia dónde se moverá cada opinión (sube / baja), sin números exactos."""
        arbol = self.partida.arbol
        if arbol.terminado:
            return
        cambio = arbol.efecto(arbol.actual, self.decision)
        for i, c in enumerate(CATEGORIAS):
            cx = x + i * 78
            dibujar_texto(sup, ETIQUETAS_OPINION[c], (cx, y), COLORES_OPINION[c])
            fx = cx + 22
            if cambio[c] > 0:
                pygame.draw.polygon(sup, C["verde"], [(fx, y + 7), (fx + 6, y + 7), (fx + 3, y + 2)])
            elif cambio[c] < 0:
                pygame.draw.polygon(sup, C["rojo"], [(fx, y + 2), (fx + 6, y + 2), (fx + 3, y + 7)])
            if abs(cambio[c]) >= 15:   # cambio fuerte: doble flecha
                fx += 8
                color = C["verde"] if cambio[c] > 0 else C["rojo"]
                puntos = [(fx, y + 7), (fx + 6, y + 7), (fx + 3, y + 2)] if cambio[c] > 0 \
                    else [(fx, y + 2), (fx + 6, y + 2), (fx + 3, y + 7)]
                pygame.draw.polygon(sup, color, puntos)

    def _dibujar_sello(self, sup):
        if self.se_puede_revocar and self.t_sello > 0.4:
            pygame.draw.rect(sup, C["negro"], (8, 90, 240, 13))
            dibujar_texto(sup, "X / B: REVOCAR (1 VEZ, CUESTA OPINIÓN)", (128, 92), C["blanco"], centrado=True)
        texto = "¡SE ESCAPÓ!" if self.escapo else SELLOS[self.decision]
        color = C["rojo"] if self.decision == LIBERAR else C["verde"]
        caja = pygame.Rect(0, 0, 180, 32)
        if self.t_sello < 0.12:                          # "golpe" del sello al caer
            caja.inflate_ip(24, 10)
        caja.center = (128, 70)
        pygame.draw.rect(sup, C["negro"], caja)
        pygame.draw.rect(sup, color, caja, 2)
        dibujar_texto(sup, texto, (128, 61), color, 2, centrado=True)
