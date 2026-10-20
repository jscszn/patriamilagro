"""Himno Nacional de Colombia: introducción y coro, escritos a mano nota por nota.

Música de Oreste Síndici (1887), de dominio público. La melodía se cotejó con una partitura
publicada para flauta (flutetunes.com, tune 742) y el bajo con la grabación orquestal de
assets/sonidos_raw/.

Está escrito en DO MAYOR para que se lea fácil; TRANSPORTE lo lleva a Mi bemol mayor (la
tonalidad original), una octava más abajo que la flauta.

Cada compás (4 pulsos) es una cadena de notas "NOTA@inicio+duración", en pulsos:
    "C5@0+1.5"  = Do de la 5.ª octava, empieza en el pulso 0 y dura un pulso y medio.
El bajo es la fundamental del acorde en cada mitad del compás: "C G" = Do dos pulsos, Sol dos.
"""

TEMPO = 108            # pulsos (negras) por minuto
TRANSPORTE = -9        # semitonos: Do mayor -> Mi bemol mayor, octava de abajo

MELODIA = [
    # --- Introducción (fanfarria) ---
    "C5@0+1.5 C5@1.5+0.25 C5@1.75+0.25 C5@2+0.25 G4@2.5+0.25 C5@3+0.25 E5@3.5+0.25",
    "G5@0+2 E5@2+1",
    "G5@0+0.25 G5@0.5+0.25 G5@0.75+0.25 G5@1+0.25 G5@1.5+0.25 G5@2+0.25 G5@2.5+0.25 A5@3+0.25 G5@3.5+0.25",
    "F5@0+0.25 D6@0.5+0.25 D6@0.75+0.25 D6@1+0.25 D6@1.5+0.25 D6@2+1",
    "D5@0+1.5 D5@1.5+0.25 D5@1.75+0.25 D5@2+0.25 A4@2.5+0.25 D5@3+0.25 F5@3.5+0.25",
    "A5@0+2 F5@2+1",
    "E5@0+0.25 E5@0.5+0.25 E5@0.75+0.25 F5@1+0.25 E5@1.5+0.25 D5@2+0.25 D5@2.5+0.25 D5@2.75+0.25 E5@3+0.25 D5@3.5+0.25",
    "C5@0+1 C6@1+0.5 C6@2+0.5 E5@3+0.75 F5@3.75+0.25",          # ...y la anacrusa: "¡Oh..."
    # --- Coro: "¡Oh gloria inmarcesible! ¡Oh júbilo inmortal!" ---
    "G5@0+1 G5@1+1 A5@2+1 G5@3+0.75 F#5@3.75+0.25",
    "G5@0+2 E5@2+1 C5@3+0.75 D5@3.75+0.25",
    "E5@0+1 G5@1+1 F5@2+1 D5@3+1",
    "C5@0+2 E5@3+0.75 F5@3.75+0.25",
    # --- "¡En surcos de dolores el bien germina ya!" ---
    "G5@0+1 G5@1+1 A5@2+1 G5@3+0.75 F#5@3.75+0.25",
    "G5@0+2 E5@2+1 G5@3+1",
    "G5@0+1 F#5@1+0.75 G5@1.75+0.25 A5@2+1 G5@3+0.75 A5@3.75+0.25",
    "B5@0+3 B5@3+0.75 A5@3.75+0.25",
    "A5@0+1 G5@1+0.75 F5@1.75+0.25 F5@2+1 E5@3+0.75 D5@3.75+0.25",
    "C5@0+1 C6@1+0.5 C6@2+0.5",
    # --- Repetición con más fuerza ---
    "C6@0+1 C6@1+1.5 C6@2.5+0.5 B5@3+0.5 A5@3.5+0.5",
    "B5@0+2 E5@2+1",
    "A5@0+1 A5@1+1.5 A5@2.5+0.5 G5@3+0.5 F5@3.5+0.5",
    "G5@0+2 E5@3+0.75 D5@3.75+0.25",
    "C5@0+1 G5@1+0.75 F5@1.75+0.25 E5@2+1 C6@3+0.75 B5@3.75+0.25",
    "B5@0+1 A5@1+2 B5@3+0.75 C6@3.75+0.25",
    "E5@0+1 A5@1+0.75 G5@1.75+0.25 D5@2+1 F5@3+0.75 E5@3.75+0.25",
    "C5@0+1 C6@1+0.5 C6@2+0.5",
]

BAJO = [
    "C C", "C C", "A A", "D D", "D D", "D D", "G G", "C C",          # introducción
    "C C", "C C", "C G", "C C",                                      # ¡Oh gloria...!
    "C C", "C C", "B B", "E E", "G G", "C C",                        # ¡En surcos...!
    "A A", "B E", "F F", "G G", "C C", "F G", "G G", "C C",          # repetición
]
