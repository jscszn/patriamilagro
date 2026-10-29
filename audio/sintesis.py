"""Sonido sintetizado por código (estilo NES): ondas de pulso, triángulo y ruido.

Funciones puras con numpy: devuelven arreglos float32 en [-1, 1] a `sr` muestras por segundo
(mono, o estéreo con forma (muestras, 2) en la música). No dependen de pygame, así que se
pueden probar sin tarjeta de sonido.

Para que suene limpio y no "áspero":
- las ondas de pulso son de banda limitada (PolyBLEP): sin el chirrido del aliasing;
- 44,1 kHz;
- la melodía lleva vibrato en las notas largas y un eco en estéreo (como hacían en la NES
  con el segundo canal de pulso);
- todo pasa por un limitador suave al final, así nunca satura.

La música está escrita nota por nota en audio/musica_datos.py (temas) y audio/himno_datos.py.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

import settings
from audio import musica_datos

try:                                   # notas del himno, escritas a mano
    from audio import himno_datos as HIMNO
except ImportError:                    # sin el archivo, el menú usa el tema genérico
    HIMNO = None

SR = 44100
TEMAS = musica_datos.TEMAS
JINGLES = musica_datos.JINGLES


def frecuencia(midi: float) -> float:
    """Nota MIDI -> Hz (69 = La 440)."""
    return 440.0 * 2 ** ((midi - 69) / 12)


def _tiempo(duracion: float, sr: int) -> np.ndarray:
    return np.arange(int(duracion * sr)) / sr


# =============================================================================
# Osciladores
# =============================================================================
def _polyblep(t: np.ndarray, dt: np.ndarray) -> np.ndarray:
    """Corrección de banda limitada para un salto en la fase 0 (t y dt en ciclos)."""
    salida = np.zeros_like(t)
    a = t < dt
    x = t[a] / dt[a]
    salida[a] = x + x - x * x - 1
    b = t > 1 - dt
    x = (t[b] - 1) / dt[b]
    salida[b] = x * x + x + x + 1
    return salida


def _pulso_fase(fase: np.ndarray, paso: np.ndarray, ciclo: float) -> np.ndarray:
    """Onda de pulso de banda limitada a partir de la fase acumulada (en ciclos)."""
    t = fase % 1.0
    onda = np.where(t < ciclo, 1.0, -1.0)
    onda += _polyblep(t, paso)
    onda -= _polyblep((t - ciclo) % 1.0, paso)
    return (onda - (2 * ciclo - 1)).astype(np.float32)     # sin componente continua


def _fase(freqs: np.ndarray, sr: int) -> Tuple[np.ndarray, np.ndarray]:
    paso = np.clip(freqs / sr, 1e-6, 0.5)
    return np.cumsum(paso) - paso[0], paso


def cuadrada(freq: float, duracion: float, sr: int = SR, ciclo: float = 0.5,
             vibrato: float = 0.0, retraso_vibrato: float = 0.12) -> np.ndarray:
    """Pulso de banda limitada. vibrato: profundidad en semitonos (empieza tras un momento)."""
    n = int(duracion * sr)
    freqs = np.full(n, float(freq))
    if vibrato and n:
        t = np.arange(n) / sr
        entrada = np.clip((t - retraso_vibrato) / 0.15, 0, 1)
        freqs *= 2 ** (vibrato * entrada * np.sin(2 * np.pi * 5.6 * t) / 12)
    fase, paso = _fase(freqs, sr)
    return _pulso_fase(fase, paso, ciclo)


def triangular(freq: float, duracion: float, sr: int = SR, pasos: int = 32) -> np.ndarray:
    """Triángulo escalonado como el de la NES (pasos niveles por ciclo)."""
    fase = (_tiempo(duracion, sr) * freq) % 1.0
    onda = 4 * np.abs(fase - 0.5) - 1
    if pasos:
        onda = np.round(onda * pasos / 2) / (pasos / 2)
    return onda.astype(np.float32)


def ruido(duracion: float, sr: int = SR, semilla: int = 0, periodo: int = 1) -> np.ndarray:
    """Ruido blanco. periodo > 1 repite cada valor ese número de muestras: más grave y
    "metálico", como el canal de ruido de la NES."""
    n = int(duracion * sr)
    base = np.random.default_rng(semilla).uniform(-1, 1, n // max(1, periodo) + 1).astype(np.float32)
    return np.repeat(base, max(1, periodo))[:n]


def barrido(f0: float, f1: float, duracion: float, sr: int = SR, ciclo: float = 0.5) -> np.ndarray:
    """Pulso cuya frecuencia va de f0 a f1 (subidas y caídas), de banda limitada."""
    n = int(duracion * sr)
    t = np.arange(n) / sr
    freqs = f0 * (f1 / f0) ** (t / max(duracion, 1e-6))
    fase, paso = _fase(freqs, sr)
    return _pulso_fase(fase, paso, ciclo)


def seno_barrido(f0: float, f1: float, duracion: float, sr: int = SR) -> np.ndarray:
    """Seno con caída de frecuencia (golpe grave: bombo, impactos)."""
    n = int(duracion * sr)
    t = np.arange(n) / sr
    freqs = f0 * (f1 / f0) ** (t / max(duracion, 1e-6))
    return np.sin(2 * np.pi * np.cumsum(freqs) / sr).astype(np.float32)


# =============================================================================
# Envolventes, filtros y mezcla
# =============================================================================
def envolvente(senal: np.ndarray, ataque: float = 0.005, caida: float = 0.0, sr: int = SR,
               soltar: float = 0.0) -> np.ndarray:
    """Ataque lineal, caída exponencial (caida = segundos hasta ~4 % del volumen; 0 = sin caída)
    y, si soltar > 0, un final suave de esos segundos (evita clics al cortar la nota)."""
    n = len(senal)
    env = np.ones(n, np.float32)
    a = min(n, int(ataque * sr))
    if a:
        env[:a] = np.linspace(0, 1, a)
    if caida > 0:
        env *= np.exp(-np.arange(n) / sr / (caida / 3.2)).astype(np.float32)
    s = min(n, int(soltar * sr))
    if s:
        env[n - s:] *= np.linspace(1, 0, s)
    return senal * env


def pasa_bajos(senal: np.ndarray, corte_inicio: float, corte_fin: float, sr: int = SR) -> np.ndarray:
    """Filtro pasa bajos cuyo corte va de corte_inicio a corte_fin Hz (explosiones que se
    apagan, golpes sordos). Promedio móvil de largo variable, aplicado dos veces."""
    n = len(senal)
    if n == 0:
        return senal
    cortes = corte_inicio * (corte_fin / corte_inicio) ** (np.arange(n) / max(1, n - 1))
    largos = np.clip((sr / (2 * cortes)).astype(np.int64), 1, n)
    salida = senal.astype(np.float64)
    idx = np.arange(n)
    for _ in range(2):
        acumulada = np.concatenate([[0.0], np.cumsum(salida)])
        inicio = np.maximum(0, idx + 1 - largos)
        salida = (acumulada[idx + 1] - acumulada[inicio]) / (idx + 1 - inicio)
    return salida.astype(np.float32)


def unir(*partes: np.ndarray) -> np.ndarray:
    return np.concatenate(partes).astype(np.float32)


def mezclar(*pistas: Tuple[np.ndarray, float]) -> np.ndarray:
    """Suma pistas (señal, volumen) de distinto largo (todas mono o todas estéreo)."""
    largo = max(len(p) for p, _ in pistas)
    forma = (largo,) + pistas[0][0].shape[1:]
    salida = np.zeros(forma, np.float32)
    for p, vol in pistas:
        salida[:len(p)] += p * vol
    return salida


def normalizar(senal: np.ndarray, pico: float = 0.9) -> np.ndarray:
    maximo = float(np.max(np.abs(senal))) or 1.0
    return (senal / maximo * pico).astype(np.float32)


def limitar(senal: np.ndarray, pico: float = 0.85) -> np.ndarray:
    """Normaliza al pico pedido con una curva suave (tanh): los golpes fuertes no saturan y
    el resto suena más lleno."""
    maximo = float(np.max(np.abs(senal))) or 1.0
    x = senal / maximo * 1.6
    return (np.tanh(x) / np.tanh(1.6) * pico).astype(np.float32)


def _filtro_circular(x: np.ndarray, nucleo: np.ndarray) -> np.ndarray:
    """Convolución que da la vuelta: lo que se sale por un extremo entra por el otro."""
    m = len(nucleo) // 2
    extendida = np.concatenate([x[-m:], x, x[:m]]) if m else x
    return np.convolve(extendida, nucleo, mode="valid").astype(np.float32)


def calidez(senal: np.ndarray, sr: int = SR, agudos: float = 13000.0, graves: float = 25.0) -> np.ndarray:
    """Filtro de salida como el de la NES: pasa bajos suave (sinc con ventana, 31 coeficientes)
    y quita lo que está por debajo de `graves` Hz (resta el promedio móvil). Es circular: en un
    tema en bucle el final empalma perfecto con el principio."""
    if len(senal) < 64:
        return senal.astype(np.float32)
    n = np.arange(31) - 15
    nucleo = np.sinc(2 * agudos / sr * n) * np.hamming(31)
    nucleo /= nucleo.sum()
    ventana = max(1, int(sr / graves))
    canales = senal.reshape(len(senal), -1).T
    salida = []
    for x in canales:
        x = _filtro_circular(np.ascontiguousarray(x, dtype=np.float32), nucleo)
        if ventana < len(x):                       # promedio móvil circular con suma acumulada
            m = ventana // 2
            extendida = np.concatenate([x[-m - 1:], x, x[:m]]).astype(np.float64)
            acumulada = np.cumsum(extendida)
            promedio = (acumulada[2 * m + 1:] - acumulada[:-2 * m - 1]) / (2 * m + 1)
            x = (x - promedio[:len(x)]).astype(np.float32)
        salida.append(x)
    return (np.stack(salida, axis=1) if senal.ndim == 2 else salida[0]).astype(np.float32)


def panear(mono: np.ndarray, pan: float) -> np.ndarray:
    """Mono -> estéreo. pan -1 = izquierda, 0 = centro, 1 = derecha (ley de potencia constante)."""
    angulo = (pan + 1) * np.pi / 4
    return np.stack([mono * np.cos(angulo), mono * np.sin(angulo)], axis=1).astype(np.float32) * np.sqrt(2)


def _poner(pista: np.ndarray, senal: np.ndarray, inicio: float, sr: int) -> None:
    """Suma una nota a la pista en el segundo `inicio` (recortando si se sale)."""
    a = int(inicio * sr)
    senal = senal[:max(0, len(pista) - a)]
    pista[a:a + len(senal)] += senal


def _poner_en_bucle(pista: np.ndarray, senal: np.ndarray, inicio: int) -> None:
    """Como _poner, pero lo que se sale por el final entra por el principio (bucle sin corte)."""
    n = len(pista)
    inicio %= n
    resto = senal
    while len(resto):
        trozo = resto[:n - inicio]
        pista[inicio:inicio + len(trozo)] += trozo
        resto = resto[len(trozo):]
        inicio = 0


# =============================================================================
# Batería (canal de ruido + golpes graves)
# =============================================================================
def golpes(sr: int = SR) -> Dict[str, np.ndarray]:
    bombo = envolvente(seno_barrido(150, 42, 0.16, sr), ataque=0.001, caida=0.16, sr=sr)
    bombo[:int(0.004 * sr)] += ruido(0.004, sr, 11)[:int(0.004 * sr)] * 0.6        # clic del parche
    caja = mezclar((envolvente(ruido(0.16, sr, 12, periodo=3), ataque=0.001, caida=0.13, sr=sr), 0.7),
                   (envolvente(seno_barrido(210, 160, 0.08, sr), ataque=0.001, caida=0.08, sr=sr), 0.45))
    charles = envolvente(ruido(0.035, sr, 13), ataque=0.0005, caida=0.03, sr=sr) * 0.5
    abierto = envolvente(ruido(0.16, sr, 14), ataque=0.0005, caida=0.15, sr=sr) * 0.42
    platillo = pasa_bajos(envolvente(ruido(0.9, sr, 15), ataque=0.001, caida=0.9, sr=sr), 9000, 3000, sr) * 0.6
    tambor = envolvente(seno_barrido(220, 110, 0.14, sr), ataque=0.001, caida=0.14, sr=sr) * 0.8
    return {"k": bombo, "s": caja, "h": charles, "o": abierto, "c": mezclar((platillo, 1.0), (bombo, 1.0)),
            "t": tambor}


# =============================================================================
# Efectos de sonido
# =============================================================================
def efectos(sr: int = SR) -> Dict[str, np.ndarray]:
    """Todos los efectos del juego. Las claves coinciden con los eventos que los disparan."""
    e = {}
    # Disparos: chasquido de ruido + pulso que cae (cada arma con su color)
    e["disparo_jugador"] = mezclar((envolvente(barrido(1500, 520, 0.07, sr, 0.25), caida=0.07, sr=sr), 0.45),
                                   (pasa_bajos(envolvente(ruido(0.05, sr, 21), caida=0.04, sr=sr), 9000, 2500, sr), 0.5))
    e["disparo_enemigo"] = mezclar((envolvente(barrido(700, 260, 0.1, sr, 0.5), caida=0.1, sr=sr), 0.4),
                                   (pasa_bajos(envolvente(ruido(0.07, sr, 22, 2), caida=0.06, sr=sr), 6000, 1500, sr), 0.45))
    e["disparo_jefe"] = mezclar((pasa_bajos(envolvente(ruido(0.18, sr, 1, 2), caida=0.16, sr=sr), 5000, 600, sr), 0.7),
                                (envolvente(barrido(320, 90, 0.16, sr), caida=0.16, sr=sr), 0.35),
                                (envolvente(seno_barrido(110, 45, 0.15, sr), caida=0.15, sr=sr), 0.5))
    # Explosiones: ruido que se apaga (el filtro baja) + golpe grave
    e["explosion"] = mezclar((pasa_bajos(envolvente(ruido(0.5, sr, 2, 2), ataque=0.002, caida=0.45, sr=sr), 6000, 300, sr), 1.0),
                             (envolvente(seno_barrido(120, 35, 0.3, sr), caida=0.3, sr=sr), 0.7))
    e["explosion_grande"] = mezclar(
        (pasa_bajos(envolvente(ruido(1.6, sr, 3, 3), ataque=0.003, caida=1.5, sr=sr), 5000, 120, sr), 1.0),
        (envolvente(seno_barrido(90, 28, 1.0, sr), caida=1.0, sr=sr), 0.9),
        (np.concatenate([np.zeros(int(0.12 * sr), np.float32),          # segundo estallido
                         pasa_bajos(envolvente(ruido(0.6, sr, 31, 2), caida=0.55, sr=sr), 4000, 200, sr)]), 0.6))
    e["impacto"] = mezclar((envolvente(barrido(2400, 900, 0.035, sr, 0.25), caida=0.035, sr=sr), 0.35),
                           (envolvente(ruido(0.03, sr, 4), caida=0.025, sr=sr), 0.35))
    e["herido"] = mezclar((envolvente(barrido(620, 140, 0.28, sr, 0.5), caida=0.28, sr=sr), 0.55),
                          (pasa_bajos(envolvente(ruido(0.1, sr, 23, 2), caida=0.09, sr=sr), 5000, 800, sr), 0.5))
    e["muerte"] = unir(envolvente(barrido(880, 110, 0.55, sr, 0.5), caida=0.6, sr=sr),
                       envolvente(cuadrada(frecuencia(45), 0.35, sr, 0.25), caida=0.35, sr=sr)) * 0.6
    e["salto"] = envolvente(barrido(220, 680, 0.11, sr, 0.25), caida=0.13, sr=sr, soltar=0.01) * 0.32
    e["powerup"] = unir(*[envolvente(cuadrada(frecuencia(n), 0.055, sr, 0.25), caida=0.09, sr=sr, soltar=0.004)
                          for n in (72, 76, 79, 84, 88, 91)]) * 0.42
    e["mover"] = envolvente(cuadrada(frecuencia(84), 0.035, sr, 0.25), caida=0.035, sr=sr, soltar=0.004) * 0.28
    e["confirmar"] = unir(envolvente(cuadrada(frecuencia(76), 0.05, sr, 0.5), caida=0.06, sr=sr, soltar=0.004),
                          envolvente(cuadrada(frecuencia(83), 0.11, sr, 0.5), caida=0.11, sr=sr, soltar=0.01)) * 0.34
    e["sello"] = mezclar((pasa_bajos(envolvente(ruido(0.25, sr, 5, 2), caida=0.22, sr=sr), 4000, 300, sr), 0.8),
                         (envolvente(seno_barrido(150, 45, 0.25, sr), caida=0.25, sr=sr), 0.8))
    e["temblor"] = mezclar((envolvente(seno_barrido(80, 30, 0.45, sr), caida=0.45, sr=sr), 0.9),
                           (pasa_bajos(envolvente(ruido(0.45, sr, 24, 4), caida=0.4, sr=sr), 1500, 120, sr), 0.6))
    e["logro"] = unir(*[envolvente(cuadrada(frecuencia(n), d, sr, 0.25, vibrato=0.25 if d > 0.2 else 0),
                                   caida=d * 1.5, sr=sr, soltar=0.01)
                        for n, d in ((79, 0.08), (84, 0.08), (88, 0.08), (91, 0.4))]) * 0.4
    # Avisos de los refuerzos, suministros y cuenta regresiva
    e["alerta"] = unir(*[envolvente(cuadrada(frecuencia(n), 0.09, sr, 0.25), caida=0.2, sr=sr, soltar=0.005)
                         for n in (81, 76, 81, 76)]) * 0.4
    e["suministro"] = unir(*[envolvente(triangular(frecuencia(n), 0.08, sr), caida=0.12, sr=sr, soltar=0.005)
                             for n in (67, 72, 76, 79)]) * 0.55
    e["tic"] = envolvente(cuadrada(frecuencia(93), 0.03, sr, 0.125), caida=0.03, sr=sr, soltar=0.003) * 0.3
    e = {k: calidez(v, sr, agudos=15000.0, graves=20.0) for k, v in e.items()}
    return {k: normalizar(v, min(0.95, float(np.max(np.abs(v))))) for k, v in e.items()}


# Variantes de tono para los efectos que se repiten mucho (no cansan el oído)
VARIANTES = {"disparo_jugador": 3, "disparo_enemigo": 2, "impacto": 3, "explosion": 2}


def variantes(senal: np.ndarray, cantidad: int) -> List[np.ndarray]:
    """La misma señal remuestreada a tonos un poco distintos (±4 %)."""
    salida = []
    for i in range(cantidad):
        factor = 1.0 + (i - (cantidad - 1) / 2) * 0.04
        idx = np.arange(0, len(senal) - 1, factor)
        salida.append(np.interp(idx, np.arange(len(senal)), senal).astype(np.float32))
    return salida


# =============================================================================
# Lectura de partituras
# =============================================================================
SEMITONO = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
ACORDES = {"": (0, 4, 7), "m": (0, 3, 7), "7": (0, 4, 7, 10), "m7": (0, 3, 7, 10), "dim": (0, 3, 6),
           "sus": (0, 5, 7)}


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


def leer_secuencia(texto: str) -> List[Tuple[Optional[int], int]]:
    """"A4:2 r:2 C5:4" -> [(69, 2), (None, 2), (72, 4)]: (nota o None si es silencio, semicorcheas)."""
    salida = []
    for palabra in texto.split():
        nombre, dur = palabra.split(":")
        salida.append((None if nombre == "r" else nota_midi(nombre), int(dur)))
    return salida


def leer_acorde(nombre: str) -> Tuple[int, Tuple[int, ...]]:
    """"F#m7" -> (6, (0, 3, 7, 10)): clase de la raíz (0 = Do) e intervalos."""
    raiz = SEMITONO[nombre[0]]
    resto = nombre[1:]
    while resto[:1] in ("#", "b"):
        raiz += 1 if resto[0] == "#" else -1
        resto = resto[1:]
    return raiz % 12, ACORDES[resto]


# =============================================================================
# Música
# =============================================================================
def _voz_pulso(nota: int, segundos: float, sr: int, ciclo: float, larga: bool) -> np.ndarray:
    onda = cuadrada(frecuencia(nota), segundos, sr, ciclo, vibrato=0.22 if larga else 0.0)
    return envolvente(onda, ataque=0.004, caida=max(0.6, segundos * 3), sr=sr, soltar=min(0.03, segundos * 0.3))


def _voz_triangulo(nota: int, segundos: float, sr: int) -> np.ndarray:
    onda = triangular(frecuencia(nota), segundos, sr)
    return envolvente(onda, ataque=0.003, caida=max(0.5, segundos * 2.5), sr=sr, soltar=min(0.02, segundos * 0.3))


def _bajo_estilo(estilo: str, raiz: int, semis: int) -> List[Tuple[Optional[int], int]]:
    """Línea de bajo sobre un acorde que dura `semis` semicorcheas (raíz MIDI de octava 2)."""
    if estilo == "octavas":                         # corcheas que saltan de octava
        patron = [(raiz, 2), (raiz + 12, 2)]
    elif estilo == "galope":                        # corchea + dos semicorcheas
        patron = [(raiz, 2), (raiz, 1), (raiz, 1)]
    elif estilo == "metralla":                      # semicorcheas sin respiro
        patron = [(raiz, 1), (raiz, 1), (raiz + 12, 1), (raiz, 1)]
    elif estilo == "latido":                        # notas largas
        patron = [(raiz, 8)]
    else:                                           # marcha: raíz y quinta
        patron = [(raiz, 4), (raiz + 7, 4)]
    salida, total = [], 0
    while total < semis:
        for nota, dur in patron:
            dur = min(dur, semis - total)
            if dur <= 0:
                break
            salida.append((nota, dur))
            total += dur
    return salida


def _largo_rapido(muestras: float) -> int:
    """Largo redondeado hacia arriba a un múltiplo de 64 (como mucho 1,5 ms más)."""
    return int(np.ceil(muestras / 64)) * 64


def _arreglo(t: dict, sr: int, repeticiones: int = 1):
    """Pistas mono (melodía, arpegio, bajo, batería) de un tema y su largo en muestras."""
    semicorchea = 60.0 / t["tempo"] / 4
    compases = [(t["secciones"][s], i) for s in t["orden"] for i in range(len(t["secciones"][s]["acordes"]))]
    compases = compases * repeticiones
    largo = _largo_rapido(len(compases) * 16 * semicorchea * sr)
    melodia, arpegio, bajo, bateria = (np.zeros(largo, np.float32) for _ in range(4))
    ciclo_arpegio = t.get("onda_arpegio", 0.25)
    kit = golpes(sr)
    cache: Dict[tuple, np.ndarray] = {}

    def nota(voz, midi, semis):
        clave = (voz, midi, semis)
        if clave not in cache:
            segundos = semis * semicorchea * 0.94
            if voz == "melodia":
                cache[clave] = _voz_pulso(midi, segundos, sr, 0.5, larga=semis >= 6)
            elif voz == "arpegio":
                cache[clave] = _voz_pulso(midi, semicorchea * 0.8, sr, ciclo_arpegio, larga=False)
            else:
                cache[clave] = _voz_triangulo(midi, segundos, sr)
        return cache[clave]

    for n, (seccion, i) in enumerate(compases):
        inicio = n * 16
        # Melodía
        pos = inicio
        for midi, dur in leer_secuencia(seccion["melodia"][i]):
            if midi is not None:
                _poner_en_bucle(melodia, nota("melodia", midi, dur), int(round(pos * semicorchea * sr)))
            pos += dur
        # Acordes: arpegio y (si no está escrito) el bajo
        acordes = seccion["acordes"][i].split()
        semis_acorde = 16 // len(acordes)
        for k, nombre in enumerate(acordes):
            raiz, intervalos = leer_acorde(nombre)
            tonos = [60 + raiz + iv for iv in intervalos[:3]]
            for s in range(semis_acorde):
                grado = t["arpegio"][(k * semis_acorde + s) % len(t["arpegio"])]
                if grado is None:
                    continue
                midi = tonos[grado % 3] + 12 * (grado // 3)
                _poner_en_bucle(arpegio, nota("arpegio", midi, 1),
                                int(round((inicio + k * semis_acorde + s) * semicorchea * sr)))
            if seccion.get("bajo") is None and t.get("bajo"):
                pos = inicio + k * semis_acorde
                for midi, dur in _bajo_estilo(t["bajo"], 36 + raiz if raiz < 8 else 24 + raiz, semis_acorde):
                    _poner_en_bucle(bajo, nota("bajo", midi, dur), int(round(pos * semicorchea * sr)))
                    pos += dur
        if seccion.get("bajo") is not None:
            pos = inicio
            for midi, dur in leer_secuencia(seccion["bajo"][i]):
                if midi is not None:
                    _poner_en_bucle(bajo, nota("bajo", midi, dur), int(round(pos * semicorchea * sr)))
                pos += dur
        # Batería
        patron = musica_datos.PATRONES[seccion["bateria"][i]]
        for s, golpe in enumerate(patron):
            if golpe in kit:
                _poner_en_bucle(bateria, kit[golpe], int(round((inicio + s) * semicorchea * sr)))
    return melodia, arpegio, bajo, bateria, semicorchea, largo


def _eco(senal: np.ndarray, retardo: int, ganancia: float, veces: int = 3) -> np.ndarray:
    """Repeticiones cada vez más suaves de la señal (en bucle)."""
    salida = np.zeros_like(senal)
    for k in range(1, veces + 1):
        salida += np.roll(senal, retardo * k) * ganancia ** k
    return salida


def _mezcla_estereo(melodia, arpegio, bajo, bateria, semicorchea, sr) -> np.ndarray:
    eco = _eco(melodia, int(3 * semicorchea * sr), 0.32)
    pistas = [(panear(melodia, -0.12), 0.30), (panear(eco, 0.55), 0.30),
              (panear(arpegio, 0.35), 0.12), (panear(bajo, 0.0), 0.50), (panear(bateria, 0.05), 0.36)]
    return mezclar(*pistas)


def tema(nombre: str, sr: int = SR, repeticiones: int = 1) -> np.ndarray:
    """Un tema completo en estéreo, listo para tocarse en bucle (el final empalma con el principio)."""
    if nombre == "menu" and HIMNO:
        return himno(sr)
    pistas = _arreglo(TEMAS[nombre], sr, repeticiones)
    return limitar(calidez(_mezcla_estereo(*pistas[:5], sr), sr), 0.82)


def jingle(nombre: str, sr: int = SR) -> np.ndarray:
    """Fanfarria corta (no se repite): se le agrega una cola para que el último acorde respire."""
    t = JINGLES[nombre]
    melodia, arpegio, bajo, bateria, semicorchea, largo = _arreglo(t, sr)
    segundos_cola = t.get("cola", 1.2)
    cola = np.zeros(int(segundos_cola * sr), np.float32)
    # Acorde final sostenido con la melodía y el bajo
    ultimo = t["secciones"][t["orden"][-1]]
    raiz, intervalos = leer_acorde(ultimo["acordes"][-1].split()[-1])
    for iv in intervalos[:3]:
        cola[:] += envolvente(cuadrada(frecuencia(72 + raiz + iv), segundos_cola, sr, 0.25),
                              caida=segundos_cola, sr=sr)[:len(cola)] * 0.25
    melodia, arpegio, bajo, bateria = (np.concatenate([p, z]) for p, z in
                                       ((melodia, np.zeros(len(cola), np.float32)), (arpegio, cola),
                                        (bajo, np.zeros(len(cola), np.float32)), (bateria, np.zeros(len(cola), np.float32))))
    mezcla = calidez(_mezcla_estereo(melodia, arpegio, bajo, bateria, semicorchea, sr), sr)
    fin = int(0.02 * sr)                                            # sin clic al terminar
    mezcla[-fin:] *= np.linspace(1, 0, fin)[:, None]
    return limitar(mezcla, 0.8)


def himno(sr: int = SR, con_bajo: Optional[bool] = None) -> np.ndarray:
    """Himno Nacional de Colombia en estilo arcade: SOLO la melodía (pulso con vibrato en las
    notas largas y un eco suave en estéreo) y, si settings.HIMNO_CON_BAJO está activo, un bajo
    de marcha (triángulo). Las notas están escritas a mano en audio/himno_datos.py."""
    h = HIMNO
    con_bajo = settings.HIMNO_CON_BAJO if con_bajo is None else con_bajo
    pulso = 60.0 / h.TEMPO
    compas = 4 * pulso
    total = len(h.MELODIA) * compas
    melodia = np.zeros(_largo_rapido(total * sr), np.float32)
    bajo = np.zeros_like(melodia)
    for i, texto in enumerate(h.MELODIA):
        for nota, inicio, duracion in leer_compas(texto):
            segundos = duracion * pulso * 0.92                    # un respiro entre nota y nota
            onda = cuadrada(frecuencia(nota + h.TRANSPORTE), segundos, sr, 0.5,
                            vibrato=0.2 if duracion >= 1.5 else 0.0)
            _poner(melodia, envolvente(onda, ataque=0.008, caida=max(0.5, segundos * 2.5), sr=sr,
                                       soltar=min(0.03, segundos * 0.3)),
                   i * compas + inicio * pulso, sr)
    if con_bajo:
        for i, texto in enumerate(h.BAJO):
            for mitad, letra in enumerate(texto.split()):
                raiz = nota_midi(letra + "2") + h.TRANSPORTE + 12
                for k in range(2):                                # grave en el pulso fuerte, agudo en el débil
                    onda = triangular(frecuencia(raiz + 12 * k), pulso * 0.9, sr)
                    _poner(bajo, envolvente(onda, ataque=0.01, caida=pulso * 1.5, sr=sr, soltar=0.02),
                           i * compas + (mitad * 2 + k) * pulso, sr)
    eco = np.roll(melodia, int(0.75 * pulso * sr)) * 0.22
    eco[:int(0.75 * pulso * sr)] = 0                              # el himno no empalma: sin eco al inicio
    mezcla = mezclar((panear(melodia, -0.1), 0.34), (panear(eco, 0.5), 0.34), (panear(bajo, 0.0), 0.5))
    return limitar(calidez(mezcla, sr), 0.8)


def a_int16(senal: np.ndarray, canales: int = 2) -> np.ndarray:
    """float [-1, 1] -> int16 con la forma que pide pygame.sndarray (muestras x canales).
    Acepta mono (n,) o estéreo (n, 2)."""
    datos = (np.clip(senal, -1, 1) * 32767).astype(np.int16)
    if datos.ndim == 2:
        if canales == 1:
            return datos.mean(axis=1).astype(np.int16)
        return np.ascontiguousarray(datos)
    if canales == 1:
        return datos
    return np.repeat(datos[:, None], canales, axis=1)
