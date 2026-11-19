"""Intro del juego: una película corta antes del menú, al estilo de las consolas de 16 bits.

Solo se ve al abrir el juego (nunca al volver al menú desde una partida) y no se puede saltar.
Todo se arma con lo que ya tiene el juego (fondos de los niveles, jefes, tropas, vehículos, el
presidente, la fuente, las explosiones, la música y la frase "Bienvenido a la Patria Milagro"),
en una franja de cine con bandas negras arriba y abajo. Cada escena tiene varios planos que se
mueven a distinta velocidad (profundidad): fondo lejano, figura gigante, calle y primer plano.

  1. negro       pantalla negra
  2. calma       Medellín de noche, el rótulo "COLOMBIA, AÑO 2026" y un dron que pasa
  3. amenaza     escuadrón de drones, explosiones, humo, motos y camioneta; el cielo se pone rojo
  4. jefes       los tres jefes, enormes y translúcidos, cada uno sobre su zona y con su tropa
  5. frase       letras rojas gigantes que cruzan la pantalla
  6. accion      el presidente corre por la selva disparando
  7. presidente  primer plano con el atardecer del menú y su frase hablada; luego arranca el himno

Los textos y las duraciones son datos fáciles de editar.
"""
from __future__ import annotations

import math
import random

import pygame

import settings
from audio import gestor as audio
from levels import cargar_nivel
from render.efectos import Bola, Efectos
from render.fondos import Fondo
from render.texto import dibujar_texto, fuente
from render.ui import superficie_opaca
from scenes.base import Scene
from scenes.menu import MenuScene

C = settings.COLORES
BANDA = 28                                   # alto de cada banda negra (franja de cine)
FRANJA = pygame.Rect(0, BANDA, settings.ANCHO, settings.ALTO - 2 * BANDA)
ALTO_CALLE = 14                              # la calle del primer plano, al pie de la franja
PIE = FRANJA.bottom - ALTO_CALLE + 4         # donde pisan tropas y vehículos

# --- Guion: (parte, segundos) ---------------------------------------------------------------
PARTES = [("negro", 1.0), ("calma", 7.0), ("amenaza", 9.0), ("jefes", 15.0), ("frase", 5.0),
          ("accion", 8.0), ("presidente", 8.5)]
DURACION = sum(d for _, d in PARTES)
ROTULO = "COLOMBIA, AÑO 2026"
TEXTO_AMENAZA = "TRES CAPOS SE REPARTIERON EL PAÍS."
# nivel (su fondo y su jefe), zona, lo que hace, desde dónde se mira el fondo
JEFES = [(1, "VICHADA", "TALA LA SELVA Y ENVENENA LOS RÍOS", 40),
         (2, "MEDELLÍN", "EXTORSIONA Y COMPRA A MEDIA ALCALDÍA", 330),
         (3, "LA GUAJIRA", "NADA CRUZA LA FRONTERA SIN PAGARLE", 20)]
FRASE = "¡LA CRUZADA COMIENZA!"
TEXTO_ACCION = "UN PRESIDENTE DECIDIÓ IR POR ELLOS."
NOMBRE_PRESIDENTE = "PRESIDENTE A. MILAGRO"
FRASE_PRESIDENTE = "BIENVENIDO A LA PATRIA MILAGRO."

SEGUNDOS_POR_JEFE = dict(PARTES)["jefes"] / len(JEFES)
# segundos dentro de "amenaza" en que estalla cada explosión (cada vez más seguidas)
EXPLOSIONES = (2.6, 3.3, 3.9, 4.4, 4.9, 5.3, 5.7, 6.1, 6.5, 6.9, 7.2, 7.5, 7.8, 8.1, 8.35, 8.6)
ROJO_CIELO = (255, 96, 84)                   # tinte del desastre (multiplica los colores del fondo)
ROJO_ZONA = (255, 132, 112)                  # tinte de las zonas de los jefes (más suave)
ESCALA_FRASE = 12                            # la fuente del juego, 12 veces más grande
MOMENTO_VOZ = 1.7                            # segundos dentro de "presidente"
# La música entra un instante después de abrir: en el navegador el sonido tarda en arrancar y,
# si se pide en el primer cuadro, el comienzo sale cortado
ARRANQUE_MUSICA = 0.6
# La música no se corta: se apaga poco a poco desde el final de "accion" y termina justo antes
# de que hable el presidente
APAGADO_MUSICA = 2.8                         # segundos que tarda en apagarse
VEL_CIUDAD = 16.0                            # px/s de la cámara sobre Medellín (calma y amenaza)
FACTOR_EDIFICIOS = 0.32                      # la capa de edificios se mueve a esta parte de la cámara
VEL_FRASE = 360                              # px/s de las letras gigantes: 6 px exactos por cuadro
# "accion": cuándo entra cada enemigo por la derecha (sicarios) y la moto que embiste
SICARIOS_ACCION = (1.3, 1.9, 2.4, 3.0, 3.4, 4.0, 4.5, 5.6, 6.1, 6.5)
MOTO_ACCION = 5.0
# "accion" se dibuja en pequeño y se amplía al doble (plano cercano): estas medidas son de la
# imagen pequeña, de 128 x 84
# Velocidades en píxeles enteros por cuadro (60, 120 y 180 px/s): el movimiento no da tirones
VEL_SELVA = 60.0                             # px/s que avanza la cámara mientras el presidente corre
VEL_MOTO = 60.0                              # lo que la moto avanza, además, contra la cámara
VEL_BALA = 180.0
X_PRESIDENTE = 36
MARGEN_PLANO = 4                             # sobrante a los lados para el sacudón de la cámara
PLANO_ACCION = pygame.Rect(MARGEN_PLANO, FRANJA.bottom - FRANJA.h // 2, settings.ANCHO // 2, FRANJA.h // 2)


def _mezcla(a, b, t: float):
    t = max(0.0, min(1.0, t))
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def _gris(k: float):
    v = int(255 * max(0.0, min(1.0, k)))
    return (v, v, v)


def _suavizar(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 3


class IntroScene(Scene):
    def __init__(self, juego, **datos):
        super().__init__(juego, **datos)
        self.tiempo = 0.0
        niveles = {n: cargar_nivel(n) for n in (1, 2, 3)}
        self.fondos = {n: Fondo(datos_nivel) for n, datos_nivel in niveles.items()}
        self.ambientes = {n: datos_nivel["ambiente"] for n, datos_nivel in niveles.items()}
        self.sprites = juego.sprites
        doble = lambda nombre: pygame.transform.scale_by(  # noqa: E731
            self.sprites.frame(nombre, "quieto", 0), 2).convert_alpha()
        self.jefes = [doble(f"jefe{n}") for n, *_ in JEFES]
        self.busto = doble("presidente_menu")
        # primer plano: pasa rozando la cámara (mira a la izquierda, hacia donde vuela)
        self.dron_cerca = pygame.transform.flip(doble("dron"), True, False)
        self.rotulo = self._con_sombra(ROTULO, 2, C["blanco"])
        self.frase = fuente(ESCALA_FRASE).render(FRASE, False, C["rojo"])
        self.atardecer = MenuScene._pintar_fondo()            # el mismo cielo del menú
        self._capa_rayos = pygame.Surface((settings.ANCHO, settings.ALTO), pygame.SRCALPHA)
        self._plano = superficie_opaca((settings.ANCHO, settings.ALTO))   # donde se dibuja "accion" antes de ampliarla
        self.efectos = Efectos(random.Random(11))
        self.rng = random.Random(5)
        self._parte = None                    # la parte del cuadro anterior (para limpiar al cambiar)
        self._estallidos = 0                  # cuántas explosiones de "amenaza" ya salieron
        self._columnas = []                   # [x, y]: sitios que siguen echando humo
        self._temblor = 0.0                   # segundos que le quedan al sacudón de la cámara
        self._desvio = 0                      # píxeles que la cámara se corre en este cuadro
        self._hechos = set()                  # sonidos y músicas que ya se lanzaron
        self._balas = []                      # "accion": [x, y] de las balas del presidente
        self._enemigos = []                   # "accion": [tipo, x, x en la que le dan] de sicarios y moto
        self._proximo_disparo = 0.0
        self._salidos = 0                     # cuántos sicarios de SICARIOS_ACCION ya entraron
        self.voz_lanzada = False

    @staticmethod
    def _con_sombra(texto: str, escala: int, color) -> pygame.Surface:
        f = fuente(escala)
        ancho, alto = f.size(texto)
        sup = pygame.Surface((ancho + escala, alto + escala), pygame.SRCALPHA)
        sup.blit(f.render(texto, False, C["negro"]), (escala, escala))
        sup.blit(f.render(texto, False, color), (0, 0))
        return sup

    # --- Guion ------------------------------------------------------------------------------
    def parte(self):
        """(nombre de la parte actual, segundos dentro de ella, su duración)."""
        t = self.tiempo
        for nombre, duracion in PARTES:
            if t < duracion:
                return nombre, t, duracion
            t -= duracion
        return PARTES[-1][0], PARTES[-1][1], PARTES[-1][1]

    def _una_vez(self, clave: str) -> bool:
        if clave in self._hechos:
            return False
        self._hechos.add(clave)
        return True

    def _sacudir(self, segundos: float = 0.25) -> None:
        self._temblor = max(self._temblor, segundos)

    def _sacudon(self) -> int:
        """Desvío de la cámara en este cuadro (el mismo para todo lo que se dibuja en él)."""
        return self._desvio

    def _explotar(self, x: float, y: float, tam: float) -> None:
        """Explosión del juego con el resplandor más contenido: ampliado o sobre el cielo rojo,
        el disco de luz completo se ve como una mancha."""
        self.efectos.explosion(x, y, tam)
        self.efectos.destellos[-1][2] *= 0.5

    def _arrastrar_efectos(self, dx: float) -> None:
        """Mueve fuego, humo y chispas con el suelo: quedan pegados al sitio donde nacieron."""
        e = self.efectos
        for lista in (e.particulas, e.bolas, e.anillos):
            for cosa in lista:
                cosa.x -= dx
        for destello in e.destellos:
            destello[0] -= dx

    # --- Lógica -----------------------------------------------------------------------------
    def update(self, dt, acciones):
        self.tiempo += dt
        self.efectos.update(dt)
        self._temblor = max(0.0, self._temblor - dt)
        self._desvio = self.rng.choice((-2, -1, 1, 2)) if self._temblor > 0 else 0
        if self.tiempo >= ARRANQUE_MUSICA and self._una_vez("musica_inicio"):
            audio.musica("decision")
        if self.tiempo >= DURACION:           # al menú; la frase ya se dijo aquí: no se repite
            self.juego.escenas.cambiar("menu", desde_intro=self.voz_lanzada)
            return
        nombre, t, _ = self.parte()
        if nombre != self._parte:             # cambio de plano: no arrastra chispas ni humo
            self._parte = nombre
            self.efectos = Efectos(random.Random(11))
            self._columnas = []
        getattr(self, "_actualizar_" + nombre, lambda *_: None)(t, dt)

    def _actualizar_amenaza(self, t, dt):
        if t >= 0.6 and self._una_vez("alerta"):
            audio.efecto("alerta")
        while self._estallidos < len(EXPLOSIONES) and t >= EXPLOSIONES[self._estallidos]:
            i = self._estallidos
            self._estallidos += 1
            if i == 0:
                audio.musica("jefe")
            grande = i >= 6
            x, y = self.rng.randint(24, 232), self.rng.randint(96, 160)
            self._explotar(x, y, 3.0 if grande else 2.0)
            self._columnas.append([x, y])
            self._sacudir(0.35 if grande else 0.22)
            audio.efecto("explosion_grande" if grande else "explosion")
        arrastre = VEL_CIUDAD * FACTOR_EDIFICIOS * dt     # el fuego se queda en su edificio
        self._arrastrar_efectos(arrastre)
        for columna in self._columnas:        # cada sitio golpeado sigue echando humo hacia arriba
            columna[0] -= arrastre
            x, y = columna
            if self.rng.random() < 0.3:
                self.efectos.bolas.append(Bola(x + self.rng.uniform(-3, 3), y - 4, self.rng.uniform(3, 6),
                                               1.6, edad=0.62 * 1.6, sube=34))
        for k in range(3):                    # el escape de las motos
            x = self._x_moto_amenaza(t, k)
            if 0 < x < settings.ANCHO and self.rng.random() < 0.5:
                self.efectos.humo(x - 18, PIE - 6)

    def _actualizar_jefes(self, t, dt):
        if self._una_vez("musica_jefe"):
            audio.musica("jefe")
        i = min(len(JEFES) - 1, int(t / SEGUNDOS_POR_JEFE))
        u = t - i * SEGUNDOS_POR_JEFE
        if self._una_vez(f"jefe{i}"):
            audio.efecto("explosion_grande")
            self._sacudir(0.4)
        if i == 0 and int(u * 5) != int((u - dt) * 5) and 0.8 < u < SEGUNDOS_POR_JEFE - 0.4:
            audio.efecto("disparo_enemigo")   # la tropa del Jaguar dispara al marchar
        if i > 0:                             # polvo y humo detrás de motos y camionetas
            for x in self._x_vehiculos(i, u):
                if 0 < x < settings.ANCHO and self.rng.random() < 0.35:
                    self.efectos.polvo(x - 22, PIE, 2, hacia=-1)

    def _actualizar_frase(self, t, dt):
        if self._una_vez("temblor"):
            audio.efecto("temblor")
            self._sacudir(0.3)

    def _actualizar_accion(self, t, dt):
        """El presidente dispara sin parar; lo que entra por la derecha estalla al primer tiro."""
        x_pres = self._x_presidente(t)
        self._arrastrar_efectos(VEL_SELVA * dt)             # explosiones y polvo quedan atrás con el suelo
        if t >= dict(PARTES)["accion"] - APAGADO_MUSICA + MOMENTO_VOZ and self._una_vez("apagar_musica"):
            audio.apagar_musica(int(APAGADO_MUSICA * 1000))
        if t >= self._proximo_disparo and 1.1 < t < 7.2:
            self._proximo_disparo = t + 0.16
            bx, by = self._boca(t)
            self._balas.append([x_pres + bx, PIE + by + 2])
            audio.efecto("disparo_jugador")
        while self._salidos < len(SICARIOS_ACCION) and t >= SICARIOS_ACCION[self._salidos]:
            self._salidos += 1
            self._enemigos.append(["sicario", PLANO_ACCION.w + 14.0, self.rng.uniform(84, 116)])
        if t >= MOTO_ACCION and self._una_vez("moto"):
            self._enemigos.append(["moto", PLANO_ACCION.w + 24.0, 108.0])
        for e in self._enemigos:              # el sicario queda atrás con el suelo; la moto embiste
            e[1] -= (VEL_SELVA if e[0] == "sicario" else VEL_SELVA + VEL_MOTO) * dt
        for b in self._balas:
            b[0] += VEL_BALA * dt
            for e in self._enemigos:          # le dan cuando ya entró bien en el cuadro
                if e[1] is not None and e[1] <= e[2] and b[0] >= e[1] - 8:
                    moto = e[0] == "moto"
                    self._explotar(e[1], PIE - (14 if moto else 20), 2.0 if moto else 1.0)
                    audio.efecto("explosion_grande" if moto else "explosion")
                    self._sacudir(0.3 if moto else 0.12)
                    e[1], b[0] = None, 999.0
                    break
        self._enemigos = [e for e in self._enemigos if e[1] is not None and e[1] > -40]
        self._balas = [b for b in self._balas if b[0] < PLANO_ACCION.w + 8]
        if self.rng.random() < 0.4:           # polvo de las botas
            self.efectos.polvo(x_pres - 6, PIE, 1, color=(120, 150, 90), hacia=-1)

    def _actualizar_presidente(self, t, dt):
        if self._una_vez("apagar_musica"):                  # por si no se apagó antes
            audio.apagar_musica(int(MOMENTO_VOZ * 1000))
        if t >= MOMENTO_VOZ and not self.voz_lanzada:
            self.voz_lanzada = True
            audio.presentar("bienvenida", "menu")       # calla la música, habla y luego suena el himno

    # --- Posiciones (dependen solo del tiempo: el dibujo y la lógica coinciden) -------------------
    @staticmethod
    def _x_moto_amenaza(t: float, k: int) -> float:
        return -40 + (t - (3.4, 4.6, 6.4)[k]) * 175

    @staticmethod
    def _x_vehiculos(i: int, u: float):
        """Tráfico continuo de la tropa del jefe i (1 = motos de Medellín, 2 = convoy de La Guajira)."""
        if i == 1:
            return [((u * 175 - k * 105) % 520) - 60 for k in range(4)]
        return [((u * 95 - k * 150) % 560) - 110 for k in range(3)]

    def _boca(self, t: float):
        """Punta del fusil del presidente (relativa a sus pies) en el cuadro de carrera del instante t:
        de ahí salen las balas y el fogonazo, también cuando baja el arma al dar el paso."""
        conf = self.sprites.config.get("jugador", {})
        cuadros = conf.get("animaciones", {}).get("correr") or []
        if not cuadros:
            return 16, -27
        cuadro = cuadros[int(t * self.sprites.fps("jugador")) % len(cuadros)]
        return tuple(conf.get("bocas", {}).get(cuadro, (16, -27)))

    @staticmethod
    def _x_presidente(t: float) -> float:
        return min(X_PRESIDENTE, -24 + t * 60)              # entra corriendo por la izquierda

    # --- Dibujo -----------------------------------------------------------------------------
    def draw(self, sup):
        nombre, t, duracion = self.parte()
        sup.fill(C["negro"])
        getattr(self, "_dibujar_" + nombre)(sup, t, duracion)
        sup.fill(C["negro"], (0, 0, settings.ANCHO, BANDA))                      # bandas de cine
        sup.fill(C["negro"], (0, settings.ALTO - BANDA, settings.ANCHO, BANDA))
        getattr(self, "_rotulos_" + nombre, lambda *_: None)(sup, t, duracion)

    def _calle(self, sup, nivel: int, camara: float, factor: float = 1.6, tinte=None) -> None:
        """Primer plano: una franja de suelo con los colores del nivel y marcas que corren con la
        cámara (es lo que más rápido se mueve: da la sensación de profundidad). tinte: la luz de
        la escena (multiplica los colores, igual que al fondo)."""
        amb = self.ambientes[nivel]
        y = FRANJA.bottom - ALTO_CALLE
        sup.fill(amb.get("suelo", (70, 60, 70)), (0, y, settings.ANCHO, ALTO_CALLE))
        sup.fill(amb.get("suelo_borde", (150, 146, 156)), (0, y, settings.ANCHO, 2))
        detalle = amb.get("suelo_detalle", (50, 44, 52))
        d = -int(camara * factor) % 48
        for x in range(d - 48, settings.ANCHO, 48):
            sup.fill(detalle, (x, y + 6, 14, 2))
            sup.fill(detalle, (x + 26, y + 10, 8, 2))
        if tinte:
            sup.fill(tinte, (0, y, settings.ANCHO, ALTO_CALLE), special_flags=pygame.BLEND_RGB_MULT)

    @staticmethod
    def _escrito(sup, texto: str, letras: int, y: int, color) -> None:
        """Texto que se va escribiendo: centrado según el texto COMPLETO, así no se corre."""
        x = (settings.ANCHO - fuente(1).size(texto)[0]) // 2
        dibujar_texto(sup, texto[:max(0, letras)], (x, y), color)

    def _sprite(self, sup, nombre, x, pie, t=0.0, anim="quieto", voltear=False):
        self.sprites.dibujar(sup, nombre, anim, t, x, pie, 0, voltear=voltear)

    def _dron(self, sup, x, y, voltear=True):
        """Dron lejano con su luz roja intermitente."""
        self._sprite(sup, "dron", x, y, voltear=voltear)
        if int(self.tiempo * 6) % 2:
            sup.fill((255, 60, 40), (int(x) - 1, int(y) + 9, 2, 2))

    def _dibujar_negro(self, sup, t, duracion):
        pass

    # ---- 2 y 3: la ciudad ---------------------------------------------------------------------
    def _camara_ciudad(self) -> float:
        """La ciudad se recorre en un solo movimiento durante la calma y la amenaza."""
        return 120 + self.tiempo * VEL_CIUDAD + self._sacudon()

    def _dron_lejano(self, sup, t_calma: float) -> None:
        """El dron que cruza a lo lejos: aparece en la calma y sigue de largo en la amenaza."""
        if t_calma > 4.2:
            self._dron(sup, 280 - (t_calma - 4.2) * 62, 62 + math.sin(t_calma * 3) * 3)

    def _dibujar_calma(self, sup, t, duracion):
        camara = self._camara_ciudad()
        self.fondos[2].dibujar_fondo(sup, camara, self.tiempo)
        self._dron_lejano(sup, t)
        self._calle(sup, 2, camara)
        sup.fill(_gris(t / 1.2), special_flags=pygame.BLEND_RGB_MULT)            # sale del negro
        aparece = min((t - 1.4) / 0.6, (4.6 - t) / 0.6)                          # el rótulo entra y se va
        if aparece > 0:
            self.rotulo.set_alpha(int(255 * min(1.0, aparece)))
            sup.blit(self.rotulo, self.rotulo.get_rect(center=(128, 100)))

    def _dibujar_amenaza(self, sup, t, duracion):
        camara = self._camara_ciudad()
        self.fondos[2].dibujar_fondo(sup, camara, self.tiempo)
        luz = _mezcla((255, 255, 255), ROJO_CIELO, (t - 2.4) / 3.0)
        sup.fill(luz, special_flags=pygame.BLEND_RGB_MULT)
        self._dron_lejano(sup, t + dict(PARTES)["calma"])
        for k in range(7):                                                       # escuadrón, al fondo
            x = 300 + k * 44 - t * 74
            self._dron(sup, x, 52 + (k % 3) * 17 + math.sin(t * 3 + k) * 3)
        self.efectos.dibujar(sup, 0)                                             # fuego y humo en los edificios
        self._calle(sup, 2, camara, tinte=luz)
        for k in range(3):                                                       # motos por la calle
            self._sprite(sup, "moto", self._x_moto_amenaza(t, k), PIE)
        self._sprite(sup, "camioneta", -60 + (t - 6.0) * 120, PIE)
        for k, t0 in enumerate((1.4, 2.3, 7.0)):                                 # drones rozando la cámara
            x = settings.ANCHO + 40 - (t - t0) * 210
            sup.blit(self.dron_cerca, (int(x), 40 + k * 26 + int(math.sin(t * 4 + k) * 4)))
        self._destello(sup, (t - (duracion - 0.3)) / 0.3)                        # termina en blanco

    def _rotulos_amenaza(self, sup, t, duracion):
        if t > 0.6:
            self._escrito(sup, TEXTO_AMENAZA, int((t - 0.6) * 30), 205, C["blanco"])

    # ---- 4: los jefes ---------------------------------------------------------------------------
    def _dibujar_jefes(self, sup, t, duracion):
        i = min(len(JEFES) - 1, int(t / SEGUNDOS_POR_JEFE))
        u = t - i * SEGUNDOS_POR_JEFE
        nivel, _, _, origen = JEFES[i]
        camara = origen + u * 14 + self._sacudon()
        self.fondos[nivel].dibujar_fondo(sup, camara, self.tiempo)
        sup.fill(ROJO_ZONA, special_flags=pygame.BLEND_RGB_MULT)
        # El jefe, gigante y translúcido: sube despacio y se desliza al revés que el fondo
        jefe = self.jefes[i]
        jefe.set_alpha(int(225 * min(1.0, u / 1.2)))
        subida = int(14 * (1 - _suavizar(u / 1.6)))
        sup.blit(jefe, jefe.get_rect(midbottom=(118 + int(u * 5), FRANJA.bottom + 2 + subida)))
        self._calle(sup, nivel, camara, tinte=ROJO_ZONA)
        getattr(self, f"_tropa_{i}")(sup, u)
        self.efectos.dibujar(sup, 0)
        self._destello(sup, 1 - u / 0.35)                                        # cada jefe entra con un fogonazo
        if i < len(JEFES) - 1:                                                   # y el fogonazo del siguiente va creciendo
            self._destello(sup, 1 - (SEGUNDOS_POR_JEFE - u) / 0.15)
        if i == len(JEFES) - 1:                                                  # el último se va a negro
            sup.fill(_gris((duracion - t) / 0.5), special_flags=pygame.BLEND_RGB_MULT)

    def _tropa_0(self, sup, u):
        """Vichada: una columna de sicarios marcha disparando y dos drones la cubren."""
        for k in range(7):
            x = -18 - k * 30 + u * 46
            self._sprite(sup, "sicario", x, PIE - (int(u * 6 + k) % 2))          # el paso
            fase = (u * 0.8 + k * 0.37) % 1.0                                    # su bala sale de la pantalla
            if x > -10:
                self._sprite(sup, "bala_enemigo", x + 16 + fase * 330, PIE - 24, t=u)
                if fase < 0.07:                                                  # fogonazo del fusil
                    sup.fill((255, 240, 160), (int(x) + 13, PIE - 28, 3, 3))
        for k in range(2):
            # vuelan por encima de la cabeza del jefe: no le tapan la cara
            self._dron(sup, -30 - k * 70 + u * 60, 40 + k * 4 + math.sin(u * 3 + k) * 2, voltear=False)

    def _tropa_1(self, sup, u):
        """Medellín: las motos imponen el toque de queda; detrás, una camioneta."""
        self._sprite(sup, "camioneta", -80 + u * 62, PIE)
        for x in self._x_vehiculos(1, u):
            self._sprite(sup, "moto", x, PIE)

    def _tropa_2(self, sup, u):
        """La Guajira: el convoy del contrabando, con drones de escolta."""
        for k, x in enumerate(self._x_vehiculos(2, u)):
            self._sprite(sup, "camioneta", x, PIE)
            self._dron(sup, x + 10, 40 + k * 3 + math.sin(u * 3 + k) * 2, voltear=False)

    def _rotulos_jefes(self, sup, t, duracion):
        i = min(len(JEFES) - 1, int(t / SEGUNDOS_POR_JEFE))
        u = t - i * SEGUNDOS_POR_JEFE
        nivel, zona, hace, _ = JEFES[i]
        if u < 0.3 or (i == len(JEFES) - 1 and duracion - t < 0.4):
            return
        dibujar_texto(sup, zona, (128, 10), C["cian"], centrado=True)
        dibujar_texto(sup, settings.JEFES[nivel]["nombre"], (128, 200), C["naranja"], centrado=True)
        self._escrito(sup, hace, int((u - 0.3) * 30), 211, C["blanco"])

    # ---- 5: la frase gigante -------------------------------------------------------------------
    def _dibujar_frase(self, sup, t, duracion):
        """Letras gigantes de derecha a izquierda sobre líneas de velocidad (dos planos)."""
        for k in range(26):
            lejos = k % 2
            largo, vel = (18, 260) if lejos else (44, 620)
            x = settings.ANCHO - ((t * vel + k * 97) % (settings.ANCHO + 60))
            sup.fill((70, 12, 6) if lejos else (130, 24, 8), (int(x), FRANJA.y + 4 + (k * 37) % (FRANJA.h - 8), largo, 1))
        x = settings.ANCHO - round(t * VEL_FRASE)
        y = FRANJA.centery - self.frase.get_height() // 2 - ESCALA_FRASE + self._sacudon()
        sup.blit(self.frase, (x, y))

    # ---- 6: el presidente en acción --------------------------------------------------------------
    def _dibujar_accion(self, sup, t, duracion):
        """Plano cercano: se dibuja la esquina de abajo de la selva y se amplía al doble exacto."""
        plano = self._plano
        zona = PLANO_ACCION.inflate(2 * MARGEN_PLANO, 0)                        # con sobrante para el sacudón
        plano.set_clip(zona)
        camara = 60 + round(t * VEL_SELVA)
        self.fondos[1].dibujar_fondo(plano, camara, self.tiempo)
        self._calle(plano, 1, camara, factor=1.0)                               # el suelo que pisan
        for tipo, x, _ in self._enemigos:
            self._sprite(plano, tipo, round(x) + MARGEN_PLANO, PIE, voltear=True)
        for x, y in self._balas:
            self._sprite(plano, "bala_jugador", round(x) + MARGEN_PLANO, y + 2, t=t)
        x_pres = round(self._x_presidente(t)) + MARGEN_PLANO
        self._sprite(plano, "jugador", x_pres, PIE, t=t, anim="correr")
        if 0 <= self._proximo_disparo - t > 0.11:                               # fogonazo del fusil
            bx, by = self._boca(t)
            plano.fill((255, 244, 170), (x_pres + bx, PIE + by - 1, 3, 3))
        self.efectos.dibujar(plano, -MARGEN_PLANO)
        plano.set_clip(None)
        vista = PLANO_ACCION.move(self._sacudon(), 0)                           # el sacudón mueve TODO el plano
        sup.blit(pygame.transform.scale_by(plano.subsurface(vista), 2), FRANJA.topleft)
        sup.fill(_gris(min(t / 0.4, (duracion - t) / 0.5)), special_flags=pygame.BLEND_RGB_MULT)

    def _rotulos_accion(self, sup, t, duracion):
        if 0.5 < t < duracion - 0.5:
            self._escrito(sup, TEXTO_ACCION, int((t - 0.5) * 30), 205, C["blanco"])

    # ---- 7: primer plano -------------------------------------------------------------------------
    def _dibujar_presidente(self, sup, t, duracion):
        sup.set_clip(FRANJA)
        sol_x = 128
        sup.blit(self.atardecer, (sol_x - 88, 0))                                # el sol, justo detrás de él
        sup.blit(self.atardecer, (sol_x - 88 - settings.ANCHO, 0))
        capa = self._capa_rayos                                                  # rayos que giran despacio
        capa.fill((0, 0, 0, 0))
        for k in range(10):
            ang = t * 0.22 + k * math.tau / 10
            puntos = [(sol_x, 158)] + [(sol_x + math.cos(a) * 280, 158 + math.sin(a) * 280)
                                       for a in (ang - 0.09, ang + 0.09)]
            pygame.draw.polygon(capa, (255, 220, 140, 26), puntos)
        sup.blit(capa, (0, 0))
        subida = int(46 * (1 - _suavizar(t / 1.1)))                              # el busto sube al entrar
        respiro = int(math.sin(t * 1.6) * 1.2)
        sup.blit(self.busto, self.busto.get_rect(midtop=(128, FRANJA.y + 8 + subida + respiro)))
        franjas = ((C["amarillo"], 6), (C["azul"], 3), (C["rojo"], 3))            # la bandera ondea al pie
        for x in range(0, settings.ANCHO, 2):
            y = FRANJA.bottom - 10 + int(math.sin(t * 3 + x * 0.05) * 2)
            for color, alto in franjas:
                sup.fill(color, (x, y, 2, alto))
                y += alto
        sup.set_clip(None)
        sup.fill(_gris(min(t / 0.7, (duracion - t) / 0.3)), special_flags=pygame.BLEND_RGB_MULT)

    def _rotulos_presidente(self, sup, t, duracion):
        if 0.6 < t < duracion - 0.3:
            dibujar_texto(sup, NOMBRE_PRESIDENTE, (128, 10), C["amarillo"], centrado=True)
        if MOMENTO_VOZ <= t < duracion - 0.3:
            self._escrito(sup, FRASE_PRESIDENTE, int((t - MOMENTO_VOZ) * 16), 205, C["blanco"])

    @staticmethod
    def _destello(sup, fuerza: float) -> None:
        """Fogonazo blanco: fuerza 0..1 (1 = pantalla blanca)."""
        if fuerza > 0:
            sup.fill(_gris(fuerza), special_flags=pygame.BLEND_RGB_ADD)
