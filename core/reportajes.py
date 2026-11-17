"""Reportajes al final de cada nivel: el país comenta la decisión sobre el jefe de ese nivel.

Después del teléfono de cada nivel (antes del informe del siguiente o de la pantalla final),
el país opina en UNO de tres formatos, uno por cada categoría de opinión del árbol. Cada partida
reparte los tres formatos entre los tres niveles en un orden al azar (formatos(semilla)): en una
partida el nivel 1 lo comenta el influencer, en otra el noticiero, etc.
  - NOTICIERO (medios): la presentadora de VENTANA 7 TV y un analista.
  - EN VIVO (influencers): @NICOVIRAL reacciona y le responde al chat.
  - LA CALLE (pueblo): una reportera entrevista a un vecino en cada lugar del país.

Cada escena = introducción + (pregunta, comentario) sobre la decisión del nivel. En el nivel 3 va
además un cierre que depende de cómo terminó la opinión de esa categoría (alta, media o baja).

Para editar los textos basta con cambiar los diccionarios de este archivo:
  COMENTARIOS[categoría][decisión][nivel]   -> el comentario sobre la decisión de ese nivel
  ESPECIALES[categoría][contexto]           -> reemplaza al comentario según el camino del árbol
                                               (reincidente, rectifica, racha; ver core/news.py)
  PREGUNTAS, INTROS y CIERRES               -> lo que dicen los anfitriones
Marcadores: {jefe}, {lugar}. El juego lo muestra todo en mayúsculas y sin emojis.
Las pruebas (tests/test_reportajes.py) revisan que todo exista y quepa en el cuadro de diálogo.
Todo es ficticio y satírico: no se menciona a personas, medios ni partidos reales.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

from core.decision_tree import CAPTURAR, DECISIONES, EXTRADITAR, LIBERAR
from core.news import INFLUENCERS, LUGARES, MEDIOS, PUEBLO, contexto_de, contraer, narrado

# Escenario (cómo se dibuja) de cada categoría, en el orden en que se muestran
ESCENARIOS = {MEDIOS: "noticiero", INFLUENCERS: "en_vivo", PUEBLO: "calle"}
ORDEN = (MEDIOS, INFLUENCERS, PUEBLO)
TITULOS = {MEDIOS: "NOTICIERO", INFLUENCERS: "EN VIVO", PUEBLO: "LA CALLE"}
CANAL = "VENTANA 7"

ULTIMO = 3                     # en este nivel van los cierres

# Umbrales del cierre: opinión final de la categoría (0..100)
ALTA, BAJA = 60, 40


@dataclass(frozen=True)
class Hablante:
    nombre: str          # lo que se ve en la pestaña del cuadro de diálogo
    cargo: str           # rótulo en pantalla (p. ej. "ANALISTA")


# Las claves son también las del aspecto de cada personaje (render/personajes.py)
HABLANTES: Dict[str, Hablante] = {
    "presentadora": Hablante("LUCÍA PRADO", "PRESENTADORA"),
    "analista": Hablante("DR. ORTIZ", "ANALISTA"),
    "influencer": Hablante("@NICOVIRAL", "EN VIVO"),
    "reportera": Hablante("TATIANA RÍOS", "REPORTERA"),
    "jhon": Hablante("JHON", "TAXISTA"),
    "efrain": Hablante("DON EFRAÍN", "TENDERO"),
    "carmen": Hablante("ABUELA CARMEN", "JUBILADA"),
}
# En el directo, las preguntas vienen del chat: un seguidor distinto por nivel
CHAT = {1: "@TIOMEMES", 2: "@PROFEOPINA", 3: "@GAMERPATRIOTA"}
# En la calle, un vecino distinto por nivel (cada uno en su lugar del país). La abuela Carmen
# además da el veredicto del cierre (nivel 3); como la calle sale una sola vez por partida,
# nunca aparece dos veces en la misma.
VECINOS = {1: "carmen", 2: "jhon", 3: "efrain"}

# Quién pregunta y quién comenta en cada escena (el chat se resuelve con CHAT)
ANFITRION = {MEDIOS: "presentadora", INFLUENCERS: "chat", PUEBLO: "reportera"}
COMENTARISTA = {MEDIOS: "analista", INFLUENCERS: "influencer", PUEBLO: "vecino"}

# --- Textos ---------------------------------------------------------------------------------
INTROS: Dict[str, List[tuple]] = {
    MEDIOS: [
        ("presentadora", "Buenas noches. Esta noche seguimos de cerca las decisiones del presidente "
                         "Milagro."),
    ],
    INFLUENCERS: [
        ("influencer", "¡Holaaa, mi gente! Hoy reacciono a lo que hace el presi Milagro con los "
                       "capos. Denle like."),
    ],
    PUEBLO: [
        ("reportera", "Salimos a la calle a preguntarle a la gente qué piensa de las decisiones del "
                      "presidente."),
    ],
}

# Conector de cada nivel + la pregunta según la decisión
CONECTORES = {
    MEDIOS: {1: "Empezamos en {lugar}.", 2: "Pasamos a {lugar}.", 3: "Y por último, {lugar}."},
    INFLUENCERS: {1: "", 2: "", 3: ""},
    PUEBLO: {1: "Disculpe,", 2: "Buenas, una pregunta:", 3: "Y usted, señor:"},
}
PREGUNTAS = {
    MEDIOS: {
        CAPTURAR: "{jefe} fue capturado y lo juzgarán en el país. Doctor, ¿qué nos dice?",
        EXTRADITAR: "{jefe} fue extraditado al exterior. ¿Cómo lo lee, doctor?",
        LIBERAR: "El presidente dejó libre a {jefe}. Doctor, ¿tiene explicación?",
    },
    INFLUENCERS: {
        CAPTURAR: "¿Y lo de {jefe}? ¿Sí lo metieron preso o es montaje?",
        EXTRADITAR: "Nico, ¿qué opinas de que extraditaran a {jefe}?",
        LIBERAR: "NICO REACCIONA A LO DE {jefe} PLIS",
    },
    PUEBLO: {
        CAPTURAR: "¿qué opina de que capturaran a {jefe}?",
        EXTRADITAR: "¿qué opina de que extraditaran a {jefe}?",
        LIBERAR: "¿qué opina de que dejaran libre a {jefe}?",
    },
}

COMENTARIOS: Dict[str, Dict[str, Dict[int, str]]] = {
    MEDIOS: {          # el analista
        CAPTURAR: {
            1: "Un golpe limpio. Juzgarlo aquí fortalece a nuestros jueces... si el juicio no se "
               "vuelve un reality.",
            2: "Capturarlo en plena ciudad fue un mensaje: el Estado volvió a las calles. Ahora toca "
               "sostenerlo.",
            3: "En la frontera era tentador mandarlo afuera. Juzgarlo aquí es más lento, pero es "
               "soberano.",
        },
        EXTRADITAR: {
            1: "Afuera lo juzgarán rápido, sí. Pero las víctimas de la selva lo verán por "
               "televisión, si acaso.",
            2: "Los socios internacionales, felices. Los jueces nacionales, no tanto: se sienten de "
               "adorno.",
            3: "Con la frontera ahí mismo, extraditarlo era lo lógico. Hasta sus críticos lo "
               "admiten.",
        },
        LIBERAR: {
            1: "Es inexplicable. Arriesgar soldados para capturarlo y luego abrirle la puerta.",
            2: "Soltarlo en la ciudad es invitarlo a volver a cobrar vacunas. Un error grave.",
            3: "Dejarlo libre en la frontera es regalarle la salida del país. No hay forma de "
               "defenderlo.",
        },
    },
    INFLUENCERS: {     # @NICOVIRAL
        CAPTURAR: {
            1: "Capturado en la selva. El presi con botas pantaneras, chicos. Ícono. #JusticiaYa",
            2: "Lo cogieron en plena ciudad y hubo transmisión en vivo. Yo lloré. Bueno, casi.",
            3: "Ni la frontera lo salvó. Mano dura nivel final de temporada. Le doy un nueve.",
        },
        EXTRADITAR: {
            1: "Se fue en avión y yo sin vacaciones. Igual: juicio afuera, menos show aquí. Aprobado.",
            2: "Lo mandaron afuera. Elegante, sí. Pero el chat dice: ¿y la justicia de aquí qué?",
            3: "Extraditado desde la frontera. Literal le quedaba a dos pasos. Muy práctico, presi.",
        },
        LIBERAR: {
            1: "Lo soltó. En la selva. Así nomás. Necesito un minuto. No, mejor dos.",
            2: "Libre en la ciudad. Mis seguidores de allá me están escribiendo en mayúsculas.",
            3: "Lo dejó libre en la frontera. O sea, le abrió la puerta del país. Hoy no hay meme.",
        },
    },
    PUEBLO: {          # el vecino de cada nivel (VECINOS)
        CAPTURAR: {
            1: "Ay, por fin algo bueno en las noticias, mija. Que lo juzguen aquí, que vean lo que "
               "hizo.",
            2: "Desde que lo cogieron, la avenida se siente distinta. Hasta propina me están dando.",
            3: "Ya puedo abrir la tienda hasta las nueve. Eso para mí es una captura bien hecha.",
        },
        EXTRADITAR: {
            1: "Que lo juzguen donde sea, pero que no vuelva. Aunque las víctimas son de aquí, ¿no?",
            2: "Se lo llevaron en avión. Qué envidia, yo no conozco ni el aeropuerto por dentro.",
            3: "Que se lo lleven, que allá las cárceles sí tienen rejas. Aquí se salen por la ventana.",
        },
        LIBERAR: {
            1: "Ay no, presidente, ¿y entonces pa' qué lo cogió? Explíqueme, que no entiendo.",
            2: "Yo lo vi pasar por la avenida, muy tranquilo el señor. Ni el pico y placa respeta.",
            3: "Voy a cerrar la tienda temprano, por si acaso. Y a esconder la caja registradora.",
        },
    },
}

# Si el jefe ESCAPÓ (se acabó el reloj mientras el presidente dudaba), se pregunta y se comenta
# eso, no una liberación. Cuenta como dejarlo libre para la opinión, pero no se narra igual.
PREGUNTAS_ESCAPE = {
    MEDIOS: "{jefe} escapó mientras el presidente decidía. Doctor, ¿qué pasó ahí?",
    INFLUENCERS: "NICO, ¿VISTE QUE {jefe} SE LES VOLÓ?",
    PUEBLO: "¿qué opina de que {jefe} se escapara mientras el presidente dudaba?",
}
COMENTARIOS_ESCAPE: Dict[str, Dict[int, str]] = {
    MEDIOS: {
        1: "La duda también es una decisión. En la selva, quince segundos bastan para perderse.",
        2: "En plena ciudad y con todas las cámaras: se le fue por indeciso. Eso no se olvida.",
        3: "Dudar en la frontera es abrirle la puerta. Del otro lado ya nadie lo alcanza.",
    },
    INFLUENCERS: {
        1: "El presi pensándolo y el capo ya iba por el tercer árbol. Hoy el meme se hace solo.",
        2: "Se le voló en plena ciudad. En vivo. No sé si reír o llorar, chicos.",
        3: "Lo tenía al lado de la frontera y se puso a pensar. Game over, presi.",
    },
    PUEBLO: {          # el vecino de cada nivel (VECINOS)
        1: "Ay, mija, se le fue mientras pensaba. Como mi gallina el domingo.",
        2: "Se le voló como pasajero sin pagar: uno se distrae y chao.",
        3: "Mientras él pensaba, el otro ya iba por la trocha. Aquí nadie espera.",
    },
}

# Reemplazan al comentario cuando el camino del árbol lo amerita (desde el nivel 2)
ESPECIALES: Dict[str, Dict[str, str]] = {
    MEDIOS: {
        "reincidente": "Ya no es un error aislado: es un patrón. Nadie en el gabinete sabe "
                       "explicarlo.",
        "rectifica": "Al menos rectificó. Capturar después de liberar dice que escuchó las críticas.",
        "racha": "Coherente, eso sí: la misma decisión otra vez. ¿Convicción o costumbre?",
    },
    INFLUENCERS: {
        "reincidente": "Otro libre. Ya no es error, es estilo. #RenunciaMilagro está en tendencia.",
        "rectifica": "Plot twist: el presi aprendió la lección. Le doy un siete por arrepentirse.",
        "racha": "Otra vez lo mismo. El presi no cambia el guion ni por error. Ya hice el meme.",
    },
    PUEBLO: {
        "reincidente": "¿Otro más libre? Ya ni los clientes quieren salir de noche, mija.",
        "rectifica": "Más vale tarde que nunca, presidente. Esa sí me gustó.",
        "racha": "Otra vez lo mismo. Por lo menos uno ya sabe qué esperar del presidente.",
    },
}

CIERRES: Dict[str, Dict[str, List[tuple]]] = {
    MEDIOS: {
        "alta": [("analista", "La prensa le pone buena nota. Milagro termina con los titulares a "
                              "favor."),
                 ("presentadora", "Así cierra el mandato. Soy Lucía Prado. Buenas noches.")],
        "media": [("analista", "Luces y sombras. Ni los editoriales se ponen de acuerdo."),
                  ("presentadora", "El debate sigue abierto. Soy Lucía Prado. Buenas noches.")],
        "baja": [("analista", "La prensa lo reprueba. Quedan demasiadas preguntas sin respuesta."),
                 ("presentadora", "Seguiremos preguntando. Soy Lucía Prado. Buenas noches.")],
    },
    INFLUENCERS: {
        "alta": [("influencer", "Veredicto del directo: Milagro es tendencia por las buenas. "
                                "Suscríbanse, chao.")],
        "media": [("influencer", "Veredicto: el presi, ni fu ni fa. El chat está dividido. Nos "
                                 "vemos en el próximo.")],
        "baja": [("influencer", "Veredicto: #RenunciaMilagro número uno. Apago, que el chat se "
                                "puso feo.")],
    },
    PUEBLO: {
        "alta": [("carmen", "Ese muchacho Milagro va bien. Que coma bien y que siga así."),
                 ("reportera", "Así piensa la calle. Tatiana Ríos, para " + CANAL + ".")],
        "media": [("carmen", "Ni muy muy, ni tan tan. Como el caldo de los domingos."),
                  ("reportera", "Así piensa la calle. Tatiana Ríos, para " + CANAL + ".")],
        "baja": [("carmen", "En mis tiempos eso no se veía. Que Dios nos coja confesados."),
                 ("reportera", "Así piensa la calle. Tatiana Ríos, para " + CANAL + ".")],
    },
}


# --- Guion ----------------------------------------------------------------------------------
@dataclass
class Linea:
    """Un cuadro de diálogo."""
    hablante: str                  # clave de HABLANTES (o del chat)
    nombre: str                    # lo que se muestra en la pestaña
    texto: str
    nivel: Optional[int] = None    # el nivel del reportaje
    decision: Optional[str] = None # la decisión comentada (None en la intro y el cierre)
    escapo: bool = False           # el jefe de este nivel escapó (decision es liberar)
    parte: str = "decision"        # intro | decision | cierre


@dataclass
class Segmento:
    categoria: str
    escenario: str
    lineas: List[Linea] = field(default_factory=list)
    banda: str = "media"           # cómo terminó la opinión de esta categoría


def banda(valor: int) -> str:
    if valor >= ALTA:
        return "alta"
    if valor <= BAJA:
        return "baja"
    return "media"


def _formatear(texto: str, jefe: str, nivel: Optional[int]) -> str:
    return contraer(texto.format(jefe=jefe, lugar=LUGARES.get(nivel, "el país")))


def _linea(clave: str, texto: str, jefe: str = "", nivel: int = None, decision: str = None,
           parte: str = "decision") -> Linea:
    nombre = clave if clave.startswith("@") else HABLANTES[clave].nombre
    return Linea(clave, nombre, _formatear(texto, jefe, nivel), nivel=nivel, decision=decision, parte=parte)


def comentario(categoria: str, camino: Sequence[str], nivel: int, escapes: Sequence[int] = ()) -> str:
    """El comentario sobre la decisión del nivel dado (camino[:nivel] es lo decidido hasta ahí).
    escapes: niveles cuyo jefe escapó (se comentan como escape y no cuentan como liberación)."""
    if nivel in escapes:
        return COMENTARIOS_ESCAPE[categoria][nivel]
    contexto = contexto_de(narrado(camino[:nivel], escapes))
    especial = ESPECIALES[categoria].get(contexto) if nivel > 1 else None
    return especial or COMENTARIOS[categoria][camino[nivel - 1]][nivel]


def _quien(rol: str, categoria: str, nivel: int) -> str:
    if rol == "chat":
        return CHAT[nivel]
    if rol == "vecino":
        return VECINOS[nivel]
    return rol


def formatos(semilla) -> Dict[int, str]:
    """Qué formato (categoría) comenta cada nivel en esta partida: los tres en un orden al azar,
    fijo para la misma semilla (así se repite igual si se vuelve a jugar la misma partida)."""
    orden = random.Random(f"reportajes-{semilla}").sample(ORDEN, len(ORDEN))
    return {nivel: categoria for nivel, categoria in enumerate(orden, start=1)}


def guion(camino: Sequence[str], jefes: Sequence[str], opinion: Dict[str, int],
          nivel: int = None, categorias: Sequence[str] = ORDEN, escapes: Sequence[int] = ()) -> List[Segmento]:
    """Los segmentos (uno por cada categoría pedida) del reportaje del `nivel` (por defecto, el
    último decidido). El juego pide una sola categoría por nivel (ver formatos).

    camino: las decisiones hasta ahora (camino[nivel - 1] es la que se comenta; las anteriores
    deciden si hay comentario especial); jefes: el nombre del jefe de cada nivel; opinion: la
    opinión actual por categoría. Es determinista: el mismo camino produce el mismo guion.
    """
    nivel = nivel or len(camino)
    decision = camino[nivel - 1]
    jefe = jefes[nivel - 1] if nivel - 1 < len(jefes) else "el capo"
    segmentos = []
    for categoria in categorias:
        seg = Segmento(categoria, ESCENARIOS[categoria], banda=banda(opinion.get(categoria, 50)))
        seg.lineas += [_linea(h, t, nivel=nivel, parte="intro") for h, t in INTROS[categoria]]
        conector = CONECTORES[categoria][nivel]
        escapo = nivel in escapes
        cuerpo = PREGUNTAS_ESCAPE[categoria] if escapo else PREGUNTAS[categoria][decision]
        pregunta = (conector + " " if conector else "") + cuerpo
        for clave, texto in ((_quien(ANFITRION[categoria], categoria, nivel), pregunta),
                             (_quien(COMENTARISTA[categoria], categoria, nivel),
                              comentario(categoria, camino, nivel, escapes))):
            linea = _linea(clave, texto, jefe, nivel, decision)
            linea.escapo = escapo
            seg.lineas.append(linea)
        if nivel == ULTIMO:
            seg.lineas += [_linea(h, t, nivel=nivel, parte="cierre") for h, t in CIERRES[categoria][seg.banda]]
        segmentos.append(seg)
    return segmentos


def todos_los_textos() -> List[str]:
    """Todos los textos crudos (para validarlos en las pruebas)."""
    textos = [t for por_cat in INTROS.values() for _, t in por_cat]
    textos += [t for por_cat in CONECTORES.values() for t in por_cat.values()]
    textos += [t for por_cat in PREGUNTAS.values() for t in por_cat.values()]
    textos += [t for por_cat in COMENTARIOS.values() for por_dec in por_cat.values() for t in por_dec.values()]
    textos += [t for por_cat in ESPECIALES.values() for t in por_cat.values()]
    textos += list(PREGUNTAS_ESCAPE.values())
    textos += [t for por_cat in COMENTARIOS_ESCAPE.values() for t in por_cat.values()]
    textos += [t for por_cat in CIERRES.values() for lista in por_cat.values() for _, t in lista]
    textos += [h.nombre for h in HABLANTES.values()] + [h.cargo for h in HABLANTES.values()]
    return textos + list(CHAT.values())


assert all(set(COMENTARIOS[c]) == set(DECISIONES) for c in ORDEN)
