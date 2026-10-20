"""Recorta y limpia la frase "Bienvenido a la Patria Milagro": genera assets/sonidos/bienvenida.wav.

    python tools/limpiar_voz.py

El clip original dura 5 s y tiene DOS frases (transcritas con Whisper):
    0,0 a 1,9 s   "Creía que podía desafiar el Estado."
    2,2 a 3,0 s   dos pitidos de radio
    3,2 a 4,7 s   "Bienvenido a la Patria Milagro."      <- la única que se usa (INICIO a FIN)

Entrada (assets/sonidos_raw/):
  bienvenida_original.wav  el clip tal cual, en mono
  bienvenida_voz.wav       solo la voz, separada con Demucs (pista "vocals")
  bienvenida_radio.wav     chasquidos y estática del radio (pista "drums")
La voz separada sola suena limpia pero pierde consonantes (se midió con Whisper: se entiende
peor que el original). Por eso se mezcla con el original: MEZCLA_ORIGINAL = 0 es solo la voz
separada (sin música, más artificial) y 1 es el original (más natural, con música de fondo).

Pasos (solo numpy): mezcla -> puerta espectral (baja lo que suena siempre: música y siseo) ->
ecualización (corta graves, realza 2 a 4,5 kHz) -> nivelado (la última palabra viene más baja)
-> recorte de la frase -> eco corto -> normalización.
"""
from __future__ import annotations

import os
import wave

import numpy as np

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CRUDOS = os.path.join(RAIZ, "assets", "sonidos_raw")
SALIDA = os.path.join(RAIZ, "assets", "sonidos", "bienvenida.wav")
SR_SALIDA = 22050
INICIO, FIN = 3.05, 4.95    # segundos del clip donde está la frase
MEZCLA_ORIGINAL = 0.5       # 0 = solo la voz separada; 1 = el clip original
ECO = 0.06                  # eco corto de sala (0 = seco)


def leer(ruta: str):
    with wave.open(ruta) as w:
        sr = w.getframerate()
        x = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
        if w.getnchannels() == 2:
            x = x.reshape(-1, 2).mean(1)
    return x, sr


def escribir(ruta: str, x: np.ndarray, sr: int) -> None:
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    with wave.open(ruta, "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes((np.clip(x, -1, 1) * 32767).astype(np.int16).tobytes())


def puerta_espectral(x: np.ndarray, n: int = 1024, salto: int = 256, umbral: float = 2.5,
                     piso: float = 0.12) -> np.ndarray:
    """Atenúa en cada frecuencia lo que no supera `umbral` veces el ruido de fondo estimado."""
    ventana = np.hanning(n).astype(np.float32)
    relleno = np.pad(x, (n, n))
    cuadros = 1 + (len(relleno) - n) // salto
    espectro = np.array([np.fft.rfft(relleno[i * salto:i * salto + n] * ventana) for i in range(cuadros)])
    magnitud = np.abs(espectro)
    ruido = np.percentile(magnitud, 15, axis=0)                 # lo que suena "siempre" es ruido
    mascara = np.clip((magnitud - ruido * umbral) / (ruido * umbral + 1e-9), piso, 1.0)
    mascara = (mascara + np.roll(mascara, 1, 0) + np.roll(mascara, -1, 0)) / 3   # sin saltos bruscos
    salida = np.zeros(len(relleno), np.float32)
    peso = np.zeros(len(relleno), np.float32)
    for i, cuadro in enumerate(espectro * mascara):
        a = i * salto
        salida[a:a + n] += np.fft.irfft(cuadro, n).astype(np.float32) * ventana
        peso[a:a + n] += ventana ** 2
    return (salida / np.maximum(peso, 1e-3))[n:n + len(x)]


def ecualizar(x: np.ndarray, sr: int) -> np.ndarray:
    """Curva de ganancia aplicada en frecuencia (fase cero)."""
    espectro = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / sr)
    ganancia = 1 / np.sqrt(1 + (110.0 / np.maximum(f, 1.0)) ** 8)                 # pasa-altos 110 Hz
    ganancia *= 1 + 0.6 * np.exp(-0.5 * ((np.log2(np.maximum(f, 1.0) / 3000.0)) / 0.55) ** 2)   # presencia
    ganancia *= 1 + 0.15 * np.exp(-0.5 * ((np.log2(np.maximum(f, 1.0) / 180.0)) / 0.5) ** 2)    # cuerpo
    ganancia *= 1 / np.sqrt(1 + (f / 9000.0) ** 8)                                # corta el siseo agudo
    return np.fft.irfft(espectro * ganancia, len(x)).astype(np.float32)


def eco_de_sala(x: np.ndarray, sr: int, cantidad: float) -> np.ndarray:
    """Varias repeticiones cortas que se apagan: da amplitud sin embarrar las palabras."""
    cola = int(0.6 * sr)
    seco = np.pad(x, (0, cola))
    mojado = np.zeros_like(seco)
    for retardo_ms, fuerza in ((31, 0.7), (47, 0.6), (67, 0.5), (89, 0.4)):
        d = int(retardo_ms / 1000 * sr)
        for k in range(1, 7):
            mojado[k * d:] += seco[:len(seco) - k * d] * (fuerza ** k)
    return seco + mojado * cantidad


def remuestrear(x: np.ndarray, sr: int, destino: int) -> np.ndarray:
    if sr == destino:
        return x
    espectro = np.fft.rfft(x)                                   # recorta en frecuencia: sin aliasing
    n = int(len(x) * destino / sr)
    return (np.fft.irfft(espectro[:n // 2 + 1], n) * (n / len(x))).astype(np.float32)


def nivelar(x: np.ndarray, sr: int, objetivo: float = 0.12, maximo: float = 4.0) -> np.ndarray:
    """Empareja el volumen sílaba a sílaba: sube lo que quedó bajo (hasta `maximo` veces)."""
    ventana = int(0.12 * sr)
    nivel = np.sqrt(np.convolve(x ** 2, np.ones(ventana) / ventana, "same") + 1e-9)
    ganancia = np.clip(objetivo / nivel, 0.5, maximo)
    return (x * np.convolve(ganancia, np.ones(ventana) / ventana, "same")).astype(np.float32)


def main() -> None:
    original, sr = leer(os.path.join(CRUDOS, "bienvenida_original.wav"))
    voz, _ = leer(os.path.join(CRUDOS, "bienvenida_voz.wav"))
    radio, _ = leer(os.path.join(CRUDOS, "bienvenida_radio.wav"))
    n = min(len(original), len(voz), len(radio))
    separada = voz[:n] + radio[:n]                              # la voz con el chasquido del radio
    mezcla = MEZCLA_ORIGINAL * original[:n] + (1 - MEZCLA_ORIGINAL) * separada
    mezcla = nivelar(ecualizar(puerta_espectral(mezcla), sr), sr)
    mezcla = mezcla[int(INICIO * sr):int(FIN * sr)]             # solo la frase, sin los pitidos
    borde = int(0.03 * sr)                                      # entra y sale sin "clic"
    mezcla[:borde] *= np.linspace(0, 1, borde)
    mezcla[-borde * 3:] *= np.linspace(1, 0, borde * 3)
    mezcla = remuestrear(eco_de_sala(mezcla, sr, ECO), sr, SR_SALIDA)
    mezcla = mezcla / (np.abs(mezcla).max() or 1) * 0.95
    escribir(SALIDA, mezcla, SR_SALIDA)
    print(f"escrito {os.path.relpath(SALIDA, RAIZ)}: {len(mezcla) / SR_SALIDA:.2f} s a {SR_SALIDA} Hz")


if __name__ == "__main__":
    main()
