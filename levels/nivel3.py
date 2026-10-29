"""NIVEL 3 - LA FRONTERA. El más difícil: muchos sicarios, más apariciones por detrás,
más precipicios (río y quebradas) y tiradores sobre las rocas.

Coordenadas en píxeles del mundo. El suelo normal está en y=192 (la pantalla mide 224).
La última pantalla (largo - 256) es la arena cerrada del jefe (La Sombra de la Raya).
"""

SUELO = 192

NIVEL = {
    "numero": 3,
    "nombre": "LA GUAJIRA",
    "largo": 3328,
    "jefe": 3,

    # Tramos de tierra [x_inicio, x_fin, altura]. Los huecos son el río y las quebradas.
    "suelo": [
        [0, 420, SUELO],
        [464, 760, SUELO],
        [760, 900, 176],
        [900, 1000, 160],          # loma rocosa
        [1000, 1180, SUELO],
        [1224, 1480, SUELO],
        [1524, 1900, SUELO],
        [1900, 2050, 168],
        [2094, 2400, SUELO],
        [2444, 2700, SUELO],
        [2700, 2820, 172],
        [2820, 3328, SUELO],       # incluye la arena del jefe (3072-3328)
    ],
    # Rocas [x, y, ancho, alto]
    "bloques": [
        [600, 176, 24, 16],
        [1350, 176, 24, 16],
        [2200, 176, 24, 16],
        [2950, 176, 24, 16],
    ],
    # Salientes de roca y puentes de tablas [x, y, ancho]
    "plataformas": [
        [300, 148, 48],
        [520, 140, 64],
        [600, 116, 48],
        [930, 116, 48],
        [1100, 148, 48],
        [1300, 140, 64],
        [1460, 150, 80],           # puente sobre la quebrada
        [1700, 148, 48],
        [1764, 120, 48],
        [1960, 124, 48],
        [2150, 148, 64],
        [2230, 120, 48],
        [2500, 148, 48],
        [2564, 120, 48],
        [2760, 128, 64],
        [2900, 148, 64],
    ],

    # Sicarios rasos: los mismos de siempre, pero muchos más y desde todos lados.
    "enemigos": [
        {"x": 280},
        {"x": 320, "y": 148},
        {"x": 360},
        {"x": 400, "lado": "izquierda"},
        {"x": 540, "y": 140},
        {"x": 580},
        {"x": 620},
        {"x": 620, "y": 116},
        {"x": 700, "lado": "izquierda"},
        {"x": 820},
        {"x": 950, "y": 116},
        {"x": 980},
        {"x": 1050},
        {"x": 1110, "y": 148},
        {"x": 1150, "lado": "izquierda"},
        {"x": 1280},
        {"x": 1320, "y": 140},
        {"x": 1420},
        {"x": 1480, "y": 150},
        {"x": 1560},
        {"x": 1600, "lado": "izquierda"},
        {"x": 1720, "y": 148},
        {"x": 1760},
        {"x": 1780, "y": 120},
        {"x": 1870},
        {"x": 1970, "y": 124},
        {"x": 2000, "lado": "izquierda"},
        {"x": 2120},
        {"x": 2170, "y": 148},
        {"x": 2240},
        {"x": 2250, "y": 120},
        {"x": 2350, "lado": "izquierda"},
        {"x": 2480},
        {"x": 2510, "y": 148},
        {"x": 2560},
        {"x": 2580, "y": 120},
        {"x": 2660, "lado": "izquierda"},
        {"x": 2780, "y": 128},
        {"x": 2860},
        {"x": 2920, "y": 148},
        {"x": 2980},
        {"x": 3000, "lado": "izquierda"},
    ],

    "powerups": [
        {"x": 546, "y": 120, "tipo": "triple"},
        {"x": 1716, "y": 128, "tipo": "triple"},
        {"x": 2246, "y": 100, "tipo": "vida"},
    ],

    # Refuerzos y suministros ALEATORIOS (core/director.py). Rangos (mínimo, máximo): el azar
    # decide cuántos salen y dónde. "desde": x mínima de aparición. "detras": probabilidad de que
    # una moto entre por la espalda, pero nunca antes de "detras_desde" (unos 15 s de juego).
    # "fijos": suministros garantizados (a mitad de nivel), además de los que caen al azar.
    "aleatorio": {
        "dron": (4, 5), "moto": (3, 4), "camioneta": (1, 2), "vida_camioneta": 8,
        "suministro": (2, 3), "desde": 360, "detras": 0.4, "detras_desde": 1100,
        "fijos": [{"x": 1400, "clase": "vida"}, {"x": 1750, "clase": "rapida"}],
    },

    "tutorial": [],

    "ambiente": {
        "paisaje": "guajira",                                    # render/paisajes.py
        "cielo": [(46, 150, 214), (255, 236, 160)],
        "estilo": "desierto",                                    # cómo se pinta el suelo
        "estratos": [(244, 196, 96), (222, 164, 76), (236, 182, 88)],   # arena amarilla en capas
        "decoracion": {
            "calor": True,
            "particulas": "rodadoras",
            "adornos": ["roca", "cactus_chico", "roca", "craneo"],
        },
        "suelo_borde": (252, 220, 132),                          # arena
        "suelo": (232, 180, 90),
        "suelo_detalle": (200, 148, 70),
        "plataforma": (156, 112, 66),                            # tablas / roca
    },
}
