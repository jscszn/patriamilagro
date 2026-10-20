"""Convierte las imágenes generadas con IA (JPG con fondo magenta) en sprites del juego.

Uso:  python tools/procesar_sprites.py            (procesa todo assets/sprites_raw/)
      python tools/procesar_sprites.py --solo dron,moto   (solo esas entradas de CONFIG; no toca
            los demás sprites, ni las poses, ni la paleta congelada; hoja: sprites_refuerzos_preview.png)

Pasos por imagen:
  1. Estima el fondo (moda de los bordes) y lo quita con flood fill desde el borde.
     Se repite por "capas" si hay más de un fondo (p. ej. franjas blancas + panel magenta).
  2. Quita huecos interiores del color del fondo y el halo del borde.
  3. Borra colores indeseados (el fogonazo violeta del arma) y restos sueltos.
  4. Recorta al personaje.
  5. Reduce a la altura objetivo usando la MODA por bloque (no promedia).
  6. Cuantiza a una paleta compartida de 24 colores y agrega contorno negro de 1 px.
  7. Guarda en assets/sprites/ y actualiza assets/sprites.json (tamaño y ancla en los pies).
  8. Genera assets/sprites_preview.png para revisar.

Poses del presidente (presidente_<pose>.jpeg):
  - El idle (presidente.jpeg) es una pose más (sale como presidente_idle.png).
  - TODAS se reducen con el MISMO factor fijo (PX_POR_PIXEL), así no "bailan" de tamaño y
    reemplazar una imagen no cambia la escala de las demás. Si el cuerpo de una pose difiere
    más de 15 % del idle, se avisa (no se corrige en silencio).
  - Se alinean en un lienzo común con la MISMA ancla en los pies (centro-abajo del cuerpo,
    sin contar el arma).
  - Se detecta la punta del arma de cada pose y se guarda en sprites.json ("bocas"),
    relativa al ancla, para que la bala salga de ahí.
  - Rasgos faciales: a 40 px la reducción se come el ojo. DESPUÉS de reducir y cuantizar se
    pinta 1 píxel de ojo (y, si se indica, ceja o nariz). Las posiciones viven en
    sprites.json -> jugador.rasgos -> {pose: {"ojo": [x, y], ...}}, relativas a la esquina del
    PNG. Para retocar una cara que la reducción deja ilegible se aceptan además "piel" y "pelo":
    listas de puntos [[x, y], ...] que se pintan antes del ojo (la pose acostada los usa).
    Si una pose no tiene posición, se detecta la cabeza (piel en el tercio superior) y se
    propone una. Las posiciones ya guardadas se respetan; para recalcularlas todas:
        python tools/procesar_sprites.py --redetectar-rasgos
  - Traje unificado (paso FINAL): todas las poses (incluido el idle) usan la rampa del traje de
    presidente_disparar. Se remapea por luminosidad cada píxel oscuro/azulado del cuerpo,
    protegiendo por posición la cabeza (pelo y barba) y la franja de los zapatos. Solo se
    usan colores que ya están en la paleta (no se agregan colores).
  - Pulgar del teléfono (pulgar.jpeg = extendido, pulgar_flex.jpeg = presionando): ambos con
    la MISMA escala (la del extendido) y alineados por la BASE (centro del borde inferior, la
    muñeca). Se guarda la yema de cada fotograma (punto de contacto) en sprites.json. Si las
    bases no miden lo mismo, se avisa (no se corrige). Hoja: assets/sprites_pulgar_preview.png
  - Busto del menú (presidente_menu.png): una pose a gran tamaño, recortada a la cintura y
    disuelta en píxeles hacia abajo con tramado ordenado (Bayer 4x4). Ver BUSTO_MENU.
  - Paleta CONGELADA: la paleta compartida se guarda en assets/paleta.json la primera vez y
    luego se reutiliza, para que reemplazar una imagen no cambie los colores de los demás
    sprites. Para recalcularla:  python tools/procesar_sprites.py --recalcular-paleta
  - Hoja de contacto: assets/sprites_presidente_preview.png (poses + idle, fila con los
    píxeles remapeados en magenta y zoom x8 de las cabezas)

Si un sprite queda con restos de fondo o huecos, ajusta su entrada en CONFIG.
Solo usa pygame y numpy.
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame  # noqa: E402

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
RUTA_RAW = os.path.join(RAIZ, "assets", "sprites_raw")
RUTA_SALIDA = os.path.join(RAIZ, "assets", "sprites")
RUTA_JSON = os.path.join(RAIZ, "assets", "sprites.json")
RUTA_PREVIEW = os.path.join(RAIZ, "assets", "sprites_preview.png")
RUTA_PREVIEW_POSES = os.path.join(RAIZ, "assets", "sprites_presidente_preview.png")
RUTA_PALETA = os.path.join(RAIZ, "assets", "paleta.json")
RUTA_PREVIEW_PULGAR = os.path.join(RAIZ, "assets", "sprites_pulgar_preview.png")
RUTA_PREVIEW_SOLO = os.path.join(RAIZ, "assets", "sprites_refuerzos_preview.png")

# Busto épico del menú principal
BUSTO_MENU = {
    "fuente": "presidente_diag_arriba",   # pose de origen (fusil en alto)
    "alto_figura": 200,                   # alto de la figura completa al reducir (px)
    "filas": 116,                         # se conserva de la cabeza hacia abajo (hasta la cintura)
    "fundido": 0.4,                       # fracción inferior que se disuelve en píxeles
    "salida": "presidente_menu.png",
}
BAYER_4X4 = np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]) / 16.0

# Pulgar: archivo original -> animación. El primero define la escala del grupo.
GRUPO_PULGAR = {"pulgar": "quieto", "pulgar_flex": "presionando"}
TOLERANCIA_BASE = 0.10       # aviso si el ancho de la base difiere más de 10 % entre fotogramas
EXTENSIONES = (".jpg", ".jpeg", ".png")

N_COLORES = 24
NEGRO = np.array([0, 0, 0])

# Configuración por imagen (clave = nombre del archivo sin extensión).
#   tolerancia     distancia de color máxima al fondo para el flood fill
#   tol_huecos     distancia para borrar huecos interiores del color del fondo (0 = no borrar)
#   erosion        píxeles a erosionar en el borde (quita el halo)
#   borrar_colores [[color, tolerancia], ...] colores a eliminar (p. ej. fogonazo)
#   altura         altura final en píxeles (incluye el contorno)
#   salida         archivo PNG en assets/sprites/
#   sprite         nombre del sprite en sprites.json
#   ancla          "pies" (centro de las últimas filas, por defecto), "base" (centro del ancho
#                  total, abajo: objetos como las armas, cuyo apoyo sería la culata) o "centro"
#   detalles       fracción mínima del bloque para que ganen el fusil y la banda (piezas finas)
#   boca           "tirador": guarda en sprites.json la punta del arma del tirador que asoma
#                  por el techo (relativa al ancla, x hacia donde mira, y negativa = arriba)
CONFIG_BASE = {"tolerancia": 60, "tol_huecos": 50, "erosion": 1, "borrar_colores": []}
CONFIG = {
    # "presidente" (el idle) se procesa como una pose más: ver POSES_PRESIDENTE.
    "sicario": {"altura": 40, "salida": "sicario_idle.png", "sprite": "sicario"},
    "jefe_1": {"altura": 72, "salida": "jefe_1.png", "sprite": "jefe1",
               # fogonazo violeta en la boca del fusil: lo dibuja el juego como efecto aparte
               "borrar_colores": [[(200, 120, 255), 90], [(160, 60, 230), 70]]},
    "jefe_2": {"altura": 72, "salida": "jefe_2.png", "sprite": "jefe2"},
    "jefe_3": {"altura": 72, "salida": "jefe_3.png", "sprite": "jefe3"},
    # Pulgar de la escena del teléfono (ver GRUPO_PULGAR): la altura es la del extendido;
    # el flexionado usa la MISMA escala, no una altura propia.
    "pulgar": {"altura": 64},
    "pulgar_flex": {},
    # Refuerzos y armas (un solo cuadro, mirando a la derecha). Si no existe su imagen en
    # sprites_raw/, el juego usa el dibujo por código. La altura incluye al tirador del techo.
    "dron": {"altura": 20, "salida": "dron.png", "sprite": "dron", "ancla": "centro"},
    "moto": {"altura": 32, "salida": "moto.png", "sprite": "moto"},
    "camioneta": {"altura": 44, "salida": "camioneta.png", "sprite": "camioneta", "boca": "tirador"},
    # Acostado: el fusil y la banda miden 1-2 px y la moda los volvía negros (ver reducir_por_moda)
    "presidente_agachado": {"detalles": 0.3},
    # arma_triple, arma_rapida y vida: se probaron (2026-10-19) y el usuario prefirió el dibujo
    # por código (render/pixelart.py). Sus JPG siguen en sprites_raw/, pero se omiten a propósito.
}

# Poses del presidente: dirección del cañón en cada una (mirando a la derecha; y crece hacia abajo).
# Se aceptan ajustes por pose en CONFIG["presidente_<pose>"] (tolerancia, tol_huecos, ...).
POSES_PRESIDENTE = {
    "idle": (1, 1),                                        # presidente.jpeg: fusil bajo, hacia abajo
    "disparar": (1, 0), "correr_a": (1, 0), "correr_b": (1, 0), "saltar": (1, 0),
    "agachado": (1, 0), "diag_arriba": (1, -1), "arriba": (0, -1), "diag_abajo": (1, 1),
    "herido": (1, -1),
}
APUNTADAS = {"diag_arriba", "arriba", "diag_abajo"}       # si faltan: respaldo = disparar
# Poses HORIZONTALES (el presidente acostado boca abajo, cabeza a la derecha): el ancla va en el
# centro del cuerpo (así no se desplaza al pasar de pie a acostado), el tamaño se compara por el
# LARGO del cuerpo (pies a cabeza) y los zapatos se protegen por columnas (a la izquierda).
POSES_HORIZONTALES = {"agachado"}
COLUMNAS_ZAPATOS = 5       # columnas protegidas a la izquierda de una pose horizontal (zapatos)
# Factor de escala FIJO de las poses: píxeles de la imagen original por cada píxel del sprite.
# Se midió con el idle original (cuerpo de 974 px -> 38 px + contorno = 40 px). Es fijo para
# que reemplazar una imagen (como el idle) no cambie el tamaño de las demás poses.
PX_POR_PIXEL = 974 / 38
POSE_REFERENCIA_PROPORCION = "idle"                        # los avisos de tamaño se miden contra el idle
TOLERANCIA_ESCALA = 0.15                                   # aviso si el cuerpo difiere más de 15 %
# Animaciones del jugador -> lista de poses (cada pose es un cuadro)
ANIMACIONES_JUGADOR = {
    "quieto": ["idle"],               # de pie sin disparar
    "disparar": ["disparar"],         # de pie disparando al frente
    "correr": ["correr_a", "disparar", "correr_b", "disparar"],
    "saltar": ["saltar"],
    "agachado": ["agachado"],
    "herido": ["herido"],
    "diag_arriba": ["diag_arriba"],
    "arriba": ["arriba"],
    "diag_abajo": ["diag_abajo"],
    "abajo": ["diag_abajo"],          # en el aire apuntando abajo: se reutiliza diag_abajo
}


# =============================================================================
# Utilidades de máscaras (numpy, sin scipy)
# =============================================================================
def vecinos(mascara: np.ndarray, ocho: bool = True) -> np.ndarray:
    """Dilata 1 píxel: True donde algún vecino es True."""
    m = mascara
    r = m.copy()
    r[1:, :] |= m[:-1, :]
    r[:-1, :] |= m[1:, :]
    r[:, 1:] |= m[:, :-1]
    r[:, :-1] |= m[:, 1:]
    if ocho:
        r[1:, 1:] |= m[:-1, :-1]
        r[1:, :-1] |= m[:-1, 1:]
        r[:-1, 1:] |= m[1:, :-1]
        r[:-1, :-1] |= m[1:, 1:]
    return r


def erosionar(mascara: np.ndarray, pasos: int = 1) -> np.ndarray:
    for _ in range(pasos):
        mascara = ~vecinos(~mascara)
    return mascara


def inundar(semillas: np.ndarray, permitido: np.ndarray) -> np.ndarray:
    """Flood fill: crece desde las semillas solo por píxeles permitidos (8 vecinos)."""
    region = semillas & permitido
    while True:
        nueva = vecinos(region) & permitido
        if nueva.sum() == region.sum():
            return region
        # Varias dilataciones por vuelta para ir más rápido
        for _ in range(8):
            nueva = vecinos(nueva) & permitido
        region = nueva


def borde_de(forma) -> np.ndarray:
    m = np.zeros(forma, bool)
    m[0, :] = m[-1, :] = m[:, 0] = m[:, -1] = True
    return m


def distancia(img: np.ndarray, color) -> np.ndarray:
    return np.sqrt(((img.astype(np.int32) - np.array(color, np.int32)) ** 2).sum(axis=-1))


def moda_color(pixeles: np.ndarray, bits: int = 4):
    """Color más frecuente (cuantizando para tolerar el ruido JPG). Devuelve (color, fracción)."""
    q = (pixeles >> (8 - bits)).astype(np.int32)
    claves = (q[:, 0] << (2 * bits)) | (q[:, 1] << bits) | q[:, 2]
    valores, cuentas = np.unique(claves, return_counts=True)
    i = cuentas.argmax()
    color = pixeles[claves == valores[i]].mean(axis=0)
    return color, cuentas[i] / len(claves)


def caja(mascara: np.ndarray):
    ys, xs = np.nonzero(mascara)
    return ys.min(), ys.max() + 1, xs.min(), xs.max() + 1


# =============================================================================
# Pasos del procesamiento
# =============================================================================
def cargar(ruta: str) -> np.ndarray:
    sup = pygame.image.load(ruta)
    return pygame.surfarray.array3d(sup).transpose(1, 0, 2).copy()   # (alto, ancho, 3)


def quitar_fondo(img, conf, informe):
    """Paso 1: por capas, estima el fondo con la moda del borde y lo inunda desde el borde."""
    opaco = np.ones(img.shape[:2], bool)
    fondos = []
    for _ in range(3):
        y0, y1, x0, x1 = caja(opaco)
        sub_img, sub_op = img[y0:y1, x0:x1], opaco[y0:y1, x0:x1]
        perimetro = borde_de(sub_op.shape)
        b = perimetro & sub_op
        if b.sum() < 20:
            break
        color, _ = moda_color(sub_img[b])
        # Es fondo solo si ocupa la mayor parte de TODO el perímetro (no solo de lo opaco):
        # así no confundimos el contorno negro del personaje con un fondo. Se mide por
        # distancia de color (y no por "bin" exacto) porque el ruido JPG reparte el magenta.
        parecidos = (distancia(sub_img[b], color) <= conf["tolerancia"]).sum()
        fraccion = parecidos / perimetro.sum()
        informe.setdefault("fracciones", []).append(round(float(fraccion), 2))
        if fraccion < 0.5:
            break
        cerca = (distancia(sub_img, color) <= conf["tolerancia"]) & sub_op
        # Semillas: esquinas y todo el borde (hay personajes que tocan el borde inferior)
        quitado = inundar(borde_de(sub_op.shape), cerca)
        if quitado.sum() == 0:
            break
        opaco[y0:y1, x0:x1] &= ~quitado
        fondos.append(color)
        informe["fondos"].append([int(c) for c in color])
    return opaco, fondos


def quitar_huecos_y_halo(img, opaco, fondos, conf):
    """Paso 2: huecos interiores del color del fondo + halo del borde."""
    if conf["tol_huecos"] and fondos:
        # Solo el ÚLTIMO fondo (el que toca al personaje) puede quedar encerrado en huecos,
        # p. ej. entre las piernas. Los fondos externos (franjas blancas de jefe_3) no: si no,
        # se borraría también un traje blanco.
        opaco &= distancia(img, fondos[-1]) > conf["tol_huecos"]
    if conf["erosion"]:
        opaco = erosionar(opaco, conf["erosion"])
    # Píxeles del borde cuyo color está más cerca del fondo que del interior del personaje
    interior = erosionar(opaco, 2)
    borde = opaco & ~interior
    suma = np.zeros(img.shape, np.float64)
    cuenta = np.zeros(img.shape[:2], np.float64)
    for dy in (-2, -1, 0, 1, 2):
        for dx in (-2, -1, 0, 1, 2):
            desplazado = np.roll(np.roll(interior, dy, 0), dx, 1)
            suma += np.roll(np.roll(img, dy, 0), dx, 1) * desplazado[..., None]
            cuenta += desplazado
    media_interior = suma / np.maximum(cuenta, 1)[..., None]
    d_personaje = np.sqrt(((img - media_interior) ** 2).sum(-1))
    d_fondo = np.min([distancia(img, f) for f in fondos], axis=0) if fondos else np.inf
    halo = borde & (cuenta > 0) & (d_fondo < d_personaje)
    return opaco & ~halo


def componentes(mascara: np.ndarray):
    """Etiqueta componentes conexas (8 vecinos) con BFS. Devuelve (etiquetas, tamaños)."""
    from collections import deque
    alto, ancho = mascara.shape
    etiquetas = np.zeros(mascara.shape, np.int32)
    tamanos = [0]
    for y0, x0 in zip(*np.nonzero(mascara)):
        if etiquetas[y0, x0]:
            continue
        n = len(tamanos)
        etiquetas[y0, x0] = n
        cola, tam = deque([(y0, x0)]), 0
        while cola:
            y, x = cola.popleft()
            tam += 1
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    yy, xx = y + dy, x + dx
                    if 0 <= yy < alto and 0 <= xx < ancho and mascara[yy, xx] and not etiquetas[yy, xx]:
                        etiquetas[yy, xx] = n
                        cola.append((yy, xx))
        tamanos.append(tam)
    return etiquetas, np.array(tamanos)


def quedarse_con_principal(opaco: np.ndarray, factor: int = 4, minimo: float = 0.05) -> np.ndarray:
    """Paso 3b: conserva la figura principal (la componente más grande) y las piezas grandes
    sueltas (>5 % de la principal, p. ej. un arma separada); borra motas y fogonazos sueltos.
    Se etiqueta sobre una versión reducida x4 para que sea rápido en Python puro."""
    alto, ancho = opaco.shape
    h, w = alto // factor, ancho // factor
    reducida = opaco[:h * factor, :w * factor].reshape(h, factor, w, factor).any(axis=(1, 3))
    etiquetas, tamanos = componentes(reducida)
    grande = tamanos.max()
    validas = np.nonzero(tamanos >= grande * minimo)[0]
    validas = validas[validas > 0]
    mantener = np.isin(etiquetas, validas)
    mantener = np.repeat(np.repeat(mantener, factor, 0), factor, 1)
    resultado = np.zeros_like(opaco)
    resultado[:h * factor, :w * factor] = mantener
    return opaco & resultado


def es_detalle(img: np.ndarray) -> np.ndarray:
    """Piezas finas que la moda se come: el gris del fusil y los colores muy saturados de la
    banda tricolor (rojo, amarillo, azul)."""
    m = img.astype(np.int32)
    return es_arma(img) | ((m.max(-1) - m.min(-1) > 110) & (m.max(-1) > 120))


def reducir_por_moda(img, opaco, altura_contenido=None, bloque=None, detalles=None):
    """Paso 5: cada píxel de salida = color más frecuente de su bloque (si el bloque es opaco).
    Se indica la altura de salida (el bloque sale de ella) o directamente el tamaño de bloque
    (así varias imágenes comparten el MISMO factor de escala).
    detalles=f: si las piezas finas (es_detalle) cubren al menos la fracción f del bloque, gana
    la moda de esas piezas (para que un fusil delgado no se vuelva negro de contorno)."""
    finos = es_detalle(img) if detalles else None
    alto, ancho = opaco.shape
    if bloque is None:
        bloque = alto / altura_contenido
    altura_contenido = max(1, round(alto / bloque))
    ancho_salida = max(1, round(ancho / bloque))
    salida = np.zeros((altura_contenido, ancho_salida, 3), np.uint8)
    alfa = np.zeros((altura_contenido, ancho_salida), bool)
    for oy in range(altura_contenido):
        y0, y1 = int(oy * bloque), max(int(oy * bloque) + 1, int((oy + 1) * bloque))
        for ox in range(ancho_salida):
            x0, x1 = int(ox * bloque), max(int(ox * bloque) + 1, int((ox + 1) * bloque))
            m = opaco[y0:y1, x0:x1]
            if m.mean() < 0.5:
                continue
            if finos is not None and (finos[y0:y1, x0:x1] & m).mean() >= detalles:
                color, _ = moda_color(img[y0:y1, x0:x1][m & finos[y0:y1, x0:x1]], bits=5)
            else:
                color, _ = moda_color(img[y0:y1, x0:x1][m], bits=5)
            salida[oy, ox] = color.round().astype(np.uint8)
            alfa[oy, ox] = True
    return salida, alfa


def kmeans(pixeles: np.ndarray, k: int, iteraciones: int = 40) -> np.ndarray:
    """K-means sobre los colores DISTINTOS (no sobre todos los píxeles), para que los detalles
    pequeños y saturados (banda presidencial, cadenas de oro) no se pierdan frente a los trajes.
    Inicialización k-means++ con semilla fija: el resultado es siempre el mismo."""
    datos = np.unique((pixeles >> 3) << 3, axis=0).astype(np.float64)
    rng = np.random.default_rng(7)
    centros = [datos[rng.integers(len(datos))]]
    for _ in range(k - 1):
        d = np.min([((datos - c) ** 2).sum(1) for c in centros], axis=0)
        centros.append(datos[rng.choice(len(datos), p=d / d.sum())])
    centros = np.array(centros)
    for _ in range(iteraciones):
        etiquetas = ((datos[:, None, :] - centros[None]) ** 2).sum(-1).argmin(1)
        for j in range(k):
            if (etiquetas == j).any():
                centros[j] = datos[etiquetas == j].mean(0)
    return centros.round().astype(np.uint8)


def cuantizar(img, alfa, paleta):
    d = ((img[..., None, :].astype(np.int32) - paleta[None, None].astype(np.int32)) ** 2).sum(-1)
    resultado = paleta[d.argmin(-1)]
    resultado[~alfa] = 0
    return resultado


def contorno(img, alfa):
    """Paso 6b: agrega un contorno negro de 1 px alrededor de la silueta (4 vecinos)."""
    borde = vecinos(alfa, ocho=False) & ~alfa
    img = img.copy()
    img[borde] = NEGRO
    return img, alfa | borde


def ancla_pies(alfa: np.ndarray):
    """Punto de apoyo: centro horizontal de los píxeles de las últimas filas (los pies)."""
    filas = np.nonzero(alfa.any(1))[0]
    abajo = filas.max()
    zona = alfa[max(0, abajo - max(2, alfa.shape[0] // 12)):abajo + 1]
    xs = np.nonzero(zona.any(0))[0]
    return int(round((xs.min() + xs.max()) / 2)), int(abajo + 1)


def ancla_centro(alfa: np.ndarray):
    """Centro de la caja de la silueta (para lo que vuela, como el dron)."""
    ys, xs = np.nonzero(alfa)
    return int(round((xs.min() + xs.max()) / 2)), int(round((ys.min() + ys.max() + 1) / 2))


def ancla_base(alfa: np.ndarray):
    """Centro del ancho total de la silueta, en su fila más baja."""
    ys, xs = np.nonzero(alfa)
    return int(round((xs.min() + xs.max()) / 2)), int(ys.max() + 1)


def boca_tirador(alfa: np.ndarray):
    """Punta del arma del tirador que asoma por el techo (sunroof): el techo es la primera fila
    (desde arriba) cuya silueta ocupa más de la mitad del ancho; lo de encima es el tirador, y
    su píxel más adelantado (a la derecha) es la boca del fusil."""
    anchos = alfa.sum(1)
    techo = int(np.nonzero(anchos > anchos.max() * 0.5)[0][0])
    ys, xs = np.nonzero(alfa[:techo])
    if not len(xs):
        return None
    i = int(np.argmax(xs))
    return int(xs[i]), int(ys[i])


def a_superficie(img, alfa) -> pygame.Surface:
    alto, ancho = alfa.shape
    sup = pygame.Surface((ancho, alto), pygame.SRCALPHA)
    rgba = np.dstack([img, (alfa * 255).astype(np.uint8)])
    pygame.surfarray.pixels3d(sup)[:] = rgba[..., :3].transpose(1, 0, 2)
    pygame.surfarray.pixels_alpha(sup)[:] = rgba[..., 3].T
    return sup


# =============================================================================
# Arma, cuerpo y punta del cañón (para las poses)
# =============================================================================
def es_arma(img: np.ndarray, valor_min: int = 110) -> np.ndarray:
    """Píxeles del fusil: grises poco saturados (la camisa blanca es más clara, el traje es
    azul saturado y el contorno es negro, así que no se confunden)."""
    m = img.astype(np.int32)
    saturacion = m.max(-1) - m.min(-1)
    valor = m.max(-1)
    return (saturacion < 32) & (valor >= valor_min) & (valor <= 232)


def altura_cuerpo(opaco: np.ndarray, img: np.ndarray) -> int:
    """Alto del cuerpo (cabeza a pies) sin contar el arma."""
    cuerpo = opaco & ~es_arma(img)
    filas = np.nonzero(cuerpo.any(1))[0]
    return int(filas.max() - filas.min() + 1)


def largo_cuerpo(opaco: np.ndarray, img: np.ndarray) -> int:
    """Ancho del cuerpo sin contar el arma (para una pose horizontal es su largo, pies a cabeza)."""
    cuerpo = opaco & ~es_arma(img)
    columnas = np.nonzero(cuerpo.any(0))[0]
    return int(columnas.max() - columnas.min() + 1)


def ancla_cuerpo_horizontal(alfa: np.ndarray, img: np.ndarray):
    """Ancla de una pose acostada: fila más baja del cuerpo y, en x, el centro del cuerpo sin el
    arma. De pie el ancla es el centro de las piernas; acostado, el centro del cuerpo queda en
    el mismo punto, así que el presidente se tiende hacia los dos lados sin saltar."""
    cuerpo = alfa & ~es_arma(img)
    filas = np.nonzero(cuerpo.any(1))[0]
    columnas = np.nonzero(cuerpo.any(0))[0]
    return int(round((columnas.min() + columnas.max()) / 2)), int(filas.max() + 1)


def ancla_cuerpo(alfa: np.ndarray, img: np.ndarray):
    """Ancla en los pies: fila más baja del cuerpo (sin arma) y, en x, la mediana del cuerpo en
    su 40 % inferior (las piernas): estable aunque las piernas se abran al correr."""
    cuerpo = alfa & ~es_arma(img)
    filas = np.nonzero(cuerpo.any(1))[0]
    arriba, abajo = filas.min(), filas.max()
    desde = int(abajo - (abajo - arriba) * 0.4)
    _, xs = np.nonzero(cuerpo[desde:abajo + 1])
    return int(round(np.median(xs))), int(abajo + 1)


def punta_arma(alfa: np.ndarray, img: np.ndarray, direccion):
    """Píxel del arma más lejano en la dirección del cañón (o None si no hay arma visible).
    Al reducir, el cañón queda en gris medio, así que aquí se aceptan grises más oscuros que
    al medir el cuerpo; solo cuentan los grises conectados a la parte clara del fusil."""
    claro = alfa & es_arma(img)
    if not claro.any():
        return None
    arma = inundar(claro, alfa & es_arma(img, valor_min=60))
    ys, xs = np.nonzero(arma)
    dx, dy = direccion
    i = int(np.argmax(xs * dx + ys * dy))
    x, y = int(xs[i]), int(ys[i])
    # Al reducir, la punta del cañón queda negra (se funde con el contorno): se sigue avanzando
    # en la dirección del cañón mientras haya píxeles opacos (tolerando 1 px de desvío lateral).
    alto, ancho = alfa.shape
    lateral = [(0, 0), (dy, -dx), (-dy, dx)] if dx and dy else [(0, 0), (abs(dy), abs(dx)), (-abs(dy), -abs(dx))]
    for _ in range(20):
        for ox, oy in lateral:
            nx, ny = x + dx + ox, y + dy + oy
            if 0 <= nx < ancho and 0 <= ny < alto and alfa[ny, nx]:
                x, y = nx, ny
                break
        else:
            break
    return x, y


# =============================================================================
# Diagnóstico
# =============================================================================
def es_magenta(img: np.ndarray) -> np.ndarray:
    """Píxeles de tono magenta (rojo y azul altos, verde bajo): típicos restos del fondo."""
    r, g, b = (img[..., i].astype(np.int32) for i in range(3))
    return (r - g > 70) & (b - g > 50)


def diagnosticar(img, alfa, fondos):
    """Cuenta restos de fondo (píxeles magenta) y huecos interiores en el sprite final."""
    restos = int((alfa & es_magenta(img)).sum())
    exterior = inundar(borde_de(alfa.shape), ~alfa)
    huecos = int((~alfa & ~exterior).sum())
    return restos, huecos


# =============================================================================
def configuracion(nombre: str) -> dict:
    conf = dict(CONFIG_BASE)
    conf.update(CONFIG.get(nombre, {}))
    return conf


def procesar(nombre: str, ruta: str, bloque: float = None, altura: int = None) -> dict:
    """Limpia la imagen y la reduce: a conf["altura"] (o `altura`), o con un tamaño de `bloque` fijo."""
    conf = configuracion(nombre)
    if altura is not None:
        conf["altura"] = altura
    if "altura" not in conf and bloque is None:
        raise ValueError(f"Falta configuración para '{nombre}' en CONFIG")
    informe = {"nombre": nombre, "fondos": []}
    img = cargar(ruta)

    opaco, fondos = quitar_fondo(img, conf, informe)
    opaco = quitar_huecos_y_halo(img, opaco, fondos, conf)
    for color, tol in conf["borrar_colores"]:                 # paso 3: fogonazo
        opaco &= distancia(img, color) > tol
    opaco &= ~es_magenta(img)                                # restos de halo con tono magenta
    opaco = quedarse_con_principal(opaco)

    y0, y1, x0, x1 = caja(opaco)                              # paso 4: recorte (1 px de margen)
    y0, x0 = max(0, y0 - 1), max(0, x0 - 1)
    y1, x1 = min(img.shape[0], y1 + 1), min(img.shape[1], x1 + 1)
    img, opaco = img[y0:y1, x0:x1], opaco[y0:y1, x0:x1]

    informe["altura_cuerpo_original"] = altura_cuerpo(opaco, img)
    informe["largo_cuerpo_original"] = largo_cuerpo(opaco, img)
    if bloque is None:
        bloque = opaco.shape[0] / (conf["altura"] - 2)            # 1 px por lado para el contorno
    reducido, alfa = reducir_por_moda(img, opaco, bloque=bloque, detalles=conf.get("detalles"))
    informe.update(conf=conf, reducido=reducido, alfa=alfa, fondos_rgb=fondos, bloque=bloque,
                   tamano_original=cargar_tamano(nombre))
    return informe


def cargar_tamano(nombre: str):
    """Tamaño (ancho, alto) de la imagen original, para el informe."""
    for ext in EXTENSIONES:
        ruta = os.path.join(RUTA_RAW, nombre + ext)
        if os.path.isfile(ruta):
            return pygame.image.load(ruta).get_size()
    return None


def cargar_paleta():
    """Paleta congelada (lista de [r, g, b]) o None si no existe o está dañada."""
    try:
        with open(RUTA_PALETA, encoding="utf-8") as f:
            colores = json.load(f)["colores"]
        paleta = np.array(colores, np.uint8)
        return paleta if paleta.ndim == 2 and paleta.shape[1] == 3 else None
    except (OSError, ValueError, KeyError):
        return None


def guardar_paleta(paleta) -> None:
    datos = {"_ayuda": "Paleta compartida de los sprites (congelada). Bórrala o usa "
                       "--recalcular-paleta para recalcularla con k-means.",
             "colores": [[int(v) for v in c] for c in paleta]}
    with open(RUTA_PALETA, "w", encoding="utf-8") as f:
        json.dump(datos, f, indent=2)


def solo_pedidos():
    """Nombres de --solo a,b,c (o None si no se pasó)."""
    for i, arg in enumerate(sys.argv):
        if arg == "--solo" and i + 1 < len(sys.argv):
            return [n for n in sys.argv[i + 1].split(",") if n]
        if arg.startswith("--solo="):
            return [n for n in arg.split("=", 1)[1].split(",") if n]
    return None


def main():
    redetectar = "--redetectar-rasgos" in sys.argv
    recalcular_paleta = "--recalcular-paleta" in sys.argv
    solo = solo_pedidos()
    if solo is not None:
        desconocidos = [n for n in solo if n not in CONFIG or "salida" not in CONFIG[n]]
        if desconocidos or recalcular_paleta:
            print(f"--solo: {desconocidos or 'no se combina con --recalcular-paleta'}"
                  " (solo entradas de CONFIG con salida propia)")
            return
    pygame.init()
    archivos = sorted(f for f in os.listdir(RUTA_RAW) if f.lower().endswith(EXTENSIONES))
    if not archivos:
        print(f"No hay imágenes en {RUTA_RAW}")
        return
    rutas = {os.path.splitext(a)[0]: os.path.join(RUTA_RAW, a) for a in archivos}
    informes = []
    if solo is not None:
        faltan = [n for n in solo if n not in rutas]
        if faltan:
            print(f"--solo: no están en {RUTA_RAW}: {faltan}")
            return
        rutas = {n: rutas[n] for n in solo}
    for nombre, ruta in rutas.items():
        if nombre_pose(nombre) is not None or nombre in GRUPO_PULGAR:
            continue                                   # poses y pulgar van después, con escala común
        if nombre not in CONFIG:
            print(f"  (se omite {os.path.basename(ruta)}: no está en CONFIG)")
            continue
        print(f"Procesando {os.path.basename(ruta)}...")
        informes.append(procesar(nombre, ruta))

    poses = procesar_poses(rutas) if solo is None else []
    pulgar = procesar_pulgar(rutas) if solo is None else []

    # Paleta compartida (todos los sprites y poses): congelada en assets/paleta.json
    paleta = cargar_paleta() if not recalcular_paleta else None
    if paleta is None and solo is not None:
        print(f"--solo necesita la paleta congelada ({os.path.relpath(RUTA_PALETA, RAIZ)}): corre el script completo")
        return
    if paleta is None:
        todos = np.concatenate([inf["reducido"][inf["alfa"]] for inf in informes + poses + pulgar])
        paleta = np.vstack([kmeans(todos, N_COLORES - 1), NEGRO[None].astype(np.uint8)])
        guardar_paleta(paleta)
        print(f"Paleta recalculada y guardada en {os.path.relpath(RUTA_PALETA, RAIZ)}")
    else:
        print(f"Paleta congelada: {os.path.relpath(RUTA_PALETA, RAIZ)} ({len(paleta)} colores)")

    os.makedirs(RUTA_SALIDA, exist_ok=True)
    with open(RUTA_JSON, encoding="utf-8") as f:
        config_sprites = json.load(f)
    for inf in informes:
        img = cuantizar(inf["reducido"], inf["alfa"], paleta)
        alto_c, ancho_c = inf["alfa"].shape
        lienzo = np.zeros((alto_c + 2, ancho_c + 2, 3), np.uint8)
        alfa = np.zeros((alto_c + 2, ancho_c + 2), bool)
        lienzo[1:-1, 1:-1], alfa[1:-1, 1:-1] = img, inf["alfa"]
        img, alfa = contorno(lienzo, alfa)
        sup = a_superficie(img, alfa)
        pygame.image.save(sup, os.path.join(RUTA_SALIDA, inf["conf"]["salida"]))
        ancla = {"centro": ancla_centro, "base": ancla_base}.get(inf["conf"].get("ancla"), ancla_pies)(alfa)
        restos, huecos = diagnosticar(img, alfa, inf["fondos_rgb"])
        inf.update(superficie=sup, ancla=ancla, restos=restos, huecos=huecos)
        if inf["conf"].get("sprite"):
            entrada = {
                "archivo": f"sprites/{inf['conf']['salida']}",
                "frame": [sup.get_width(), sup.get_height()],
                "ancla": list(ancla),
                "fps": 8,
                "animaciones": {"quieto": [0]},
            }
            if inf["conf"].get("boca") == "tirador":
                punta = boca_tirador(alfa)
                if punta is None:
                    print(f"  AVISO {inf['nombre']}: no se encontró al tirador del techo")
                else:
                    inf["boca"] = punta
                    entrada["boca"] = [punta[0] - ancla[0], punta[1] - ancla[1]]
            config_sprites[inf["conf"]["sprite"]] = entrada
        print(f"  {inf['nombre']:<11} {sup.get_width():>3}x{sup.get_height():<3} ancla={ancla} "
              f"fondos={inf['fondos']} perimetro={inf.get('fracciones')} restos_fondo={restos} huecos_interiores={huecos}")
    if poses:
        previos = {} if redetectar else config_sprites.get("jugador", {}).get("rasgos", {})
        config_sprites["jugador"] = guardar_poses(poses, paleta, previos,
                                                  config_sprites.get("jugador", {}).get("ancla"))
    if pulgar:
        config_sprites["pulgar"] = guardar_pulgar(pulgar, paleta)
    if BUSTO_MENU["fuente"] in rutas and solo is None:
        config_sprites["presidente_menu"] = generar_busto(rutas[BUSTO_MENU["fuente"]], paleta)
    # Escritura atómica: si algo falla al serializar, sprites.json queda intacto
    temporal = RUTA_JSON + ".tmp"
    with open(temporal, "w", encoding="utf-8") as f:
        json.dump(config_sprites, f, indent=2, ensure_ascii=False)
    os.replace(temporal, RUTA_JSON)
    verificar_sin_marcas()

    if solo is not None:
        generar_preview_comparacion(informes)
        print(f"Listo. Revisa {os.path.relpath(RUTA_PREVIEW_SOLO, RAIZ)}")
        return
    generar_preview(informes, paleta)
    print(f"Listo. Revisa {os.path.relpath(RUTA_PREVIEW, RAIZ)}"
          + (f" y {os.path.relpath(RUTA_PREVIEW_POSES, RAIZ)}" if poses else ""))


# =============================================================================
# Poses del presidente
# =============================================================================
def nombre_pose(nombre_archivo: str):
    """presidente -> idle; presidente_correr_a -> correr_a; otro -> None."""
    if nombre_archivo == "presidente":
        return "idle"
    if nombre_archivo.startswith("presidente_"):
        return nombre_archivo[len("presidente_"):]
    return None


def procesar_poses(rutas: dict) -> list:
    """Limpia y reduce las poses (idle incluido) con el MISMO factor de escala fijo."""
    poses = []
    print(f"Poses del presidente: 1 píxel del sprite = {PX_POR_PIXEL:.1f} px de la imagen original")
    for nombre, ruta in rutas.items():
        pose = nombre_pose(nombre)
        if pose is None:
            continue
        if pose not in POSES_PRESIDENTE:
            print(f"  (se omite {nombre}: pose desconocida)")
            continue
        inf = procesar(nombre, ruta, bloque=PX_POR_PIXEL)
        inf["pose"] = pose
        poses.append(inf)
    if not poses:
        return []
    # Proporción del cuerpo respecto al idle (o a la primera pose si no hay idle)
    ref = next((p for p in poses if p["pose"] == POSE_REFERENCIA_PROPORCION), poses[0])
    for p in poses:
        medida = "largo_cuerpo_original" if p["pose"] in POSES_HORIZONTALES else "altura_cuerpo_original"
        p["proporcion"] = p[medida] / ref["altura_cuerpo_original"]
    return poses


def guardar_poses(poses: list, paleta, rasgos_previos: dict = None, ancla_previa=None) -> dict:
    """Cuantiza, alinea por los pies en un lienzo común, pinta los rasgos faciales, guarda PNG y
    arma la entrada del JSON. rasgos_previos: posiciones ya guardadas (se respetan).
    ancla_previa: ancla común con que se guardaron; si el lienzo crece (p. ej. por una pose más
    ancha), los rasgos guardados se desplazan igual que el ancla y siguen sobre la cara."""
    rasgos_previos = rasgos_previos or {}
    rasgos_finales = {}
    preparadas = []
    for inf in poses:
        img = cuantizar(inf["reducido"], inf["alfa"], paleta)
        alto_c, ancho_c = inf["alfa"].shape
        lienzo = np.zeros((alto_c + 2, ancho_c + 2, 3), np.uint8)
        alfa = np.zeros((alto_c + 2, ancho_c + 2), bool)
        lienzo[1:-1, 1:-1], alfa[1:-1, 1:-1] = img, inf["alfa"]
        # Ancla y punta del arma se miden con los colores antes del contorno
        ref = np.zeros_like(lienzo)
        ref[1:-1, 1:-1] = inf["reducido"]
        horizontal = inf["pose"] in POSES_HORIZONTALES
        ancla = (ancla_cuerpo_horizontal if horizontal else ancla_cuerpo)(alfa, ref)
        punta = punta_arma(alfa, ref, POSES_PRESIDENTE[inf["pose"]])
        img, alfa = contorno(lienzo, alfa)
        restos, huecos = diagnosticar(img, alfa, inf["fondos_rgb"])
        preparadas.append(dict(inf, img=img, alfa_final=alfa, ancla=ancla, punta=punta,
                               restos=restos, huecos=huecos))

    # Lienzo común: todas las poses comparten tamaño y ancla
    izquierda = max(p["ancla"][0] for p in preparadas)
    derecha = max(p["alfa_final"].shape[1] - p["ancla"][0] for p in preparadas)
    arriba = max(p["ancla"][1] for p in preparadas)
    abajo = max(p["alfa_final"].shape[0] - p["ancla"][1] for p in preparadas)
    ancho, alto = izquierda + derecha, arriba + abajo
    ancla_comun = (izquierda, arriba)
    if ancla_previa is not None and tuple(ancla_previa) != ancla_comun:
        dx, dy = ancla_comun[0] - ancla_previa[0], ancla_comun[1] - ancla_previa[1]
        print(f"  El lienzo común cambió: los rasgos guardados se desplazan ({dx:+d}, {dy:+d})")
        rasgos_previos = {pose: {k: desplazar_rasgo(v, dx, dy) for k, v in r.items()}
                          for pose, r in rasgos_previos.items()}

    archivos, bocas = {}, {}
    for p in preparadas:
        ax, ay = p["ancla"]
        ox, oy = izquierda - ax, arriba - ay
        img = np.zeros((alto, ancho, 3), np.uint8)
        alfa = np.zeros((alto, ancho), bool)
        h, w = p["alfa_final"].shape
        img[oy:oy + h, ox:ox + w], alfa[oy:oy + h, ox:ox + w] = p["img"], p["alfa_final"]

        # Rasgos faciales (después de reducir y cuantizar)
        cara, dudas = detectar_cabeza(img, alfa)
        if p["pose"] in rasgos_previos:
            rasgos = rasgos_previos[p["pose"]]
            origen = "guardado"
        elif cara is not None:
            ojo, dudas_ojo = proponer_ojo(cara)
            rasgos, origen = {"ojo": ojo}, "auto"
            dudas += dudas_ojo
        else:
            rasgos, origen = {}, "sin cara"
        dudas += dibujar_rasgos(img, alfa, rasgos, paleta)
        rasgos_finales[p["pose"]] = rasgos
        p.update(cara=cara, rasgos=rasgos, origen_rasgos=origen, dudas_rasgos=dudas,
                 img_lienzo=img, alfa_lienzo=alfa, protegida=zona_protegida(img, alfa, cara, arriba,
                                                    horizontal=p["pose"] in POSES_HORIZONTALES))

    # Paso FINAL: traje con la rampa de la pose de referencia, en todas las poses y el idle
    ref = next((p for p in preparadas if p["pose"] == POSE_REFERENCIA_TRAJE), preparadas[0])
    rampa = rampa_traje(ref["img_lienzo"], ref["alfa_lienzo"], ref["protegida"])
    print(f"  Rampa del traje (de {ref['pose']}): {[tuple(int(v) for v in c) for c in rampa]} "
          f"+ negro del contorno interior (no se toca)")

    for p in preparadas:
        ax, ay = p["ancla"]
        img, alfa = p["img_lienzo"], p["alfa_lienzo"]
        img, cambiados, resumen = unificar_traje(img, alfa, p["protegida"], rampa)
        p.update(img_lienzo=img, cambiados=cambiados, resumen_traje=resumen)

        sup = a_superficie(img, alfa)
        archivo = f"sprites/presidente_{p['pose']}.png"
        pygame.image.save(sup, os.path.join(RAIZ, "assets", archivo))
        archivos[p["pose"]] = archivo
        p["superficie"] = sup
        if p["punta"] is not None:
            bocas[archivo] = [p["punta"][0] - ax, p["punta"][1] - ay]   # relativa al ancla (pies)
        aviso = ""
        if abs(p["proporcion"] - 1) > TOLERANCIA_ESCALA:
            aviso = f"  <-- AVISO: cuerpo {p['proporcion'] * 100 - 100:+.0f}% respecto al idle"
        print(f"  {p['pose']:<12} cuerpo={p['proporcion'] * 100:5.1f}% del idle  boca={bocas.get(archivo)} "
              f"restos_fondo={p['restos']} huecos={p['huecos']}{aviso}")
        estado = "DUDOSO: " + "; ".join(p["dudas_rasgos"]) if p["dudas_rasgos"] else "ok"
        print(f"  {'':<12} rasgos ({p['origen_rasgos']}) {p['rasgos']}  -> {estado}")
        print(f"  {'':<12} traje: {int(cambiados.sum())} px remapeados {p['resumen_traje']}")

    # Respaldos si falta una pose: apuntadas -> disparar; el resto -> idle
    respaldo_idle = archivos.get("idle", archivos.get("disparar"))

    def archivo_de(pose: str) -> str:
        if pose in archivos:
            return archivos[pose]
        if pose in APUNTADAS and "disparar" in archivos:
            print(f"  (falta la pose '{pose}': se usa disparar)")
            return archivos["disparar"]
        print(f"  (falta la pose '{pose}': se usa el idle)")
        return respaldo_idle

    generar_preview_poses(preparadas, ancla_comun, bocas, archivos)
    return {
        "frame": [ancho, alto],
        "ancla": list(ancla_comun),
        "fps": 8,
        "animaciones": {anim: [archivo_de(p) for p in lista] for anim, lista in ANIMACIONES_JUGADOR.items()},
        "bocas": bocas,
        "rasgos": rasgos_finales,
    }


def generar_preview_poses(preparadas, ancla, bocas, archivos):
    """Hoja de contacto, alineada por los pies:
      fila 1: todas las poses (idle incluido) x4, con línea de suelo, ancla y boca del arma;
      fila 2: el mismo conjunto con los píxeles del traje REMAPEADOS marcados en magenta;
      fila 3: zoom x8 de las cabezas (rasgos con marco amarillo).
    Las guías se dibujan SOLO aquí, nunca dentro de los PNG."""
    from render.fuente_pixel import FuentePixel
    fuente, fuente1 = FuentePixel(2), FuentePixel(1)
    escala, sep, zoom, lado = 4, 16, 8, 14

    # Todas las poses comparten lienzo y ancla
    entradas = [dict(nombre=p["pose"], sup=p["superficie"], ancla=ancla, cambiados=p["cambiados"],
                     img=p["img_lienzo"], cara=p["cara"], rasgos=p["rasgos"], dudas=p["dudas_rasgos"],
                     boca=bocas.get(archivos[p["pose"]]), proporcion=p["proporcion"]) for p in preparadas]

    ancho_celda = max(max(e["sup"].get_width() * escala, fuente.size(e["nombre"].upper())[0], lado * zoom)
                      for e in entradas)
    sobre_suelo = max(e["ancla"][1] for e in entradas) * escala
    bajo_suelo = max(e["sup"].get_height() - e["ancla"][1] for e in entradas) * escala
    alto_fila = 40 + sobre_suelo + bajo_suelo + 30
    hoja = pygame.Surface((sep + len(entradas) * (ancho_celda + sep), alto_fila * 2 + lado * zoom + 60))
    hoja.fill((128, 128, 128))

    for fila in (0, 1):
        y0 = fila * alto_fila
        suelo = y0 + 40 + sobre_suelo
        pygame.draw.line(hoja, (40, 200, 60), (0, suelo), (hoja.get_width(), suelo), 2)
        titulo = "POSES + IDLE" if fila == 0 else "TRAJE REMAPEADO (MAGENTA)"
        hoja.blit(fuente1.render(titulo, False, (255, 255, 255)), (4, y0 + 2))
        for i, e in enumerate(entradas):
            x = sep + i * (ancho_celda + sep)
            cx = x + ancla[0] * escala                       # misma columna de ancla para todos
            ex, ey = e["ancla"]
            sup = e["sup"]
            if fila == 1:                                    # copia con los píxeles cambiados en magenta
                img = e["img"].copy()
                img[e["cambiados"]] = (255, 0, 255)
                sup = a_superficie(img, np.asarray(pygame.surfarray.array_alpha(e["sup"]).T > 0))
            hoja.blit(pygame.transform.scale_by(sup, escala), (cx - ex * escala, suelo - ey * escala))
            pygame.draw.line(hoja, (40, 200, 60), (cx, suelo - 8), (cx, suelo + 8), 2)
            if fila == 0 and e["boca"]:
                pygame.draw.circle(hoja, (255, 40, 40), (cx + e["boca"][0] * escala, suelo + e["boca"][1] * escala), 4)
            if fila == 0:
                hoja.blit(fuente.render(e["nombre"].upper(), False, (255, 255, 255)), (x, y0 + 14))
                texto = f"{e['proporcion'] * 100:.0f}%"
                color = (255, 220, 60) if abs(e["proporcion"] - 1) > TOLERANCIA_ESCALA else (230, 230, 230)
                hoja.blit(fuente.render(texto, False, color), (x, suelo + 12))
            else:
                hoja.blit(fuente1.render(f"{int(e['cambiados'].sum())} PX", False, (255, 255, 255)), (x, suelo + 12))

    # Zoom x8 de las cabezas, centrado en la cara detectada
    y_cab = alto_fila * 2 + 10
    for i, e in enumerate(entradas):
        x = sep + i * (ancho_celda + sep)
        if e["cara"] is not None:
            ys, xs = np.nonzero(e["cara"])
            cx, cy = int(xs.mean()), int(ys.mean())
        else:
            cx, cy = e["sup"].get_width() // 2, 6
        recorte = pygame.Rect(cx - lado // 2, cy - lado // 2, lado, lado)
        cabeza = pygame.Surface((lado, lado), pygame.SRCALPHA)
        cabeza.blit(e["sup"], (0, 0), recorte)
        hoja.blit(pygame.transform.scale_by(cabeza, zoom), (x, y_cab))
        for nombre_rasgo, pos in e["rasgos"].items():
            if pos and nombre_rasgo in RASGOS_PUNTO:
                rx, ry = (pos[0] - recorte.x) * zoom, (pos[1] - recorte.y) * zoom
                pygame.draw.rect(hoja, (255, 230, 0), (x + rx - 2, y_cab + ry - 2, zoom + 4, zoom + 4), 1)
        color = (255, 120, 80) if e["dudas"] else (230, 230, 230)
        etiqueta = e["nombre"].upper() + (" ?" if e["dudas"] else "")
        hoja.blit(fuente1.render(etiqueta, False, color), (x, y_cab + lado * zoom + 8))
    pygame.image.save(hoja, RUTA_PREVIEW_POSES)


# =============================================================================
# Busto del menú
# =============================================================================
def disolver(alfa: np.ndarray, desde: int) -> np.ndarray:
    """Tramado ordenado: desde la fila `desde` hasta abajo, cada vez quedan menos píxeles,
    siguiendo el patrón de Bayer (se ve como un degradado hecho de píxeles)."""
    alfa = alfa.copy()
    alto, ancho = alfa.shape
    for y in range(desde, alto):
        t = (y - desde + 1) / max(1, alto - desde)
        umbral = BAYER_4X4[y % 4, np.arange(ancho) % 4]
        alfa[y] &= umbral >= t
    return alfa


def generar_busto(ruta: str, paleta) -> dict:
    """Pose grande, recortada a la cintura y disuelta en píxeles hacia abajo."""
    print(f"Procesando busto del menú ({os.path.basename(ruta)})...")
    inf = procesar(BUSTO_MENU["fuente"], ruta, altura=BUSTO_MENU["alto_figura"])
    h, w = inf["alfa"].shape
    img = np.zeros((h + 2, w + 2, 3), np.uint8)
    alfa = np.zeros((h + 2, w + 2), bool)
    img[1:-1, 1:-1], alfa[1:-1, 1:-1] = cuantizar(inf["reducido"], inf["alfa"], paleta), inf["alfa"]
    img, alfa = contorno(img, alfa)
    filas = BUSTO_MENU["filas"]
    img, alfa = img[:filas], alfa[:filas]
    alfa = disolver(alfa, int(filas * (1 - BUSTO_MENU["fundido"])))
    # Recorte horizontal a lo que quedó visible
    columnas = np.nonzero(alfa.any(0))[0]
    img, alfa = img[:, columnas.min():columnas.max() + 1], alfa[:, columnas.min():columnas.max() + 1]
    sup = a_superficie(img, alfa)
    pygame.image.save(sup, os.path.join(RUTA_SALIDA, BUSTO_MENU["salida"]))
    print(f"  presidente_menu  {sup.get_width()}x{sup.get_height()} (figura de {BUSTO_MENU['alto_figura']} px, "
          f"disuelto el {BUSTO_MENU['fundido'] * 100:.0f}% inferior)")
    return {"archivo": f"sprites/{BUSTO_MENU['salida']}", "frame": [sup.get_width(), sup.get_height()],
            "fps": 1, "animaciones": {"quieto": [0]}}


# =============================================================================
# Pulgar del teléfono (2 fotogramas: extendido y presionando)
# =============================================================================
def procesar_pulgar(rutas: dict) -> list:
    """Limpia y reduce los fotogramas del pulgar con la MISMA escala (la del primero)."""
    nombres = [n for n in GRUPO_PULGAR if n in rutas]
    if not nombres:
        return []
    fotogramas, bloque = [], None
    for nombre in nombres:
        print(f"Procesando {os.path.basename(rutas[nombre])}...")
        inf = procesar(nombre, rutas[nombre], bloque=bloque)
        bloque = inf["bloque"]                       # el resto usa la escala del primero
        inf["animacion"] = GRUPO_PULGAR[nombre]
        fotogramas.append(inf)
    return fotogramas


def base_y_yema(alfa: np.ndarray):
    """Base = centro del borde inferior (la muñeca cortada); yema = centro de la fila más alta
    (la punta del dedo). Devuelve (base_x, base_y, ancho_base, yema_x, yema_y)."""
    filas = np.nonzero(alfa.any(1))[0]
    abajo, arriba = int(filas.max()), int(filas.min())
    xs_base = np.nonzero(alfa[abajo])[0]
    xs_yema = np.nonzero(alfa[arriba])[0]
    return (int(round((xs_base.min() + xs_base.max()) / 2)), abajo + 1, len(xs_base),
            int(round((xs_yema.min() + xs_yema.max()) / 2)), arriba)


def guardar_pulgar(fotogramas: list, paleta) -> dict:
    """Cuantiza, alinea por la base en un lienzo común, guarda PNG, avisa si las bases no
    coinciden y devuelve la entrada de sprites.json (con la yema de cada fotograma)."""
    preparados = []
    for inf in fotogramas:
        h, w = inf["alfa"].shape
        img = np.zeros((h + 2, w + 2, 3), np.uint8)
        alfa = np.zeros((h + 2, w + 2), bool)
        img[1:-1, 1:-1], alfa[1:-1, 1:-1] = cuantizar(inf["reducido"], inf["alfa"], paleta), inf["alfa"]
        bx, by, ancho_base, yx, yy = base_y_yema(alfa)      # medido antes del contorno
        img, alfa = contorno(img, alfa)
        preparados.append(dict(inf, img=img, alfa_final=alfa, base=(bx, by), ancho_base=ancho_base,
                               yema=(yx, yy)))

    izquierda = max(p["base"][0] for p in preparados)
    derecha = max(p["alfa_final"].shape[1] - p["base"][0] for p in preparados)
    arriba = max(p["base"][1] for p in preparados)
    abajo = max(p["alfa_final"].shape[0] - p["base"][1] for p in preparados)
    ancho, alto = izquierda + derecha, arriba + abajo

    referencia = preparados[0]
    animaciones, yemas = {}, {}
    for p in preparados:
        bx, by = p["base"]
        ox, oy = izquierda - bx, arriba - by
        img = np.zeros((alto, ancho, 3), np.uint8)
        alfa = np.zeros((alto, ancho), bool)
        h, w = p["alfa_final"].shape
        img[oy:oy + h, ox:ox + w], alfa[oy:oy + h, ox:ox + w] = p["img"], p["alfa_final"]
        sup = a_superficie(img, alfa)
        archivo = f"sprites/{p['nombre']}.png"
        pygame.image.save(sup, os.path.join(RAIZ, "assets", archivo))
        p["superficie"] = sup
        animaciones[p["animacion"]] = [archivo]
        yemas[archivo] = [p["yema"][0] - bx, p["yema"][1] - by]          # relativa a la base
        proporcion = p["ancho_base"] / referencia["ancho_base"]
        aviso = ""
        if abs(proporcion - 1) > TOLERANCIA_BASE:
            aviso = (f"  <-- AVISO: la base mide {p['ancho_base']} px y la del {referencia['nombre']} "
                     f"{referencia['ancho_base']} px ({proporcion * 100 - 100:+.0f}%). No se corrige.")
        p["proporcion_base"] = proporcion
        print(f"  {p['nombre']:<12} original={p['tamano_original']} sprite={w}x{h} base={p['ancho_base']} px "
              f"yema={yemas[archivo]}{aviso}")
    if "presionando" not in animaciones:
        animaciones["presionando"] = animaciones["quieto"]
    generar_preview_pulgar(preparados, (izquierda, arriba), yemas)
    return {"frame": [ancho, alto], "ancla": [izquierda, arriba], "fps": 8,
            "animaciones": animaciones, "yemas": yemas}


def generar_preview_pulgar(preparados, base, yemas):
    """Fotogramas x6 alineados por la base (línea verde) con la yema marcada en rojo, y un
    tercer panel con ambos superpuestos para ver si algo salta. Guías solo aquí."""
    from render.fuente_pixel import FuentePixel
    fuente, fuente1 = FuentePixel(2), FuentePixel(1)
    escala, sep = 6, 30
    w, h = preparados[0]["superficie"].get_size()
    paneles = len(preparados) + 1
    hoja = pygame.Surface((sep + paneles * (w * escala + sep), h * escala + 110))
    hoja.fill((128, 128, 128))
    suelo = 40 + base[1] * escala
    pygame.draw.line(hoja, (40, 200, 60), (0, suelo), (hoja.get_width(), suelo), 2)
    for i, p in enumerate(preparados):
        x = sep + i * (w * escala + sep)
        hoja.blit(pygame.transform.scale_by(p["superficie"], escala), (x, 40))
        cx = x + base[0] * escala
        pygame.draw.line(hoja, (40, 200, 60), (cx, suelo - 10), (cx, suelo + 10), 2)
        yema = yemas[f"sprites/{p['nombre']}.png"]
        pygame.draw.circle(hoja, (255, 40, 40), (cx + yema[0] * escala, suelo + yema[1] * escala), 5, 2)
        hoja.blit(fuente.render(p["animacion"].upper(), False, (255, 255, 255)), (x, 10))
        color = (255, 220, 60) if abs(p["proporcion_base"] - 1) > TOLERANCIA_BASE else (230, 230, 230)
        hoja.blit(fuente1.render(f"BASE {p['ancho_base']} PX", False, color), (x, suelo + 16))
    # Superpuestos: extendido opaco + flexionado semitransparente
    x = sep + len(preparados) * (w * escala + sep)
    for j, p in enumerate(preparados):
        capa = pygame.transform.scale_by(p["superficie"], escala)
        capa.set_alpha(255 if j == 0 else 140)
        hoja.blit(capa, (x, 40))
    hoja.blit(fuente.render("SUPERPUESTOS", False, (255, 255, 255)), (x, 10))
    pygame.image.save(hoja, RUTA_PREVIEW_PULGAR)


# =============================================================================
# Rasgos faciales de las poses
# =============================================================================
def es_piel(img: np.ndarray) -> np.ndarray:
    m = img.astype(np.int32)
    r, g, b = m[..., 0], m[..., 1], m[..., 2]
    return (r > 150) & (r > g) & (r - b > 40) & (g > 90)


def es_pelo(img: np.ndarray) -> np.ndarray:
    """Pelo y barba: oscuros y cafés (rojo >= azul). Excluye el negro puro del contorno y el
    azul del traje."""
    m = img.astype(np.int32)
    r, b = m[..., 0], m[..., 2]
    valor = m.max(-1)
    return (valor > 15) & (valor <= 120) & (r >= b)


def detectar_cabeza(img: np.ndarray, alfa: np.ndarray):
    """Busca la cara: entre las manchas de piel del tercio superior del cuerpo, la que tiene
    más pelo/barba alrededor (las manos están junto al fusil gris, no junto al pelo).
    Devuelve (máscara_de_la_cara, motivos_de_duda)."""
    dudas = []
    filas = np.nonzero(alfa.any(1))[0]
    tope, pie = filas.min(), filas.max()
    tercio = np.zeros_like(alfa)
    tercio[tope:tope + max(3, (pie - tope) // 3 + 1)] = True
    piel = alfa & es_piel(img) & tercio
    etiquetas, tamanos = componentes(piel)
    if len(tamanos) <= 1:
        return None, ["no se encontró piel en el tercio superior"]
    # Pelo/barba: cafés oscuros, o negro INTERIOR (al cuantizar, a veces el pelo cae en el mismo
    # negro del contorno; el contorno toca lo transparente, el pelo interior no).
    negro = alfa & (img.astype(np.int32).sum(-1) == 0)
    interior = ~vecinos(~alfa, ocho=False)
    pelo = alfa & (es_pelo(img) | (negro & interior))
    puntajes = []
    for n in range(1, len(tamanos)):
        mancha = etiquetas == n
        vecinos_pelo = int((vecinos(mancha) & ~mancha & pelo).sum())
        puntajes.append((vecinos_pelo * 2 + tamanos[n], n, vecinos_pelo))
    puntajes.sort(reverse=True)
    mejor, n, vecinos_pelo = puntajes[0]
    cara = etiquetas == n
    if tamanos[n] < 6:
        dudas.append(f"cara muy pequeña ({tamanos[n]} px de piel)")
    if vecinos_pelo < 3:
        dudas.append("casi sin pelo/barba alrededor")
    if len(puntajes) > 1 and puntajes[1][0] >= 0.6 * mejor:
        dudas.append(f"otra mancha de piel parecida ({tamanos[puntajes[1][1]]} px, ¿una mano?)")
    return cara, dudas


def proponer_ojo(cara: np.ndarray):
    """Ojo a ~35 % de la altura de la cara y a la derecha de su centro (mira a la derecha)."""
    dudas = []
    ys, xs = np.nonzero(cara)
    y0, y1 = ys.min(), ys.max()
    fila = int(y0 + max(1, round((y1 - y0) * 0.35))) if y1 > y0 else int(y0)
    xs_fila = np.nonzero(cara[fila])[0]
    if len(xs_fila) == 0:
        fila = int(np.bincount(ys).argmax())
        xs_fila = np.nonzero(cara[fila])[0]
    izquierda, derecha = xs_fila.min(), xs_fila.max()
    if derecha - izquierda + 1 < 3:
        dudas.append(f"cara angosta en la fila del ojo ({derecha - izquierda + 1} px)")
    centro = (izquierda + derecha) / 2
    x = int(round(centro + max(1, (derecha - izquierda) / 4)))
    x = min(x, derecha - 1) if derecha - izquierda >= 2 else derecha   # no pegarlo al contorno
    return [int(x), int(fila)], dudas


def color_mas_oscuro(paleta) -> np.ndarray:
    return paleta[int(np.argmin(paleta.astype(np.int32).sum(1)))]


def color_sombra_piel(paleta) -> np.ndarray:
    """El tono de piel más oscuro de la paleta (para la nariz)."""
    pieles = [c for c in paleta if es_piel(c[None])[0]]
    if not pieles:
        return color_mas_oscuro(paleta)
    return min(pieles, key=lambda c: int(c.astype(np.int32).sum()))


RASGOS_PUNTO = ("ojo", "ceja", "nariz")     # un píxel cada uno
RASGOS_ZONA = ("piel", "pelo")              # retoques: listas de píxeles, se pintan antes


def desplazar_rasgo(valor, dx: int, dy: int):
    """Mueve un rasgo (un punto [x, y] o una lista de puntos) cuando el lienzo común cambia."""
    if not valor:
        return valor
    if isinstance(valor[0], list):
        return [[x + dx, y + dy] for x, y in valor]
    return [valor[0] + dx, valor[1] + dy]


def color_piel(img, alfa, paleta) -> np.ndarray:
    """El tono de piel más usado en la pose (el de la cara); si no hay, el más claro de la paleta."""
    piel = alfa & es_piel(img)
    if piel.any():
        colores, cuentas = np.unique(img[piel], axis=0, return_counts=True)
        return colores[cuentas.argmax()]
    pieles = [c for c in paleta if es_piel(c[None])[0]]
    return max(pieles, key=lambda c: int(c.astype(np.int32).sum())) if pieles else paleta[0]


def color_pelo(paleta) -> np.ndarray:
    """El café más oscuro de la paleta (el del pelo y la barba de las poses de pie)."""
    pelos = [c for c in paleta if es_pelo(c[None])[0]]
    return min(pelos, key=lambda c: int(c.astype(np.int32).sum())) if pelos else color_mas_oscuro(paleta)


def dibujar_rasgos(img, alfa, rasgos: dict, paleta) -> list:
    """Pinta los rasgos sobre la pose ya cuantizada: primero los retoques de piel y pelo, después
    ojo, ceja y nariz. Devuelve advertencias."""
    colores = {"ojo": color_mas_oscuro(paleta), "ceja": color_mas_oscuro(paleta),
               "nariz": color_sombra_piel(paleta)}
    avisos = []
    zonas = {"piel": color_piel(img, alfa, paleta), "pelo": color_pelo(paleta)}
    for nombre in RASGOS_ZONA:
        for x, y in rasgos.get(nombre) or []:
            if not (0 <= y < alfa.shape[0] and 0 <= x < alfa.shape[1]) or not alfa[y, x]:
                avisos.append(f"{nombre} en {[x, y]} cae fuera del personaje")
                continue
            img[y, x] = zonas[nombre]
    for nombre, pos in rasgos.items():
        if nombre not in colores or not pos:
            continue
        x, y = pos
        if not (0 <= y < alfa.shape[0] and 0 <= x < alfa.shape[1]) or not alfa[y, x]:
            avisos.append(f"{nombre} en {pos} cae fuera del personaje")
            continue
        img[y, x] = colores[nombre]
    return avisos


# =============================================================================
# Traje unificado (paso final de las poses del presidente)
# =============================================================================
POSE_REFERENCIA_TRAJE = "disparar"
UMBRAL_TRAJE = 60          # luminancia máxima de un tono de traje (más claro: banda, arma, camisa...)
FILAS_ZAPATOS = 3          # franja inferior protegida (zapatos)
FILAS_BAJO_CARA = 5        # hasta dónde se busca barba bajo la cara


def luminancia_img(img: np.ndarray) -> np.ndarray:
    m = img.astype(np.float64)
    return m[..., 0] * 0.299 + m[..., 1] * 0.587 + m[..., 2] * 0.114


def zona_protegida(img, alfa, cara, pie_y: int, horizontal: bool = False) -> np.ndarray:
    """Zonas que NO se remapean aunque sean oscuras: la cabeza (todo lo que está a la altura
    de la cara o más arriba, más la barba conectada debajo) y la franja de los zapatos.
    horizontal=True (acostado): la cabeza solo en las columnas de la cara, y los zapatos son
    las COLUMNAS_ZAPATOS de la izquierda (si no, la espalda y las piernas quedarían protegidas)."""
    protegida = np.zeros_like(alfa)
    filas = np.nonzero(alfa.any(1))[0]
    if horizontal:
        columnas = np.nonzero(alfa.any(0))[0]
        protegida[:, :columnas.min() + COLUMNAS_ZAPATOS] = True
        if cara is not None:
            ys, xs = np.nonzero(cara)
            protegida[:ys.max() + 2, xs.min() - 1:] = True
            negro = alfa & (img.astype(np.int32).sum(-1) == 0)
            interior = ~vecinos(~alfa, ocho=False)
            limite = np.zeros_like(alfa)
            limite[:ys.max() + FILAS_BAJO_CARA + 1, xs.min() - 2:] = True
            protegida |= inundar(cara, ((es_pelo(img) | (negro & interior)) & alfa & limite) | cara)
        return protegida
    if cara is not None:
        fondo_cara = int(np.nonzero(cara.any(1))[0].max())
        protegida[:fondo_cara + 2] = True
        limite = np.zeros_like(alfa)
        limite[:fondo_cara + FILAS_BAJO_CARA + 1] = True
        negro = alfa & (img.astype(np.int32).sum(-1) == 0)
        interior = ~vecinos(~alfa, ocho=False)
        pelo = alfa & (es_pelo(img) | (negro & interior)) & limite
        protegida |= inundar(cara, pelo | cara)
    else:   # sin cara detectada: se protege el cuarto superior del cuerpo
        tope = int(filas.min())
        protegida[:tope + (pie_y - tope) // 4] = True
    protegida[max(0, pie_y - FILAS_ZAPATOS):] = True
    return protegida


def candidatos_traje(img, alfa, protegida, excluir_calidos: bool = True) -> np.ndarray:
    """Píxeles del traje: oscuros (pero no el negro de contorno/ojos), sin piel, fuera de las
    zonas protegidas. La banda roja/amarilla, la camisa y el arma son más claros que el umbral.

    excluir_calidos=True (poses, cuyo traje ya es azul): los oscuros cálidos (rojo >= azul) no
    son traje sino zapatos (también los de un pie levantado, fuera de la franja inferior) o barba.
    excluir_calidos=False (para un traje original gris/negro que al cuantizar quede en café
    oscuro): ese café sí es traje.

    Dentro de las zonas protegidas (cabeza y zapatos) solo se aceptan píxeles CLARAMENTE azules
    (azul - rojo > 20): pelo, barba y zapatos nunca lo son, pero el cuello del saco y las bastas
    del pantalón sí, y deben quedar del mismo tono que el resto del traje."""
    lum = luminancia_img(img)
    m = img.astype(np.int32)
    azul_claro = m[..., 2] - m[..., 0] > 20
    # El azul de la banda tricolor es muy saturado (azul muy por encima de rojo y verde);
    # el azul marino del traje no. La banda nunca se toca.
    azul_banda = m[..., 2] - np.maximum(m[..., 0], m[..., 1]) > 80
    candidatos = (alfa & (~protegida | azul_claro) & (lum > 0) & (lum <= UMBRAL_TRAJE)
                  & ~es_piel(img) & ~azul_banda)
    if excluir_calidos:
        candidatos &= m[..., 0] < m[..., 2]
    return candidatos


def rampa_traje(img, alfa, protegida) -> np.ndarray:
    """Tonos del traje de la pose de referencia (los que cubren al menos 8 % del traje),
    ordenados de oscuro a claro."""
    traje = candidatos_traje(img, alfa, protegida)
    colores, cuentas = np.unique(img[traje], axis=0, return_counts=True)
    tonos = colores[cuentas >= 0.08 * cuentas.sum()]
    return tonos[np.argsort(luminancia_img(tonos))]


def unificar_traje(img, alfa, protegida, rampa, excluir_calidos: bool = True):
    """Remapea cada píxel del traje al tono de la rampa más cercano por luminosidad.
    Devuelve (imagen_nueva, máscara_de_píxeles_cambiados, resumen {origen->destino: n})."""
    traje = candidatos_traje(img, alfa, protegida, excluir_calidos)
    lum_rampa = luminancia_img(rampa)
    indice = np.abs(luminancia_img(img)[..., None] - lum_rampa).argmin(-1)
    nueva = img.copy()
    nueva[traje] = rampa[indice[traje]]
    cambiados = traje & (nueva != img).any(-1)
    resumen = {}
    for y, x in zip(*np.nonzero(cambiados)):
        clave = f"{tuple(int(v) for v in img[y, x])}->{tuple(int(v) for v in nueva[y, x])}"
        resumen[clave] = resumen.get(clave, 0) + 1
    return nueva, cambiados, resumen


def verificar_sin_marcas():
    """Comprueba que ningún PNG final contenga las guías verdes de la hoja de contacto."""
    for archivo in sorted(os.listdir(RUTA_SALIDA)):
        if not archivo.endswith(".png") or archivo.startswith("_"):
            continue
        sup = pygame.image.load(os.path.join(RUTA_SALIDA, archivo))
        rgb = pygame.surfarray.array3d(sup).astype(np.int32)
        alfa = pygame.surfarray.array_alpha(sup)
        verdes = (rgb[..., 1] > 180) & (rgb[..., 0] < 90) & (rgb[..., 2] < 90) & (alfa > 0)
        if verdes.any():
            print(f"  ! {archivo}: {int(verdes.sum())} píxeles verde guía; revisa el proceso")


def generar_preview(informes, paleta):
    """Todos los sprites x4 sobre fondo gris, con su nombre, ancla y la paleta debajo."""
    from render.fuente_pixel import FuentePixel
    fuente = FuentePixel(2)
    escala, sep = 4, 24
    columnas = [max(inf["superficie"].get_width() * escala, fuente.size(inf["nombre"])[0]) for inf in informes]
    ancho = sum(c + sep for c in columnas) + sep
    alto_max = max(inf["superficie"].get_height() for inf in informes) * escala
    preview = pygame.Surface((max(ancho, N_COLORES * 24 + 2 * sep), alto_max + 120))
    preview.fill((128, 128, 128))
    x = sep
    for inf, columna in zip(informes, columnas):
        sup = pygame.transform.scale_by(inf["superficie"], escala)
        y = 40 + alto_max - sup.get_height()
        preview.blit(sup, (x, y))
        ax, ay = inf["ancla"]
        pygame.draw.line(preview, (0, 255, 0), (x + ax * escala - 6, y + ay * escala), (x + ax * escala + 6, y + ay * escala))
        preview.blit(fuente.render(inf["nombre"].upper(), False, (255, 255, 255)), (x, 10))
        x += columna + sep
    for i, color in enumerate(paleta):
        pygame.draw.rect(preview, [int(c) for c in color], (sep + i * 24, alto_max + 70, 22, 22))
    pygame.image.save(preview, RUTA_PREVIEW)


def generar_preview_comparacion(informes):
    """Hoja x4 de los sprites procesados junto al sicario y al presidente (los PNG ya
    guardados, sin regenerarlos), todos apoyados en la misma línea de suelo para comparar
    escala. Verde: ancla. Rojo: boca del tirador. Arriba, el tamaño de cada uno."""
    from render.fuente_pixel import FuentePixel
    fuente = FuentePixel(2)
    escala, sep = 4, 28
    referencias = []
    for nombre, archivo in (("sicario", "sicario_idle.png"), ("presidente", "presidente_idle.png")):
        ruta = os.path.join(RUTA_SALIDA, archivo)
        if os.path.isfile(ruta):
            sup = pygame.image.load(ruta)
            referencias.append({"nombre": nombre, "superficie": sup, "ancla": ancla_pies(
                pygame.surfarray.array_alpha(sup).T > 0)})
    piezas = referencias + informes
    columnas = [max(p["superficie"].get_width() * escala, fuente.size(p["nombre"].upper())[0]) for p in piezas]
    alto_max = max(p["superficie"].get_height() for p in piezas) * escala
    suelo = 60 + alto_max
    preview = pygame.Surface((sum(c + sep for c in columnas) + sep, suelo + 60))
    preview.fill((128, 128, 128))
    pygame.draw.line(preview, (90, 90, 90), (0, suelo), (preview.get_width(), suelo))
    x = sep
    for p, columna in zip(piezas, columnas):
        sup = pygame.transform.scale_by(p["superficie"], escala)
        ax, ay = p["ancla"]
        if p.get("conf", {}).get("ancla") == "centro":
            y = suelo - sup.get_height() - 8 * escala          # lo que vuela, un poco en el aire
        else:
            y = suelo - ay * escala
        preview.blit(sup, (x, y))
        cx, cy = x + ax * escala, y + ay * escala
        pygame.draw.line(preview, (0, 255, 0), (cx - 8, cy), (cx + 8, cy), 2)
        pygame.draw.line(preview, (0, 255, 0), (cx, cy - 8), (cx, cy + 8), 2)
        if p.get("boca"):
            bx, by = p["boca"]
            pygame.draw.circle(preview, (255, 0, 0), (x + bx * escala + 2, y + by * escala + 2), 6, 2)
        w, h = p["superficie"].get_size()
        preview.blit(fuente.render(p["nombre"].upper(), False, (255, 255, 255)), (x, 10))
        preview.blit(fuente.render(f"{w}X{h}", False, (230, 230, 230)), (x, 30))
        x += columna + sep
    pygame.image.save(preview, RUTA_PREVIEW_SOLO)


if __name__ == "__main__":
    main()
