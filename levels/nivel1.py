"""NIVEL 1 - LA SELVA. Nivel de aprendizaje: pocos sicarios, bien espaciados.

Coordenadas en píxeles del mundo. El suelo normal está en y=192 (la pantalla mide 224).
La última pantalla (largo - 256) es la arena cerrada del jefe.
"""

SUELO = 192

NIVEL = {
    "numero": 1,
    "nombre": "LA SELVA",
    "largo": 2816,
    "jefe": 1,

    # Tramos de suelo [x_inicio, x_fin, altura]. Los huecos entre tramos son precipicios.
    "suelo": [
        [0, 520, SUELO],
        [560, 900, SUELO],
        [900, 1080, 176],          # loma: hay que saltar para subir
        [1080, 1180, SUELO],
        [1224, 1680, SUELO],
        [1740, 2180, SUELO],
        [2180, 2250, 176],
        [2250, 2816, SUELO],       # incluye la arena del jefe (2560-2816)
    ],
    # Bloques sólidos [x, y, ancho, alto]
    "bloques": [
        [1480, 176, 16, 16],
        [1980, 176, 16, 16],
    ],
    # Plataformas de una vía [x, y, ancho]
    "plataformas": [
        [300, 150, 48],
        [610, 148, 64],
        [690, 118, 48],             # escalón desde la plataforma de 610
        [1010, 132, 48],
        [1300, 150, 64],
        [1380, 116, 48],            # escalón desde la de 1300 (tiene la vida extra)
        [1676, 160, 68],           # puente sobre el precipicio
        [1900, 148, 64],
        [1990, 136, 48],
    ],

    # Sicarios rasos. "x": aparecen cuando el borde derecho de la cámara llega a x.
    # "lado": "izquierda" -> entran por detrás. "y": altura de los pies (sobre una plataforma).
    "enemigos": [
        {"x": 330},
        {"x": 470},
        {"x": 640, "y": 148},
        {"x": 800},
        {"x": 860},
        {"x": 1040, "y": 132},
        {"x": 1150},
        {"x": 1150, "lado": "izquierda"},
        {"x": 1330, "y": 150},
        {"x": 1400},
        {"x": 1560},
        {"x": 1620},
        {"x": 1800},
        {"x": 1930, "y": 148},
        {"x": 2000, "lado": "izquierda"},
        {"x": 2100},
        {"x": 2300},
        {"x": 2380},
        {"x": 2440, "lado": "izquierda"},
    ],

    "powerups": [
        {"x": 636, "y": 128, "tipo": "triple"},
        {"x": 1398, "y": 96, "tipo": "vida"},
    ],

    # Refuerzos y suministros ALEATORIOS (core/director.py). Rangos (mínimo, máximo): el azar
    # decide cuántos salen y dónde. "desde": x mínima de aparición. "detras": probabilidad de que
    # una moto entre por la espalda, pero nunca antes de "detras_desde" (unos 15 s de juego).
    # "fijos": suministros garantizados (a mitad de nivel), además de los que caen al azar.
    "aleatorio": {
        "dron": (2, 3), "moto": (1, 2), "camioneta": (0, 0), "vida_camioneta": 6,
        "suministro": (2, 3), "desde": 760, "detras": 0.0, "detras_desde": 0,
        "fijos": [],
    },

    # Mensajes del tutorial contextual: aparecen cuando el jugador pasa por x.
    "tutorial": [
        [0, "FLECHAS: MOVERTE   Z: SALTAR"],
        [120, "X: DISPARAR. APUNTA CON LAS FLECHAS"],
        [260, "MANTÉN X PARA DISPARO CONTINUO"],
        [440, "¡SALTA EL PRECIPICIO!"],
        [580, "SUBE A LA PLATAFORMA: HAY UN POWER-UP"],
        [820, "ABAJO: AGÁCHATE Y LAS BALAS PASAN"],
        [1620, "ABAJO + Z: BAJAR DE UNA PLATAFORMA"],
        [2420, "¡EL JEFE TE ESPERA ADELANTE!"],
    ],

    # Ambientación (solo para el dibujo). Capas de parallax de la más lejana a la más cercana.
    "ambiente": {
        "cielo": [(40, 120, 176), (150, 210, 200)],
        "capas": [
            {"tipo": "montanas", "color": (60, 110, 120), "factor": 0.15, "base": 150, "alto": 60},
            {"tipo": "colinas", "color": (30, 100, 60), "factor": 0.35, "base": 170, "alto": 40},
            {"tipo": "arboles", "color": (16, 70, 36), "factor": 0.6, "base": 196, "alto": 70},
            {"tipo": "lianas", "color": (24, 90, 44), "factor": 0.8, "base": 24, "alto": 50},
        ],
        "decoracion": {
            "nubes": {"color": (235, 245, 245), "y": 30, "velocidad": 6},
            "animales": "aves",
            "particulas": "luciernagas",
            "adornos": ["pasto", "flor", "helecho", "pasto"],
        },
        "suelo_borde": (60, 170, 40),
        "suelo": (110, 70, 30),
        "suelo_detalle": (80, 50, 20),
        "plataforma": (140, 90, 40),
    },
}
