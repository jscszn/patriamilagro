"""Graba la música sintetizada como archivos OGG: assets/sonidos/musica_<tema>.ogg

Uso:  python tools/grabar_musica.py          (requiere: pip install soundfile; el juego NO lo necesita)

Por qué: sintetizar la música al iniciar el juego es caro en MEMORIA. El resultado pesa ~46 MB,
pero los cálculos intermedios de numpy llevan el proceso a ~840 MB y el sistema no los devuelve.
En la versión web eso es grave (la memoria del navegador no se reduce). audio/gestor.py ya usa
assets/sonidos/musica_<tema>.ogg si existe, así que con los archivos grabados no se sintetiza nada.

La música sigue definida en código (audio/musica_datos.py, audio/himno_datos.py, audio/sintesis.py).
Si se cambia, hay que volver a correr este script: guarda una HUELLA de esas fuentes en
assets/sonidos/musica.json, y tests/test_musica_grabada.py falla si la huella ya no coincide.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import settings  # noqa: E402
from audio import sintesis  # noqa: E402

RUTA_SONIDOS = os.path.join(RAIZ, "assets", "sonidos")
RUTA_HUELLA = os.path.join(RUTA_SONIDOS, "musica.json")
FUENTES = ("audio/sintesis.py", "audio/musica_datos.py", "audio/himno_datos.py")
# Vorbis: 0 = máxima calidad, 1 = mínima. Las ondas cuadradas estilo NES delatan la compresión:
# 0.2 da ~36 dB de relación señal-ruido con 7 MB en total (la calidad por defecto, 26 dB con 3,7 MB).
# El salto en el punto donde la música se repite queda muy por debajo del paso normal entre
# muestras: no hay clic en el bucle.
CALIDAD = 0.2


def huella() -> str:
    """Resumen de todo lo que define la música: si cambia, la grabación quedó vieja."""
    h = hashlib.sha256()
    for ruta in FUENTES:
        with open(os.path.join(RAIZ, ruta), "rb") as f:
            h.update(f.read())
    h.update(repr(settings.HIMNO_CON_BAJO).encode())                # el himno cambia con esta opción
    return h.hexdigest()


def nombres():
    return list(sintesis.TEMAS) + list(sintesis.JINGLES)


def ruta_de(nombre: str) -> str:
    return os.path.join(RUTA_SONIDOS, f"musica_{nombre}.ogg")


def main() -> None:
    try:
        import soundfile as sf
    except ImportError:
        sys.exit("Falta soundfile: pip install soundfile (solo para esta herramienta)")
    total = 0
    for nombre in nombres():
        datos = sintesis.tema(nombre, sintesis.SR) if nombre in sintesis.TEMAS else \
            sintesis.jingle(nombre, sintesis.SR)
        muestras = sintesis.a_int16(datos, 2)                         # igual que el juego al sintetizar
        sf.write(ruta_de(nombre), muestras, sintesis.SR, format="OGG", subtype="VORBIS",
                 compression_level=CALIDAD)
        tam = os.path.getsize(ruta_de(nombre))
        total += tam
        print(f"  musica_{nombre}.ogg  {len(muestras) / sintesis.SR:5.1f} s  {tam / 1024:6.0f} KB")
    with open(RUTA_HUELLA, "w", encoding="utf-8") as f:
        json.dump({"_ayuda": "Huella de las fuentes de la música grabada (tools/grabar_musica.py). "
                             "Si no coincide, vuelve a correr ese script.",
                   "huella": huella(), "temas": nombres()}, f, indent=2, ensure_ascii=False)
    print(f"Total: {total / 1024 / 1024:.1f} MB en {len(nombres())} archivos. Huella en {os.path.relpath(RUTA_HUELLA, RAIZ)}")


if __name__ == "__main__":
    main()
