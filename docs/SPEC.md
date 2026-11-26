# Especificación — whyfish

## 1. Flujos de usuario

### 1.1 Jugar
- Elegir color (blancas / negras / aleatorio) y nivel del bot.
- Nivel del bot: presets con nombre (p. ej. "Principiante ~800", "Club ~1500",
  "Fuerte ~2000", "Máximo"). Implementación: `UCI_LimitStrength` + `UCI_Elo` donde el
  motor lo permita; por debajo del Elo mínimo soportado, `Skill Level` y tiempo/profundidad
  reducidos. Calibración en `config.py`.
- Sin reloj ni control de tiempo (descartado: es una herramienta de aprendizaje).
- Durante la partida: sin ayudas por defecto. Opciones activables: deshacer jugada,
  pista (muestra la pieza a mover, no la casilla destino).
- Abandonar / ofrecer tablas. Fin por mate, ahogado, repetición, 50 jugadas, material insuficiente.
- Al terminar: botón **"Analizar partida"**.

### 1.2 Importar
- Pegar o subir un **PGN** (primera partida, línea principal; admite `[SetUp]`/`[FEN]`), o
  (fase posterior) importar desde Lichess/Chess.com por usuario. Un FEN suelto no se importa:
  para eso está "Nueva partida desde FEN".
- El color del usuario se indica o se detecta comparando `PLAYER_NAME` con las cabeceras
  `White`/`Black`; si no se puede, la app pregunta.
- Mismo flujo de análisis que una partida jugada (las importadas siempre son analizables).

### 1.3 Revisión (Game Review)
- **Mientras se analiza**, el tablero ya muestra la partida y el panel la barra de progreso.
- **Primero el Resumen:** precisión de cada jugador (la del usuario destacada), tabla de
  categorías con insignia y recuento por jugador y **hasta 5 momentos clave** (ver §3.4). El
  tablero muestra la posición final. Botón principal **"Empezar revisión"** → jugada 1.
- **Tablero:** franjas de jugador encima y debajo (el usuario siempre abajo); barra de
  evaluación que gira con el tablero; casillas de origen (~30 %) y destino (~55 %) con el color
  de la clasificación e insignia SVG en la esquina del destino. Las piezas se deslizan al
  avanzar o retroceder paso a paso; los saltos largos van sin animación.
- **Gráfica de evaluación** (clic → ir a la jugada) con puntos en !!, ?, ?? y ✗ y una línea en
  la jugada actual.
- **Lista de jugadas** en dos columnas, con insignia solo en !!, !, ?!, ?, ?? y ✗.
- **Navegación:** ⏮ ◀ ▶ ⏭, ← → Inicio Fin, **"Siguiente error"** (tecla N: siguiente ?!, ?, ??
  o ✗ del usuario) y ayuda de atajos.
- **Panel del coach** al seleccionar una jugada:
  - Insignia + frase corta ("Nf3 es un error") y debajo la explicación.
  - **Mejor jugada automática:** si la jugada hecha no es la mejor (excelente, buena, ?!, ?, ??,
    ✗) se muestran la flecha verde en el tablero y "La mejor era X"; **"Ver línea"** despliega
    su continuación clicable. Si es la mejor (★, !, !!, libro) no se muestra ninguna alternativa.
  - Fila de acciones que crece por fases: **"Profundizar"** (nivel 2, Fase 4) y
    **"Pruébalo tú"** (en errores: repetir la posición e intentar encontrar la mejor jugada).
  - "Detalles del motor" plegado (recuerda su estado): % de victoria, Δ, evaluación y líneas.
  - **Nivel 1 — explicación simple** (1–2 frases, siempre visible).
  - **Nivel 2 — "Profundizar"**: amenazas, variante principal comentada, comparación con
    la mejor jugada, conceptos implicados.
  - **Nivel 3 — "Pregunta al coach"**: chat sobre esa posición ("¿y si juego Nxe5?").
- **Explorar variantes** en el tablero (salir de la línea de la partida y volver), con
  evaluación del motor (`POST /api/analysis/evaluate`, ~0,3 s, con debounce) en la barra y
  flecha con la mejor jugada.
- **Diseño adaptable:** en escritorio, tablero y gráfica caben en el alto de la ventana; en
  móvil, tablero a todo el ancho, barra horizontal y el panel debajo con pestañas.

## 2. Análisis con motor
- Por cada posición de la partida: evaluación con MultiPV = 3 a profundidad/tiempo
  configurable (por defecto ~0,5–1 s por posición o profundidad 18; ajustable).
- Análisis como **trabajo en segundo plano** con progreso vía SSE; resultados cacheados
  en SQLite por FEN + ajustes del motor.
- Normalizar todas las evaluaciones al punto de vista del jugador que mueve.
- El motor recibe cada posición **con su historial reversible** (las jugadas desde la última
  captura o movimiento de peón), para que detecte repeticiones. La clave de caché es esa
  misma información (posición raíz + jugadas), así que dos partidas que llegan a la misma
  posición con la misma historia reversible comparten caché.
- Análisis en paralelo con un pool de varios motores. Número de motores (`ENGINE_POOL_SIZE`)
  y tiempo/profundidad por posición configurables en `config.py` / `.env`.

### 2.1 Probabilidad de victoria
Convertir centipeones a % de victoria esperada con una función logística, p. ej.
`win% = 50 + 50 * (2 / (1 + exp(-0.00368208 * cp)) - 1)` (la que usa Lichess).
Mates → 100 % / 0 %. Toda la clasificación trabaja sobre **pérdida de win%**, no sobre
centipeones brutos (perder 2 peones con +8 importa poco; con 0.0 importa mucho).

## 3. Clasificación de jugadas
Valores por defecto, todos en `config.py`. `Δ` = win% antes − win% después, desde el
punto de vista de quien mueve.

Orden de evaluación: **Teoría → Oportunidad perdida → Brillante → Gran jugada → Mejor →
umbrales de Δ** (Excelente, Buena, Imprecisión, Error, Grave error). Gana la primera que cumpla.

| Símbolo | Categoría   | Regla                                                                          |
|---------|-------------|--------------------------------------------------------------------------------|
| 📖      | Teoría      | La posición resultante está en el libro de aperturas (dataset `lichess-org/chess-openings`) **y Δ < 10**; si no, se clasifica normalmente (el libro contiene trampas como "Barnes Opening: Fool's Mate"). |
| !!      | Brillante   | Ver 3.1.                                                                       |
| !       | Gran jugada | Ver 3.2.                                                                       |
| ★       | Mejor       | Es la jugada nº 1 del motor (o Δ ≈ 0).                                         |
| —       | Excelente   | Δ < 2                                                                          |
| —       | Buena       | Δ < 5                                                                          |
| ?!      | Imprecisión | Δ < 10                                                                         |
| ?       | Error       | Δ < 20                                                                         |
| ??      | Grave error | Δ ≥ 20                                                                         |
| ✗       | Oportunidad perdida | El rival acababa de cometer un error/grave error y la jugada no lo castiga (Δ respecto a la mejor ≥ 10 y la mejor habría ganado ventaja decisiva). |

### 3.1 Brillante (!!)
Todas deben cumplirse:
1. Es la mejor jugada o casi (Δ < 2).
2. Implica un **sacrificio real**, en cualquiera de estas formas:
   - el material del jugador baja ≥ 2 puntos al final de un horizonte corto de la variante
     principal (configurable) y no se recupera inmediatamente con una recaptura obvia; o
   - tras la jugada, **cualquier pieza propia** (no solo la movida) queda en prise según el SEE
     —el rival ganaría ≥ 2 puntos capturándola, descontando lo que capturó la propia jugada— y
     antes no lo estaba, **o ya lo estaba pero existía una jugada que la ponía a salvo y no se
     hizo** (p. ej. Byrne–Fischer 1956, 17…Be6!!, que deja la dama atacada en b6). Una pieza
     atrapada que se pierde de todos modos no cuenta.
3. La posición **no** estaba ya totalmente ganada antes (win% previo < 90).
4. La posición resultante es al menos igualada para el jugador (win% posterior ≥ 45,
   configurable; p. ej. Kasparov–Topalov 1999, 24.Rxd4!!, ≈ 46 %).

### 3.2 Gran jugada (!)
Es la mejor jugada, no es la única jugada legal, ni una recaptura obvia (captura en la casilla
donde el rival acaba de capturar), ni un **mate en una** (esos quedan como ★), y se cumple al
menos una de estas condiciones:
- a) la segunda opción del MultiPV es ≥ 10 puntos de win% peor; o
- b) la segunda opción cambia de **categoría de resultado** respecto a la mejor: ganado
  (win% > 75), igualado o perdido (win% < 25). Umbrales configurables.

### 3.3 Precisión
Precisión por jugada a partir de Δ (fórmula tipo Lichess), media ponderada por la
volatilidad de la posición. Documentar la fórmula exacta en el código.

### 3.4 Momentos clave
Centrados en el jugador humano (parámetro de *perspectiva*: el color del usuario; en partidas
importadas habrá que indicarlo). Hasta 5, en este orden:
1. sus jugadas ?!, ?, ?? y oportunidades perdidas, por Δ descendente (solo Δ ≥ 5);
2. si quedan huecos, sus jugadas ! y !!.
Las jugadas del bot (o del rival) nunca son momentos clave.

### 3.5 Tests de clasificación
`tests/fixtures/classification/real_positions.json` (partidas en `tests/fixtures/games/`, con la
fuente de cada posición) se clasifica con Stockfish real a profundidad fija 16, un hilo,
MultiPV 3. `tests/fixtures/` contiene posiciones con la clasificación esperada: sacrificios
brillantes conocidos (p. ej. de partidas clásicas), "única jugada" en finales, errores
graves tácticos, recapturas obvias (no deben ser "!"). Los umbrales se ajustan contra estos fixtures.

## 4. Extracción de hechos (`analysis/facts.py`)
Para cada jugada se construye un `MoveFacts` serializable, sin texto libre:

- `played`, `best`, `best_line` (SAN, 4–8 plies), `played_line` (refutación tras la jugada hecha).
- `classification`, `win_before`, `win_after`, `delta`.
- `material_change_in_line` (por lado, a lo largo de cada variante).
- `hanging_pieces_after` (piezas atacadas e insuficientemente defendidas, con SEE).
- `threats_allowed` (qué gana el rival con su mejor respuesta y cómo).
- `threats_created` (qué amenaza la jugada hecha / la mejor).
- `tactical_motifs` detectados en las variantes: clavada, doble ataque, ataque a la
  descubierta, jaque doble, mate en N, promoción. **Desviación, sobrecarga y rayos X quedan
  para más adelante** (difíciles de detectar sin falsos positivos; decidido en la Fase 4).
- `king_safety` (escudo de peones, columnas abiertas hacia el rey, atacantes cercanos).
- `pawn_structure` cambios: aislados, doblados, retrasados, pasados creados/perdidos.
- `piece_activity` (movilidad antes/después; piezas sin desarrollar en apertura).
- `phase` (apertura / medio juego / final) y `opening_name` si aplica.

Cada detector es una función pura con tests propios. Si un detector no está seguro, no
emite el hecho: **es preferible callar a afirmar algo falso**.

Cada hecho lleva **las casillas implicadas** (pieza colgada, atacantes, jugada que amenaza,
piezas del doble ataque…) para poder dibujarlo en el tablero. Los hechos salen de las líneas
MultiPV ya guardadas por el análisis (antes y después de la jugada) + python-chess; no se vuelve
a llamar al motor.

Reglas para no afirmar de más (Fase 4):
- El material de una línea se cuenta en las primeras 6 medias jugadas (alargando si hay un
  intercambio en curso) y se cierra con SEE. "Gana / ganaba X" solo si la captura que lo
  consigue está entre las 5 primeras medias jugadas de la línea (las que el texto muestra), no
  solo en el cierre con SEE, y —para jugadas buenas— si la línea deja al que mueve con ≥ 55 % de
  victoria (si no, suele ser un sacrificio rival a medias).
- Una pieza se nombra ("pierdes el caballo de c3") solo si explica la diferencia y el otro bando
  no recuperó más que peones.
- Doble ataque y clavada exigen que la pieza que ataca no se pueda ganar (SEE).
- Las amenazas nuevas de una jugada son las de la pieza movida o descubiertas por ella, y no se
  calculan si se respondía a un jaque.

## 5. Explicaciones (`explain/`)

### 5.1 Niveles
- **Nivel 1 (simple):** 1–2 frases, lenguaje llano, sin jerga innecesaria ni cifras de
  evaluación, centrado en *la idea principal* (qué amenaza no viste, qué pieza quedó colgada,
  qué ganaba la mejor jugada):
  "Dejaste el caballo de f3 sin defensa; tras …[[Bxf3]] pierdes una pieza. Mejor era [[Be2]]."
- **Nivel 2 (profundizar):** 1 párrafo + variante comentada jugada a jugada, comparación
  hecha vs. mejor, concepto general aplicable ("antes de mover, revisa qué deja de defender la pieza").
- **Nivel 3 (chat):** el LLM recibe la posición, los hechos y **herramientas**
  (`evaluate_position(fen)`, `analyze_move(fen, san)`, `get_threats(fen)`,
  `legal_moves(fen)`) y responde solo con datos obtenidos de ellas.

**Idea principal** (`explain/idea.py`), por prioridad:
- Errores (?!, ?, ??): mate permitido > mate perdido > pieza colgada > táctica permitida
  (doble ataque, clavada…) > material perdido > material que ganaba la mejor > comentario
  posicional (debilidad del enroque, peones doblados/aislados solo en ?!; motivo de la mejor:
  enroque, desarrollo, amenaza, defensa). Si no hay hechos, una frase prudente sin motivo.
- Oportunidad perdida (✗): mate perdido > material perdido primero.
- Gran jugada (!): **por qué fallaban las alternativas**, con la segunda línea del MultiPV
  («[[X]] era la única: si [[Y]], sigue [[Z]] y …»). Si además fuerza mate, el mate va primero.
- Brillante (!!): el sacrificio primero.
- Jugadas buenas (!, !!, ★): mate > material ganado > amenaza creada > amenaza neutralizada.
  La ★ solo se explica si hay alguna de estas ideas y no es una recaptura obvia ni la única
  legal. Excelente/buena: «[[X]] era algo más precisa» con su motivo si lo hay.
- Teoría: nombre de la apertura.

Persona: segunda persona en las jugadas del usuario, tercera ("las blancas…") en las del rival.
Piezas por su nombre en español; jugadas en SAN inglés marcadas `[[...]]`.

**Apoyo visual:** cada idea trae anotaciones sobre la posición tras la jugada: flecha roja para
la amenaza del rival, casilla roja para la pieza en peligro, flecha ámbar para lo que ataca una
jugada buena, casilla ámbar para la pieza objetivo o salvada. El nivel 1 dibuja solo las de la
idea principal (máx. 3 elementos); el nivel 2 puede mostrar hasta 6.

### 5.2 Generación
1. **Plantillas deterministas** (proveedor `none`) para todos los niveles 1 y 2. Siempre disponibles.
2. Con LLM: prompt de sistema fijo + `MoveFacts` en JSON + nivel del usuario. Instrucciones:
   usar solo los hechos, no inventar jugadas, no dar evaluaciones numéricas salvo que se pidan,
   tono de entrenador amable, en español. Jugadas **siempre en SAN inglés** (K, Q, R, B, N)
   y **marcadas como `[[Nf3]]`**.
3. **Validación posterior:** extraer todas las marcas `[[...]]` del texto; cada jugada debe existir
   en los hechos o ser legal en el contexto citado. Si falla → reintento con el error → si vuelve a
   fallar, plantilla. Las plantillas usan el mismo formato de marcas.
4. **Frontend:** renderiza cada `[[SAN]]` como una jugada clicable que se muestra en el tablero.
5. Caché por `(fen, move, level, provider, model, prompt_version)` (tabla `Explanation`, en la
   Fase 5: las plantillas se calculan bajo demanda en milisegundos).
6. Generación perezosa: nivel 1 para momentos clave al terminar el análisis; el resto bajo demanda.

### 5.3 Proveedores
Interfaz `LLMProvider` con `complete(messages, tools=None)` y `stream(...)`.
Implementaciones: Anthropic, OpenAI, Ollama, None. Configuración solo por `.env`.
Registrar tokens usados por partida en logs.

## 6. API (orientativa)
Todas las rutas van bajo el prefijo `/api` (p. ej. `/api/games`), igual en desarrollo y en producción.

- `POST /games` crear partida (color, nivel) · `POST /games/{id}/moves` jugada del usuario → respuesta del motor
- `POST /games/import` (`{pgn, user_color?}`; 422 `color_required` si no se puede deducir)
- `POST /games/{id}/analysis` lanza análisis · `GET /games/{id}/analysis/stream` (SSE progreso)
- `GET /games/{id}/review` resumen + jugadas clasificadas
- `POST /analysis/evaluate` (`{fen, moves?, multipv?}`): evaluación bajo demanda con el pool de
  análisis; devuelve líneas (UCI + SAN), puntuación y mejor jugada. Herramienta del coach (Fase 6).
- `GET /games/{id}/moves/{ply}/explanation?level=1|2` → `{ply, level, text, refs, annotations,
  idea}`: `text` con marcas `[[SAN]]` (null si no hay nada que decir), `refs` una por marca en
  orden (`{san, line, base, path}`: jugadas UCI desde la posición `base` de la partida, para
  mostrarla en el tablero), `annotations` (flechas/casillas con su papel).
- `POST /games/{id}/moves/{ply}/chat` (streaming)
- `GET /games` historial

## 7. Persistencia
SQLite: `Game`, `Move`, `AnalysisJob`, `PositionAnalysis` (caché por posición + historia
reversible + ajustes), `Explanation` (caché), `ChatMessage`. Migraciones con **Alembic**
(`backend/migrations/`), aplicadas al arrancar; una base anterior a Alembic se marca con la
revisión base y se migra.

## 8. Fuera de alcance (por ahora)
Multijugador, cuentas de usuario, exposición pública a internet, móvil nativo, entrenamiento de
modelos propios. El despliegue en una Raspberry Pi doméstica (LAN, Tailscale opcional) es un
objetivo final (ROADMAP Fase 8).
