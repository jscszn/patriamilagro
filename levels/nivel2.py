"""NIVEL 2 - LA CIUDAD. Más sicarios que en la selva, en grupos y desde balcones.

Coordenadas en píxeles del mundo. El suelo normal está en y=192 (la pantalla mide 224).
La última pantalla (largo - 256) es la arena cerrada del jefe (Don Concreto).
"""

SUELO = 192

NIVEL = {
    "numero": 2,
    "nombre": "MEDELLÍN",
    "largo": 3072,
    "jefe": 2,

    # Tramos de calle [x_inicio, x_fin, altura]. Los huecos son excavaciones de obra.
    "suelo": [
        [0, 600, SUELO],
        [640, 980, SUELO],
        [980, 1120, 172],          # plazoleta elevada
        [1120, 1400, SUELO],
        [1444, 1800, SUELO],
        [1800, 1900, 168],         # escaleras de un puente peatonal
        [1900, 2000, 152],
        [2000, 2200, SUELO],
        [2240, 2560, SUELO],
        [2560, 2600, 176],
        [2600, 3072, SUELO],       # incluye la arena del jefe (2816-3072)
    ],
    # Autos estacionados [x, y, ancho, alto]
    "bloques": [
        [420, 176, 32, 16],
        [1250, 176, 32, 16],
        [2350, 176, 32, 16],
    ],
    # Balcones y andamios [x, y, ancho]
    "plataformas": [
        [250, 150, 64],
        [700, 148, 48],
        [770, 118, 48],             # escalón desde el balcón de 700
        [1050, 128, 64],
        [1300, 148, 48],
        [1520, 150, 64],
        [1600, 124, 48],
        [1960, 112, 48],
        [2100, 150, 64],
        [2420, 148, 64],
        [2680, 148, 48],
    ],

    # Sicarios rasos (el mismo enemigo de siempre): aquí son más y llegan en grupos.
    "enemigos": [
        {"x": 290, "y": 150},
        {"x": 330},
        {"x": 380},
        {"x": 520},
        {"x": 560},
        {"x": 560, "lado": "izquierda"},
        {"x": 720, "y": 148},
        {"x": 860},
        {"x": 900},
        {"x": 940},
        {"x": 1080, "y": 128},
        {"x": 1180},
        {"x": 1230},
        {"x": 1300, "lado": "izquierda"},
        {"x": 1320, "y": 148},
        {"x": 1500},
        {"x": 1560, "y": 150},
        {"x": 1620},
        {"x": 1620, "y": 124},
        {"x": 1800, "lado": "izquierda"},
        {"x": 1880},
        {"x": 1970, "y": 112},
        {"x": 2060},
        {"x": 2130, "y": 150},
        {"x": 2250, "lado": "izquierda"},
        {"x": 2300},
        {"x": 2380},
        {"x": 2440, "y": 148},
        {"x": 2520},
        {"x": 2600, "lado": "izquierda"},
        {"x": 2650},
        {"x": 2700, "y": 148},
        {"x": 2760},
    ],

    "powerups": [
        {"x": 786, "y": 98, "tipo": "triple"},
        {"x": 1616, "y": 104, "tipo": "vida"},
    ],

    # Refuerzos y suministros ALEATORIOS (core/director.py). Rangos (mínimo, máximo): el azar
    # decide cuántos salen y dónde. "desde": x mínima de aparición. "detras": probabilidad de que
    # una moto entre por la espalda, pero nunca antes de "detras_desde" (unos 15 s de juego).
    # "fijos": suministros garantizados (a mitad de nivel), además de los que caen al azar.
    "aleatorio": {
        "dron": (3, 4), "moto": (2, 3), "camioneta": (1, 1), "vida_camioneta": 7,
        "suministro": (2, 3), "desde": 420, "detras": 0.25, "detras_desde": 1100,
        "fijos": [{"x": 1500, "clase": "vida"}],
    },

    "tutorial": [],

    "ambiente": {
        "paisaje": "medellin",                                   # render/paisajes.py
        "cielo": [(16, 8, 30), (176, 84, 66)],
        "estilo": "ciudad",                                      # cómo se pinta el suelo
        "decoracion": {
            "lluvia": True,
            "animales": "helicoptero",
            "adornos": ["farol", "hidrante", "basurero", "farol"],
        },
        "suelo_borde": (150, 146, 156),                          # bordillo
        "suelo": (74, 64, 74),                                   # asfalto
        "suelo_detalle": (58, 50, 60),
        "plataforma": (110, 108, 124),                           # andamio metálico
    },
}
