"""Procesa el arte de los reportajes: assets/sprites_raw/reportajes/*.jpeg -> assets/reportajes/*.png

Uso:  python tools/procesar_reportajes.py

Mismo pipeline que tools/procesar_sprites.py (se importan sus funciones):
  1. flood fill del fondo con tolerancia, desde el borde;
  2. huecos del color del fondo y halo del borde;
  3. la figura principal (se borran motas sueltas);
  4. reducción por MODA de cada bloque (no promedia: el pixel art queda nítido);
  5. cuantización a los colores congelados de assets/paleta.json (28: incluye celeste y morado);
  6. contorno negro de 1 px.

PERSONAJES (bustos de 88 x 116, el doble de detalle que los dibujados por código). Todos con el
MISMO factor de escala (BLOQUE píxeles del original por píxel), así se ven del mismo tamaño entre
sí, y alineados por la BOCA: el punto BOCAS[nombre] del original cae en (44, 42) del busto, que es
donde el juego pone la animación. El busto NO se estira: termina donde termina el dibujo y las
escenas tapan el corte con el escritorio o el cuadro de diálogo (plano medio de televisión).
Los estados que no vienen dibujados se generan a partir del busto, sin cambiar la escala ni la
posición (así el personaje no salta al cambiar de estado):
  <nombre>_habla1.png  boca entreabierta     <nombre>_habla2.png  boca abierta
  <nombre>_parpadeo.png  ojos cerrados (en los puntos OJOS[nombre], marcados a mano como los
                         rasgos del presidente: la detección confundía canas y bigotes blancos)
FONDOS: el usuario prefirió los fondos dibujados por código (2026-11-12). Sus JPG siguen en
assets/sprites_raw/reportajes/, pero no se procesan: a 256 x 160 y con la paleta de 24 colores
quedaban manchados (la paleta no tiene sus tonos intermedios).
Al final se guarda una hoja de contacto x4: assets/reportajes_preview.png.
"""
from __future__ import annotations

import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame  # noqa: E402

import procesar_sprites as ps  # noqa: E402

RAIZ = ps.RAIZ
RUTA_RAW = os.path.join(RAIZ, "assets", "sprites_raw", "reportajes")
RUTA_SALIDA = os.path.join(RAIZ, "assets", "reportajes")
RUTA_HOJA = os.path.join(RAIZ, "assets", "reportajes_preview.png")

ANCHO, ALTO = 88, 116
BOCA_DESTINO = (44, 42)
BLOQUE = 12.0               # píxeles del original por píxel del busto (igual para todos)
# Centro de la boca en cada original (x, y), medido sobre la imagen de 896 x 1200
BOCAS = {
    "presentadora": (545, 525),
    "analista": (550, 585),
    "influencer": (555, 515),
    "reportera": (535, 505),
    "jhon": (560, 582),
    "efrain": (575, 572),
    "carmen": (545, 505),
}
# Centro de cada ojo (izquierdo, derecho) en el original, medido igual que la boca
OJOS = {
    "presentadora": ((485, 405), (610, 405)),
    "analista": ((490, 403), (625, 403)),
    "influencer": ((485, 400), (610, 400)),
    "reportera": ((475, 385), (595, 385)),
    "jhon": ((485, 435), (625, 435)),
    "efrain": ((520, 425), (630, 425)),
    "carmen": ((485, 380), (605, 380)),
}

# Colores de la boca y los párpados generados (todos están en la paleta)
INTERIOR_BOCA = (51, 42, 33)
LENGUA = (188, 27, 31)
DIENTES = (240, 240, 240)
PARPADO = (13, 9, 10)


def paleta() -> np.ndarray:
    p = ps.cargar_paleta()
    if p is None:
        sys.exit(f"Falta la paleta congelada {ps.RUTA_PALETA}: corre primero tools/procesar_sprites.py")
    return p


def mas_cercano(color, pal: np.ndarray) -> np.ndarray:
    return pal[((pal.astype(np.int32) - np.array(color)) ** 2).sum(1).argmin()]


# --- Personajes -------------------------------------------------------------------------------
def recortar_figura(ruta: str):
    img = ps.cargar(ruta)
    conf = dict(ps.CONFIG_BASE)
    informe = {"fondos": []}
    opaco, fondos = ps.quitar_fondo(img, conf, informe)
    opaco = ps.quitar_huecos_y_halo(img, opaco, fondos, conf)
    opaco = ps.quedarse_con_principal(opaco)
    return img, opaco


def ojos_en_busto(centros, dx: int, dy: int) -> list:
    """Dónde caen en el busto los centros de los ojos del original."""
    return [(int(cx // BLOQUE) + dx, int(cy // BLOQUE) + dy) for cx, cy in centros]


def busto(nombre: str, pal: np.ndarray):
    """(img, alfa, recortes, ojos) del busto en reposo (ALTO x ANCHO), alineado por la boca."""
    img, opaco = recortar_figura(os.path.join(RUTA_RAW, f"{nombre}.jpeg"))
    reducido, alfa = ps.reducir_por_moda(img, opaco, bloque=BLOQUE)
    reducido = ps.cuantizar(reducido, alfa, pal)
    bx, by = BOCAS[nombre]
    dx = BOCA_DESTINO[0] - int(round(bx / BLOQUE))
    dy = BOCA_DESTINO[1] - int(round(by / BLOQUE))
    lienzo = np.zeros((ALTO, ANCHO, 3), np.uint8)
    mascara = np.zeros((ALTO, ANCHO), bool)
    alto, ancho = alfa.shape
    for y in range(alto):
        for x in range(ancho):
            yy, xx = y + dy, x + dx
            if 0 <= yy < ALTO and 0 <= xx < ANCHO and alfa[y, x]:
                lienzo[yy, xx], mascara[yy, xx] = reducido[y, x], True
    recortes = {"arriba": int((alfa[:max(0, -dy)]).any()),          # la cabeza no se corta
                "abajo": int(alfa[max(0, ALTO - dy):].any())}           # ni se pierde el pecho
    return lienzo, mascara, recortes, ojos_en_busto(OJOS[nombre], dx, dy)


def fila_boca(img, alfa):
    """Fila de la línea de la boca cerca de BOCA_DESTINO: la más oscura de las 7 filas vecinas."""
    cx, cy = BOCA_DESTINO
    mejor, puntaje = cy, -1
    for y in range(cy - 3, cy + 4):
        zona = img[y, cx - 3:cx + 4].astype(int)
        oscuros = int(((zona.sum(1) < 330) & alfa[y, cx - 3:cx + 4]).sum())
        if oscuros > puntaje or (oscuros == puntaje and abs(y - cy) < abs(mejor - cy)):
            mejor, puntaje = y, oscuros
    return mejor


def hablando(img, alfa, abierta: int):
    """Boca entreabierta (1) o abierta (2), dibujada sobre la línea de la boca."""
    img = img.copy()
    cx = BOCA_DESTINO[0]
    y = fila_boca(img, alfa)
    if abierta == 1:
        img[y, cx - 3:cx + 3] = INTERIOR_BOCA
        img[y + 1, cx - 2:cx + 2] = INTERIOR_BOCA
        img[y + 1, cx - 1:cx + 1] = LENGUA
    else:
        img[y, cx - 4:cx + 4] = INTERIOR_BOCA
        img[y, cx - 3:cx + 3] = DIENTES
        img[y + 1, cx - 4:cx + 4] = INTERIOR_BOCA
        img[y + 2, cx - 3:cx + 3] = INTERIOR_BOCA
        img[y + 2, cx - 2:cx + 2] = LENGUA
        img[y + 3, cx - 2:cx + 2] = INTERIOR_BOCA
    return img


def parpadeando(img, alfa, puestos: list):
    """Ojos cerrados: en cada ojo (unos 5 x 3 px) el blanco y la pupila pasan a color piel y se
    dibuja el párpado. Los píxeles de otro color (marco de gafas, cejas) no se tocan."""
    img = img.copy()
    cx, cy = BOCA_DESTINO
    zona = (slice(cy - 8, cy - 3), slice(cx - 12, cx + 6))            # mejillas, bajo los ojos
    piel = moda(img[zona][alfa[zona]])
    for x, y in puestos:
        for yy in range(y - 1, y + 2):
            for xx in range(x - 2, x + 3):
                c = img[yy, xx].astype(int)
                ojo = c.min() > 170 or c.sum() < 150                  # blanco del ojo o pupila
                if alfa[yy, xx] and ojo:
                    img[yy, xx] = piel
        img[y + 1, x - 2:x + 3] = PARPADO
    return img


def moda(pixeles: np.ndarray):
    valores, cuentas = np.unique(pixeles.reshape(-1, 3), axis=0, return_counts=True)
    return valores[cuentas.argmax()]


def guardar(img, alfa, nombre: str) -> pygame.Surface:
    img, alfa = ps.contorno(img, alfa)
    sup = ps.a_superficie(img, alfa)
    pygame.image.save(sup, os.path.join(RUTA_SALIDA, nombre))
    return sup


# --- Hoja de contacto -------------------------------------------------------------------------
def hoja(bustos: dict) -> None:
    """x4: una fila por personaje con sus 4 estados."""
    escala, sep = 4, 6
    h = pygame.Surface((4 * (ANCHO * escala + sep) + 150, len(bustos) * (ALTO * escala + sep) + 8))
    h.fill((96, 96, 104))
    fuente = pygame.font.SysFont(None, 22)
    y = 8
    for nombre, estados in bustos.items():
        h.blit(fuente.render(nombre, True, (255, 255, 255)), (6, y + 4))
        for i, (estado, sup) in enumerate(estados.items()):
            x = 150 + i * (ANCHO * escala + sep)
            h.blit(pygame.transform.scale_by(sup, escala), (x, y))
            h.blit(fuente.render(estado, True, (230, 230, 230)), (x + 2, y + ALTO * escala - 16))
            bx, by = BOCA_DESTINO
            pygame.draw.rect(h, (0, 255, 0), (x + bx * escala, y + by * escala, escala, escala), 1)
        y += ALTO * escala + sep
    pygame.image.save(h, RUTA_HOJA)


def main() -> None:
    pygame.init()
    os.makedirs(RUTA_SALIDA, exist_ok=True)
    pal = paleta()
    bustos = {}
    for nombre in BOCAS:
        if not os.path.isfile(os.path.join(RUTA_RAW, f"{nombre}.jpeg")):
            print(f"  (falta {nombre}.jpeg: el juego lo sigue dibujando por código)")
            continue
        img, alfa, recortes, puestos = busto(nombre, pal)
        estados = {"quieto": guardar(img, alfa, f"{nombre}.png"),
                   "habla1": guardar(hablando(img, alfa, 1), alfa, f"{nombre}_habla1.png"),
                   "habla2": guardar(hablando(img, alfa, 2), alfa, f"{nombre}_habla2.png")}
        estados["parpadeo"] = guardar(parpadeando(img, alfa, puestos), alfa, f"{nombre}_parpadeo.png")
        if any(recortes.values()):
            print(f"  AVISO {nombre}: el busto se sale del lienzo {recortes}")
        bustos[nombre] = estados
        print(f"  {nombre:<13} ojos en {puestos}  boca en fila {fila_boca(img, alfa)}")
    hoja(bustos)
    print(f"Hoja de contacto: {os.path.relpath(RUTA_HOJA, RAIZ)}")


if __name__ == "__main__":
    main()
