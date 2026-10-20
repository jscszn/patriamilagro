"""HUD: vidas, salud, puntaje, arma, opinión popular y barra del jefe."""
from __future__ import annotations

import pygame

import settings
from render.texto import dibujar_texto

C = settings.COLORES
COLORES_OPINION = {"medios": (60, 188, 252), "influencers": (228, 92, 220), "pueblo": (248, 216, 32)}
ETIQUETAS_OPINION = {"medios": "MED", "influencers": "INF", "pueblo": "PUE"}


def _medalla(sup, x, y):
    pygame.draw.rect(sup, C["azul"], (x + 1, y, 3, 3))
    pygame.draw.rect(sup, C["rojo"], (x + 4, y, 3, 3))
    pygame.draw.circle(sup, C["amarillo"], (x + 4, y + 6), 3)


def _corazon(sup, x, y, lleno):
    color = C["rojo"] if lleno else C["gris_oscuro"]
    pygame.draw.rect(sup, color, (x, y + 1, 7, 3))
    pygame.draw.rect(sup, color, (x + 1, y, 2, 1))
    pygame.draw.rect(sup, color, (x + 4, y, 2, 1))
    pygame.draw.rect(sup, color, (x + 1, y + 4, 5, 1))
    pygame.draw.rect(sup, color, (x + 2, y + 5, 3, 1))
    sup.set_at((x + 3, y + 6), color)


def dibujar_hud(sup: pygame.Surface, estado, opinion_mostrada: dict, sprites=None,
                id_local: int = None) -> None:
    """sprites: para dibujar el arma recogida. id_local: de quién son las vidas (modo en red)."""
    jugador = estado.jugador(id_local) if id_local is not None else None
    jugador = jugador or estado.jugadores[0]
    varios = len(estado.jugadores) > 1
    # Fondo del HUD
    banda = pygame.Surface((settings.ANCHO, 26), pygame.SRCALPHA)
    banda.fill((0, 0, 0, 140))
    sup.blit(banda, (0, 0))

    # Jugador: vidas, corazones, puntaje, arma
    color_jugador = jugador.stats_rol["color"] if varios else C["blanco"]
    dibujar_texto(sup, f"{jugador.id_jugador}P", (3, 2), color_jugador)
    for i in range(min(jugador.vidas, 6)):
        _medalla(sup, 18 + i * 9, 2)
    for i in range(jugador.salud_max):
        _corazon(sup, 4 + i * 9, 15, i < jugador.salud and jugador.activo)
    x_puntaje = 6 + jugador.salud_max * 9
    puntaje = jugador.puntaje if varios else estado.puntaje_total       # en red: el de cada uno
    dibujar_texto(sup, f"{puntaje:06d}", (x_puntaje, 14), C["blanco"])
    if jugador.arma != "normal" and sprites is not None:              # arma recogida (sin letras)
        arma = sprites.frame(f"powerup_{jugador.arma}", "quieto", 0)
        sup.blit(arma, (x_puntaje + 42, 12))
    if varios:                                                        # puntaje de los compañeros
        otros = [j for j in estado.jugadores if j is not jugador]
        for i, j in enumerate(otros[:3]):
            color = j.stats_rol["color"] if not j.eliminado else C["gris_oscuro"]
            dibujar_texto(sup, f"{j.id_jugador}P {j.puntaje:05d}", (104, 1 + i * 8), color, sombra=False)

    # Opinión popular: tres barras pequeñas
    x = 156
    for i, clave in enumerate(("medios", "influencers", "pueblo")):
        y = 2 + i * 8
        dibujar_texto(sup, ETIQUETAS_OPINION[clave], (x, y - 3), COLORES_OPINION[clave], sombra=False)
        pygame.draw.rect(sup, C["gris_oscuro"], (x + 20, y, 76, 5))
        valor = max(0.0, min(100.0, opinion_mostrada[clave]))
        pygame.draw.rect(sup, COLORES_OPINION[clave], (x + 20, y, int(76 * valor / 100), 5))
        pygame.draw.rect(sup, C["blanco"], (x + 20 + 38, y, 1, 5))   # marca del 50

    # Barra de vida del jefe
    jefe = estado.jefe
    if jefe is not None and estado.arena_activa:
        dibujar_texto(sup, jefe.nombre, (128, 198), C["naranja"], centrado=True)
        pygame.draw.rect(sup, C["negro"], (47, 209, 162, 8))
        pygame.draw.rect(sup, C["gris_oscuro"], (48, 210, 160, 6))
        ancho = int(160 * jefe.vida / jefe.vida_max)
        color = C["rojo"] if jefe.fase2 else C["naranja"]
        pygame.draw.rect(sup, color, (48, 210, ancho, 6))


def dibujar_barras_opinion(sup: pygame.Surface, opinion: dict, x: int, y: int, ancho: int = 120,
                           alto: int = 7, separacion: int = 12, nombres_largos: bool = True) -> None:
    """Tres barras grandes (medios, influencers, pueblo) con su valor; para escenas de resumen."""
    for i, clave in enumerate(("medios", "influencers", "pueblo")):
        fila = y + i * separacion
        color = COLORES_OPINION[clave]
        etiqueta = clave.upper() if nombres_largos else ETIQUETAS_OPINION[clave]
        dibujar_texto(sup, etiqueta, (x, fila - 1), color)
        bx = x + (72 if nombres_largos else 22)
        valor = max(0.0, min(100.0, opinion[clave]))
        pygame.draw.rect(sup, C["gris_oscuro"], (bx, fila, ancho, alto))
        pygame.draw.rect(sup, color, (bx, fila, int(ancho * valor / 100), alto))
        pygame.draw.rect(sup, C["blanco"], (bx + ancho // 2, fila, 1, alto))   # marca del 50
        dibujar_texto(sup, f"{int(round(valor)):3d}", (bx + ancho + 4, fila - 1), C["blanco"])
