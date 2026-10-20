# Patria Milagro

Videojuego de acción lateral en pixel art, al estilo de los clásicos de NES, hecho en Python con
pygame-ce para el laboratorio de **Estructura de Datos II** (Universidad del Norte).

**Equipo:** Jose Castro · Santiago Gómez · Mariana Gutiérrez · Daniela Idarraga

## La idea

El presidente A. Milagro recorre el país persiguiendo a tres jefes criminales. Al vencer a cada
uno tiene 15 segundos para decidir qué hacer con él: **capturarlo, extraditarlo o dejarlo libre**.
Después revisa su teléfono y ve cómo reaccionan los **medios**, los **influencers** y el **pueblo**.

Queremos mostrar que **una decisión pública nunca es neutra**. El mismo hecho se cuenta distinto
según quién lo publique, la opinión se acumula y lo que se decide hoy cambia el camino de mañana.
El jugador no responde preguntas: aprende viendo las consecuencias en las noticias, en la opinión,
en el mapa y en el final que obtiene.

> Patria Milagro es una sátira: está inspirada en la realidad, pero su historia, sus personajes,
> medios, influencers y criminales son ficticios.

## Cómo jugar

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

| Acción | Teclado | Control NES |
|---|---|---|
| Mover / apuntar | Flechas | Cruceta |
| Saltar · Confirmar | Z | A |
| Disparar · Volver | X | B |
| Pausa | Enter / Esc | START |
| Ayuda | F1 / Tab | SELECT |

Pruebas: `python -m unittest discover -s tests -t .`

## Cómo cumple los lineamientos

Partimos del enunciado *Alcalde Digital* y llevamos sus mecánicas a nuestra propia historia. Lo
que pide el laboratorio está, con estos cambios de forma:

| Lineamiento | En Patria Milagro |
|---|---|
| **Árbol** (problema, variante, inserción, eliminación, recorridos) | Árbol n-ario de decisiones (`core/decision_tree.py`): cada nodo es una decisión y guarda la opinión acumulada. Sus 27 hojas llevan a 5 finales. Se inserta al decidir y se elimina al **revocar** una decisión. La pantalla final anima el preorden, el BFS y el camino de la hoja a la raíz. |
| **Grafo** con función real y visualización | Grafo ponderado hecho a mano (`core/grafo.py`): el **mapa del país** con 8 zonas y 16 vías. El peso de cada vía es su peligro. Antes de cada nivel el jugador elige la **ruta segura** (Dijkstra) o la **ruta corta** (BFS), y esa elección cambia los enemigos y la opinión. Se ve en el informe de cada nivel y en la pantalla final. |
| Integración árbol + grafo | Cada decisión del árbol cambia el peligro de las vías, y la ruta elegida en el grafo ajusta la opinión del nodo actual (`core/partida.py`). |
| Grafo de la ciudad | El mapa del país cumple ese papel: zonas como vértices y vías como aristas. |
| Propagación de información | **Adaptada en dos partes.** *Por el grafo:* antes de cada nivel, un BFS sale de la zona del jefe y el mapa muestra en olas hasta dónde llegan sus daños (su zona, a 1 salto y a 2 saltos). Si un jefe queda libre, sus vías se vuelven más peligrosas y cada jefe libre a 2 saltos o menos trae refuerzos al nivel. *En el teléfono:* después de cada decisión, medios, influencers y pueblo cuentan el mismo hecho a su manera y la opinión cambia. Las noticias no viajan por un grafo de ciudadanos y no hay publicaciones verdaderas o falsas. |
| Eventos aleatorios | Cada partida tiene una semilla nueva: retenes en el mapa, represalias, drones, motos, camionetas blindadas y suministros en paracaídas. |
| Habilidad y tiempo limitado | Los niveles son de acción y la decisión sobre el jefe tiene un reloj de 15 s (si se acaba, el jefe escapa). |
| Indicadores de la ciudad | Opinión de medios, influencers y pueblo (0–100), más el peligro de cada vía. |
| Elección final | En lugar de elegir alcalde, el país juzga al presidente: el final (*del pueblo*, *de mano dura*, *diplomático*, *equilibrista* o *cuestionado*) sale del camino recorrido en el árbol. |
| Puntaje individual y resultado general | En el multijugador, cada jugador tiene su puntaje y el final es de todos. Con un jugador, el puntaje es el suyo y el final, el del país. |
| Roles (2 a 4 jugadores) | En el multijugador: Presidente, General, **Periodista** (avisa antes de las emboscadas) e **Influencer** (sus decisiones mueven más la opinión). |
| Multijugador cliente-servidor con sockets | Servidor autoritativo sobre TCP en `net/`. Se juega con **un control NES por jugador**, así que se habilitará en el menú cuando el equipo tenga los controles. Hasta entonces el juego es para un jugador. |
| Interfaz gráfica | Todo se ve en la ventana: niveles, mapa, teléfono con noticias, árbol y gráficas. |
| Inclusividad | Alto contraste, filtros que corrigen los colores para daltonismo y aviso visual (mensaje y flecha) cuando llega un refuerzo, que también se anuncia con sonido. |
| Ayuda | Sección AYUDA de 12 páginas, tutorial en el nivel 1 y mensajes durante la partida. |
| Motivación | Música y efectos estilo NES, 11 logros, mensajes de ánimo y efectos al ganar o perder. |

## Más información

- [`docs/DOCUMENTACION_TECNICA.md`](docs/DOCUMENTACION_TECNICA.md): arquitectura, árbol, grafo,
  multijugador, niveles, sonido y herramientas, en detalle.
- [`docs/lineamientos.pdf`](docs/lineamientos.pdf): enunciado del laboratorio.
- [`HISTORIAL.md`](HISTORIAL.md): decisiones de diseño y pendientes.
