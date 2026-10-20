"""Configuración global de Patria Milagro: resolución, tiempos, colores y opciones del jugador."""
from __future__ import annotations

import json
import os

# --- Rutas ---------------------------------------------------------------
RUTA_BASE = os.path.dirname(os.path.abspath(__file__))
RUTA_CONFIG = os.path.join(RUTA_BASE, "config")
RUTA_ASSETS = os.path.join(RUTA_BASE, "assets")
RUTA_GAMEPAD = os.path.join(RUTA_CONFIG, "gamepad.json")
RUTA_OPCIONES = os.path.join(RUTA_CONFIG, "opciones.json")
RUTA_LOGROS = os.path.join(RUTA_CONFIG, "logros.json")

# --- Pantalla ------------------------------------------------------------
TITULO = "Patria Milagro"
ANCHO, ALTO = 256, 224          # resolución interna (como la NES)
ESCALA_INICIAL = 3              # tamaño inicial de la ventana = 768x672

# --- Tiempo --------------------------------------------------------------
FPS = 60
DT = 1.0 / FPS                  # paso fijo de simulación (segundos)
MAX_PASOS_POR_FRAME = 5         # evita la "espiral de la muerte" si el PC se atrasa
DURACION_FUNDIDO = 0.25         # segundos del fundido desde negro al cambiar de escena

# --- Jugadores -----------------------------------------------------------
JUGADOR_LOCAL = 1               # id del jugador de este PC (multijugador futuro)

# --- Paleta (inspirada en la NES) -----------------------------------------
COLORES = {
    "negro": (0, 0, 0),
    "blanco": (252, 252, 252),
    "gris": (124, 124, 124),
    "gris_oscuro": (60, 60, 60),
    "amarillo": (248, 216, 32),
    "azul": (0, 88, 248),
    "azul_oscuro": (0, 32, 120),
    "rojo": (216, 40, 0),
    "verde": (0, 168, 0),
    "cian": (60, 188, 252),
    "naranja": (252, 152, 56),
}

# --- Sonido ----------------------------------------------------------------
HIMNO_CON_BAJO = True           # False: el himno del menú suena solo con la melodía
VOLUMEN_ATENUADO = 0.15         # la música baja a este nivel mientras habla el presidente

# --- Opciones del jugador (se guardan en config/opciones.json) ------------
OPCIONES_POR_DEFECTO = {
    "alto_contraste": False,
    "daltonismo": "ninguno",     # ninguno | protanopia | deuteranopia | tritanopia
    "volumen_musica": 6,         # 0..10
    "volumen_efectos": 8,        # 0..10
    "tutorial": True,
}
MODOS_DALTONISMO = ["ninguno", "protanopia", "deuteranopia", "tritanopia"]


def cargar_opciones() -> dict:
    """Lee las opciones guardadas; si no existen o están dañadas usa las de por defecto."""
    opciones = dict(OPCIONES_POR_DEFECTO)
    try:
        with open(RUTA_OPCIONES, encoding="utf-8") as f:
            opciones.update(json.load(f))
    except (OSError, ValueError):
        pass
    return opciones


def guardar_opciones(opciones: dict) -> None:
    """Guarda las opciones en disco en formato JSON legible."""
    os.makedirs(RUTA_CONFIG, exist_ok=True)
    with open(RUTA_OPCIONES, "w", encoding="utf-8") as f:
        json.dump(opciones, f, indent=2, ensure_ascii=False)


# =============================================================================
# Jugabilidad (unidades: píxeles y segundos)
# =============================================================================
GRAVEDAD = 620.0
VEL_CAIDA_MAX = 300.0

JUGADOR = {
    "ancho": 12, "alto": 36,      # caja de colisión de pie (el sprite mide 17x40)
    # Acostado boca abajo (el sprite mide 46x12 sobre el suelo): caja ancha y baja, centrada
    # donde estaba de pie. Las balas de sicarios (29 px) y motos (26 px) le pasan por encima.
    "ancho_agachado": 36, "alto_agachado": 12,
    "velocidad": 72.0,
    "vel_salto": 245.0,
    "corte_salto": 0.45,          # al soltar SALTAR en subida, la velocidad se multiplica por esto
    "vidas": 3,
    "salud": 3,                   # corazones por vida (balas de jefe quitan más)
    "invulnerable": 2.0,          # segundos de invulnerabilidad tras un golpe
    "cadencia": 0.16,             # segundos entre disparos
    "cadencia_rapida": 0.07,      # con el arma de disparo rápido
    "vel_bala": 230.0,
    "apertura_triple": 0.22,      # radianes entre balas del disparo triple
}

# Roles del modo multijugador (2 a 4 jugadores). Cada uno juega distinto dentro del nivel.
# En un jugador siempre se es el PRESIDENTE.
#   salud: corazones por vida.  velocidad: factor sobre JUGADOR["velocidad"].
#   arma: arma con la que empieza y que recupera al reaparecer.  voto: peso en la votación.
#   puntos: factor sobre los puntos.  aviso: factor sobre el tiempo de aviso de las emboscadas.
ROLES = {
    "presidente": {"nombre": "PRESIDENTE", "salud": 3, "velocidad": 1.0, "arma": "normal", "voto": 2,
                   "puntos": 1.0, "aviso": 1.0, "color": (248, 216, 32),
                   "habilidad": "Su voto vale doble y desempata."},
    "general": {"nombre": "GENERAL", "salud": 4, "velocidad": 0.92, "arma": "triple", "voto": 1,
                "puntos": 1.0, "aviso": 1.0, "color": (0, 168, 0),
                "habilidad": "4 corazones y disparo triple permanente."},
    "periodista": {"nombre": "PERIODISTA", "salud": 3, "velocidad": 1.12, "arma": "rapida", "voto": 1,
                   "puntos": 1.0, "aviso": 2.0, "color": (60, 188, 252),
                   "habilidad": "Disparo rápido. Avisa las emboscadas con el doble de tiempo."},
    "influencer": {"nombre": "INFLUENCER", "salud": 2, "velocidad": 1.05, "arma": "normal", "voto": 1,
                   "puntos": 1.5, "aviso": 1.0, "color": (228, 92, 220),
                   "habilidad": "Puntos x1,5. Cada decisión mueve la opinión un 25 % más."},
}
ORDEN_ROLES = ("presidente", "general", "periodista", "influencer")
MAX_JUGADORES = 4

# Único enemigo común: igual en los 3 niveles. La dificultad sale de levels/.
SICARIO = {
    "ancho": 12, "alto": 36,      # caja de colisión (el sprite mide 26x40)
    "arma": (15, 7),              # boca del arma: (adelante desde el centro, abajo desde el tope de la caja)
    "velocidad": 42.0,
    "velocidad_alcance": 95.0,    # si quedó atrás, corre más que el jugador (72) para alcanzarlo
    "distancia_alcance": 90,      # "atrás" = el jugador le lleva más de 90 px de ventaja hacia la derecha
    "giro_min": 0.4,              # segundos mínimos entre dos cambios de dirección (no "tiembla")
    "margen_giro": 12,            # se da la vuelta solo si el jugador está a más de 12 px del otro lado
    "vel_salto": 210.0,           # salta los escalones en vez de darse la vuelta
    "vida": 1,
    "cadencia": 2.2,              # segundos entre disparos
    "apuntar": 0.4,               # se detiene este tiempo antes de disparar (aviso visual)
    "vel_bala": 70.0,             # bala lenta, en línea recta
    "dano_bala": 1,
    "dano_contacto": 1,
    "puntos": 100,
}

# Los jefes: más vida, balas más rápidas y dañinas. Uno por nivel.
# Caja de colisión acorde a sprites de 72 px de alto. "arma" = de dónde salen sus balas
# (adelante desde el centro, abajo desde el tope de la caja), medido sobre cada sprite.
JEFES = {
    1: {"nombre": "EL JAGUAR DEL MONTE", "ancho": 26, "alto": 66, "arma": (42, 10), "vida": 52,
        "vel_bala": 150.0, "dano_bala": 2, "dano_contacto": 2, "puntos": 5000},
    2: {"nombre": "DON CONCRETO", "ancho": 34, "alto": 66, "arma": (18, 28), "vida": 55,
        "vel_bala": 165.0, "dano_bala": 2, "dano_contacto": 2, "puntos": 7500,
        # Se agacha para embestir con el hombro: con 32 px de alto el salto (48 px) lo pasa;
        # hay que saltar cuando está a unos 60-90 px (una ventana de ~0,2 s)
        "alto_embestida": 32},
    3: {"nombre": "LA SOMBRA DE LA RAYA", "ancho": 30, "alto": 66, "arma": (24, 25), "vida": 60,
        "vel_bala": 200.0, "dano_bala": 2, "dano_contacto": 2, "puntos": 10000},
}

# Armas y ayudas que se recogen. Las armas duran hasta perder una vida.
POWERUPS = {
    "triple": {"puntos": 50, "mensaje": "¡DISPARO TRIPLE!"},      # 3 balas en abanico
    "rapida": {"puntos": 50, "mensaje": "¡DISPARO RÁPIDO!"},      # cadencia mucho mayor
    "vida": {"puntos": 50, "mensaje": "¡VIDA EXTRA!"},            # +1 vida
}
VEL_SUMINISTRO = 55.0             # px/s a los que baja un suministro lanzado en paracaídas

# -----------------------------------------------------------------------------
# Refuerzos aleatorios (core/vehiculos.py): aparecen según el plan de core/director.py
# "caja" = (ancho, alto) de colisión. "arma" = boca (adelante desde el centro, abajo desde el tope).
# -----------------------------------------------------------------------------
# Las cajas cubren el cuerpo visible del sprite (sin casco, rotores ni cabeza del tirador):
# la bala del presidente de pie sale a 27 px del suelo y tiene que dar en la moto y la camioneta.
VEHICULOS = {
    "dron": {"nombre": "DRON", "caja": (28, 14), "vida": 2, "velocidad": 58.0, "cadencia": 1.9,
             "vel_bala": 82.0, "dano_bala": 1, "dano_contacto": 1, "puntos": 200, "arma": (0, 14),
             "alcance": 78, "duracion": 11.0, "aviso": 0.5},
    "moto": {"nombre": "MOTO", "caja": (32, 28), "vida": 2, "velocidad": 128.0, "cadencia": 0.85,
             "vel_bala": 190.0, "dano_bala": 1, "dano_contacto": 1, "puntos": 300, "arma": (12, 2),
             "alcance": 150, "vel_salto": 205.0, "aviso": 0.9},
    "camioneta": {"nombre": "CAMIONETA BLINDADA", "caja": (62, 34), "vida": 8, "velocidad": 42.0,
                  "cadencia": 1.7, "vel_bala": 96.0, "dano_bala": 1, "dano_contacto": 1, "puntos": 800,
                  "arma": (-4, -9), "distancia": 96, "rafaga": 2, "aviso": 1.0},
}

# Cuántos refuerzos y suministros salen en cada nivel está en los datos de cada nivel
# (levels/nivelN.py, clave "aleatorio"): así la dificultad se ajusta nivel por nivel.
SEPARACION_ALEATORIA = 110        # px mínimos entre dos apariciones aleatorias
PESOS_SUMINISTRO = {"triple": 9, "rapida": 9, "vida": 2}

# Tiempo límite de la decisión sobre el jefe (segundos). Si se acaba, el jefe escapa (= DEJAR LIBRE)
TIEMPO_DECISION = 15.0
