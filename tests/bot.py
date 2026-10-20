"""Bot sencillo para pruebas: corre a la derecha disparando y salta huecos y paredes."""
import input_manager as im


class Bot:
    def __init__(self):
        self.saltando = 0

    def acciones(self, estado, jugador, direccion=1):
        m = {im.DISPARAR, im.DERECHA if direccion > 0 else im.IZQUIERDA}
        pulsadas = set()
        g = estado.geometria
        adelante = jugador.x + (jugador.ancho + 10 if direccion > 0 else -10)
        suelo_adelante = g.altura_suelo(adelante)
        if jugador.en_suelo and self.saltando == 0 and (
                suelo_adelante > jugador.pie + 1 or suelo_adelante < jugador.pie - 1 or jugador.choco_pared):
            pulsadas.add(im.SALTAR)
            self.saltando = 24
        if self.saltando > 0:
            m.add(im.SALTAR)
            self.saltando -= 1
        return {jugador.id_jugador: im.EstadoAcciones(frozenset(m), frozenset(pulsadas))}
