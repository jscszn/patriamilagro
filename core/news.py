"""Noticias del teléfono: titulares de MEDIOS, publicaciones de INFLUENCERS y comentarios
del PUEBLO después de cada decisión.

Todo es ficticio y satírico: medios, influencers, personas y criminales son inventados.
No se menciona a personas ni partidos reales.

Para editar los textos basta con cambiar los diccionarios de este archivo:
  NOTICIAS[decisión]["normal"][categoría]   -> al menos 3 variantes por decisión y categoría
  NOTICIAS[decisión][contexto][categoría]   -> variantes especiales según el camino del árbol
Marcadores disponibles en los textos: {jefe}, {lugar}, {nivel}.
Un texto puede ser "texto" (autor al azar de su categoría) o ("AUTOR", "texto") cuando el
comentario solo tiene sentido en boca de alguien (p. ej. el tendero que cierra su tienda).
(El juego lo muestra todo en mayúsculas; no uses emojis: la fuente pixel no los tiene.)
"""
from __future__ import annotations

import random
from dataclasses import asdict, dataclass
from typing import Dict, List, Sequence

from core.decision_tree import CAPTURAR, EXTRADITAR, LIBERAR

MEDIOS = "medios"
INFLUENCERS = "influencers"
PUEBLO = "pueblo"
CATEGORIAS = (MEDIOS, INFLUENCERS, PUEBLO)

PORTAL = "PATRIANOTICIAS"   # nombre del portal ficticio que muestra el teléfono

# --- Autores ficticios ----------------------------------------------------------
AUTORES = {
    MEDIOS: ["LA BRÚJULA TV", "EL PREGÓN", "VENTANA 7 TV", "RADIO CUMBRE", "REV. SEMÁFORO"],
    INFLUENCERS: ["@VALEVIRAL", "@PROFEOPINA", "@TIOMEMES", "@GAMERPATRIOTA", "@MODAYJUSTICIA"],
    PUEBLO: ["DOÑA RUBIELA", "JHON, TAXISTA", "ABUELA CARMEN", "DON EFRAÍN", "ESTUDIANTE U.",
             "MOTOTAXISTA"],
}

LUGARES = {1: "la selva", 2: "la ciudad", 3: "la frontera"}

# --- Textos ---------------------------------------------------------------------
NOTICIAS: Dict[str, Dict[str, Dict[str, List[str]]]] = {
    CAPTURAR: {
        "normal": {
            MEDIOS: [
                "{jefe}, capturado en {lugar}: será juzgado en el país.",
                "Operativo exitoso: el presidente Milagro entrega a {jefe} a la justicia nacional.",
                "Expertos piden garantías para el juicio de {jefe}: 'que no sea un show'.",
            ],
            INFLUENCERS: [
                "Literal el presi se puso las botas. {jefe} a la cárcel. #JusticiaYa",
                "Hice un análisis de 40 minutos sobre la captura. Link en mi bio.",
                "No sé ustedes, pero yo ya mandé a hacer la camiseta de Milagro.",
            ],
            PUEBLO: [
                "Por fin algo bueno en las noticias, mijo.",
                "Ojalá ahora sí arreglen el hueco de mi cuadra.",
                ("ABUELA CARMEN", "Que le den sopa en la cárcel, que se ve flaquito."),
            ],
        },
        # Capturar después de haber liberado a alguien antes
        "rectifica": {
            MEDIOS: ["Giro en palacio: tras liberar a un capo, Milagro ahora captura a {jefe}."],
            INFLUENCERS: ["Plot twist: el presi aprendió la lección. Le doy un 7 de 10."],
            PUEBLO: ["Más vale tarde que nunca, presidente."],
        },
        # Todas las decisiones hasta ahora fueron capturar (desde el nivel 2)
        "racha": {
            MEDIOS: ["Otra captura: crece el apoyo a Milagro... y las dudas por los excesos."],
            INFLUENCERS: ["Mano dura, temporada {nivel}. Ya hice el meme."],
            PUEBLO: [("MOTOTAXISTA", "Así sí da gusto salir a trabajar.")],
        },
    },
    EXTRADITAR: {
        "normal": {
            MEDIOS: [
                "{jefe}, extraditado: lo juzgarán en el exterior.",
                "Socios internacionales aplauden la extradición de {jefe}.",
                "Debate en el Congreso: ¿estamos delegando la justicia al extranjero?",
            ],
            INFLUENCERS: [
                "{jefe} se fue en avión y yo sin vacaciones desde hace cinco años.",
                "Explicación rápida: extraditar = juicio afuera. De nada.",
                "El presi diplomático. Muy elegante, pero... ¿y la justicia de aquí?",
            ],
            PUEBLO: [
                "Que lo juzguen donde sea, pero que no vuelva.",
                "¿Y a las víctimas de aquí quién las escucha?",
                ("ESTUDIANTE U.", "Interesante jugada geopolítica, la verdad."),
            ],
        },
        "racha": {
            MEDIOS: ["Otra extradición: críticos acusan a Milagro de 'tercerizar' la justicia."],
            INFLUENCERS: ["Ya van varios extraditados. Esto parece servicio de mensajería."],
            PUEBLO: ["¿Y aquí no tenemos jueces o qué?"],
        },
    },
    LIBERAR: {
        "normal": {
            MEDIOS: [
                "Polémica: el presidente deja libre a {jefe} tras capturarlo en {lugar}.",
                "Silencio en palacio sobre la liberación de {jefe}.",
                "Analistas: dejar libre a {jefe} 'envía un mensaje confuso'.",
            ],
            INFLUENCERS: [
                "Perdón, ¿QUÉ? {jefe} libre. Necesito un minuto.",
                "Teoría: el presi tiene un plan secreto. O no. Probablemente no.",
                "Hoy no hay meme. Hoy hay decepción. #NiUnCapoLibre",
            ],
            PUEBLO: [
                "Ay no, presidente, ¿y entonces pa' qué lo cogió?",
                ("JHON, TAXISTA", "Yo lo vi pasar por la avenida, muy tranquilo el señor."),
                ("ABUELA CARMEN", "En mis tiempos eso no se veía."),
            ],
        },
        # Liberar cuando ya se había liberado antes: los textos son más duros
        "reincidente": {
            MEDIOS: [
                "¡OTRA VEZ! Milagro libera a {jefe}: ya son varios capos sueltos en su mandato.",
                "Editorial: ¿presidente o portero que les abre la puerta a todos?",
            ],
            INFLUENCERS: [
                "Dos de dos. Ya no es un error, es un estilo. #RenunciaMilagro",
                "Estoy haciendo un mapa de los capos libres. Necesito más hojas.",
            ],
            PUEBLO: [
                ("DON EFRAÍN", "Voy a cerrar la tienda temprano, por si acaso."),
                ("JHON, TAXISTA", "Ya ni los pasajeros quieren salir de noche."),
            ],
        },
    },
}

# Hashtags: máximo 16 caracteres para que quepan en una línea de la tarjeta
TENDENCIAS = {
    CAPTURAR: ["#JusticiaYa", "#MilagroCumple", "#CapoEnCana"],
    EXTRADITAR: ["#ExtraditadoYa", "#JusticiaGlobal", "#YLaDeAquíQué"],
    LIBERAR: ["#NiUnCapoLibre", "#ExpliqueYa", "#QuéPasóPresi"],
}


@dataclass
class Publicacion:
    """Una tarjeta del feed (serializable)."""
    categoria: str          # medios | influencers | pueblo | tendencias
    autor: str
    texto: str
    reacciones: int = 0
    destacada: bool = False  # titular principal ("ÚLTIMA HORA")

    def to_dict(self) -> dict:
        return asdict(self)


def contexto_de(camino: Sequence[str]) -> str:
    """Qué variante especial corresponde según el camino acumulado del árbol."""
    if not camino:
        return "normal"
    actual, previas = camino[-1], list(camino[:-1])
    if actual == LIBERAR and LIBERAR in previas:
        return "reincidente"
    if actual == CAPTURAR and LIBERAR in previas:
        return "rectifica"
    if previas and all(d == actual for d in previas):
        return "racha"
    return "normal"


def _formatear(texto: str, jefe: str, nivel: int) -> str:
    return texto.format(jefe=jefe, lugar=LUGARES.get(nivel, "el país"), nivel=nivel)


def generar_feed(camino: Sequence[str], jefe: str, semilla: str = None) -> List[Publicacion]:
    """Arma el feed del teléfono para la última decisión del camino.

    Es determinista: el mismo camino produce siempre el mismo feed (útil en pruebas y para
    que dos jugadores en red vean lo mismo).
    """
    decision, nivel = camino[-1], len(camino)
    contexto = contexto_de(camino)
    rng = random.Random(semilla or "/".join(camino) + jefe)
    textos = NOTICIAS[decision]
    especiales = textos.get(contexto, {}) if contexto != "normal" else {}

    # Autores al azar sin repetir dentro de una categoría (se evita además a los autores fijos)
    fijos = {e[0] for por_contexto in textos.values() for lista in por_contexto.values()
             for e in lista if isinstance(e, tuple)}
    libres = {c: [a for a in AUTORES[c] if a not in fijos] for c in CATEGORIAS}
    turnos = {c: rng.sample(libres[c], k=len(libres[c])) for c in CATEGORIAS}

    def siguiente_autor(categoria: str) -> str:
        if not turnos[categoria]:
            turnos[categoria] = rng.sample(AUTORES[categoria], k=len(AUTORES[categoria]))
        return turnos[categoria].pop()

    def publicacion(categoria: str, entrada, destacada: bool = False) -> Publicacion:
        autor, texto = entrada if isinstance(entrada, tuple) else (siguiente_autor(categoria), entrada)
        base = {MEDIOS: 40000, INFLUENCERS: 120000, PUEBLO: 300}[categoria]
        return Publicacion(categoria, autor, _formatear(texto, jefe, nivel),
                           int(base * rng.uniform(0.2, 1.5)), destacada)

    # 1) Titular principal: el especial del contexto si existe (así el tono cambia con el camino)
    medios = list(textos["normal"][MEDIOS])
    rng.shuffle(medios)
    principal = especiales.get(MEDIOS, [None])[0] or medios.pop()
    feed = [publicacion(MEDIOS, principal, destacada=True)]

    # 2) Resto: especiales primero (son lo que más se comenta) y luego variantes normales
    por_categoria = {}
    for categoria in CATEGORIAS:
        lista = [t for t in especiales.get(categoria, []) if t != principal]
        normales = [t for t in textos["normal"][categoria] if t != principal and t not in lista]
        rng.shuffle(normales)
        cantidad = {MEDIOS: 2, INFLUENCERS: 3, PUEBLO: 3}[categoria]
        por_categoria[categoria] = (lista + normales)[:cantidad]

    # 3) Intercalar: influencer, pueblo, medio... con una tarjeta de tendencias en medio
    orden = [INFLUENCERS, PUEBLO, MEDIOS, PUEBLO, INFLUENCERS, MEDIOS, PUEBLO, INFLUENCERS]
    for i, categoria in enumerate(orden):
        if por_categoria[categoria]:
            feed.append(publicacion(categoria, por_categoria[categoria].pop(0)))
        if i == 2:
            etiquetas = "  ".join(TENDENCIAS[decision])
            feed.append(Publicacion("tendencias", "TENDENCIAS", etiquetas))
    return feed


def entradas() -> List[tuple]:
    """Todas las entradas de NOTICIAS como (autor_o_None, texto)."""
    return [e if isinstance(e, tuple) else (None, e) for por_decision in NOTICIAS.values()
            for por_contexto in por_decision.values() for lista in por_contexto.values() for e in lista]


def todos_los_textos() -> List[str]:
    """Todos los textos y nombres (para validarlos en las pruebas)."""
    textos = [t for _, t in entradas()] + [a for a, _ in entradas() if a]
    textos += [a for lista in AUTORES.values() for a in lista]
    textos += [t for lista in TENDENCIAS.values() for t in lista]
    return textos + [PORTAL]
