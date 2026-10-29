# Patria Milagro — documentación técnica

Run-and-gun lateral estilo *Super C* (NES) hecho en Python + pygame-ce para el curso de
**Estructura de Datos II**. El Presidente (ficticio) A. Milagro persigue criminales a través
de 3 niveles; al final de cada uno decide **CAPTURAR, EXTRADITAR o DEJAR LIBRE** al jefe, y esas
decisiones se guardan en un **árbol n-ario** que determina la opinión popular y el final.
Un **grafo**, el **mapa del país**, recibe cada decisión y ofrece dos rutas hacia el nivel
siguiente (la más segura y la más corta): la que elige el jugador cambia los refuerzos enemigos
y la opinión. Se juega solo (el multijugador en red sigue en `net/`, pero está fuera del menú
mientras se rehace como multijugador local con control NES).

> Los personajes, medios, influencers y criminales del juego son ficticios. La frase de
> bienvenida es una grabación real que aportó el equipo (ver [Sonido](#sonido-audio)).

## Instalación

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Ejecución

```bash
python main.py                     # jugar
python main.py --headless 600      # prueba sin ventana (600 frames)
python -m unittest discover -s tests -t . -v
python main.py --arena             # desarrollo: cada nivel empieza frente al jefe
python main.py --nivel 2 --arena   # desarrollo: directo al nivel 2
python -m net.servidor             # servidor dedicado del multijugador (opcional)
```

Flujo de una partida: menú → **informe del nivel** (historia, mapa y elección de ruta) → nivel →
**decisión con tiempo límite** (y opción de revocar) → teléfono → informe del nivel siguiente →
... → pantalla final.

`F11` alterna pantalla completa. La ventana se puede redimensionar: la imagen de 256x224 se
escala por un factor entero para que el pixel art se vea nítido.

## Controles

| Acción     | Teclado        | Control NES |
|------------|----------------|-------------|
| Mover      | Flechas        | Cruceta     |
| Saltar     | Z              | A           |
| Disparar   | X              | B           |
| Pausa      | Enter / Esc    | START       |
| Ayuda      | F1 / Tab       | SELECT      |
| Confirmar  | Enter / Z      | A o START   |
| Volver     | Esc / X        | B           |

El teclado siempre funciona como respaldo, aunque haya un control conectado.

## Cómo mapear el control NES USB

1. Conecta el control y ejecuta `python tools/probar_control.py`. Al presionar cada botón,
   la consola muestra su ID (`BOTON id=1`), y para la cruceta muestra `HAT` o `EJE`.
2. Hay dos formas de guardar el mapeo:
   - En el juego: **Opciones → Configurar control**. Presiona el botón para SALTAR, DISPARAR,
     PAUSA y AYUDA; se guarda en `config/gamepad.json`.
   - A mano: edita `config/gamepad.json` (`botones`, y `eje_x`/`eje_y` si la cruceta llega
     como ejes).
3. La cruceta funciona tanto si llega como *hat* como si llega como ejes analógicos. Los
   controles se pueden conectar y desconectar con el juego abierto.

## Arquitectura

```
main.py            Juego: ventana, bucle con paso fijo (DT = 1/60) y escalado
settings.py        Constantes y opciones del jugador (config/opciones.json)
input_manager.py   Teclado + gamepad -> acciones abstractas {id_jugador: EstadoAcciones}
scenes/            Máquina de escenas (Scene + SceneManager con pila) y cada pantalla
render/            Dibujo: sprites (PNG o placeholder), animación por código, fondos, terreno,
                   efectos, transiciones, HUD, texto, UI, árbol, filtros (daltonismo y CRT)
audio/             Sonido sintetizado con numpy, partituras (musica_datos, himno_datos) y
                   gestor de reproducción
core/              Lógica pura y serializable: decision_tree (árbol), grafo, mapa, partida,
                   game_state, player, enemy, vehiculos, director, boss, bullet, fisica, news,
                   historia, logros, motivacion
net/               Multijugador: protocolo (mensajes), sesion (reglas), servidor y cliente (sockets)
levels/            Definición de los niveles como datos (suelo, plataformas, sicarios, power-ups)
assets/            Recursos opcionales que reemplazan a los generados (ver assets/LEEME.txt)
tools/             probar_control.py, procesar_sprites.py (arte IA -> sprites),
                   limpiar_voz.py (audio), simular_partidas.py (dificultad) y
                   simplificar_mapa.py (departamentos de Colombia -> assets/mapa/colombia.json)
tests/             Pruebas unitarias
docs/              lineamientos.pdf (enunciado del laboratorio)
```

- **Las escenas nunca leen teclas ni botones.** Reciben `acciones = {id_jugador: EstadoAcciones}`.
  `EstadoAcciones` tiene `to_dict`/`from_dict`, así que en el modo multijugador futuro las
  acciones de un jugador remoto pueden llegar por un socket sin cambiar la lógica.
- **Paso fijo:** la lógica siempre avanza en incrementos de 1/60 s, sin importar los FPS reales.
  Así la simulación es determinista, que es lo que se necesita para sincronizar por red.
- **Pila de escenas:** la pausa y la ayuda se apilan encima del nivel, que queda congelado.

## Enemigos y jefes

- **Refuerzos aleatorios** (dron, moto y camioneta blindada): ver
  [Componente aleatorio](#componente-aleatorio-refuerzos-y-suministros).
- **Un solo enemigo de a pie, el sicario raso**, idéntico en los 3 niveles (`settings.SICARIO`):
  corre hacia el jugador, se detiene un instante para apuntar (aviso visual) y dispara una
  bala lenta en línea recta. Muere de un impacto. La dificultad de cada nivel depende
  únicamente de **cuántos** sicarios hay y **dónde** aparecen (`levels/nivelN.py`, lista
  `enemigos`).
- **Un jefe por nivel**, en una arena cerrada (la última pantalla, con la cámara bloqueada).
  Tienen más vida y balas más rápidas y dañinas (`settings.JEFES`). Cada patrón de ataque es
  una máquina de estados en `core/boss.py` (un diccionario `{estado: función}`):

  | Jefe | Estados |
  |---|---|
  | 1 · El Jaguar del Monte | `esperar → rafaga` (ametralladora horizontal alta o baja) `/ saltar / barrido` (abanico de 5 balas en varias direcciones; 6 en fase 2) |
  | 2 · Don Concreto | `esperar → abanico` (3 balas) `/ preparar → embestida → aturdido` (agachado a 32 px de alto: la embestida se salta) |
  | 3 · La Sombra de la Raya | `esperar → dirigido` (balas al jugador) `/ onda` (onda de choque) `/ invocar` (2 sicarios) |

  Al bajar a la mitad de la vida entran en *fase 2*: los mismos patrones, pero más rápidos.
  El **barrido** del jefe 1 avisa 0,45 s antes, sus balas van al 75 % de la velocidad y quitan
  1 corazón (las de la ráfaga quitan 2); entre bala y bala hay 16 grados, un hueco por el que se
  pasa. Su vida subió de 40 a 52.
- **Vidas:** 3 vidas, y en cada una 3 corazones. Una bala de sicario quita 1 corazón y una de
  jefe quita 2. Caer a un precipicio cuesta una vida entera. Tras un golpe hay invulnerabilidad
  breve.

## Niveles (`levels/nivel1.py`, `nivel2.py`, `nivel3.py`)

Cada nivel es un diccionario de datos: tramos de suelo (los huecos son precipicios), bloques,
plataformas de una vía, sicarios, power-ups, tutorial y ambientación (cielo, capas de parallax,
colores del terreno). La última pantalla es la arena del jefe.

| Nivel | Ambiente | Largo | Sicarios (por detrás) | Jefe |
|---|---|---|---|---|
| 1 | La selva del Vichada | 2816 px | 19 (3) | El Jaguar del Monte |
| 2 | Medellín (de noche, años noventa) | 3072 px | 33 (6) | Don Concreto |
| 3 | La Guajira (desierto amarillo, mar, rancherías) | 3328 px | 42 (8) | La Sombra de la Raya |

Cada nivel tiene su **paisaje** (`render/paisajes.py`, elegido en `ambiente["paisaje"]`): un cielo,
cinco capas de parallax pintadas una vez (empalman sin costura al repetirse) y cosas vivas que se
dibujan cuadro a cuadro entre las capas:

| Nivel | Paisaje |
|---|---|
| Vichada | La selva de *La Vorágine*: no se ve el cielo, todo es selva verde. Al fondo, una muralla de selva que la humedad vuelve neblina; después ceibas gigantes, troncos con matapalos y cambuches de la guerrilla; arriba, el dosel que se cierra ("la cárcel verde"). Vivo: lianas que se mecen, haces de luz, guacamayas, mariposas morpho, niebla, ojos que miran desde la espesura y luciérnagas |
| Medellín | Noche de los años noventa: el valle de Aburrá con las comunas encendidas trepando las montañas, antenas, una cruz en el cerro, la aguja y la catedral de ladrillo con su rosetón, el metro elevado y edificios de ladrillo con rejas. Vivo: relámpagos, el tren que pasa, ventanas que se apagan, dos neones, un carro quemado que humea, el helicóptero con reflector y la llovizna |
| La Guajira | A pleno sol: el mar turquesa, el Pilón de Azúcar, molinos de viento, dunas amarillas, salinas rosadas con flamencos, rancherías wayuu con chinchorros de colores, cardones, trupillos y un puesto de pimpinas de gasolina de contrabando. Vivo: aspas que giran, el mar que brilla, rodadoras y el aire caliente |

Menos es más: cada capa se funde un poco con el color del aire (`Paisaje.AIRE`, perspectiva
atmosférica), así lo lejano se aleja y los personajes y las balas resaltan. Las capas se pintan
una vez y se convierten al formato de la pantalla (blits rápidos).

Encima, los adornos del suelo de `ambiente["decoracion"]` (pasto, faroles, rocas...). No chocan
con nada; en alto contraste se omiten para no distraer.

Además, cada nivel tiene su **atmósfera** (también en `ambiente`):
- **Neblina:** las capas lejanas se funden con el color del cielo, más cerca de su base
  (`Fondo._neblina`). Así se lee la profundidad.
- **Selva:** haces de sol entre las copas (`"rayos"`). **Ciudad:** llovizna con salpicaduras
  (`"lluvia"`). **Frontera:** el aire caliente ondula el horizonte (`"calor"`).
- **Terreno pintado una sola vez** (`render/terreno.py`, estilo en `ambiente["estilo"]`): todo el
  suelo del nivel queda en una superficie y al jugar se copia el pedazo visible (un blit por
  cuadro en vez de cientos de baldosas). Selva: pasto que cuelga, vetas, piedras y raíces, y
  tablones con musgo. Ciudad: bordillo, acera con juntas y grietas, muro de ladrillo con
  alcantarillas, balcones de metal con cerchas, y los bloques son autos estacionados.
  Frontera: crestas de arena, ondas, estratos rojizos, salientes de roca y barriles.

El sicario es el mismo en los tres: la dificultad sale solo de cuántos hay y dónde aparecen.
Los que entran por detrás persiguen al jugador y aceleran si quedan atrás.

`tests/test_niveles.py` valida los datos de los tres niveles:
- precipicios saltables (o con puente) y escalones que se pueden subir;
- un **grafo de alcanzabilidad**: cada plataforma se puede alcanzar saltando con la física real
  del juego (BFS desde el suelo);
- sicarios de plataforma sobre una plataforma y power-ups que se pueden tocar;
- arena plana y sin enemigos, y la dificultad creciente;
- que un bot complete cada nivel.

## Reemplazar los gráficos

Los sprites que no tienen PNG son *placeholders* dibujados por código (`render/pixelart.py`).
Hoy están así: las dos armas, la medalla de vida, el dron, la moto y la camioneta. Para usar
tus propios gráficos:

1. Pon la hoja PNG en `assets/sprites/` (cuadros del mismo tamaño, mirando a la derecha).
2. En `assets/sprites.json` indica el `archivo`, el tamaño de cada cuadro (`frame`) y qué
   cuadros forman cada animación.

Si el PNG no existe, se usa el dibujo por código. Si el PNG existe pero le faltan
animaciones, el juego **no** mezcla estilos: las que faltan usan su base del PNG
(`correr_diag_arriba` → `correr`) o `quieto`, y `agachado` se deriva aplastando `quieto`.
El `ancla` del JSON es el punto de los pies que se apoya en el suelo. No hay que tocar la lógica.

### Procesar arte generado con IA (`tools/procesar_sprites.py`)

Convierte las imágenes de `assets/sprites_raw/` (JPG/PNG con fondo magenta) en sprites:

```bash
python tools/procesar_sprites.py
```

1. Quita el fondo con flood fill desde el borde. El color se estima con la moda del perímetro
   y se repite por capas si hay varios fondos, como las franjas blancas y el panel magenta de
   `jefe_3`.
2. Quita los huecos interiores del fondo (por ejemplo entre las piernas), el halo del borde y
   los restos magenta.
3. Borra colores indicados en la configuración, como el fogonazo violeta de `jefe_1`, y las
   motas sueltas.
4. Recorta, reduce con la **moda por bloque**, cuantiza a una **paleta compartida de 24
   colores** y agrega un contorno negro de 1 px.
5. Guarda en `assets/sprites/`, actualiza `sprites.json` (tamaño y ancla) y genera
   `assets/sprites_preview.png`.

Si un sprite queda con restos de fondo o con huecos, ajusta su entrada en el diccionario
`CONFIG` del script (`tolerancia`, `tol_huecos`, `erosion`, `borrar_colores`, `altura`). El
script imprime `restos_fondo` y `huecos_interiores` de cada sprite para comprobarlo.

Las cajas de colisión y la boca del arma de sicarios y jefes están en `settings.py` (`arma`).

**Refuerzos y suministros** (2026-10-19; se procesan solos, sin tocar lo demás, con
`python tools/procesar_sprites.py --solo dron,moto,camioneta`;
hoja de comparación: `assets/sprites_refuerzos_preview.png`):

| Archivo | Sprite | Tamaño final | Ancla | Caja de colisión (`settings.VEHICULOS`) |
|---|---|---|---|---|
| `dron.jpeg` | dron | 39×20 | centro | 28×14 |
| `moto.jpeg` | moto con sicario | 39×32 | base de las ruedas | 32×28 (sin el casco) |
| `camioneta.jpeg` | camioneta con tirador en el techo | 70×44 | base de las ruedas | 62×34 (carrocería y torso del tirador) |

Las cajas cubren el cuerpo visible: la bala del presidente de pie sale a 27 px del suelo y con
la caja vieja de la moto (22 px de alto) pasaba por encima; solo se le daba agachado. La bala de
la moto sigue a 26 px del suelo, así que acostado (12 px) se sigue esquivando, y el salto (48 px)
la sigue pasando. Lo comprueban `test_de_pie_se_le_da_a_la_moto_y_a_la_camioneta` y
`test_la_moto_se_puede_saltar`.

`arma_triple`, `arma_rapida` y `vida` se dejaron con el dibujo por código (`render/pixelart.py`),
por decisión del equipo: sus JPG están en `sprites_raw/` pero el script los omite.

Las balas de la camioneta salen del fusil del tirador del techo (`sprites.json -> camioneta.boca`,
leída por `core/datos_sprites.boca_sprite`); sin PNG se usa `arma` de `settings.VEHICULOS`.

### Poses del presidente
Las imágenes `presidente_<pose>.jpeg` (disparar, correr_a, correr_b, saltar, agachado,
diag_arriba, arriba, diag_abajo, herido) pasan por el mismo proceso, con tres reglas extra
para que las poses no "bailen":

- **Misma escala:** todas usan el factor del idle (`presidente.jpeg`), calculado con la altura
  del cuerpo sin el arma. El script avisa si una pose mide más de 15 % más o menos que el idle.
- **Mismos pies:** se alinean en un lienzo común con la misma ancla, el centro-abajo del cuerpo
  sin contar el arma.
- **Pose acostada (`agachado`, en `POSES_HORIZONTALES`):** boca abajo, con la cabeza a la derecha.
  Usa la misma escala; su tamaño se compara por el largo del cuerpo (109 % del idle) y el ancla es el
  centro del cuerpo, así que al acostarse no se desplaza. Los zapatos se protegen por columnas y,
  con `"detalles": 0.3` en `CONFIG`, el fusil y la banda (de 1–2 px) no se vuelven negros al
  reducir. Si el lienzo común crece, los rasgos guardados se desplazan con el ancla. En el juego su
  caja mide 36×12 y la bala sale a 5 px del suelo.
- **Boca del arma:** se detecta la punta del cañón de cada pose y se guarda en
  `sprites.json → jugador.bocas`, relativa a los pies. `core/datos_sprites.py` la lee (como
  JSON, sin pygame) y la bala sale de ahí.

- **Rasgos faciales:** a 40 px la reducción se come el ojo. Después de reducir y cuantizar se
  pinta 1 píxel de ojo con el color más oscuro de la paleta. Las posiciones están en
  `sprites.json → jugador.rasgos`, por pose (`"ojo": [x, y]`, relativo a la esquina del PNG);
  también se aceptan `"ceja"` y `"nariz"`. Si una pose no tiene posición, el script detecta la
  cara y propone una: busca la mancha de piel del tercio superior rodeada de pelo/barba (así
  descarta las manos) y pone el ojo a la derecha del centro. Las posiciones guardadas se
  respetan al volver a ejecutar; `--redetectar-rasgos` las recalcula todas.

- **Traje unificado (paso final):** todas las poses y el idle usan la rampa del traje de
  `disparar` (sombra (17,27,54) y base (12,52,136); el negro interior no se toca). Cada píxel
  oscuro del cuerpo se remapea al tono de la rampa más cercano por luminosidad. La cabeza y
  la franja de zapatos están protegidas por posición; dentro de ellas solo se remapean píxeles
  claramente azules (cuello del saco, bastas). En las poses, los oscuros cálidos (zapatos,
  barba) nunca se tocan. Solo se usan colores que ya están en la paleta.

Las guías (línea de suelo, ancla y boca) solo se dibujan en
`assets/sprites_presidente_preview.png`, nunca dentro de los PNG. El script lo comprueba.

`Jugador.pose()` elige la pose según el estado: herido → agachado → arriba / diag_arriba /
abajo / diag_abajo según la cruceta → saltar en el aire → correr → **disparar** (de pie,
disparando o recién disparó) → **quieto** (de pie sin disparar: el idle, con el fusil bajo).
Correr usa `[correr_a, disparar, correr_b, disparar]` a 8 fps. La bala de pie siempre sale de
la boca de `disparar`, también en el primer disparo. Si falta una pose, las apuntadas usan
`disparar` y el resto usa el idle. El idle es una pose más: comparte lienzo, ancla, escala fija
(`PX_POR_PIXEL`), ojo por código y traje unificado.

**Busto del menú** (`presidente_menu.png`): la pose `diag_arriba` reducida a 200 px de alto,
recortada a la cintura y **disuelta en píxeles** hacia abajo con tramado ordenado (Bayer 4×4);
se configura en `BUSTO_MENU`. En el menú aparece con contraluz naranja, delante de un sol de
atardecer con rayos girando, y la parte disuelta queda detrás de la bandera.

**Paleta congelada:** la paleta compartida de 24 colores se guarda en `assets/paleta.json` y
el script la reutiliza, así que reemplazar una imagen no cambia los colores de los demás
sprites. Para recalcularla con k-means: `python tools/procesar_sprites.py --recalcular-paleta`.

## Árbol de decisiones (`core/decision_tree.py`)

### Qué problema resuelve
Al final de cada nivel el jugador decide qué hacer con el jefe: **capturar**, **extraditar**
o **dejar libre**. El juego necesita:

1. saber la opinión popular (medios, influencers, pueblo) después de cada decisión;
2. que una decisión tenga consecuencias distintas según lo que pasó antes (liberar por
   segunda vez es peor que liberar una vez);
3. elegir uno de los finales según el camino completo;
4. mostrar al final todas las posibilidades y la ruta elegida.

Todo eso es un **espacio de estados ramificado**: cada decisión abre 3 futuros posibles.

### Por qué un árbol
- Cada estado tiene **un solo pasado** (un padre) y **varios futuros** (hijos). Eso es
  exactamente un árbol: no hay ciclos ni dos caminos que lleguen al mismo nodo.
- El **camino de la raíz a un nodo** es la historia de la partida. La opinión de un nodo se
  calcula a partir de su padre, así que los efectos acumulados y combinados salen solos.
- 3 niveles × 3 opciones = **27 hojas** = 27 historias posibles, que se agrupan en 5 finales.
- Una lista solo guardaría la partida actual y una matriz no expresa la jerarquía. El árbol
  permite dibujar todas las ramas y resaltar la elegida.

### Qué variante es
- **Árbol n-ario con n = 3** (grado máximo 3), de altura fija 3, con **puntero al padre**.
- Los hijos se guardan en un **diccionario `decisión → Nodo`**, que da acceso en O(1) al hijo
  de una decisión. No se usa ninguna librería de árboles.
- Se construye de forma **perezosa**: un nodo existe solo si alguien tomó esa decisión.
  `construir_completo()` inserta los 40 nodos (1 + 3 + 9 + 27) para la visualización.

```
Nodo: nivel (0..3) · decision · opinion {medios, influencers, pueblo} · padre · hijos {decisión: Nodo}

                         raíz (50/50/50)
            ┌───────────────┼───────────────┐
        capturar        extraditar        liberar          nivel 1
       ┌───┼───┐        ┌───┼───┐        ┌───┼───┐
      c    e    l      c    e    l      c    e    l        nivel 2
     ...  ...  ...    ...  ...  ...    ...  ...  ...       nivel 3: 27 hojas
```

### Cómo se inserta
`decidir(decision)` llama a `insertar(actual, decision)`:

1. valida la decisión y que el nodo actual no sea una hoja (nivel 3);
2. si el hijo **no existe**, calcula el efecto y crea el nodo:
   `efecto = EFECTOS_BASE[decisión] × PESO_NIVEL[nivel] + AJUSTES_NIVEL[(nivel, decisión)]
   + EFECTOS_COMBINADOS[(decisión_anterior, decisión)]`, y cada valor queda limitado a 0..100;
3. si el hijo **ya existe**, lo reutiliza (no hay duplicados);
4. mueve `actual` al hijo.

Todos los efectos están en diccionarios al inicio del archivo y se pueden cambiar (también
se pasan al constructor en las pruebas). Algunos ejemplos: las decisiones del nivel 3 pesan
×1,5; liberar dos veces seguidas resta 10–12 puntos extra; capturar después de haber
liberado da +5 en medios ("rectificó").

### Cómo se recorre
| Método | Recorrido | Uso |
|---|---|---|
| `camino()` | **hoja → raíz** subiendo por `padre` y luego se invierte | resumen de la partida y elección del final |
| `preorden()` | **profundidad** (nodo, luego hijos en orden capturar → extraditar → liberar), recursivo | contar nodos, buscar hojas, dibujar el árbol |
| `bfs()` | **anchura**, nivel por nivel con una cola (`deque`) | dibujar el árbol por filas en la pantalla final |

`reiniciar()` vuelve a una raíz nueva para empezar otra partida. `to_dict()`/`from_dict()`
serializan el árbol completo y el camino actual.

### Cómo se elimina
`eliminar(nodo)` quita un nodo **con todo su subárbol** y devuelve cuántos nodos se fueron:

1. rechaza la raíz y los nodos que no son de este árbol (sube por `padre` hasta la raíz para
   comprobarlo);
2. cuenta el subárbol con `preorden(nodo)`;
3. borra la entrada `padre.hijos[decisión]`: al no quedar ninguna referencia, el subárbol
   entero desaparece (no hay que borrar nodo por nodo);
4. si la partida iba por dentro de lo eliminado, `actual` sube al padre.

En el juego es **REVOCAR LA DECISIÓN** (`revocar()`): una vez por partida, en la misma escena de
decisión y justo después de sellarla, hay 2,5 segundos para arrepentirse con X / B. Se elimina el
nodo recién insertado, el mapa vuelve a como estaba, la duda cuesta opinión (medios −6,
influencers −4, pueblo −4, que se restan en el nodo padre y por eso los hereda la nueva decisión)
y se decide de nuevo. Si el jefe escapó por tiempo no se puede revocar. Eliminar la rama
`capturar` de un árbol completo quita 13 nodos (1 + 3 + 9) y deja 27.

### Ajuste desde fuera del árbol
`ajustar(nodo, cambios)` suma a la opinión de un nodo algo que no es una decisión y lo anota en
`nodo.ajuste`. Lo usan tres cosas: la **ruta** con que se llega al nivel (una ruta larga resta
al pueblo), **revocar** una decisión y, en multijugador, el **influencer** (cada decisión pesa un
25 % más). Como los hijos calculan su opinión a partir del padre, el ajuste se hereda.

### Finales (las 27 hojas en 5 grupos)
Se evalúan en orden y gana el primero que se cumple (`final_de(nodo)`):

| Final | Condición | Hojas |
|---|---|---|
| Presidente cuestionado | liberó ≥ 2 veces, o promedio de opinión < 35 | 7 |
| Presidente de mano dura | capturó ≥ 2 veces, la última fue capturar y medios < 70 | 3 |
| Presidente diplomático | extraditó ≥ 2 veces y medios ≥ 55 | 7 |
| Presidente del pueblo | pueblo ≥ 65 | 3 |
| Presidente equilibrista | todos los demás | 7 |

Las pruebas (`tests/test_arbol.py`) comprueban: la raíz en 50/50/50, que la inserción no
duplica, como máximo 3 hijos, los límites 0–100, los efectos acumulativos, modulados por nivel
y combinados, el preorden, el BFS, el camino hoja→raíz, las 27 hojas, el reinicio, que los 5
finales sean alcanzables y la serialización. La eliminación, la revocación y el ajuste se
prueban en `tests/test_grafos.py` (`TestArbolEliminar`).

## Grafo: el mapa del país (`core/grafo.py` y `core/mapa.py`)

### La estructura
`Grafo` está hecho a mano con **listas de adyacencia**: `adyacencia = {vértice: {vecino: peso}}`.
Sirve dirigido o no dirigido, siempre ponderado; el juego lo usa no dirigido.

**Por qué un grafo.** El país son zonas unidas por vías, y entre dos zonas hay *varios* caminos
posibles con costos distintos. Eso no cabe en un árbol (en un árbol hay un solo camino entre dos
nodos) ni en una lista: hace falta una estructura con ciclos y pesos.

**Por qué listas de adyacencia y no una matriz.** El mapa es disperso (9 zonas, 15 vías de 36
posibles), los pesos cambian durante la partida y casi todo lo que se pregunta es "¿qué vecinos
tiene esta zona?", que aquí cuesta O(grado) en vez de O(V). Además un diccionario por vértice
guarda el peso junto al vecino, sin celdas vacías.

| Operación | Método | Costo | Uso en el juego |
|---|---|---|---|
| Insertar vértice / arista | `agregar_vertice`, `agregar_arista` | O(1) | armar el mapa |
| Eliminar arista / vértice | `eliminar_arista`, `eliminar_vertice` | O(1) / O(V) | (disponibles y probadas) |
| Cambiar un peso | `cambiar_peso` | O(1) | cada decisión y cada retén |
| Anchura por olas | `bfs_por_olas`, `saltos` | O(V + E) | hasta dónde llega la red de un jefe |
| Camino con menos saltos | `camino_con_menos_saltos` (BFS) | O(V + E) | **ruta corta** |
| Camino más barato | `dijkstra`, `camino_mas_barato` | O((V + E) log V) | **ruta segura** |
| Costo de un camino | `costo_de` | O(largo) | peligro de cada ruta |
| Profundidad, componentes | `dfs`, `componentes` | O(V + E) | (disponibles y probadas) |

### El mapa: 9 zonas reales de Colombia y 15 vías, peso = peligro
Bogotá (el palacio), el Meta, el Vichada, Casanare, Barrancabermeja, Medellín, Cartagena, Santa
Marta y La Guajira, cada una en su latitud y longitud reales (`core/mapa.py -> ZONAS`). El
presidente **cruza el país de sur a norte**: cada nivel sale de donde terminó el anterior
(`ORIGEN_NIVEL`): Bogotá → Vichada (nivel 1), Vichada → Medellín (nivel 2), Medellín → La Guajira
(nivel 3). Las vías directas son cortas pero peligrosas, así que en los tres niveles la ruta corta
y la segura son distintas (con el mapa limpio y con cualquier retén).

Se dibuja sobre un **mapa de Colombia con relieve en pixel art** (`render/mapa_colombia.py`): los
contornos reales de los 33 departamentos (DANE, simplificados con Douglas-Peucker por
`tools/simplificar_mapa.py` en `assets/mapa/colombia.json`), un modelo de elevación con las tres
cordilleras, la Sierra Nevada, Perijá, la Macarena y los volcanes, colores de atlas por altura y
por región (Amazonía, llano, Pacífico, Caribe, desierto de La Guajira), sombreado de relieve,
ríos principales, el mar con aguas someras y los países vecinos apagados.

- **Qué resuelve:** cómo llega el presidente a cada nivel y qué le cuesta. Sin el grafo no
  habría elección de ruta, la dificultad sería una tabla fija y las decisiones del árbol no
  cambiarían nada del nivel siguiente.
- **Dos rutas, dos algoritmos** (`Mapa.rutas`):
  - **Ruta segura** = Dijkstra sobre los pesos: el menor peligro total.
  - **Ruta corta** = BFS: el menor número de tramos, sin mirar los pesos.
- **Efecto de la ruta elegida** (`Partida.elegir_ruta`):
  - *Refuerzos:* por cada 2 puntos de peligro de más respecto a la ruta segura del mapa limpio
    llega 1 refuerzo enemigo extra al nivel, más 1 por cada jefe libre a 2 saltos o menos (tope
    2, 2 y 3 según el nivel). Los agrega `core/director.py` al plan aleatorio.
  - *Opinión:* cada tramo de más respecto a la ruta más corta resta 3 puntos al pueblo (el
    presidente llegó tarde). Se resta en el nodo actual del árbol.
- **Daños del jefe (BFS por olas):** las zonas a 1 y 2 saltos de la zona de un jefe son las que
  alcanza su red; se ven en la primera página del informe.
- **Azar:** al empezar la partida aparecen 1 o 2 *retenes ilegales* en vías al azar (+1 o +2).

Ejemplo con el mapa limpio:

| Nivel | Ruta segura (Dijkstra) | Ruta corta (BFS) |
|---|---|---|
| 1 | Bogotá → Meta → Vichada: 2 tramos, peligro 3, sin refuerzos, pueblo −3 | Bogotá → Vichada: 1 tramo, peligro 6, +2 refuerzos |
| 2 | Vichada → Casanare → Barrancabermeja → Medellín: peligro 7 | Vichada → Bogotá → Medellín: peligro 11, +2 |
| 3 | Medellín → Cartagena → Santa Marta → La Guajira: peligro 7 | Medellín → Barrancabermeja → La Guajira: peligro 10, +2 |

### Cómo se integran el árbol y el grafo (`core/partida.py`)
```
decisión ──► ÁRBOL.insertar ──► MAPA.aplicar_decision (cambia los pesos de las vías)
                                     │
elegir ruta ◄── Dijkstra y BFS ◄─────┘
     ├──► refuerzos extra ──► plan aleatorio del nivel siguiente
     └──► ÁRBOL.ajustar (opinión del nodo actual)
```
- Capturar o extraditar resta 1 al peligro de las vías de esa zona; extraditar además provoca
  represalias (+1) en otra vía al azar; liberar suma 2 y deja al jefe operando.
- Con esos pesos nuevos, Dijkstra puede cambiar de camino: si se libera a Don Concreto, la ruta
  segura hacia el Vichada deja de pasar por Medellín; y salir de la zona de un jefe libre es más
  peligroso.
- La historia de cada nivel (`core/historia.py`) cambia según el camino del árbol y muestra lo
  que calculó el grafo.
- Revocar la decisión elimina el nodo del árbol y restaura el mapa.

### Dónde se ve
- **Informe del nivel** (`scenes/historia.py`): el mapa arriba, **con zoom** sobre las zonas de la
  pantalla (`render/mapa_colombia.encuadre`), y el texto abajo. El departamento del jefe late.
  Página 1, las olas del BFS desde la zona del jefe (con los nombres del jefe y sus vecinos).
  Página 2, solo las dos rutas: la segura en **cian** y la corta en **magenta** (colores que no
  aparecen en el mapa), con borde oscuro; la elegida va sólida, se traza tramo por tramo y llega
  con una flecha; la otra va punteada; solo esas vías llevan número. Izquierda/derecha cambia
  de ruta. Lo ya recorrido en los niveles anteriores se ve en blanco.
- **Pantalla final**, página GRAFOS: todo el recorrido con zoom, un color por nivel, el peso de
  esas vías, jefes libres (X) y retenes.
- Fuera de Colombia todo va apagado (mar azul oscuro con una cuadrícula de meridianos y
  paralelos, países vecinos en gris pizarra) y el país lleva un contorno claro con sombra: se lee
  solo, a cualquier zoom. Los nombres y los pesos usan una fuente pequeña de 3 x 5 px
  (`render/fuente_mini.py`) y se colocan donde no tapen otro nombre, una zona ni una vía
  (`tests/test_graficos.py` lo comprueba en todos los niveles). El JSON de `capturas/` guarda la semilla, el mapa y las rutas.

`tests/test_grafos.py` cubre cada operación del grafo, las dos rutas y su efecto, y la unión con
el árbol (incluida la revocación).

## Componente aleatorio: refuerzos y suministros

Cada partida tiene una **semilla** nueva (`random.SystemRandom`). De ella salen los retenes del
mapa, las represalias y el **plan** de cada nivel (`core/director.py`). Los rangos están en los
datos de cada nivel (`levels/nivelN.py`, clave `"aleatorio"`):

| Nivel | Drones | Motos | Camionetas (blindaje) | Suministros | Motos por detrás |
|---|---|---|---|---|---|
| 1 · selva | 2–3 | 1–2 | 0 | 2–3 al azar | nunca |
| 2 · ciudad | 3–4 | 2–3 | 1 (7) | 2–3 al azar + 1 vida fija | 25 %, desde x = 1100 |
| 3 · frontera | 4–5 | 3–4 | 1–2 (8) | 2–3 al azar + vida y arma fijas | 40 %, desde x = 1100 |

El azar decide cuántos, cuáles y dónde (separados al menos 110 px); la tabla fija los rangos. La
ruta elegida en el mapa agrega más. Con la misma semilla el plan es idéntico: por eso el estado
se serializa con solo la semilla y el servidor y los clientes ven lo mismo. Los sicarios de a pie
siguen fijos, como antes.

**Ajuste de dificultad (nivel 3):** tenía 5–7 drones, 4–5 motos, 2–3 camionetas de blindaje 10 y
1–2 suministros, y el jefe 70 de vida. Ahora: −25 % de drones y motos, una camioneta menos y con
blindaje 8, ninguna moto por la espalda en los primeros 15 segundos (x < 1100), una vida y un
arma garantizadas a mitad de nivel, y el jefe con 60 de vida (−15 %). El nivel 2 también bajó un
poco (antes 3–5 drones, 2–4 motos, 1–2 camionetas de blindaje 8).

| Refuerzo (`core/vehiculos.py`) | Comportamiento | Cómo se supera |
|---|---|---|
| **Dron** (2 de vida) | Se pone sobre el jugador y suelta balas hacia abajo; a los 11 s se va | Disparar hacia arriba o en diagonal |
| **Moto** (2 de vida) | Cruza la pantalla a 128 px/s disparando al frente; salta huecos y escalones | Saltarla; agachado, sus balas pasan por encima |
| **Camioneta blindada** | Se planta a distancia y el tirador del techo dispara ráfagas apuntadas | Destruirla (suelta un arma) |

Todos avisan antes de entrar: sonido, mensaje y una flecha en el borde por donde vienen.

**Armas** (reemplazan a las letras): **disparo triple** y **disparo rápido** (una bala cada
0,07 s en vez de 0,16). Caen en paracaídas sobre suelo firme o las suelta una camioneta, y se
pierden al morir. La medalla da una vida. Los power-ups fijos de los niveles se conservan (el
tutorial del nivel 1 señala el primero), ahora con el dibujo de las armas.

### Simulador de dificultad (`tools/simular_partidas.py`)
```bash
python tools/simular_partidas.py              # 40 partidas con semilla por nivel
python tools/simular_partidas.py -n 100 --nivel 3
```
Un jugador automático juega N partidas por nivel y reporta la tasa de superación, cuántas llegan
al jefe y con cuántas vidas, y el resultado contra el jefe solo. **No es una persona:** contra
los jefes 1 y 2 pierde casi siempre aunque un jugador real los vence, así que sirve para comparar
versiones, no como dificultad absoluta. Con las semillas 1 a 40:

| Nivel 3 | Antes del ajuste | Después |
|---|---|---|
| Supera el nivel completo | 2 % | 22 % |
| Llega al jefe | 22 % | 57 % |
| Vidas al llegar al jefe | 0,5 | 1,5 |

## Historia antes de cada nivel (`core/historia.py`, `scenes/historia.py`)

Antes de cada nivel aparece el **informe de inteligencia**, con texto de máquina de escribir y,
detrás del texto, **el jefe del nivel grande y desvanecido** (bajo una capa oscura para que el
texto se lea): es el villano de la historia. El mapa queda despejado.

1. **Los daños:** qué le está haciendo el jefe a su zona (la selva talada y los ríos
   envenenados; la extorsión y las obras fantasma de la ciudad; el agua y el paso de la
   frontera). Añade una frase según lo que se hizo con el jefe anterior.
2. **La ruta:** se elige con izquierda/derecha entre la segura y la corta; el texto dice sus
   tramos, su peligro y su efecto (refuerzos y opinión).

El recuadro del texto se dimensiona por medición real (`HistoriaScene.lineas_que_caben`), y una
prueba mide el alto del texto contra el recuadro en los 3 niveles, con todas las variantes del
jefe anterior, las dos rutas y 12 mapas distintos.

## Tiempo límite

- **Decisión sobre el jefe:** 15 segundos (`settings.TIEMPO_DECISION`). Si se acaban, el jefe
  **escapa**, que cuenta como dejarlo libre. Los últimos 5 segundos suenan.
- **Revocar:** tras sellar la decisión hay 2,5 segundos para arrepentirse (una vez por partida).
- Abrir la ayuda detiene el reloj.

## Multijugador (`net/`, `scenes/multijugador.py`)

De 2 a 4 jugadores en la misma red, con arquitectura **cliente-servidor y servidor
autoritativo** sobre **sockets TCP**:

```
cliente 1 ──botones, votos──►  ┌──────────┐  ──estado──►  cliente 1
cliente 2 ──botones, votos──►  │ SERVIDOR │  ──estado──►  cliente 2
cliente 3 ──botones, votos──►  │ (Sesion) │  ──estado──►  cliente 3 ...
```

- **Fuera del menú desde el 2026-10-19** (se rehará como multijugador local con control NES).
  Antes: menú → MULTIJUGADOR. Un equipo elige CREAR PARTIDA (arranca el servidor en un
  hilo y muestra su IP); los demás eligen UNIRSE y escriben esa IP. Puerto 50505. En la sala
  cada uno elige su rol (izquierda/derecha) y marca LISTO; el anfitrión empieza.
- **Protocolo** (`net/protocolo.py`): cada mensaje es JSON con un prefijo de 4 bytes con su
  longitud, porque TCP entrega un flujo de bytes sin fronteras.
- **Servidor** (`net/servidor.py`): un solo hilo con sockets no bloqueantes. En cada vuelta (60
  por segundo) acepta conexiones, lee mensajes, avanza la sesión y envía instantáneas (30 por
  segundo en el nivel, 10 en las demás fases).
- **Reglas** (`net/sesion.py`, sin sockets y por eso fácil de probar): fases sala → informe →
  nivel → votación → resultado → final. El servidor guarda y sincroniza el estado de la partida,
  los jugadores, el mapa, los eventos, los puntajes y los turnos de votación.
- **Cliente** (`net/cliente.py`): manda botones y votos, y dibuja la última instantánea. No
  simula nada, así que todos ven lo mismo.
- Reutiliza lo que ya había: `EstadoJuego.update(dt, {id: acciones})` y `to_dict()`.

| Rol | Dentro del nivel | Además |
|---|---|---|
| **Presidente** | 3 corazones | Su voto vale doble y desempata |
| **General** | 4 corazones, disparo triple permanente, 8 % más lento | — |
| **Periodista** | Disparo rápido permanente, 12 % más veloz; con él en pie, las emboscadas se avisan con el doble de tiempo | — |
| **Influencer** | 2 corazones, 5 % más veloz, puntos ×1,5 | Cada decisión mueve la opinión un 25 % más |

- **Informe:** el anfitrión elige la ruta (arriba/abajo en la página de la ruta).
- **Votación:** al caer el jefe todos votan con el mismo reloj de 15 s. Si nadie vota, escapa.
  En un empate sin presidente gana la opción más dura (capturar, extraditar, liberar).
- **Resultado:** qué se decidió, el voto de cada uno y cómo quedó la opinión.
- **Puntaje:** cada jugador tiene el suyo (se ve en el HUD y en la tabla final); el final del
  país, que sale del árbol, es de todos.
- Si un cliente se desconecta, su personaje sale del nivel y los demás siguen. Si se cae el
  servidor, los clientes vuelven a la sala con un aviso.
- Todos usan el sprite del presidente; los distinguen el color del contorno y el número.
- En red no hay teléfono ni revocación.

`tests/test_red.py` prueba el protocolo (mensajes partidos, pegados y grandes), las reglas de
la sesión y partidas reales por TCP en `127.0.0.1`.

## Escena del teléfono (`scenes/phone.py` + `core/news.py`)

Entre niveles, el presidente revisa **PATRIANOTICIAS** en su teléfono mientras carga el
siguiente nivel. Si no tocas nada, el feed se desplaza solo y la escena sigue sola a los 10 s
(se puede saltar con Enter / A desde los 3 s). Con **arriba/abajo** (flechas o cruceta)
desplazas el feed a mano: deja de moverse solo y la escena espera a que pulses Enter / A,
para que leas a tu ritmo. El feed mezcla
titulares de **medios**, publicaciones de **influencers** y comentarios del **pueblo**, y a la
derecha la opinión popular se anima del valor anterior al nuevo, con la diferencia de cada barra.

- Los textos viven en `core/news.py`, en diccionarios fáciles de editar: al menos 3 variantes
  por decisión y categoría, con los marcadores `{jefe}`, `{lugar}` y `{nivel}`. Un comentario
  puede llevar autor fijo: `("DON EFRAÍN", "Voy a cerrar la tienda...")`.
- **Varían según el camino del árbol** (`contexto_de`): liberar por segunda vez usa textos
  más duros (*reincidente*); capturar después de haber liberado, *rectifica*; repetir la misma
  decisión, *racha*.
- El feed es **determinista**: el mismo camino produce siempre las mismas noticias.
- **Pulgar** (sprite `pulgar`, 2 fotogramas procesados desde `pulgar.jpeg` y `pulgar_flex.jpeg`):
  en reposo se ve extendido sobre la pantalla; mientras desplazas (o en cada toque automático)
  cambia al flexionado, y vuelve al extendido 100 ms después de soltar. La base (la muñeca) está
  fija y queda cortada por el borde inferior; la yema del flexionado cae en el punto de contacto
  (`CONTACTO` en `scenes/phone.py`). La yema de cada fotograma se guarda en
  `sprites.json → pulgar.yemas`. Los dos fotogramas usan la misma escala y se alinean por la base;
  el script avisa si las bases no miden lo mismo (hoja: `assets/sprites_pulgar_preview.png`).
- Todo es ficticio: medios, influencers, personas y criminales son inventados. El tono es
  satírico y no menciona personas ni partidos reales.
- `tests/test_noticias.py` comprueba las variantes, los marcadores, que la fuente pixel pueda
  dibujar cada carácter, el largo de los textos y que los nombres quepan en las tarjetas.

## Pantalla final (`scenes/ending.py` + `render/arbol_visual.py`)

Cuatro páginas, que se recorren con izquierda/derecha:

1. **Resultado:** el final obtenido, las 3 decisiones con su jefe, una gráfica de la evolución
   de la opinión (inicio → nivel 1 → 2 → 3), la opinión final y el puntaje total.
2. **Árbol:** los 40 nodos. Las hojas tienen el color de su final, la ruta elegida va resaltada
   en amarillo y cada arista lleva la letra de su decisión (C, E, L). Con **arriba/abajo** se
   cambia de modo y se anima el recorrido nodo a nodo:
   - *Ruta elegida*;
   - *Preorden* (`preorden()`, en profundidad);
   - *BFS* (`bfs()`, por niveles con una cola);
   - *Camino hoja > raíz*: `camino()` sube por los padres y al final se invierte.
3. **Finales:** las 27 hojas agrupadas en los 5 finales, con la regla de cada uno y cuántas
   hojas llevan a él.
4. **Grafos:** el mapa del país como quedó (peligro de cada vía), la ruta elegida hacia cada
   nivel con su peligro y sus refuerzos, los jefes libres y los retenes.

Para dibujar el árbol completo se usa una **copia** con los 40 nodos (`construir_completo()`);
el árbol de la partida no se modifica.

**Evidencia para la sustentación:** al terminar una partida se guardan en `capturas/` la
imagen del árbol (`arbol_<fecha>.png`, a 4×) y un JSON con el camino, el final, la opinión
por nivel, el puntaje, el árbol de la partida (`to_dict()`), la semilla, el mapa y las rutas.

## Sonido (`audio/`)

Casi todo el sonido se **sintetiza con numpy** al iniciar el juego (≈1,3 s), en estilo NES:
ondas de pulso, triángulo y ruido (`audio/sintesis.py`), a 44,1 kHz y en estéreo.
- **Ondas limpias:** los pulsos son de banda limitada (PolyBLEP), sin el chirrido del aliasing;
  el triángulo es escalonado como el de la NES. Al final, un filtro de salida circular (pasa
  bajos suave y corte de graves extremos) y un limitador suave: nunca satura y los bucles
  empalman sin clic.
- **18 efectos** con capas (chasquido + tono + golpe grave; explosiones con un filtro que se
  cierra): disparos, explosiones, golpe, salto, power-up, menús, sello de la decisión, logro,
  alerta de refuerzos, suministro y tic del reloj. Los que se repiten mucho (disparos, impactos,
  explosiones) tienen **variantes de tono** y un **tope de voces** (`gestor.MAX_VOCES`), así una
  ráfaga no tapa el resto.
- **8 temas en bucle, compuestos nota por nota** en `audio/musica_datos.py` (composición
  original): selva (La menor, heroico), ciudad (Re dórico, bajo sincopado), frontera (Mi frigio,
  a galope), jefe, decisión (con latido), noticias, final y una marcha de respaldo para el menú.
  Cada tema tiene secciones A y B con melodía, acordes (arpegio), bajo y batería
  (`"A4:2 C5:2 E5:4"` = notas en semicorcheas; cada compás suma 16). La melodía lleva vibrato en
  las notas largas y un **eco en estéreo** de corchea con puntillo, como en la NES.
- **2 fanfarrias** que no se repiten (`JINGLES`): victoria al derrotar al jefe (cabe en los 3 s
  antes de la decisión) y game over.
- **Menú: el Himno Nacional de Colombia en versión arcade** (58 s: introducción y coro). Suena
  **solo la melodía** (onda cuadrada) **y un bajo** de marcha (onda triangular); el bajo se apaga
  con `settings.HIMNO_CON_BAJO = False`. Las notas están **escritas a mano** en
  `audio/himno_datos.py`, compás por compás y en Do mayor para que se lean fácil
  (`"C5@0+1.5"` = Do, empieza en el pulso 0, dura pulso y medio); `TRANSPORTE` las lleva a Mi
  bemol mayor. Las toca `sintesis.himno()`, con vibrato en las notas largas y un eco suave. La música es de Oreste Síndici (1887), de dominio
  público; la melodía se cotejó con una partitura para flauta publicada en flutetunes.com.
  Para usar otra grabación, basta poner `assets/sonidos/musica_menu.ogg`.
- **Voz: "Bienvenido a la Patria Milagro"** (`assets/sonidos/bienvenida.wav`, 2,5 s). El clip
  original tenía dos frases; se transcribió con Whisper para saber cuál era cuál ("Creía que
  podía desafiar el Estado" de 0 a 1,9 s; "Bienvenido a la Patria Milagro" de 3,2 a 4,7 s) y
  `tools/limpiar_voz.py` recorta **solo la segunda**, sin los pitidos del radio, y le aplica
  puerta de ruido, ecualización y nivelado. `MEZCLA_ORIGINAL` regula cuánta música de fondo
  queda (0 = solo la voz separada con Demucs; 1 = el clip original).
- **Nunca suenan a la vez a todo volumen** (`Audio.presentar`): al entrar al menú y a la pantalla
  final **primero habla el presidente y la música arranca cuando termina la frase**. Si la música
  ya sonaba (al volver al menú desde Opciones), no se corta: baja al 15 %
  (`settings.VOLUMEN_ATENUADO`) mientras dura la frase. Si otra escena pide su música, la voz se
  calla.

Para reemplazar un sonido sin tocar el código, pon un archivo en `assets/sonidos/`:
`<efecto>.wav` / `.ogg` (por ejemplo `salto.wav`) o `musica_<tema>.ogg` (por ejemplo
`musica_jefe.ogg`). Los nombres están en `audio/sintesis.py` (`efectos()` y `TEMAS`). El volumen
de música y efectos se ajusta en Opciones. Si no hay tarjeta de sonido, el juego sigue en
silencio.

## Accesibilidad e inclusividad

- **Filtro CRT** (Opciones, apagado por defecto): líneas de barrido, rejilla de fósforo suave y
  esquinas oscurecidas, como un televisor de tubo (`render/filtros.mascara_crt`). Es una capa que
  se multiplica sobre la imagen ya escalada y se calcula una vez por tamaño de ventana.
- **Alto contraste** (Opciones): oscurece el fondo, pone un contorno blanco al presidente y uno
  amarillo a los enemigos, un aro a las balas enemigas y bordes blancos al suelo y las plataformas.
- **Filtro de daltonismo** (Opciones: protanopia, deuteranopia, tritanopia). Usa
  *daltonización* (Fidaner et al., 2005): no simula la deficiencia, **corrige** los colores
  (`render/filtros.py`). Se simula cómo ve la persona, se calcula la información de color que
  pierde y se traslada a canales que sí distingue; todo se reduce a una matriz 3×3. Medido con
  los colores del juego, aumenta la distancia entre los pares más parecidos (opinión y finales)
  en 5 de 6 casos; por ejemplo, en deuteranopia los finales pasan de 18 a 46.
- **Remapeo del control** y teclado siempre disponible.
- **Ayuda** (menú, pausa o F1 / SELECT) con 12 páginas (objetivo, controles, reglas, roles,
  significado de los indicadores, cómo se gana...), y tutorial contextual en el nivel 1.
- Los avisos sonoros de los refuerzos también son **visuales**: mensaje y flecha en el borde.
- La opinión se muestra con etiquetas (MED, INF, PUE) y números, no solo con colores.

## Motivación: logros y mensajes

- **11 logros** (`core/logros.py`): primera captura, extradición y liberación, disparo triple,
  100 sicarios, nivel sin perder vidas, jefe sin recibir daño, leer todo el teléfono, ver los 4
  recorridos del árbol, terminar una partida y descubrir los 5 finales. Al ganarlos aparece un
  aviso con sonido. Se consultan en el menú (LOGROS) y se guardan en `config/logros.json`.
- **Mensajes de ánimo** (`core/motivacion.py`) al reaparecer, en la fase 2 del jefe, al vencerlo
  y en el game over.
- Temblor de pantalla y cadena de explosiones al derrotar a un jefe, y cortina de rombos entre
  escenas (`render/transiciones.py`).
- **Respuesta a los golpes** (`render/efectos.py`, solo dibujo): bolas de fuego con núcleo
  blanco que terminan en humo, onda expansiva y escombros; sicarios que salen despedidos
  girando; casquillos que rebotan; polvo al saltar, aterrizar y correr; puntos que flotan
  (+100); humo de los escapes y del blindaje roto; brillo en las balas enemigas y estela en las
  propias; sombras bajo los pies; **pausa de impacto** (unos cuadros congelados al recibir un
  golpe, destruir la camioneta o vencer al jefe); el jefe se aclara al recibir un impacto en vez
  de volverse una silueta plana; y con un solo corazón, ese corazón parpadea en el HUD.
- **Animación por código** (`render/animacion.py`): el PNG del sicario trae una sola pose; a
  partir de ella se generan los pasos (las piernas se abren en tijera y el cuerpo rebota) y la
  respiración. El presidente también corre apuntando arriba o en diagonal. Los **jefes no se
  deforman** (con sus sacos largos, cortar el dibujo se veía como si se rompieran): se mueven
  enteros, con un rebote al caminar y un culatazo de 1 px al disparar.
- **Créditos** en el menú, con el equipo, la materia y el origen del arte y la música.

## Estado del desarrollo

- [x] (a) Ventana, escenas, entrada unificada, remapeo, ayuda y opciones
- [x] (b) Nivel 1 jugable: scroll, disparo en 8 direcciones, sicarios, power-ups, vidas, HUD y los 3 jefes
- [x] (c) Escena de decisión, árbol n-ario con pruebas y flujo completo de partida
- [x] (d) Escena del teléfono con noticias según el camino del árbol y opinión animada
- [x] (e) Niveles 2 (la ciudad) y 3 (la frontera), con validación automática de los datos
- [x] (f) Pantalla final con gráfica de opinión, árbol de 40 nodos con recorridos animados y evidencia en capturas/
- [x] (g) Accesibilidad (alto contraste, daltonización), sonido y música sintetizados, logros, mensajes de ánimo y fundidos
- [x] (h) Grafo del mapa del país (rutas con Dijkstra y BFS) integrado con el árbol; eliminación en el árbol (revocar)
- [x] (i) Componente aleatorio: refuerzos (dron, moto, camioneta), armas y suministros, retenes del mapa
- [x] (j) Historia antes de cada nivel con el jefe de fondo, tiempo límite en la decisión, jefe 1 con disparo en varias direcciones
- [x] (k) Multijugador local cliente-servidor con sockets, 2 a 4 jugadores con roles
- [x] (l) Himno escrito a mano (melodía y bajo) y voz de bienvenida, que suena antes que la música
- [x] (m) Dificultad de los niveles 2 y 3 ajustada en `levels/`, con simulador de partidas
- [x] (n) Pulido gráfico y sonoro: animación por código, efectos, terreno y atmósfera por nivel, transiciones, CRT, créditos, música compuesta y síntesis de banda limitada

## Lineamientos del laboratorio (`docs/lineamientos.pdf`)

| Requisito | Dónde está |
|---|---|
| Árboles: problema, variante, inserción, **eliminación**, recorridos | `core/decision_tree.py`; revocar en la escena de decisión; pantalla final |
| Grafos con función en el juego, operaciones y visualización | `core/grafo.py`, `core/mapa.py`; informe del nivel y página GRAFOS |
| Integración de grafos con árboles | `core/partida.py` (`decidir`, `elegir_ruta`, `revocar`) |
| Componente aleatorio que varía entre partidas | semilla por partida, `core/director.py`, retenes y represalias del mapa |
| Habilidad y decisiones con tiempo limitado | el nivel; reloj de la decisión |
| Indicadores que cambian durante la partida | opinión (medios, influencers, pueblo) y peligro de las vías |
| Puntaje individual y resultado general | puntaje por jugador; final del árbol |
| 2 a 4 jugadores con roles distintos | `settings.ROLES` |
| Multijugador local cliente-servidor con sockets | `net/` |
| Interfaz gráfica | todo se dibuja en la ventana; no hay modo consola |
| Componente inclusivo | alto contraste, daltonización, avisos visuales de eventos sonoros |
| Sistema de ayuda | 12 páginas y mensajes durante la partida |
| Elementos motivadores | sonido, animaciones, logros, mensajes, efectos al ganar o perder |
| Repositorio Git | **pendiente del equipo:** falta el primer commit y que cada integrante haga los suyos |

**Lo que queda sin cubrir.** El punto 7 del enunciado, *propagación de información*: quiénes
reciben una publicación, cuántos, qué tan rápido y con qué consecuencias, sobre un **grafo
social**. El equipo quitó la red social, así que el único grafo es el mapa. Lo más parecido que
queda es el BFS por olas de la influencia de cada jefe, que se muestra pero no propaga
publicaciones. El enunciado da el grafo social como una posibilidad ("podrán existir dos tipos
de relaciones"), pero describe la propagación como "una de las mecánicas principales".

El tema del enunciado (redes sociales en Ciudad Nova) tampoco es el de este juego; el equipo
conservó su propio tema.

