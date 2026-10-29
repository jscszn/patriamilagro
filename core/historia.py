"""Historia antes de cada nivel: qué daño está haciendo el jefe en su zona.

Los textos son datos fáciles de editar. Todo es ficticio. El informe tiene dos páginas:
  1. LOS DAÑOS: lo que hace el jefe, con una frase que depende del camino del árbol (qué se
     hizo con los jefes anteriores).
  2. LA RUTA: lo que calcula el grafo del país (core/mapa.py) para la ruta elegida: el camino,
     sus tramos y su peligro, y lo que eso significa (refuerzos enemigos y opinión).
(El juego lo muestra en mayúsculas, en una columna angosta junto al mapa: cada página debe
caber en su recuadro; lo comprueba tests/test_novedades.py.)
"""
from __future__ import annotations

from typing import List, Sequence

from core.decision_tree import CAPTURAR, EXTRADITAR, LIBERAR
from core.mapa import NOMBRE_RUTA, SEGURA, Mapa

DANOS = {
    1: "EL JAGUAR DEL MONTE HIZO DE LA SELVA DEL VICHADA SU FORTALEZA. TALA EL BOSQUE PARA ABRIR "
       "PISTAS, ENVENENA LOS RÍOS CON SUS LABORATORIOS Y RECLUTA A LOS NIÑOS DE LAS VEREDAS. "
       "QUIEN NO LE PAGA, SE VA.",
    2: "DON CONCRETO ES EL DUEÑO DE MEDELLÍN. EXTORSIONA A LOS TENDEROS, "
       "LAVA DINERO EN OBRAS QUE NUNCA TERMINAN Y COMPRÓ A MEDIA ALCALDÍA. SUS MOTOS "
       "IMPONEN EL TOQUE DE QUEDA.",
    3: "LA SOMBRA DE LA RAYA MANDA EN LA GUAJIRA. NADA CRUZA LA FRONTERA SIN PAGARLE: GASOLINA, "
       "GANADO, GENTE. SE LLEVA EL AGUA DE LAS RANCHERÍAS Y QUIEN DENUNCIA DESAPARECE.",
}

# Frase extra según lo que se hizo con el jefe ANTERIOR (camino del árbol)
SEGUN_ANTERIOR = {
    2: {CAPTURAR: "CON EL JAGUAR PRESO, PERDIÓ SUS RUTAS: ESTÁ NERVIOSO.",
        EXTRADITAR: "TRAS LA EXTRADICIÓN DEL JAGUAR, JURA QUE A ÉL NO LO SACAN.",
        LIBERAR: "EL JAGUAR, LIBRE, LE SIGUE MANDANDO ARMAS DESDE LA SELVA."},
    3: {CAPTURAR: "CON DON CONCRETO PRESO, SE QUEDÓ SIN QUIEN LE LAVE EL DINERO.",
        EXTRADITAR: "DON CONCRETO HABLÓ EN EL EXTRANJERO: LA SOMBRA SABE QUE VIENEN POR ELLA.",
        LIBERAR: "DON CONCRETO, LIBRE, LE FINANCIA UN EJÉRCITO NUEVO."},
}
INICIO = "TU MISIÓN, PRESIDENTE: LLEGAR HASTA ÉL Y DECIDIR SU DESTINO."


def pagina_danos(nivel: int, camino: Sequence[str]) -> str:
    extra = SEGUN_ANTERIOR.get(nivel, {}).get(camino[-1]) if camino else None
    return DANOS[nivel] + (" " + extra if extra else "")


def pagina_ruta(nivel: int, mapa: Mapa, clave: str = SEGURA) -> str:
    """Lo que calculó el grafo para la ruta `clave` y qué le hace al nivel."""
    opciones = mapa.rutas(nivel)
    r = opciones.get(clave) or opciones[SEGURA]
    partes = [f"{NOMBRE_RUTA[clave]}: " + " > ".join(mapa.nombre(z) for z in r["camino"])
              + f". {r['tramos']} {'TRAMO' if r['tramos'] == 1 else 'TRAMOS'}, PELIGRO {r['peligro']}."]
    partes.append(f"REFUERZOS ENEMIGOS: +{r['refuerzos']}." if r["refuerzos"] else "SIN REFUERZOS EXTRA.")
    pueblo = r["opinion"]["pueblo"]
    partes.append(f"LLEGAS TARDE: PUEBLO {pueblo}." if pueblo else "LLEGAS A TIEMPO.")
    cerca = mapa.jefes_cerca(nivel)
    if cerca:
        partes.append("JEFE LIBRE CERCA: " + ", ".join(mapa.nombre(z) for z in cerca) + ".")
    return " ".join(partes)


def informe(nivel: int, camino: Sequence[str], mapa: Mapa, clave: str = SEGURA) -> List[str]:
    """Las dos páginas del informe del nivel."""
    return [pagina_danos(nivel, camino), pagina_ruta(nivel, mapa, clave)]
