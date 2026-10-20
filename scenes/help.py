"""Pantalla de AYUDA: varias páginas navegables con IZQUIERDA/DERECHA."""
from __future__ import annotations

import pygame

import input_manager as im
import settings
from render.texto import dibujar_parrafo, dibujar_texto
from render.ui import dibujar_marco, oscurecer
from scenes.base import Scene

C = settings.COLORES

PAGINAS = [
    ("OBJETIVO",
     "Eres el Presidente A. Milagro. Persigue a los jefes criminales a través de "
     "3 niveles: selva, ciudad y frontera.\n\n"
     "Al vencer a cada jefe decides su destino. El país entero opinará sobre lo que hagas."),
    ("CONTROLES",
     "Mover: flechas / cruceta\n"
     "Saltar: Z / botón A\n"
     "Disparar: X / botón B (apunta en 8 direcciones con la cruceta)\n"
     "Agacharse: abajo\n"
     "Pausa: Enter o Esc / START\n"
     "Ayuda: F1 / SELECT\n\n"
     "Puedes remapear el control en Opciones."),
    ("DECISIONES",
     "CAPTURAR: juicio en el país. Gusta al pueblo, los medios lo vigilan.\n\n"
     "EXTRADITAR: lo envías al extranjero. Agrada a los medios, divide al pueblo.\n\n"
     "DEJAR LIBRE: evitas un conflicto... pero la opinión suele caer, y repetirlo sale caro."),
    ("OPINIÓN POPULAR",
     "Tres indicadores de 0 a 100 en el HUD:\n"
     "MEDIOS - lo que dicen los noticieros.\n"
     "INFLUENCERS - el humor de las redes.\n"
     "PUEBLO - lo que piensa la gente común.\n\n"
     "Empiezan en 50. Las mueven tus decisiones, las rutas largas y revocar."),
    ("CÓMO SE GANA",
     "Supera los 3 niveles sin perder tus 3 vidas. Recoge armas y suministros para resistir.\n\n"
     "El final depende del camino de decisiones y de la opinión final: "
     "hay 5 finales distintos. ¡Prueba todos!"),
    ("ARMAS Y REFUERZOS",
     "Cada partida es distinta: los refuerzos y los suministros aparecen al azar.\n"
     "ESCOPETA: disparo triple. SUBFUSIL: disparo rápido. MEDALLA: una vida. "
     "Caen en paracaídas; pierdes el arma al morir.\n"
     "DRON: dispárale hacia arriba. MOTO: sáltala o agáchate ante sus balas. "
     "CAMIONETA BLINDADA: hay que destruirla."),
    ("TIEMPO LÍMITE",
     "Decidir el destino del jefe tiene un reloj de 15 segundos. Si dudas, el jefe ESCAPA "
     "y cuenta como dejarlo libre.\n\n"
     "REVOCAR: justo después de decidir, con X / B puedes arrepentirte una vez por partida. "
     "La decisión se borra y eliges de nuevo, pero dudar te cuesta opinión."),
    ("EL MAPA DEL PAÍS",
     "Antes de cada nivel ves el mapa: zonas unidas por vías. El número de cada tramo "
     "es su peligro. Con izquierda/derecha eliges la ruta:\n"
     "SEGURA: menos peligro, pero más tramos; llegas tarde y el pueblo lo nota.\n"
     "CORTA: menos tramos, pero más peligro: llegan más refuerzos enemigos.\n"
     "Capturar o extraditar calma la zona; liberar la empeora."),
    ("EL TELÉFONO",
     "Entre niveles lees las noticias sobre tu decisión.\n\n"
     "Arriba/abajo: desplazar el feed y leer a tu ritmo.\n"
     "Enter / A: seguir al próximo nivel."),
    ("PANTALLA FINAL",
     "Izquierda/derecha: cambiar de página (resultado, árbol, finales, grafos).\n\n"
     "En el árbol, arriba/abajo anima los recorridos: ruta elegida, preorden, BFS y "
     "camino de la hoja a la raíz."),
    ("ACCESIBILIDAD",
     "En Opciones:\n"
     "ALTO CONTRASTE: oscurece el fondo y resalta personajes y balas.\n"
     "DALTONISMO: corrige los colores (protanopia, deuteranopia, tritanopia).\n"
     "Volumen de música y efectos.\n"
     "Configurar control: elige qué botón hace cada acción."),
    ("LOGROS",
     "Hay 11 logros: tu primera captura, superar un nivel sin perder vidas, vencer a un "
     "jefe sin recibir daño, descubrir los 5 finales...\n\n"
     "Míralos en el menú, opción LOGROS."),
]


class HelpScene(Scene):
    def __init__(self, juego, **datos):
        super().__init__(juego, **datos)
        self.pagina = 0
        # Si se abrió desde la pausa, se dibuja encima del nivel congelado.
        self.transparente = bool(datos.get("superpuesta"))

    def update(self, dt, acciones):
        entrada = acciones[settings.JUGADOR_LOCAL]
        if entrada.pulso(im.DERECHA):
            self.pagina = min(self.pagina + 1, len(PAGINAS) - 1)
        if entrada.pulso(im.IZQUIERDA):
            self.pagina = max(self.pagina - 1, 0)
        if entrada.pulso(im.CANCELAR) or entrada.pulso(im.AYUDA) or entrada.pulso(im.CONFIRMAR):
            if self.transparente:
                self.juego.escenas.desapilar()
            else:
                self.juego.escenas.cambiar("menu")

    def draw(self, sup):
        if self.transparente:
            oscurecer(sup)
        else:
            sup.fill((8, 8, 32))
        marco = pygame.Rect(12, 12, 232, 200)
        dibujar_marco(sup, marco)
        titulo, texto = PAGINAS[self.pagina]
        dibujar_texto(sup, titulo, (128, 20), C["amarillo"], 2, centrado=True)
        dibujar_parrafo(sup, texto, (24, 42), 208, C["blanco"], 1)
        dibujar_texto(sup, f"< {self.pagina + 1}/{len(PAGINAS)} >   Enter/Esc: volver",
                      (128, 196), C["gris"], 1, centrado=True)
