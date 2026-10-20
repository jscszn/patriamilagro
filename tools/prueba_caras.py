"""PRUEBA COMPARATIVA (no modifica el pipeline): ¿cómo conservar la cara del presidente al reducir?

Uso:  python tools/prueba_caras.py      -> genera assets/prueba_caras.png

Filas (todas SIN rasgos dibujados por código: solo lo que sobrevive desde el JPG):
  A) Actual: 40 px, moda por bloque, paleta actual de 24 colores.
  B) 40 px, moda por bloque, pero en los bloques de la cara un grupo pequeño de píxeles
     claramente más oscuros (ojo, ceja) gana a la moda.
  C) B + paleta con 4 colores RESERVADOS para la cara (piel, sombra, ojo, ceja) + 20 libres.
  D) C a 48 px.
  E) C a 56 px.
Todas usan el MISMO factor de escala para las 4 imágenes (el del idle), como el pipeline.
Solo importa funciones de tools/procesar_sprites.py; no lo modifica.
"""
from __future__ import annotations

import glob
import os
import sys

import numpy as np

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import procesar_sprites as ps  # noqa: E402

RAIZ = ps.RAIZ
SALIDA = os.path.join(RAIZ, "assets", "prueba_caras.png")
IMAGENES = ["presidente_disparar", "presidente_correr_a", "presidente_diag_arriba", "presidente"]
ETIQUETAS = {"presidente": "IDLE", "presidente_disparar": "DISPARAR",
             "presidente_correr_a": "CORRER_A", "presidente_diag_arriba": "DIAG_ARRIBA"}

# Parámetros del detalle oscuro (variante B)
DIFERENCIA_OSCURO = 60     # luminancia: "claramente más oscuro" que el color de la moda
FRACCION_MIN = 0.04        # el grupo oscuro debe ocupar al menos 4 % del bloque...
FRACCION_MAX = 0.40        # ...y como máximo 40 % ("grupo pequeño"; si es mayoría ya gana la moda)
PIEL_MIN_BLOQUE = 0.20     # solo en bloques de la cara (con al menos 20 % de piel)


def luminancia(c: np.ndarray) -> np.ndarray:
    return c[..., 0] * 0.299 + c[..., 1] * 0.587 + c[..., 2] * 0.114


# =============================================================================
# Limpieza (mismo orden que ps.procesar, pero devolviendo la imagen recortada)
# =============================================================================
def limpiar(nombre: str):
    ruta = glob.glob(os.path.join(ps.RUTA_RAW, nombre + ".*"))[0]
    conf = ps.configuracion(nombre)
    informe = {"nombre": nombre, "fondos": []}
    img = ps.cargar(ruta)
    opaco, fondos = ps.quitar_fondo(img, conf, informe)
    opaco = ps.quitar_huecos_y_halo(img, opaco, fondos, conf)
    for color, tol in conf["borrar_colores"]:
        opaco &= ps.distancia(img, color) > tol
    opaco &= ~ps.es_magenta(img)
    opaco = ps.quedarse_con_principal(opaco)
    y0, y1, x0, x1 = ps.caja(opaco)
    y0, x0 = max(0, y0 - 1), max(0, x0 - 1)
    return img[y0:y1 + 1, x0:x1 + 1], opaco[y0:y1 + 1, x0:x1 + 1]


def zona_cabeza(img, opaco) -> np.ndarray:
    """Tercio superior del cuerpo (sin arma) en la imagen original."""
    cuerpo = opaco & ~ps.es_arma(img)
    filas = np.nonzero(cuerpo.any(1))[0]
    zona = np.zeros_like(opaco)
    zona[filas.min(): filas.min() + (filas.max() - filas.min()) // 3] = True
    return zona


# =============================================================================
# Reducción con detalle oscuro (variante B)
# =============================================================================
def reducir_con_detalle(img, opaco, bloque: float, cabeza: np.ndarray):
    """Como ps.reducir_por_moda, pero en los bloques de la cara un grupo pequeño de píxeles
    claramente más oscuros que la moda (ojo, ceja) gana: se usa el color típico de ese grupo."""
    alto, ancho = opaco.shape
    filas, cols = max(1, round(alto / bloque)), max(1, round(ancho / bloque))
    salida = np.zeros((filas, cols, 3), np.uint8)
    alfa = np.zeros((filas, cols), bool)
    piel = ps.es_piel(img)
    for oy in range(filas):
        y0, y1 = int(oy * bloque), max(int(oy * bloque) + 1, int((oy + 1) * bloque))
        for ox in range(cols):
            x0, x1 = int(ox * bloque), max(int(ox * bloque) + 1, int((ox + 1) * bloque))
            m = opaco[y0:y1, x0:x1]
            if m.mean() < 0.5:
                continue
            pix = img[y0:y1, x0:x1][m]
            color, _ = ps.moda_color(pix, bits=5)
            es_cara = cabeza[y0:y1, x0:x1].any() and piel[y0:y1, x0:x1][m].mean() >= PIEL_MIN_BLOQUE
            if es_cara:
                oscuros = luminancia(pix.astype(np.float64)) < luminancia(color) - DIFERENCIA_OSCURO
                fraccion = oscuros.mean()
                if FRACCION_MIN <= fraccion <= FRACCION_MAX:
                    color, _ = ps.moda_color(pix[oscuros], bits=5)
            salida[oy, ox] = color.round().astype(np.uint8)
            alfa[oy, ox] = True
    return salida, alfa


# =============================================================================
# Paletas
# =============================================================================
def paleta_actual() -> np.ndarray:
    """Los 24 colores que hoy tienen los PNG generados por el pipeline."""
    colores = set()
    for f in glob.glob(os.path.join(ps.RUTA_SALIDA, "*.png")):
        s = pygame.image.load(f)
        a = pygame.surfarray.array_alpha(s) > 0
        colores |= {tuple(int(v) for v in c) for c in pygame.surfarray.array3d(s)[a]}
    return np.array(sorted(colores), np.uint8)


def colores_cara(fuentes) -> np.ndarray:
    """4 colores reservados medidos en los JPG: piel, sombra de piel, ojo y ceja."""
    piel_px, oscuros_cara = [], []
    for img, opaco in fuentes:
        cabeza = zona_cabeza(img, opaco) & opaco
        piel = cabeza & ps.es_piel(img)
        piel_px.append(img[piel])
        # Rasgos oscuros DENTRO de la cara: oscuros rodeados de piel (no el pelo del contorno)
        ys, xs = np.nonzero(piel)
        caja = np.zeros_like(opaco)
        caja[ys.min():ys.max() + 1, xs.min():xs.max() + 1] = True
        oscuros_cara.append(img[caja & opaco & (luminancia(img.astype(np.float64)) < 90)])
    piel_px = np.concatenate(piel_px)
    lum = luminancia(piel_px.astype(np.float64))
    piel, _ = ps.moda_color(piel_px[lum >= np.median(lum)], bits=5)
    sombra, _ = ps.moda_color(piel_px[lum < np.percentile(lum, 25)], bits=5)
    oscuros = np.concatenate(oscuros_cara)
    lum_o = luminancia(oscuros.astype(np.float64))
    ojo, _ = ps.moda_color(oscuros[lum_o < np.percentile(lum_o, 30)], bits=5)      # lo más oscuro
    ceja, _ = ps.moda_color(oscuros[lum_o >= np.percentile(lum_o, 60)], bits=5)    # café oscuro
    return np.array([piel, sombra, ojo, ceja]).round().astype(np.uint8)


def paleta_con_reservados(reservados: np.ndarray, pixeles: np.ndarray) -> np.ndarray:
    """20 colores libres por k-means + negro del contorno ya incluido + 4 reservados = 24.
    Los reservados no participan en el k-means: no se pueden fusionar con otros colores."""
    libres = ps.kmeans(pixeles, ps.N_COLORES - 1 - len(reservados))
    return np.vstack([libres, reservados, ps.NEGRO[None].astype(np.uint8)])


# =============================================================================
def sprite_final(reducido, alfa, paleta):
    """Cuantiza y agrega el contorno, igual que el pipeline (sin rasgos dibujados)."""
    img = ps.cuantizar(reducido, alfa, paleta)
    h, w = alfa.shape
    lienzo = np.zeros((h + 2, w + 2, 3), np.uint8)
    a = np.zeros((h + 2, w + 2), bool)
    lienzo[1:-1, 1:-1], a[1:-1, 1:-1] = img, alfa
    img, a = ps.contorno(lienzo, a)
    return img, a


def recorte_cabeza(img, alfa, lado: int):
    """Cuadrado de `lado` px centrado en la cara (piel del tercio superior junto al pelo)."""
    cara, _ = ps.detectar_cabeza(img, alfa)
    if cara is None:
        ys, xs = np.nonzero(alfa)
        cy, cx = ys.min() + lado // 2, int(xs.mean())
    else:
        ys, xs = np.nonzero(cara)
        cy, cx = int(ys.mean()), int(xs.mean())
    sup = ps.a_superficie(img, alfa)
    cabeza = pygame.Surface((lado, lado), pygame.SRCALPHA)
    cabeza.blit(sup, (0, 0), pygame.Rect(cx - lado // 2, cy - lado // 2, lado, lado))
    return cabeza, cara


def rasgos_sobrevivientes(img, cara) -> int:
    """Píxeles oscuros (ojo/ceja) DENTRO de la cara: rodeados por piel en al menos 2 lados."""
    if cara is None:
        return 0
    ys, xs = np.nonzero(cara)
    zona = np.zeros_like(cara)
    zona[ys.min():ys.max() + 1, xs.min():xs.max() + 1] = True
    oscuro = luminancia(img.astype(np.float64)) < 110
    piel_vecina = sum(np.roll(cara, d, eje).astype(int) for d in (-1, 1) for eje in (0, 1))
    return int((zona & oscuro & ~cara & (piel_vecina >= 2)).sum())


def main():
    pygame.init()
    from render.fuente_pixel import FuentePixel
    print("Limpiando imágenes originales...")
    fuentes = {n: limpiar(n) for n in IMAGENES}
    alto_idle = ps.altura_cuerpo(fuentes["presidente"][1], fuentes["presidente"][0])
    reservados = colores_cara(list(fuentes.values()))
    print("Colores reservados (piel, sombra, ojo, ceja):", [tuple(int(v) for v in c) for c in reservados])

    actual = paleta_actual()
    variantes = [
        ("A", "ACTUAL 40 PX (MODA)", 40, False, False),
        ("B", "40 PX + DETALLE OSCURO", 40, True, False),
        ("C", "B + COLORES DE CARA", 40, True, True),
        ("D", "C A 48 PX", 48, True, True),
        ("E", "C A 56 PX", 56, True, True),
    ]
    zoom, filas_hoja = 8, []
    # Para la paleta de C/D/E: colores de todos los sprites actuales + las caras reducidas
    base = np.concatenate([np.array(actual)] * 4)
    resultados = {}
    for letra, titulo, altura, detalle, reservar in variantes:
        bloque = alto_idle / (altura - 2)
        reducidos = {}
        for n, (img, opaco) in fuentes.items():
            cabeza = zona_cabeza(img, opaco)
            if detalle:
                reducidos[n] = reducir_con_detalle(img, opaco, bloque, cabeza)
            else:
                reducidos[n] = ps.reducir_por_moda(img, opaco, bloque=bloque)
        if reservar:
            pix = np.concatenate([base] + [r[0][r[1]] for r in reducidos.values()])
            paleta = paleta_con_reservados(reservados, pix)
        else:
            paleta = actual
        lado = round(14 * altura / 40)
        celdas = []
        for n in IMAGENES:
            img, alfa = sprite_final(*reducidos[n], paleta)
            cabeza, cara = recorte_cabeza(img, alfa, lado)
            celdas.append((n, cabeza, alfa.shape, rasgos_sobrevivientes(img, cara)))
        resultados[letra] = celdas
        filas_hoja.append((letra, titulo, altura, celdas))

    # Tamaños: comparación con A
    print("\nTamaño de cada sprite (ancho x alto) y píxeles oscuros que sobreviven dentro de la cara:")
    print(f"{'':<4}" + "".join(f"{ETIQUETAS[n]:>22}" for n in IMAGENES))
    for letra, titulo, altura, celdas in filas_hoja:
        textos = []
        for (n, _, (h, w), oscuros), (_, _, (h0, w0), _) in zip(celdas, resultados["A"]):
            textos.append(f"{w}x{h} ({w * h / (w0 * h0) * 100:3.0f}%) ojo:{oscuros}")
        print(f"{letra:<4}" + "".join(f"{t:>22}" for t in textos))

    # Hoja
    fuente2, fuente1 = FuentePixel(2), FuentePixel(1)
    lado_max = round(14 * 56 / 40) * zoom
    margen_izq, sep = 260, 16
    hoja = pygame.Surface((margen_izq + len(IMAGENES) * (lado_max + sep),
                           40 + len(filas_hoja) * (lado_max + sep)))
    hoja.fill((110, 110, 110))
    for i, n in enumerate(IMAGENES):
        hoja.blit(fuente2.render(ETIQUETAS[n], False, (255, 255, 255)), (margen_izq + i * (lado_max + sep), 12))
    for f, (letra, titulo, altura, celdas) in enumerate(filas_hoja):
        y = 40 + f * (lado_max + sep)
        hoja.blit(fuente2.render(f"{letra})", False, (255, 230, 0)), (12, y + 4))
        hoja.blit(fuente1.render(titulo, False, (255, 255, 255)), (12, y + 30))
        for i, (n, cabeza, (h, w), oscuros) in enumerate(celdas):
            x = margen_izq + i * (lado_max + sep)
            hoja.blit(pygame.transform.scale_by(cabeza, zoom), (x, y))
            hoja.blit(fuente1.render(f"{w}X{h}", False, (230, 230, 230)), (x, y + cabeza.get_height() * zoom + 2))
    pygame.image.save(hoja, SALIDA)
    print(f"\nHoja: {os.path.relpath(SALIDA, RAIZ)}")


if __name__ == "__main__":
    main()
