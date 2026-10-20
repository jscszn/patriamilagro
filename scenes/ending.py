"""Pantalla final: el resultado de la partida y el árbol de decisiones recorrido.

Cuatro páginas (IZQUIERDA / DERECHA):
  1. RESULTADO: final obtenido, las 3 decisiones, evolución de la opinión y puntaje.
  2. ÁRBOL: los 40 nodos con la ruta elegida resaltada. ARRIBA / ABAJO cambia el modo para
     animar los recorridos: ruta elegida, preorden, BFS y camino hoja -> raíz.
  3. FINALES: cómo se agrupan las 27 hojas en los 5 finales.
  4. GRAFOS: cómo quedó el mapa del país (pesos de las vías, jefes libres) y las rutas elegidas.
Al llegar aquí (fuera de las pruebas) se guarda la evidencia en capturas/: imagen del árbol
y JSON de la partida.
"""
from __future__ import annotations

import datetime
import json
import os

import pygame

import input_manager as im
import settings
from audio import gestor as audio
from core.decision_tree import FINALES, final_de
from render import arbol_visual as av
from core.mapa import NOMBRE_RUTA
from render.grafo_visual import dibujar_mapa
from render.ui import dibujar_marco
from render.hud import COLORES_OPINION, ETIQUETAS_OPINION
from render.texto import dibujar_parrafo, dibujar_texto
from scenes.base import Scene

C = settings.COLORES
NOMBRES = {"capturar": "CAPTURAR", "extraditar": "EXTRADITAR", "liberar": "DEJAR LIBRE"}
PAGINAS = ("RESULTADO", "ÁRBOL", "FINALES", "GRAFOS")
MODOS = [("ruta", "RUTA ELEGIDA"), ("preorden", "PREORDEN"), ("bfs", "BFS"),
         ("hoja_raiz", "HOJA > RAÍZ")]
PASO_ANIMACION = {"preorden": 0.12, "bfs": 0.12, "hoja_raiz": 0.6}
AREA_ARBOL = pygame.Rect(8, 38, 240, 104)
LIMITE_CONTENIDO = 198       # nada de las páginas baja de aquí: debajo va el pie de navegación
RUTA_CAPTURAS = os.path.join(settings.RUTA_BASE, "capturas")


class EndingScene(Scene):
    def __init__(self, juego, **datos):
        super().__init__(juego, **datos)
        self.partida = juego.partida
        arbol = self.partida.arbol
        self.final = final_de(arbol.actual)
        self.arbol_vis = av.arbol_completo(arbol)     # copia con los 40 nodos; la partida no cambia
        self.ruta = av.ids_ruta(self.arbol_vis)
        self.historial = self._historial_opinion()
        self.conteo_finales = {f.clave: 0 for f in FINALES}
        for hoja in self.arbol_vis.hojas():
            self.conteo_finales[final_de(hoja).clave] += 1
        self.pagina = 0
        self.modo = 0
        self.t_modo = 0.0
        self.tiempo = 0.0
        self.archivo_evidencia = None
        self.modos_vistos = set()
        audio.presentar("bienvenida", "final")        # la frase del presidente y luego la música
        juego.logros.notificar("final", clave=self.final.clave)
        if not juego.headless:                        # las pruebas no deben llenar capturas/
            self.archivo_evidencia = self.guardar_evidencia()

    def _historial_opinion(self):
        """Opinión en la raíz y después de cada decisión (para la gráfica)."""
        nodos, n = [], self.partida.arbol.actual
        while n is not None:
            nodos.append(n.opinion)
            n = n.padre
        return list(reversed(nodos))

    # --- Lógica -------------------------------------------------------------------------------
    @property
    def clave_modo(self) -> str:
        return MODOS[self.modo][0]

    def paso_animacion(self):
        """(nodos ya visitados, nodo actual) del recorrido animado en el modo actual."""
        orden = av.secuencia(self.arbol_vis, self.clave_modo)
        if not orden:
            return [], None
        paso = PASO_ANIMACION[self.clave_modo]
        ciclo = len(orden) + 3                          # pausa de 3 pasos al terminar, y repite
        k = min(int(self.t_modo / paso) % ciclo, len(orden) - 1)
        return orden[:k + 1], orden[k]

    def update(self, dt, acciones):
        self.tiempo += dt
        self.t_modo += dt
        entrada = acciones[settings.JUGADOR_LOCAL]
        if entrada.pulso(im.DERECHA):
            self.pagina = (self.pagina + 1) % len(PAGINAS)
        if entrada.pulso(im.IZQUIERDA):
            self.pagina = (self.pagina - 1) % len(PAGINAS)
        if PAGINAS[self.pagina] == "ÁRBOL":
            self.modos_vistos.add(self.modo)
            if len(self.modos_vistos) == len(MODOS):
                self.juego.logros.notificar("recorridos_vistos")
            if entrada.pulso(im.ABAJO):
                self.modo, self.t_modo = (self.modo + 1) % len(MODOS), 0.0
            if entrada.pulso(im.ARRIBA):
                self.modo, self.t_modo = (self.modo - 1) % len(MODOS), 0.0
        if self.tiempo > 1.5 and (entrada.pulso(im.CONFIRMAR) or entrada.pulso(im.CANCELAR)):
            self.juego.partida = None
            self.juego.escenas.cambiar("menu")

    # --- Evidencia ----------------------------------------------------------------------------
    def guardar_evidencia(self) -> str:
        """capturas/arbol_<fecha>.png (página del árbol x4) y .json (partida y árbol)."""
        os.makedirs(RUTA_CAPTURAS, exist_ok=True)
        base = os.path.join(RUTA_CAPTURAS, "arbol_" + datetime.datetime.now().strftime("%Y%m%d_%H%M%S"))
        lienzo = pygame.Surface((settings.ANCHO, settings.ALTO))
        modo, pagina = self.modo, self.pagina
        self.modo, self.pagina = 0, 1
        self.draw(lienzo)
        self.modo, self.pagina = modo, pagina
        pygame.image.save(pygame.transform.scale_by(lienzo, 4), base + ".png")
        datos = {
            "fecha": datetime.datetime.now().isoformat(timespec="seconds"),
            "camino": self.partida.arbol.camino(),
            "final": self.final.titulo,
            "opinion_final": self.partida.arbol.opinion(),
            "historial_opinion": self.historial,
            "puntaje": self.partida.puntaje,
            "jefes": self.partida.jefes_derrotados,
            "arbol": self.partida.arbol.to_dict(),
            "semilla": self.partida.semilla,
            "mapa": self.partida.mapa.to_dict(con_azar=False),
            "rutas": {str(n): r for n, r in self.partida.rutas.items()},
        }
        with open(base + ".json", "w", encoding="utf-8") as f:
            json.dump(datos, f, indent=2, ensure_ascii=False)
        print(f"[final] Evidencia guardada en {os.path.relpath(base, settings.RUTA_BASE)}.png/.json")
        return base + ".png"

    # --- Dibujo -------------------------------------------------------------------------------
    def draw(self, sup):
        sup.fill((8, 8, 24))
        pagina = PAGINAS[self.pagina]
        {"RESULTADO": self._resultado, "ÁRBOL": self._arbol, "FINALES": self._finales,
         "GRAFOS": self._grafos}[pagina](sup)
        # Pie: navegación, separado del contenido por una línea
        pygame.draw.line(sup, (34, 34, 60), (8, LIMITE_CONTENIDO + 3), (248, LIMITE_CONTENIDO + 3))
        for i in range(len(PAGINAS)):
            color = C["amarillo"] if i == self.pagina else C["gris_oscuro"]
            pygame.draw.rect(sup, color, (112 + i * 12, 206, 8, 3))
        dibujar_texto(sup, "< >", (8, 211), C["gris"], sombra=False)
        dibujar_texto(sup, pagina, (30, 211), C["gris"], sombra=False)
        if self.tiempo > 1.5:
            dibujar_texto(sup, "ENTER: MENÚ", (248, 211), C["blanco"], sombra=False, derecha=True)

    def _resultado(self, sup):
        color = av.COLOR_FINAL[self.final.clave]
        dibujar_texto(sup, "FINAL", (128, 4), C["gris"], centrado=True)
        dibujar_texto(sup, self.final.titulo, (128, 15), color, centrado=True)
        y = dibujar_parrafo(sup, self.final.resumen, (12, 31), 232, C["blanco"], interlineado=2) + 4
        for i, (decision, jefe) in enumerate(zip(self.partida.arbol.camino(), self.partida.jefes_derrotados)):
            dibujar_texto(sup, f"{i + 1}. {NOMBRES[decision]}", (12, y), C["cian"])
            dibujar_texto(sup, jefe, (104, y), C["gris"])
            y += 11
        # Gráfica y opinión final, pegadas abajo (sobre el puntaje) y con aire arriba
        arriba = max(y + 8, 104)
        self._grafica(sup, pygame.Rect(26, arriba + 14, 112, 168 - (arriba + 14)))
        x = 156
        dibujar_texto(sup, "OPINIÓN FINAL", (x, arriba), C["amarillo"])
        for i, clave in enumerate(("medios", "influencers", "pueblo")):
            valor = self.historial[-1][clave]
            yy = arriba + 15 + i * 18
            dibujar_texto(sup, ETIQUETAS_OPINION[clave], (x, yy), COLORES_OPINION[clave])
            dibujar_texto(sup, f"{valor:3d}", (x + 24, yy), C["blanco"])
            pygame.draw.rect(sup, C["gris_oscuro"], (x, yy + 10, 88, 4))
            pygame.draw.rect(sup, COLORES_OPINION[clave], (x, yy + 10, int(88 * valor / 100), 4))
        dibujar_texto(sup, f"PUNTAJE TOTAL {self.partida.puntaje:06d}", (128, 186), C["blanco"], centrado=True)

    def _grafica(self, sup, area: pygame.Rect):
        """Evolución de la opinión: inicio y después de cada nivel (0 a 100)."""
        dibujar_texto(sup, "OPINIÓN POR NIVEL", (area.x - 14, area.y - 12), C["amarillo"])
        pygame.draw.line(sup, C["gris"], area.bottomleft, area.bottomright)
        pygame.draw.line(sup, C["gris"], area.bottomleft, area.topleft)
        y50 = area.y + area.h // 2
        for x in range(area.x, area.right, 4):                        # línea punteada del 50
            sup.set_at((x, y50), C["gris_oscuro"])
        dibujar_texto(sup, "50", (area.x - 14, y50 - 4), C["gris"], sombra=False)
        n = len(self.historial)
        xs = [area.x + area.w * i / max(1, n - 1) for i in range(n)]
        for clave in ("medios", "influencers", "pueblo"):
            puntos = [(x, area.bottom - area.h * op[clave] / 100) for x, op in zip(xs, self.historial)]
            if len(puntos) > 1:
                pygame.draw.lines(sup, COLORES_OPINION[clave], False, puntos, 2)
            for p in puntos:
                pygame.draw.circle(sup, COLORES_OPINION[clave], (int(p[0]), int(p[1])), 2)
        for i, x in enumerate(xs):
            etiqueta = "INI" if i == 0 else f"N{i}"
            dibujar_texto(sup, etiqueta, (int(x) - 8, area.bottom + 3), C["gris"], sombra=False)

    def _arbol(self, sup):
        clave, nombre = MODOS[self.modo]
        dibujar_texto(sup, "ÁRBOL DE DECISIONES", (128, 4), C["amarillo"], centrado=True)
        dibujar_texto(sup, f"MODO: {nombre}", (10, 17), C["cian"])
        dibujar_texto(sup, "ARRIBA/ABAJO: MODO", (248, 17), C["gris"], sombra=False, derecha=True)
        visitados, actual = self.paso_animacion()
        ids_visitados = [id(n) for n in visitados]
        av.dibujar_arbol(sup, self.arbol_vis, AREA_ARBOL, self.ruta, ids_visitados,
                         id(actual) if actual else None, self.tiempo)
        av.dibujar_leyenda(sup, 10, AREA_ARBOL.bottom + 18, self.final.clave)
        # Línea de información según el modo
        if clave == "ruta":
            info = f"RUTA: {av.camino_texto(self.arbol_vis.actual)}  -> {av.NOMBRE_CORTO[self.final.clave]}"
        elif clave == "hoja_raiz":
            subidas = " < ".join(av.camino_texto(n).split(" > ")[-1] for n in visitados)
            info = f"camino(): {subidas}".upper()
            if len(visitados) == len(av.secuencia(self.arbol_vis, clave)):   # terminó: se invierte
                info += "  = " + " ".join(av.LETRA[d] for d in self.arbol_vis.camino())
        else:
            info = f"{len(visitados)}/{len(av.secuencia(self.arbol_vis, clave))}: {av.camino_texto(actual)}"
        dibujar_texto(sup, info, (10, LIMITE_CONTENIDO - 9), C["blanco"], sombra=False)

    def _grafos(self, sup):
        """Cómo dejaron las decisiones al grafo del país y por dónde viajó el presidente."""
        mapa = self.partida.mapa
        dibujar_texto(sup, "GRAFO: EL PAÍS DESPUÉS DE TUS DECISIONES", (128, 4), C["amarillo"], centrado=True)
        area = pygame.Rect(8, 16, 240, 102)
        dibujar_marco(sup, area, fondo=(16, 20, 40))
        dibujar_mapa(sup, mapa, area.inflate(-8, -8), tiempo=self.tiempo)
        dibujar_texto(sup, "NÚMERO = PELIGRO DE LA VÍA", (14, area.bottom - 14), C["gris"], sombra=False)
        dibujar_texto(sup, f"SEMILLA {self.partida.semilla}", (area.right - 6, area.bottom - 14), C["gris"],
                      sombra=False, derecha=True)
        y = area.bottom + 5
        for nivel in sorted(self.partida.rutas):               # la ruta elegida hacia cada nivel
            r = self.partida.rutas[nivel]
            dibujar_texto(sup, f"N{nivel} {NOMBRE_RUTA[r['clave']]}", (10, y), C["cian"])
            dibujar_texto(sup, f"PELIGRO {r['peligro']}  REFUERZOS +{r['refuerzos']}", (246, y), C["blanco"],
                          derecha=True)
            y += 11
        def corto(zona):                                       # "LA CIUDAD" -> "CIUDAD", como en el mapa
            return mapa.nombre(zona).split(" ", 1)[-1] if " " in mapa.nombre(zona) else mapa.nombre(zona)
        libres = ", ".join(corto(z) for z in mapa.jefes_libres) or "NINGUNO"
        retenes = ", ".join(f"{corto(a)}-{corto(b)}" for a, b in mapa.retenes) or "NINGUNO"
        y = dibujar_parrafo(sup, f"LIBRES (X): {libres}.", (10, y + 4), 236, C["naranja"], interlineado=1)
        dibujar_parrafo(sup, f"RETENES AL AZAR (ROJO): {retenes}.", (10, y + 3), 236, C["rojo"], interlineado=1)

    def _finales(self, sup):
        dibujar_texto(sup, "27 HOJAS, 5 FINALES", (128, 4), C["amarillo"], centrado=True)
        dibujar_texto(sup, "EN ORDEN: GANA LA PRIMERA QUE SE CUMPLE", (128, 16), C["gris"], sombra=False, centrado=True)
        y = 31
        for f in FINALES:
            elegido = f.clave == self.final.clave
            pygame.draw.rect(sup, av.COLOR_FINAL[f.clave], (10, y + 2, 7, 7))
            dibujar_texto(sup, f.titulo, (22, y), C["amarillo"] if elegido else C["blanco"])
            dibujar_texto(sup, f"{self.conteo_finales[f.clave]} HOJAS", (248, y), C["gris"], sombra=False, derecha=True)
            if elegido:
                dibujar_texto(sup, ">", (2, y), C["amarillo"])
            y = dibujar_parrafo(sup, f.regla, (22, y + 11), 222, C["gris"], interlineado=1)
            y += 5
