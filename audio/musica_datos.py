"""Partituras de la música del juego, escritas a mano (composición original del equipo).

Cada tema tiene secciones de compases de 4/4 y un orden en que se tocan (y luego se repite en
bucle). Por compás:

    melodia   notas "NOTA:duración" separadas por espacios, en semicorcheas (16 = redonda,
              4 = negra, 2 = corchea, 3 = corchea con puntillo). "r" es silencio.
              Ej.: "A4:2 C5:2 E5:4 r:8". Cada compás debe sumar 16.
    acordes   uno o dos acordes por compás: "Am", "F G" (cada uno ocupa la mitad).
              Calidades: "" mayor, "m" menor, "7", "m7", "dim", "sus".
    bajo      igual que la melodía, o None: entonces se toca el estilo de bajo del tema
              sobre los acordes (octavas, marcha, galope, metralla, latido).
    bateria   nombre de un patrón de PATRONES por compás.

Las voces imitan los 5 canales de la NES: pulso 1 (melodía), pulso 2 (arpegio), triángulo
(bajo), ruido (batería) y un eco de la melodía (truco clásico de los compositores de NES).
"""

# Batería: 16 semicorcheas por compás.
#   k bombo · s caja · h charles cerrado · o charles abierto · c platillo (con bombo) · t tambor
PATRONES = {
    "rock":     "k.hhs.hhk.kks.hh",
    "rock_b":   "k.hhs.hkk.hhs.ho",
    "relleno":  "k.hhs.hhs.ssttss",
    "entrada":  "c.hhs.hhk.kks.hh",
    "funk":     "k.hks.hk.hk.s.ho",
    "funk_b":   "k.hks.hkkhk.s.hs",
    "galope":   "k.hkk.hks.hkk.hs",
    "galope_b": "c.hkk.hks.hks.ss",
    "jefe":     "khkhs.hkkhkhs.hk",
    "jefe_b":   "khkhs.hkkhkhsstt",
    "medio":    "k...s...k.k.s...",
    "latido":   "k..k............",
    "pop":      "k.h.s.h.k.k.s.h.",
    "pop_b":    "c.h.s.h.k.k.s.ss",
    "marcha":   "k...s.s.k...s.ss",
    "redoble":  "c...s.s.s.ssssss",
    "golpe":    "c...............",
    "nada":     "................",
}

TEMAS = {
    # --- Nivel 1: LA SELVA. La menor, heroico y empujado. ------------------------------------
    "nivel1": {
        "tempo": 152, "bajo": "octavas", "arpegio": [0, 1, 2, 1, 0, 1, 2, 1, 0, 1, 2, 1, 0, 1, 2, 1],
        "orden": ["A", "B"],
        "secciones": {
            "A": {
                "acordes": ["Am", "Am", "F", "G", "Am", "Am", "F G", "E"],
                "melodia": ["A4:2 A4:1 C5:1 E5:2 A5:4 G5:2 E5:2 r:2",
                            "D5:2 E5:2 C5:2 A4:6 r:4",
                            "F4:2 A4:2 C5:2 F5:4 E5:2 D5:2 C5:2",
                            "D5:6 B4:2 G4:4 r:4",
                            "A4:2 A4:1 C5:1 E5:2 A5:4 B5:2 C6:2 r:2",
                            "B5:2 A5:2 G5:2 E5:6 r:4",
                            "F5:4 E5:2 D5:2 D5:4 C5:2 B4:2",
                            "G#4:4 B4:4 E5:8"],
                "bateria": ["entrada", "rock", "rock", "rock_b", "rock", "rock", "rock_b", "relleno"],
            },
            "B": {
                "acordes": ["F", "G", "C", "Am", "F", "G", "E", "E"],
                "melodia": ["C6:4 A5:2 F5:2 C6:3 D6:1 C6:4",
                            "B5:4 G5:2 D5:2 B5:4 A5:4",
                            "G5:6 E5:2 C5:4 E5:2 G5:2",
                            "A5:12 r:4",
                            "A5:2 C6:2 A5:2 F5:2 C5:2 F5:2 A5:4",
                            "B5:2 D6:2 B5:2 G5:2 D5:2 G5:2 B5:4",
                            "G#5:4 E5:4 B5:4 G#5:4",
                            "E6:6 D6:2 B5:4 G#5:4"],
                "bateria": ["entrada", "rock", "rock", "rock_b", "rock", "rock", "rock_b", "relleno"],
            },
        },
    },
    # --- Nivel 2: LA CIUDAD. Re menor (dórico), nocturno y con bajo sincopado. ---------------
    "nivel2": {
        "tempo": 128, "bajo": None, "arpegio": [0, None, 2, None, 1, None, 2, 0, None, 2, None, 1, 0, None, 2, None],
        "orden": ["A", "B"],
        "secciones": {
            "A": {
                "acordes": ["Dm7", "Dm7", "G", "G", "Dm7", "Dm7", "Bb", "A"],
                "melodia": ["r:2 A4:2 C5:2 D5:3 F5:3 E5:2 D5:2",
                            "C5:2 D5:6 r:4 A4:2 C5:2",
                            "B4:2 D5:2 G5:3 F5:3 D5:2 B4:4",
                            "C5:2 B4:2 G4:8 r:4",
                            "r:2 A4:2 C5:2 D5:3 F5:3 A5:4",
                            "G5:2 F5:2 E5:2 F5:2 D5:8",
                            "D5:4 F5:4 Bb5:4 A5:2 F5:2",
                            "E5:4 C#5:4 A4:4 r:4"],
                "bajo": ["D2:3 D2:1 r:2 D3:2 r:2 C3:2 A2:2 F2:2",
                         "D2:3 D2:1 r:2 D3:2 r:2 C3:2 A2:2 C3:2",
                         "G2:3 G2:1 r:2 G3:2 r:2 F3:2 D3:2 B2:2",
                         "G2:3 G2:1 r:2 G3:2 r:2 F3:2 D3:2 F3:2",
                         "D2:3 D2:1 r:2 D3:2 r:2 C3:2 A2:2 F2:2",
                         "D2:3 D2:1 r:2 D3:2 r:2 C3:2 A2:2 C3:2",
                         "A#2:3 A#2:1 r:2 A#3:2 r:2 A3:2 F3:2 D3:2",
                         "A2:3 A2:1 r:2 A3:2 r:2 G3:2 E3:2 C#3:2"],
                "bateria": ["funk", "funk", "funk", "funk_b", "funk", "funk", "funk", "funk_b"],
            },
            "B": {
                "acordes": ["Gm", "A", "Dm", "Bb", "Gm", "A", "Dm", "A"],
                "melodia": ["A#5:4 A5:2 G5:2 D5:4 G5:4",
                            "A5:6 G5:2 E5:4 C#5:4",
                            "F5:4 E5:2 D5:2 A4:4 D5:4",
                            "F5:6 D5:2 A#4:8",
                            "A#5:2 C6:2 D6:4 C6:2 A#5:2 G5:4",
                            "A5:2 A#5:2 C#6:4 A5:2 G5:2 E5:4",
                            "D6:8 A5:4 F5:4",
                            "E5:2 F5:2 G5:2 A5:2 C#6:8"],
                "bajo": ["G2:3 G2:1 r:2 G3:2 r:2 F3:2 D3:2 A#2:2",
                         "A2:3 A2:1 r:2 A3:2 r:2 G3:2 E3:2 C#3:2",
                         "D2:3 D2:1 r:2 D3:2 r:2 C3:2 A2:2 F2:2",
                         "A#2:3 A#2:1 r:2 A#3:2 r:2 A3:2 F3:2 D3:2",
                         "G2:3 G2:1 r:2 G3:2 r:2 F3:2 D3:2 A#2:2",
                         "A2:3 A2:1 r:2 A3:2 r:2 G3:2 E3:2 C#3:2",
                         "D2:3 D2:1 r:2 D3:2 r:2 C3:2 A2:2 F2:2",
                         "A2:2 A2:2 A3:2 A2:2 E3:2 A2:2 C#3:2 E3:2"],
                "bateria": ["funk", "funk_b", "funk", "funk_b", "funk", "funk_b", "funk", "relleno"],
            },
        },
    },
    # --- Nivel 3: LA FRONTERA. Mi frigio, a galope, con trompeta de western. ------------------
    "nivel3": {
        "tempo": 144, "bajo": "galope", "arpegio": [0, 2, 1, 2, 0, 2, 1, 2, 0, 2, 1, 2, 0, 2, 1, 2],
        "orden": ["A", "B"],
        "secciones": {
            "A": {
                "acordes": ["Em", "F", "Em", "F", "Am", "G", "F", "E"],
                "melodia": ["E5:6 B4:2 E5:2 F5:2 G5:4",
                            "A5:6 G5:2 F5:4 E5:4",
                            "G5:4 F5:2 E5:2 B4:8",
                            "C5:2 B4:2 A4:2 B4:2 C5:8",
                            "A5:6 C6:2 B5:4 A5:4",
                            "G5:6 B5:2 A5:4 G5:4",
                            "F5:4 E5:4 D5:4 C5:4",
                            "B4:4 G#4:4 E4:8"],
                "bateria": ["galope_b", "galope", "galope", "galope", "galope", "galope", "galope", "relleno"],
            },
            "B": {
                "acordes": ["Am", "Am", "Em", "Em", "F", "G", "E", "E"],
                "melodia": ["A4:2 A4:1 A4:1 C5:2 E5:2 A5:8",
                            "G5:2 A5:2 G5:2 E5:2 C5:8",
                            "E5:2 E5:1 E5:1 G5:2 B5:2 E6:8",
                            "D6:2 E6:2 D6:2 B5:2 G5:8",
                            "A5:4 C6:4 F6:8",
                            "D6:4 B5:4 G5:8",
                            "G#5:4 B5:4 E6:4 D6:2 B5:2",
                            "G#5:2 F5:2 E5:12"],
                "bateria": ["galope_b", "galope", "galope", "galope", "galope", "galope", "galope", "relleno"],
            },
        },
    },
    # --- Jefe: Mi menor, rápido, con bajo en semicorcheas y caja doble. ------------------------
    "jefe": {
        "tempo": 168, "bajo": "metralla", "arpegio": [0, 1, 2, 1, 0, 1, 2, 1, 0, 1, 2, 1, 0, 1, 2, 1],
        "orden": ["A", "B"],
        "secciones": {
            "A": {
                "acordes": ["Em", "Em", "C", "B", "Em", "Em", "C D", "B"],
                "melodia": ["E5:2 r:1 E5:1 G5:2 r:2 F#5:2 E5:2 D#5:2 E5:2",
                            "B5:4 A5:2 G5:2 F#5:4 D#5:4",
                            "E5:2 r:1 E5:1 G5:2 r:2 C6:4 B5:4",
                            "D#6:6 C6:2 B5:4 F#5:4",
                            "E6:2 r:1 E6:1 D6:2 r:2 B5:2 G5:2 A5:2 B5:2",
                            "G5:2 F#5:2 E5:2 F#5:2 G5:4 A5:4",
                            "G5:4 E5:4 F#5:4 A5:4",
                            "B5:8 D#6:4 F#6:4"],
                "bateria": ["entrada", "jefe", "jefe", "jefe", "jefe", "jefe", "jefe", "jefe_b"],
            },
            "B": {
                "acordes": ["Am", "Am", "Em", "Em", "C", "D", "B", "B"],
                "melodia": ["A5:8 C6:4 B5:4",
                            "A5:4 E5:4 A4:8",
                            "G5:8 B5:4 A5:4",
                            "G5:4 E5:4 B4:8",
                            "C6:8 E6:4 D6:4",
                            "D6:8 F#6:4 E6:4",
                            "D#6:4 B5:4 F#5:4 D#5:4",
                            "B4:2 D#5:2 F#5:2 B5:2 D#6:8"],
                "bateria": ["entrada", "jefe", "jefe", "jefe", "jefe", "jefe", "jefe", "jefe_b"],
            },
        },
    },
    # --- Decisión: Re menor, lento, con latido. Casi sin melodía: el jugador piensa. ----------
    "decision": {
        "tempo": 84, "bajo": "latido", "arpegio": [0, None, None, 1, None, None, 2, None, 0, None, None, 1, None, None, 2, None],
        "onda_arpegio": 0.125,
        "orden": ["A"],
        "secciones": {
            "A": {
                "acordes": ["Dm", "Dm", "A#", "A", "Dm", "Dm", "Gm", "A"],
                "melodia": ["r:8 A5:8", "r:8 A#5:8", "r:8 F5:8", "E5:8 C#5:8",
                            "r:8 D6:8", "r:8 C6:4 A#5:4", "r:8 A#5:8", "A5:8 C#6:8"],
                "bateria": ["latido"] * 8,
            },
        },
    },
    # --- Noticias: Fa mayor, cortina de noticiero. ----------------------------------------------
    "noticias": {
        "tempo": 120, "bajo": "marcha", "arpegio": [0, 1, 2, 1, 0, 1, 2, 1, 0, 1, 2, 1, 0, 1, 2, 1],
        "orden": ["A"],
        "secciones": {
            "A": {
                "acordes": ["F", "Dm", "A#", "C", "F", "Dm", "Gm C", "F"],
                "melodia": ["C5:2 F5:2 A5:4 G5:2 F5:2 C5:4",
                            "D5:2 F5:2 A5:4 D6:4 C6:4",
                            "A#5:4 A5:2 G5:2 F5:4 D5:4",
                            "E5:2 F5:2 G5:4 C5:8",
                            "C5:2 F5:2 A5:4 C6:4 A5:4",
                            "D6:4 C6:2 A5:2 F5:8",
                            "G5:4 A#5:4 C6:2 A#5:2 A5:2 G5:2",
                            "F5:8 r:8"],
                "bateria": ["pop_b", "pop", "pop", "pop", "pop", "pop", "pop", "relleno"],
            },
        },
    },
    # --- Final: Do mayor, himno de cierre (triunfal y un poco melancólico). --------------------
    "final": {
        "tempo": 96, "bajo": "marcha", "arpegio": [0, 2, 1, 2, 0, 2, 1, 2, 0, 2, 1, 2, 0, 2, 1, 2],
        "orden": ["A", "B"],
        "secciones": {
            "A": {
                "acordes": ["C", "Em", "F", "G", "Am", "F", "G", "C"],
                "melodia": ["E5:4 G5:4 C6:6 B5:2",
                            "B5:4 G5:4 E5:8",
                            "A5:4 C6:4 F6:4 E6:2 D6:2",
                            "D6:8 B5:4 G5:4",
                            "C6:4 B5:2 A5:2 E5:4 A5:4",
                            "A5:4 G5:2 F5:2 C5:4 F5:4",
                            "G5:4 A5:2 B5:2 D6:4 B5:4",
                            "C6:12 r:4"],
                "bateria": ["golpe", "medio", "medio", "medio", "medio", "medio", "medio", "marcha"],
            },
            "B": {
                "acordes": ["F", "G", "Em", "Am", "F", "G", "C", "C"],
                "melodia": ["A5:6 G5:2 F5:4 A5:4",
                            "B5:6 A5:2 G5:4 B5:4",
                            "G5:4 B5:4 E6:6 D6:2",
                            "C6:8 A5:8",
                            "F6:4 E6:2 D6:2 C6:4 A5:4",
                            "D6:4 C6:2 B5:2 G5:4 D6:4",
                            "E6:8 D6:4 C6:4",
                            "C6:16"],
                "bateria": ["golpe", "medio", "medio", "medio", "medio", "medio", "marcha", "redoble"],
            },
        },
    },
}

# El menú toca el himno (audio/himno_datos.py). Si faltara, suena una marcha con el material
# del final, más rápida.
TEMAS["menu"] = dict(TEMAS["final"], tempo=116)

# Fanfarrias cortas que NO se repiten
JINGLES = {
    "victoria": {                       # cabe en los 3 s entre el jefe derrotado y la decisión
        "tempo": 170, "bajo": "marcha", "arpegio": [0, 1, 2, 1] * 4, "orden": ["A"], "cola": 0.4,
        "secciones": {"A": {
            "acordes": ["C", "G# C"],
            "melodia": ["G4:2 C5:2 E5:2 G5:6 E5:2 G5:2",
                        "G#5:3 A#5:3 C6:10"],
            "bateria": ["redoble", "marcha"],
        }},
    },
    "game_over": {
        "tempo": 92, "bajo": "latido", "arpegio": [0, None, 1, None, 2, None, 1, None] * 2, "orden": ["A"],
        "secciones": {"A": {
            "acordes": ["Am", "Dm E", "Am"],
            "melodia": ["E5:4 D#5:4 D5:4 C#5:4", "C5:4 F5:4 B4:4 G#4:4", "A4:16"],
            "bateria": ["golpe", "nada", "golpe"],
        }},
    },
}
