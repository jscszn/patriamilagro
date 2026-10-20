"""Sonido sintetizado por código (estilo NES): ondas cuadradas, triangulares y ruido.

Funciones puras con numpy: devuelven arreglos float32 en [-1, 1] a `sr` muestras por segundo.
No dependen de pygame, así que se pueden probar sin tarjeta de sonido.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

import settings

try:                                   # notas del himno, escritas a mano
    from audio import himno_datos as HIMNO
except ImportError:                    # sin el archivo, el menú usa el tema genérico
    HIMNO = None

SR = 22050


def frecuencia(midi: float) -> float:
    """Nota MIDI -> Hz (69 = La 440)."""
    return 440.0 * 2 ** ((midi - 69) / 12)


def _tiempo(duracion: float, sr: int) -> np.ndarray:
    return np.arange(int(duracion * sr)) / sr


def cuadrada(freq: float, duracion: float, sr: int = SR, ciclo: float = 0.5) -> np.ndarray:
    fase = (_tiempo(duracion, sr) * freq) % 1.0
    return np.where(fase < ciclo, 1.0, -1.0).astype(np.float32)


def triangular(freq: float, duracion: float, sr: int = SR) -> np.ndarray:
    fase = (_tiempo(duracion, sr) * freq) % 1.0
    return (4 * np.abs(fase - 0.5) - 1).astype(np.float32)


def ruido(duracion: float, sr: int = SR, semilla: int = 0) -> np.ndarray:
    return np.random.default_rng(semilla).uniform(-1, 1, int(duracion * sr)).astype(np.float32)


def barrido(f0: float, f1: float, duracion: float, sr: int = SR, ciclo: float = 0.5) -> np.ndarray:
    """Onda cuadrada cuya frecuencia va de f0 a f1 (subidas y caídas)."""
    t = _tiempo(duracion, sr)
    freqs = f0 * (f1 / f0) ** (t / max(duracion, 1e-6))
    fase = np.cumsum(freqs) / sr % 1.0
    return np.where(fase < ciclo, 1.0, -1.0).astype(np.float32)


def envolvente(senal: np.ndarray, ataque: float = 0.005, caida: float = 0.0, sr: int = SR) -> np.ndarray:
    """Ataque lineal y caída exponencial (caida = segundos hasta ~4 % del volumen; 0 = sin caída)."""
    n = len(senal)
    env = np.ones(n, np.float32)
    a = min(n, int(ataque * sr))
    if a:
        env[:a] = np.linspace(0, 1, a)
    if caida > 0:
        env *= np.exp(-np.arange(n) / sr / (caida / 3.2)).astype(np.float32)
    return senal * env


def unir(*partes: np.ndarray) -> np.ndarray:
    return np.concatenate(partes).astype(np.float32)


def mezclar(*pistas: Tuple[np.ndarray, float]) -> np.ndarray:
    """Suma pistas (señal, volumen) de distinto largo."""
    largo = max(len(p) for p, _ in pistas)
    salida = np.zeros(largo, np.float32)
    for p, vol in pistas:
        salida[:len(p)] += p * vol
    return salida


def normalizar(senal: np.ndarray, pico: float = 0.9) -> np.ndarray:
    maximo = float(np.max(np.abs(senal))) or 1.0
    return (senal / maximo * pico).astype(np.float32)


# =============================================================================
# Efectos de sonido
# =============================================================================
def efectos(sr: int = SR) -> Dict[str, np.ndarray]:
    """Todos los efectos del juego. Las claves coinciden con los eventos que los disparan."""
    e = {}
    e["disparo_jugador"] = envolvente(barrido(1400, 700, 0.06, sr, 0.25), caida=0.06, sr=sr) * 0.5
    e["disparo_enemigo"] = envolvente(barrido(600, 300, 0.09, sr), caida=0.09, sr=sr) * 0.45
    e["disparo_jefe"] = mezclar((envolvente(ruido(0.12, sr, 1), caida=0.12, sr=sr), 0.4),
                                (envolvente(barrido(300, 120, 0.12, sr), caida=0.12, sr=sr), 0.4))
    e["explosion"] = envolvente(ruido(0.35, sr, 2), caida=0.35, sr=sr) * 0.7
    e["explosion_grande"] = mezclar((envolvente(ruido(1.2, sr, 3), caida=1.2, sr=sr), 0.8),
                                    (envolvente(barrido(120, 40, 1.2, sr), caida=1.2, sr=sr), 0.5))
    e["impacto"] = envolvente(ruido(0.04, sr, 4), caida=0.04, sr=sr) * 0.4
    e["herido"] = envolvente(barrido(500, 120, 0.25, sr), caida=0.25, sr=sr) * 0.6
    e["muerte"] = envolvente(barrido(700, 60, 0.7, sr), caida=0.7, sr=sr) * 0.6
    e["salto"] = envolvente(barrido(250, 600, 0.1, sr, 0.25), caida=0.12, sr=sr) * 0.35
    e["powerup"] = unir(*[envolvente(cuadrada(frecuencia(n), 0.06, sr), caida=0.08, sr=sr)
                          for n in (72, 76, 79, 84)]) * 0.45
    e["mover"] = envolvente(cuadrada(frecuencia(84), 0.03, sr, 0.25), caida=0.03, sr=sr) * 0.3
    e["confirmar"] = unir(envolvente(cuadrada(frecuencia(76), 0.05, sr), caida=0.05, sr=sr),
                          envolvente(cuadrada(frecuencia(83), 0.09, sr), caida=0.09, sr=sr)) * 0.35
    e["sello"] = mezclar((envolvente(ruido(0.2, sr, 5), caida=0.2, sr=sr), 0.6),
                         (envolvente(barrido(160, 50, 0.2, sr), caida=0.2, sr=sr), 0.6))
    e["temblor"] = envolvente(barrido(90, 40, 0.3, sr), caida=0.3, sr=sr) * 0.5
    e["logro"] = unir(*[envolvente(cuadrada(frecuencia(n), d, sr, 0.25), caida=d * 1.5, sr=sr)
                        for n, d in ((79, 0.08), (84, 0.08), (88, 0.08), (91, 0.25))]) * 0.4
    # Avisos de los refuerzos, suministros y cuenta regresiva
    e["alerta"] = unir(*[envolvente(cuadrada(frecuencia(n), 0.09, sr, 0.25), caida=0.2, sr=sr)
                         for n in (81, 76, 81, 76)]) * 0.4
    e["suministro"] = unir(*[envolvente(triangular(frecuencia(n), 0.07, sr), caida=0.1, sr=sr)
                             for n in (67, 72, 76)]) * 0.5
    e["tic"] = envolvente(cuadrada(frecuencia(93), 0.03, sr, 0.125), caida=0.03, sr=sr) * 0.3
    return {k: normalizar(v, min(0.95, float(np.max(np.abs(v))))) for k, v in e.items()}


# =============================================================================
# Música: progresiones de acordes tocadas con bajo, arpegio, melodía y batería
# =============================================================================
ACORDES = {"M": (0, 4, 7), "m": (0, 3, 7), "dim": (0, 3, 6), "sus": (0, 5, 7)}

# Cada tema: tempo, compases (raíz MIDI, tipo de acorde), patrón de arpegio y melodía
# (índices de grado sobre el acorde; None = silencio), y si lleva batería.
TEMAS = {
    # El menú toca el himno (función himno). Estos compases son el respaldo si faltan sus datos.
    "menu": dict(tempo=118, compases=[(60, "M"), (65, "M"), (67, "M"), (60, "M"),
                                      (57, "m"), (65, "M"), (67, "sus"), (67, "M")],
                 arpegio=[0, 2, 1, 2], melodia=[2, None, 1, 2, 0, None, 1, None], bateria=True),
    "nivel1": dict(tempo=140, compases=[(57, "m"), (57, "m"), (65, "M"), (67, "M"),
                                        (57, "m"), (62, "m"), (64, "M"), (64, "M")],
                   arpegio=[0, 1, 2, 1], melodia=[0, 0, 2, None, 1, 2, None, 1], bateria=True),
    "nivel2": dict(tempo=150, compases=[(62, "m"), (58, "M"), (60, "M"), (57, "M"),
                                        (62, "m"), (58, "M"), (55, "m"), (57, "M")],
                   arpegio=[0, 2, 0, 1], melodia=[2, 1, 0, None, 2, None, 1, 0], bateria=True),
    "nivel3": dict(tempo=160, compases=[(64, "m"), (65, "M"), (64, "m"), (62, "M"),
                                        (60, "M"), (65, "M"), (64, "m"), (64, "sus")],
                   arpegio=[0, 1, 0, 2], melodia=[0, None, 1, 0, 2, None, 1, None], bateria=True),
    "jefe": dict(tempo=172, compases=[(52, "m"), (53, "M"), (52, "m"), (58, "dim"),
                                      (52, "m"), (53, "M"), (55, "dim"), (58, "dim")],
                 arpegio=[0, 1, 2, 1], melodia=[0, 0, None, 1, 0, 2, None, None], bateria=True),
    "decision": dict(tempo=80, compases=[(50, "m"), (50, "sus"), (49, "dim"), (50, "m")],
                     arpegio=[0, None, 1, None], melodia=[None] * 8, bateria=False),
    "noticias": dict(tempo=112, compases=[(65, "M"), (62, "m"), (67, "M"), (60, "M")],
                     arpegio=[0, 1, 2, 1], melodia=[2, None, 2, 1, 0, None, None, None], bateria=True),
    "final": dict(tempo=92, compases=[(60, "M"), (64, "m"), (65, "M"), (67, "M"),
                                      (60, "M"), (65, "M"), (67, "sus"), (60, "M")],
                  arpegio=[0, 2, 1, 2], melodia=[2, None, None, 1, 0, None, None, None], bateria=False),
}


def _nota(acorde: Tuple[int, str], grado: Optional[int], octava: int = 0) -> Optional[float]:
    if grado is None:
        return None
    raiz, tipo = acorde
    return raiz + ACORDES[tipo][grado % 3] + 12 * (octava + grado // 3)


SEMITONO = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}


def nota_midi(nombre: str) -> int:
    """"C5" -> 72, "F#5" -> 78, "Bb4" -> 70 (Do central = C4 = 60)."""
    letra, resto = nombre[0], nombre[1:]
    alteracion = resto.count("#") - resto.count("b")
    return 12 * (int(resto.strip("#b")) + 1) + SEMITONO[letra] + alteracion


def leer_compas(texto: str) -> List[Tuple[int, float, float]]:
    """"C5@0+1.5 G4@2+0.5" -> [(72, 0.0, 1.5), (67, 2.0, 0.5)]: (nota, pulso de inicio, pulsos)."""
    notas = []
    for palabra in texto.split():
        nombre, tiempos = palabra.split("@")
        inicio, duracion = tiempos.split("+")
        notas.append((nota_midi(nombre), float(inicio), float(duracion)))
    return notas


def _poner(pista: np.ndarray, senal: np.ndarray, inicio: float, sr: int) -> None:
    """Suma una nota a la pista en el segundo `inicio` (recortando si se sale)."""
    a = int(inicio * sr)
    senal = senal[:max(0, len(pista) - a)]
    pista[a:a + len(senal)] += senal


def himno(sr: int = SR, con_bajo: Optional[bool] = None) -> np.ndarray:
    """Himno Nacional de Colombia en estilo arcade: SOLO la melodía (onda cuadrada) y, si
    settings.HIMNO_CON_BAJO está activo, un bajo de marcha (onda triangular). Las notas están
    escritas a mano en audio/himno_datos.py."""
    h = HIMNO
    con_bajo = settings.HIMNO_CON_BAJO if con_bajo is None else con_bajo
    pulso = 60.0 / h.TEMPO
    compas = 4 * pulso
    total = len(h.MELODIA) * compas
    melodia = np.zeros(int(total * sr) + 1, np.float32)
    bajo = np.zeros_like(melodia)
    for i, texto in enumerate(h.MELODIA):
        for nota, inicio, duracion in leer_compas(texto):
            segundos = duracion * pulso * 0.92                    # un respiro entre nota y nota
            onda = cuadrada(frecuencia(nota + h.TRANSPORTE), segundos, sr, 0.5)
            _poner(melodia, envolvente(onda, ataque=0.008, caida=max(0.5, segundos * 2.5), sr=sr),
                   i * compas + inicio * pulso, sr)
    if con_bajo:
        for i, texto in enumerate(h.BAJO):
            for mitad, letra in enumerate(texto.split()):
                raiz = nota_midi(letra + "2") + h.TRANSPORTE + 12
                for k in range(2):                                # grave en el pulso fuerte, agudo en el débil
                    onda = triangular(frecuencia(raiz + 12 * k), pulso * 0.9, sr)
                    _poner(bajo, envolvente(onda, ataque=0.01, caida=pulso * 1.5, sr=sr),
                           i * compas + (mitad * 2 + k) * pulso, sr)
    return normalizar(mezclar((melodia, 0.34), (bajo, 0.5)), 0.8)


def tema(nombre: str, sr: int = SR, repeticiones: int = 2) -> np.ndarray:
    """Genera un tema completo (para tocarse en bucle)."""
    if nombre == "menu" and HIMNO:
        return himno(sr)
    t = TEMAS[nombre]
    negra = 60.0 / t["tempo"]
    corchea = negra / 2
    bajo, arpegio, melodia, bateria = [], [], [], []
    for _ in range(repeticiones):
        for acorde in t["compases"]:
            for i in range(8):                                    # 8 corcheas por compás
                n_bajo = _nota(acorde, 0, -2 if i % 2 == 0 else -1)
                bajo.append(envolvente(triangular(frecuencia(n_bajo), corchea, sr), caida=corchea * 1.2, sr=sr))
                g = t["arpegio"][i % len(t["arpegio"])]
                n = _nota(acorde, g, 0)
                arpegio.append(envolvente(cuadrada(frecuencia(n), corchea, sr, 0.25), caida=corchea, sr=sr)
                               if n is not None else np.zeros(int(corchea * sr), np.float32))
                g = t["melodia"][i % len(t["melodia"])]
                n = _nota(acorde, g, 1)
                melodia.append(envolvente(cuadrada(frecuencia(n), corchea, sr, 0.5), caida=corchea * 1.8, sr=sr)
                               if n is not None else np.zeros(int(corchea * sr), np.float32))
                if t["bateria"]:
                    if i % 4 == 0:                                # bombo
                        golpe = envolvente(barrido(120, 45, corchea, sr), caida=0.12, sr=sr)
                    elif i % 4 == 2:                              # caja
                        golpe = envolvente(ruido(corchea, sr, i), caida=0.08, sr=sr) * 0.7
                    else:                                         # charles
                        golpe = envolvente(ruido(corchea, sr, 7 + i), caida=0.02, sr=sr) * 0.35
                    bateria.append(golpe)
    pistas: List[Tuple[np.ndarray, float]] = [(unir(*bajo), 0.55), (unir(*arpegio), 0.18),
                                              (unir(*melodia), 0.28)]
    if bateria:
        pistas.append((unir(*bateria), 0.35))
    return normalizar(mezclar(*pistas), 0.8)


def a_int16(senal: np.ndarray, canales: int = 2) -> np.ndarray:
    """float [-1, 1] -> int16 con la forma que pide pygame.sndarray (muestras x canales)."""
    datos = (np.clip(senal, -1, 1) * 32767).astype(np.int16)
    if canales == 1:
        return datos
    return np.repeat(datos[:, None], canales, axis=1)
