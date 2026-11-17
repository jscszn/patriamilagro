"""Arma la versión web del juego con pygbag (Python + pygame dentro del navegador).

    python tools/empaquetar_web.py            # arma el paquete y abre un servidor de prueba local
    python tools/empaquetar_web.py --armar    # solo arma el paquete (no deja nada corriendo)
    python tools/empaquetar_web.py --sitio RUTA    # arma y copia la página a la carpeta de un sitio
    python tools/empaquetar_web.py --musica 0.6    # música más comprimida SOLO en la versión web

Requiere `pip install pygbag soundfile` (solo para esta herramienta; el juego no los usa).

Qué hace:
  1. Copia a web/patriamilagro/ SOLO lo que el juego necesita para correr: el código y los
     recursos finales. Quedan fuera HISTORIAL.md, tests/, tools/, docs/, config/ (preferencias
     de cada jugador), los originales de assets/sprites_raw y sonidos_raw y las hojas de revisión.
  2. Convierte los WAV a OGG (pygbag solo admite OGG). Con --musica N vuelve a comprimir
     assets/sonidos/musica_*.ogg con esa calidad Vorbis (0 = máxima, 1 = mínima; el juego de
     escritorio usa 0.2 y no se toca). Medido sobre los 10 temas: 0.2 = 7,3 MB (36 dB de
     relación señal-ruido); 0.4 = 5,7 MB (32 dB); 0.6 = 3,9 MB (28 dB). Las ondas cuadradas
     estilo NES se comprimen mal: decidir de oído.
  3. Llama a pygbag, que deja la página en web/patriamilagro/build/web/ (index.html + el paquete
     .apk + favicon). Con el servidor de prueba se abre en http://localhost:8000

La carpeta web/ se genera entera con este script: no editar nada ahí (está en .gitignore).
Nada se sube a internet. Con --sitio RUTA la página se copia a RUTA/public/patriamilagro/ (la
carpeta de archivos estáticos del sitio): index.html, patriamilagro.tar.gz y favicon.png. Al
index se le agrega <base href="/patriamilagro/"> para que encuentre sus archivos aunque la
dirección no termine en barra. Publicar el sitio es un paso aparte y manual.
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DESTINO = os.path.join(RAIZ, "web", "patriamilagro")
PUERTO = 8000
SALIDA = os.path.join(DESTINO, "build", "web")       # donde pygbag deja la página
NOMBRE = os.path.basename(DESTINO)                    # "patriamilagro": nombre del paquete y de la ruta
ARCHIVOS_SITIO = ("index.html", NOMBRE + ".tar.gz", "favicon.png")
# Página del juego: la plantilla de pygbag 0.9.3 con los textos en español, el fondo y el aviso
# de carga con el aspecto del juego, y el lienzo agrandado un número entero de veces
PLANTILLA = os.path.join(RAIZ, "tools", "web", "plantilla.tmpl")
CALIDAD_MUSICA = None     # None = la música va tal cual; un número = se recomprime para la web

ARCHIVOS = ("main.py", "settings.py", "input_manager.py", "ritmo.py", "almacen.py",
            "assets/sprites.json", "assets/paleta.json")
# carpeta -> extensiones que se copian
CARPETAS = {
    "core": (".py",), "render": (".py",), "scenes": (".py",), "audio": (".py",),
    "levels": (".py",), "net": (".py",),
    "assets/sprites": (".png",), "assets/mapa": (".json", ".png"),
    "assets/reportajes": (".png", ".json"), "assets/sonidos": (".ogg", ".wav"),
}


def copiar() -> list:
    """Copia el juego a DESTINO. Devuelve las rutas relativas copiadas."""
    if os.path.isdir(DESTINO):                    # carpeta generada: se rehace desde cero...
        for nombre in os.listdir(DESTINO):
            if nombre == "build":                 # ...salvo build/: ahí pygbag guarda lo que ya
                continue                          # descargó del motor web (no bajarlo otra vez)
            ruta = os.path.join(DESTINO, nombre)
            shutil.rmtree(ruta) if os.path.isdir(ruta) else os.remove(ruta)
    copiados = []
    for rel in ARCHIVOS:
        copiados.append(_copiar(rel))
    for carpeta, extensiones in CARPETAS.items():
        for base, _dirs, nombres in os.walk(os.path.join(RAIZ, carpeta)):
            if "__pycache__" in base:
                continue
            for nombre in sorted(nombres):
                if nombre.startswith(".") or not nombre.lower().endswith(extensiones):
                    continue
                copiados.append(_copiar(os.path.relpath(os.path.join(base, nombre), RAIZ)))
    return copiados


def _copiar(rel: str) -> str:
    """Copia un archivo; los WAV se convierten a OGG (mismo nombre, otra extensión)."""
    origen, destino = os.path.join(RAIZ, rel), os.path.join(DESTINO, rel)
    os.makedirs(os.path.dirname(destino), exist_ok=True)
    if rel.lower().endswith(".wav"):
        import soundfile                          # solo hace falta aquí
        datos, frecuencia = soundfile.read(origen)
        rel = rel[:-4] + ".ogg"
        soundfile.write(os.path.join(DESTINO, rel), datos, frecuencia, format="OGG", subtype="VORBIS")
    elif CALIDAD_MUSICA is not None and os.path.basename(rel).startswith("musica_") and rel.endswith(".ogg"):
        import soundfile
        datos, frecuencia = soundfile.read(origen, dtype="int16")
        soundfile.write(destino, datos, frecuencia, format="OGG", subtype="VORBIS",
                        compression_level=CALIDAD_MUSICA)
    else:
        shutil.copy2(origen, destino)
    return rel


def copiar_al_sitio(sitio: str) -> str:
    """Copia la página ya armada a <sitio>/public/patriamilagro/. Devuelve esa carpeta."""
    sitio = os.path.abspath(os.path.expanduser(sitio))
    if not os.path.isfile(os.path.join(sitio, "package.json")):
        sys.exit(f"[web] {sitio} no parece un sitio (no tiene package.json): no se copió nada")
    carpeta = os.path.join(sitio, "public", NOMBRE)
    os.makedirs(carpeta, exist_ok=True)
    for nombre in ARCHIVOS_SITIO:
        origen, destino = os.path.join(SALIDA, nombre), os.path.join(carpeta, nombre)
        if nombre == "index.html":
            with open(origen, encoding="utf-8") as f:
                html = f.read()
            marca = "<title>"
            if html.count(marca) != 1:
                sys.exit("[web] el index.html de pygbag cambió de forma: no encuentro dónde poner <base>")
            html = html.replace(marca, f'<base href="/{NOMBRE}/">\n    {marca}')
            with open(destino, "w", encoding="utf-8") as f:
                f.write(html)
        else:
            shutil.copy2(origen, destino)
    return carpeta


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--armar", action="store_true", help="solo arma el paquete, sin servidor de prueba")
    parser.add_argument("--puerto", type=int, default=PUERTO, help="puerto del servidor de prueba")
    parser.add_argument("--sitio", metavar="RUTA",
                        help="arma el paquete y lo copia a RUTA/public/patriamilagro/")
    parser.add_argument("--musica", type=float, metavar="CALIDAD",
                        help="recomprime la música solo para la web (0 = máxima calidad, 1 = mínima)")
    args = parser.parse_args()
    if args.musica is not None:
        if not 0.0 <= args.musica <= 1.0:
            sys.exit("[web] --musica va de 0 (máxima calidad) a 1 (mínima)")
        global CALIDAD_MUSICA
        CALIDAD_MUSICA = args.musica

    copiados = copiar()
    peso = sum(os.path.getsize(os.path.join(DESTINO, r)) for r in copiados)
    print(f"[web] {len(copiados)} archivos copiados a {os.path.relpath(DESTINO, RAIZ)} ({peso / 1e6:.1f} MB)")

    orden = [sys.executable, "-m", "pygbag", "--no_opt", "--ume_block", "1", "--can_close", "1", "--title", "Patria Milagro",
             "--template", PLANTILLA,
             "--port", str(args.puerto)]
    if args.armar or args.sitio:
        orden.append("--build")
    else:
        print(f"[web] Servidor de prueba: http://localhost:{args.puerto}  (Ctrl+C para cerrarlo)")
    orden.append(DESTINO)
    codigo = subprocess.call(orden)
    if codigo == 0 and args.sitio:
        carpeta = copiar_al_sitio(args.sitio)
        peso = sum(os.path.getsize(os.path.join(carpeta, n)) for n in ARCHIVOS_SITIO)
        print(f"[web] Página copiada a {carpeta} ({peso / 1e6:.1f} MB). Falta publicar el sitio.")
    sys.exit(codigo)


if __name__ == "__main__":
    main()
