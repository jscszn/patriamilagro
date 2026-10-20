# Historial y pendientes — Patria Milagro

Resumen para retomar el proyecto sin releer conversaciones anteriores. Última actualización:
2026-10-19. El detalle técnico está en `docs/DOCUMENTACION_TECNICA.md` (el `README.md` es la presentación corta); este archivo cuenta **qué se decidió, por qué
y qué falta**. El enunciado del laboratorio está en `docs/lineamientos.pdf`.

## Estado

Las 7 etapas del plan original están terminadas, más las mejoras visuales y, desde el
2026-10-13, lo que pedían los lineamientos y no estaba (etapas h–l):

| Etapa | Contenido |
|---|---|
| a | Ventana 256x224 escalada, máquina de escenas, entrada unificada (teclado + control NES), remapeo, ayuda, opciones |
| b | Nivel jugable: física, scroll, disparo en 8 direcciones, sicario raso, power-ups, vidas, HUD, 3 jefes (máquinas de estados en `core/boss.py`) |
| c | Escena de decisión + árbol n-ario (`core/decision_tree.py`) con pruebas + flujo completo de partida |
| d | Teléfono con noticias según el camino del árbol (`core/news.py`), desplazamiento manual y pulgar animado |
| e | Niveles 2 (ciudad) y 3 (frontera) como datos, con validación automática (grafo de alcanzabilidad) |
| f | Pantalla final: gráfica de opinión, árbol de 40 nodos con recorridos animados, evidencia en `capturas/` |
| g | Alto contraste, filtro de daltonismo (daltonización), sonido y música sintetizados, 11 logros, mensajes de ánimo |
| extra | Sprites de IA procesados (`tools/procesar_sprites.py`), poses del presidente, decoración animada de los fondos, menú épico con busto |
| h | Grafo hecho a mano (`core/grafo.py`): el mapa del país, unido al árbol en `core/partida.py`. Antes de cada nivel se ELIGE la ruta: segura (Dijkstra) o corta (BFS); cambia refuerzos y opinión. Eliminación en el árbol = revocar la decisión |
| i | Azar con semilla por partida: refuerzos (dron, moto, camioneta blindada), armas (triple y rápida) y suministros en paracaídas (`core/director.py`, `core/vehiculos.py`); retenes y represalias del mapa |
| j | Informe con la historia de los daños antes de cada nivel y el jefe desvanecido detrás del texto; reloj de 15 s en la decisión; jefe 1 con barrido en varias direcciones y 52 de vida |
| k | Multijugador local de 2 a 4 jugadores con roles, cliente-servidor por sockets TCP (`net/`) |
| l | Himno Nacional escrito a mano (melodía + bajo opcional) en el menú y voz "Bienvenido a la Patria Milagro"; primero la voz y después la música |
| m | Dificultad por nivel en `levels/` (clave `"aleatorio"`), niveles 2 y 3 suavizados y simulador `tools/simular_partidas.py` |

Pruebas: **253 tests, todos en verde** (`python -m unittest discover -s tests -t .`), unos 24 s.

## Cómo retomar

```bash
cd PatriaMilagro
.venv/bin/python main.py                  # jugar
.venv/bin/python main.py --arena          # cada nivel empieza frente al jefe (rápido para probar)
.venv/bin/python main.py --nivel 3        # directo a un nivel
.venv/bin/python -m unittest discover -s tests -t .
.venv/bin/python main.py --headless 900   # prueba sin ventana
.venv/bin/python tools/procesar_sprites.py                       # regenera sprites desde assets/sprites_raw/
.venv/bin/python tools/procesar_sprites.py --redetectar-rasgos   # recalcula los ojos del presidente
.venv/bin/python tools/procesar_sprites.py --recalcular-paleta   # recalcula la paleta de 24 colores
.venv/bin/python tools/probar_control.py                         # IDs de botones del control NES
.venv/bin/python -m net.servidor                                 # servidor dedicado (opcional; el menú ya lo crea)
.venv/bin/python tools/limpiar_voz.py                            # regenera assets/sonidos/bienvenida.wav
.venv/bin/python tools/simular_partidas.py -n 40                 # tasa de superación por nivel (jugador automático)
```
Para probar el multijugador en un solo equipo: abrir el juego dos veces; en una, MULTIJUGADOR →
CREAR PARTIDA; en la otra, UNIRSE con `127.0.0.1`.

Entorno: Python 3.9 del sistema, con `.venv` (pygame-ce 2.5.6 + numpy). El código es compatible
con 3.9: no usar `match` ni `X | Y` en tipos sin `from __future__ import annotations`.

## Decisiones tomadas (y por qué)

- **Nombre del presidente: siempre "A. Milagro"** (nunca el nombre completo).
- **Personaje y escenarios ficticios.** Medios, influencers, criminales y personas son inventados; no se mencionan personas ni partidos reales.
- **Un solo enemigo común (sicario raso)**, idéntico en los 3 niveles (`settings.SICARIO`). La dificultad sale solo de cuántos hay y dónde aparecen (19 / 33 / 42).
- **Sicarios que persiguen:** se dan la vuelta si el jugador los pasa, aceleran (95 px/s) si quedan a más de 90 px detrás, saltan escalones y los que entran por detrás buscan suelo firme.
- **3 corazones por vida.** Una bala de sicario quita 1 y una de jefe quita 2, para que "balas más dañinas" signifique algo. En Super C un golpe mata; se cambia en `settings.JUGADOR["salud"]`.
- **Jefe 1 (fusil a 56 px de altura):** la ráfaga alta sale del fusil y castiga saltar; la baja va a ras de suelo y obliga a saltar.
- **Asignación de jefes:** nivel N = `jefe_N.png` (1 fusil, 2 calvo de traje blanco, 3 sombrero y puro).
- **Sprites del presidente:**
  - Todas las poses usan una escala fija (`PX_POR_PIXEL = 974/38`) y comparten lienzo y ancla en los pies.
  - El idle es una pose más. "Quieto" usa el idle, y "disparar" se muestra solo mientras se dispara.
  - La bala sale de la boca del arma de cada pose (`sprites.json → jugador.bocas`).
  - El ojo se pinta por código después de cuantizar (`sprites.json → jugador.rasgos`). Las caras a 40 px no conservan rasgos solas; se probó subir a 48/56 px (`tools/prueba_caras.py`) y **se decidió quedarse con 40 px**.
  - El traje está unificado con la rampa de `disparar`.
- **Paleta congelada** en `assets/paleta.json`: reemplazar una imagen no cambia los colores de los demás sprites.
- **Pulgar del teléfono:** el flexionado sale −17 % más chico, porque su JPG tiene otra resolución. El script lo avisa; **el usuario decidió dejarlo así**.
- **Teléfono:** si el jugador desplaza el feed a mano, no avanza solo; espera Enter/A.
- **Menú:** se agregó la opción "LOGROS", que no estaba en la especificación original. Si se quiere el menú original, se puede mover dentro de Ayuda.
- **Daltonismo:** se corrige con daltonización, no con simulación. En tritanopia los tonos cambian mucho, y es lo esperado. Medido, mejora la distinción de colores en 5 de 6 casos.
- **Tema del juego (2026-10-13):** el enunciado pide "Alcalde Digital" (redes sociales). **El usuario decidió conservar Patria Milagro** y cumplir solo los requisitos técnicos (estructuras, azar, multijugador...). No volver a proponer el cambio de tema.
- **Menú (2026-10-19):** JUGAR, AYUDA, OPCIONES, LOGROS, SALIR. Se quitó MULTIJUGADOR.
- **Multijugador fuera del menú (2026-10-19):** el usuario lo trabajará al final y lo quiere como
  multijugador **local con controles NES**, con un segundo personaje y sus propios sprites. El
  código en red (`net/`, `scenes/multijugador.py`, roles) se dejó en su sitio, sin acceso desde el
  menú, porque no hay commits y borrarlo no se podría deshacer. Sus páginas de ayuda se quitaron.
- **Revocar se queda (2026-10-19):** el usuario pidió quitarlo y luego lo restauró al recordar que
  es la eliminación en el árbol que piden los lineamientos. No volver a quitarlo.
- **Mapa del informe rehecho (2026-10-19):** el usuario veía las rutas segura y corta encimadas.
  Causa: el mapa era muy plano (232x46 px) y las vías desde el palacio salían casi paralelas
  (3 grados entre algunas, y 2 cruces). Cambios:
  - Nuevas posiciones en `core/mapa.py -> ZONAS`, salidas de una búsqueda: sin cruces y, en las 17
    parejas segura/corta que salen al jugar, las rutas se abren ≥17° (prueba en `tests/test_grafos.py`).
  - En LA RUTA el mapa es más alto (114 px) y el texto más corto (`AREA_MAPA_RUTA`, `CAJA_TEXTO_RUTA`).
  - Cada ruta tiene SIEMPRE su color (segura cian, corta naranja); la elegida va gruesa y la otra
    punteada; la leyenda muestra las dos con su peligro.
  - `dibujar_mapa(..., simple=True)`: vías tenues sin números; solo pesan las dos rutas, del lado
    contrario a la otra ruta. Zonas fuera de las rutas apagadas. Nombres al costado de cada zona,
    en el lado que no cruza vías (`_cajas_nombres`), con fondo oscuro.
  - Se quitó "F1: AYUDA" del informe (F1 sigue funcionando). La pantalla final (GRAFOS) muestra
    todos los pesos, ahora en recuadros, con un mapa algo más alto; sigue siendo densa.
- **Azar con semilla:** todo lo aleatorio sale de `Partida.semilla` (nueva en cada partida). Sin semilla (`EstadoJuego.nuevo(n, jugadores)`) no hay refuerzos: así las pruebas de lógica siguen siendo deterministas.
- **Los sicarios de a pie siguen fijos** en los datos de cada nivel; lo aleatorio se suma encima. Los power-ups fijos también se conservaron (el tutorial del nivel 1 señala el primero).
- **Camioneta:** no se puede saltar (mide 54 px y el salto cubre unos 37): hay que destruirla. Nivel 1 nunca tiene camionetas.
- **Jefe 1:** el barrido quita 1 corazón (la ráfaga, 2) y va al 75 % de velocidad, para que sea "pasable".
- **Tiempo agotado al decidir = el jefe escapa** (cuenta como liberar).
- **Revocar** vive en la escena de decisión: tras sellar hay 2,5 s para arrepentirse con X / B, una vez por partida. Elimina el nodo del árbol, restaura el mapa y cuesta opinión (medios −6, influencers −4, pueblo −4). Solo en un jugador.
- **Servidor autoritativo con un solo hilo** y sockets no bloqueantes: sin candados sobre el estado. El cliente no simula ni interpola.
- **Roles:** todos usan el sprite del presidente (pedido del usuario: sus sprites no cambian); se distinguen por color de contorno y número.
- **La voz se oye cada vez que se entra al menú** (pedido literal del usuario) y al llegar al final. **Nunca a la vez que la música a todo volumen:** primero la frase y luego arranca el tema; si el tema ya sonaba, baja al 15 % mientras dura (`Audio.presentar`).
- **`.gitignore` deja fuera los MP3 originales** (`assets/sonidos_raw/*.mp3`): son grabaciones de terceros y el juego no las usa.

- **Sin red social (2026-10-13, segunda sesión):** el usuario probó la pantalla de propagación de noticias y pidió quitarla por completo. Se eliminaron `core/red_social.py`, `scenes/red.py`, los rumores y la fase de red del multijugador. No volver a proponerla. Consecuencia aceptada: el punto 7 de los lineamientos (propagación por un grafo social) queda sin cubrir; está dicho en `docs/DOCUMENTACION_TECNICA.md`.
- **El mapa es el único grafo y por eso debe pesar:** se agregaron vías directas peligrosas desde el palacio para que la ruta corta (BFS) y la segura (Dijkstra) sean distintas. Segura = menos refuerzos pero llega tarde (pueblo −3 por tramo de más); corta = a tiempo pero más refuerzos.
- **Himno escrito a mano:** el usuario oyó la transcripción automática y sonaba a "varias canciones a la vez". Ahora son 26 compases a mano en `audio/himno_datos.py` (melodía cotejada con una partitura de flauta publicada; bajo deducido de la grabación), solo melodía + bajo. `settings.HIMNO_CON_BAJO` apaga el bajo.
- **Voz: solo el segundo tramo del clip.** Whisper: 0–1,9 s "Creía que podía desafiar el Estado"; 3,2–4,7 s "Bienvenido a la Patria Milagro". Se usa el segundo, sin los pitidos. La voz separada con Demucs se entendía peor que el original (medido con Whisper), así que se mezcla 50/50 (`MEZCLA_ORIGINAL`).
- **Roles sin red:** periodista = disparo rápido + avisa las emboscadas con el doble de tiempo; influencer = puntos ×1,5 + cada decisión mueve la opinión un 25 % más.
- **Dificultad en `levels/`:** los rangos de refuerzos ya no están en `settings.py`. El nivel 3 bajó (−25 % drones y motos, una camioneta menos y blindaje 8, sin motos por la espalda antes de x = 1100, vida y arma fijas a mitad de nivel, jefe 3 con 60 de vida) y el 2 un poco. Los sicarios fijos no se tocaron.

- **README corto (2026-10-20):** `README.md` es la presentación (equipo: Jose Castro, Santiago
  Gómez, Mariana Gutiérrez, Daniela Idarraga; intención; tabla de lineamientos). El detalle pasó a
  `docs/DOCUMENTACION_TECNICA.md`. Decisiones del usuario: el juego es **una sátira ficticia
  inspirada en la realidad**; el tema **sí cumple** los lineamientos (no volver a discutirlo); la
  propagación se presenta como BFS del mapa + teléfono, aclarando que no hay grafo social ni
  noticias verdaderas/falsas; el **multijugador se juega con un control NES por jugador** y se
  habilita cuando lleguen los controles (dos jugadores en un teclado sería posible, a decidir).

## Pendiente

### 1. Entrega: lo que solo puede hacer el equipo
- **Repositorio Git:** `git init` y `.gitignore` ya están; **no hay ningún commit**. Los lineamientos piden commits de cada integrante en cada entrega (2.ª: 19–23 oct 2026; final: 16–20 nov 2026; Feria Gamer: 26 nov 2026).
- **Multijugador local con control NES** (lo último que se hará): segundo personaje y sus sprites.
- **Sprites de refuerzos (2026-10-19):** dron (20 px), moto (32) y camioneta (44) procesados con
  `--solo dron,moto,camioneta` (no toca los existentes; verificado con checksums). **Al usuario le
  gustaron así**, con la paleta congelada. Las balas de la camioneta salen del fusil del tirador
  (`sprites.json -> camioneta.boca`).
- **Armas y vida: se quedan con el dibujo por código** (decisión del usuario, 2026-10-19). Sus JPG
  siguen en `sprites_raw/`, pero se quitaron de `CONFIG` y de `sprites.json` no tienen PNG.
- **Cajas de los refuerzos corregidas (2026-10-20):** el usuario vio que las motos solo morían
  agachado. La bala de pie sale a 27 px del suelo y la caja de la moto medía 22. Ahora: dron 28×14,
  moto 32×28, camioneta 62×34 (`settings.VEHICULOS`); la bala de la moto sigue a 26 px (agachado la
  esquiva) y el salto la pasa. Pruebas nuevas en `tests/test_refuerzos.py`.
- **Presidente acostado (2026-10-20):** el usuario reemplazó `presidente_agachado.jpeg` por una
  pose boca abajo. Mide 46×12 sobre el suelo y su largo es 109 % de la altura del idle (dentro del
  15 %). El script la trata como `POSES_HORIZONTALES`: ancla en el centro del cuerpo, zapatos
  protegidos por columnas y `"detalles": 0.3` para que el fusil y la banda no se vuelvan negros.
  El lienzo común creció de 35 a 46 px: las demás poses quedaron idénticas (comparadas píxel a
  píxel) y los rasgos guardados se desplazan con el ancla. Caja acostada: 36×12, centrada donde
  estaba de pie (si choca con una pared, se corre). Bala a 5 px del suelo. Le pasan por encima las
  balas de sicarios y motos; la ráfaga baja del jefe 1 todavía le pega (obliga a saltar).
- **Jefe 2 embiste agachado (2026-10-20):** caja de 32 px de alto desde `preparar` hasta que se le
  pasa `aturdido` (`settings.JEFES[2]["alto_embestida"]`); se dibuja aplastado (`escala` en
  `render/sprites.py`). Hay que saltar cuando está a ~60–90 px: unos 0,2 s quieto, 0,27 s saltando
  hacia él. Pegado a la pared no hay dónde caer (frena debajo). Falta probarlo jugando.
- **Cara acostada retocada (2026-10-20):** la reducción la dejaba como tablero (piel y barba
  alternadas). `sprites.json -> jugador.rasgos.agachado` ahora trae retoques `"piel"` y `"pelo"`
  (listas de puntos, nuevos en `tools/procesar_sprites.py`) y el ojo en [32, 34]: el mismo patrón
  de 3x3 de piel con el ojo al centro que las poses de pie.
- **Pantalla final sin textos encimados (2026-10-20):** modos "BFS" y "HOJA > RAÍZ" (el nombre largo
  chocaba con "ARRIBA/ABAJO: MODO"). En GRAFOS los números de Puerto–Ciudad y Llanos–Selva (vías de
  ~16 px) no tenían lugar y tapaban "PUERTO": `_dibujar_pesos` prueba más posiciones y las vías
  cortas eligen primero. Revisado con un detector en 18 144 dibujos (216 partidas, todas las
  páginas, modos y pasos de la animación): ningún texto se cruza con otro ni con una zona.
- **Pantalla final con más aire (2026-10-19):** pie separado por una línea (`LIMITE_CONTENIDO`), el
  modo y su ayuda en una línea, finales separados y la regla de orden arriba, semilla dentro del
  marco del grafo. Una prueba dibuja el peor caso y verifica que nada invade el pie.
- **Sustentación:** todos los integrantes deben poder explicar árbol, grafo y mecánicas (`docs/DOCUMENTACION_TECNICA.md`, secciones "Árbol", "Grafo: el mapa del país" y "Multijugador"), y saber decir que la propagación por grafo social no se hizo.

### 2. Probar a mano (nadie lo verificó todavía)
- **El usuario jugó la primera versión del 2026-10-13** y de ahí salieron las correcciones de la segunda sesión. Lo de la segunda sesión se verificó con pruebas, capturas y mediciones, **no jugando ni escuchando**:
  - **El himno escrito a mano:** hay que oírlo. Si se quiere otra cosa, `assets/sonidos/musica_menu.ogg` lo reemplaza.
  - **La voz:** Whisper la transcribe como "Bienvenido a la Patria Milano": la última palabra ya viene poco clara en la grabación original. Perillas en `tools/limpiar_voz.py` (`MEZCLA_ORIGINAL`, `ECO`, `INICIO`, `FIN`).
  - **Dificultad del nivel 3:** el simulador mejora (llega al jefe 22 % → 57 %; supera 2 % → 22 %), pero el jugador automático no es una persona: falta que el usuario lo pase. Si sigue difícil, tocar `levels/nivel3.py → "aleatorio"`, los sicarios fijos (`"enemigos"`, 42) o `settings.JEFES[3]`.
  - **El jugador automático pierde siempre contra los jefes 1 y 2** (el usuario sí los pasó): sus tasas solo sirven para comparar versiones.
  - **Multijugador entre dos equipos distintos** (solo se probó en `127.0.0.1`): firewall, IP de la red, 3 y 4 jugadores.
- **Sonido real:** solo se verificó que se genera y cambia de tema. Ajustar en `audio/sintesis.py → TEMAS` si algo molesta.
- **Control NES físico:** los IDs por defecto (A=1, B=2, SELECT=8, START=9) son una suposición. Usar `tools/probar_control.py` o Opciones → Configurar control.
- **Dificultad con una persona real**, sobre todo en los niveles 2 y 3. Un bot que no esquiva llega a todos los jefes y pierde ahí.
- Alto contraste y filtros de daltonismo con usuarios reales.

### 3. Avisos conocidos sobre el arte y el audio (no son errores de código)
- **La voz de bienvenida es de una persona real** (el archivo original la identifica como un político colombiano, en una nota de prensa). Junto con el parecido de la cara, contradice la decisión de "personaje ficticio": conviene que el equipo lo tenga presente antes de la sustentación y la feria.
- **La cara de las poses nuevas se parece a la de un presidente real de la región.** La especificación pide un personaje ficticio, así que conviene cambiar rasgos antes de la sustentación (canas, bigote, gafas).
- **Jefe 2 y jefe 3 se parecen** (los dos de traje blanco con cadena de oro).
- **Detalles de las poses:** en "herido" la bala sale de la boca de "disparar"; al correr en diagonal las piernas no se mueven (no hay pose); en "arriba" la boca queda ~2 px bajo la mira.

### 4. Limitaciones conocidas del multijugador
- Sin interpolación: el cliente dibuja 30 instantáneas por segundo tal como llegan.
- En red no hay teléfono, revocación ni logros propios del modo; el game over de todos termina la partida. La ruta la elige el anfitrión.
- La cámara sigue al jugador más adelantado; a los rezagados los empuja el borde izquierdo.
- Un jugador eliminado vuelve en el nivel siguiente con 1 vida.
- La IP se escribe con el teclado (con el control NES no se puede).

### 5. Ideas opcionales
- Animar al sicario de la moto y al tirador de la camioneta; más cuadros para los refuerzos.
- Un segundo tipo de respuesta de la camioneta (retirarse, embestir).
- Logros para lo nuevo (derribar drones, tomar la ruta corta, ganar en red). Hoy siguen siendo 11.
- Más fotogramas: correr apuntando en diagonal, agachado tumbado, animación del sicario, poses de los jefes.
- Guardar y cargar partida: `Partida.to_dict()` ya existe.
- Pantalla de créditos, que incluya las licencias si se usan recursos de terceros.
- Mano del teléfono como sprite (se quitó a pedido; hoy solo está el pulgar).

## Archivos que genera el juego (no son código)
- `assets/sonidos/bienvenida.wav`: salida de `tools/limpiar_voz.py` (parte de `assets/sonidos_raw/bienvenida_original.wav`, `bienvenida_voz.wav` y `bienvenida_radio.wav`; los dos últimos se separaron con Demucs fuera del proyecto). `audio/himno_datos.py` NO se genera: está escrito a mano.
- `config/opciones.json`, `config/gamepad.json`, `config/logros.json`: preferencias y progreso del jugador.
- `capturas/arbol_<fecha>.png|json`: evidencia del árbol al terminar cada partida (para la sustentación).
- `assets/sprites/*.png`, `assets/sprites.json`, `assets/paleta.json`: salida de `tools/procesar_sprites.py` (no editar los PNG a mano; editar la configuración y volver a ejecutar el script).
- Hojas de revisión: `assets/sprites_preview.png`, `sprites_presidente_preview.png`, `sprites_pulgar_preview.png`, `prueba_caras.png`.

## Mapa rápido
| Quiero cambiar... | Archivo |
|---|---|
| Stats del jugador, sicario, jefes | `settings.py` |
| Cuántos refuerzos y suministros salen por nivel | `levels/nivelN.py` → `"aleatorio"` |
| Vida, velocidad y disparo de dron, moto y camioneta | `settings.VEHICULOS` y `core/vehiculos.py` (`MAQUINAS`) |
| Roles del multijugador | `settings.ROLES` |
| Tiempo de la decisión; ventana para revocar | `settings.TIEMPO_DECISION`; `scenes/decision.py` → `VENTANA_REVOCAR` |
| Zonas, vías, peligro y efecto de las rutas | `core/mapa.py` (`ZONAS`, `VIAS`, `OPINION_POR_TRAMO`, `PELIGRO_POR_REFUERZO`) |
| Penalización por revocar; fuerza del influencer | `core/partida.py` (`PENALIZACION_REVOCAR`, `AMPLIFICACION_INFLUENCER`) |
| Historia de cada nivel | `core/historia.py` |
| Reglas de la partida en red | `net/sesion.py` |
| Notas del himno; bajo sí o no; mezcla de la voz | `audio/himno_datos.py`; `settings.HIMNO_CON_BAJO`; `tools/limpiar_voz.py` |
| Opacidad del jefe en el informe | `scenes/historia.py` (`OPACIDAD_JEFE`, `OPACIDAD_VELO`) |
| Patrones de los jefes | `core/boss.py` (`MAQUINAS`) |
| Efectos de las decisiones y finales | `core/decision_tree.py` (diccionarios al inicio y `FINALES`) |
| Textos de las noticias | `core/news.py` |
| Diseño de los niveles y decoración | `levels/nivel1.py`, `nivel2.py`, `nivel3.py` |
| Logros y mensajes de ánimo | `core/logros.py`, `core/motivacion.py` |
| Música y efectos | `audio/sintesis.py` |
| Posición de los ojos del presidente | `assets/sprites.json → jugador.rasgos` (y volver a ejecutar el script) |
| Recorte del busto del menú | `tools/procesar_sprites.py → BUSTO_MENU` |
| Textos de ayuda | `scenes/help.py` |
