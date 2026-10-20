"""Definiciones de los niveles como datos (diccionarios en Python, fáciles de editar)."""
from levels import nivel1, nivel2, nivel3

NIVELES = {
    1: nivel1.NIVEL,     # la selva
    2: nivel2.NIVEL,     # la ciudad
    3: nivel3.NIVEL,     # la frontera
}
ULTIMO_NIVEL = 3


def cargar_nivel(numero: int) -> dict:
    """Devuelve los datos del nivel `numero`."""
    return NIVELES[numero]
