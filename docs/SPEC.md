# Especificación — whyfish

## 1. Flujos de usuario

### 1.1 Jugar
- Elegir color (blancas / negras / aleatorio) y nivel del bot.
- Nivel del bot: presets con nombre (p. ej. "Principiante ~800", "Club ~1500",
  "Fuerte ~2000", "Máximo"). Implementación: `UCI_LimitStrength` + `UCI_Elo` donde el
  motor lo permita; por debajo del Elo mínimo soportado, `Skill Level` y tiempo/profundidad
  reducidos. Calibración en `config.py`.
- Sin reloj ni control de tiempo (descartado: es una herramienta de aprendizaje).
- **Tiempo de "pensar" mínimo del bot** (para que no responda de forma antinatural): por
  nivel, aleatorio en un rango (`LevelPreset.think_min_s/think_max_s`): Principiante y Novato
  0,8–1,6 s, Club 0,8–1,8 s, Fuerte y Máximo 0,5 s (solo si responden más rápido). El backend
  devuelve la jugada al momento junto con el rango (`bot_think` en el estado de la partida,
  escalado por `BOT_THINK_SCALE`; 0 en los tests); el frontend espera solo lo que falte (mínimo
  menos lo que tardó la petición). Durante la espera tu jugada ya se ve en el tablero, la franja
  del bot dice "pensando…" y no se puede mover. Sin espera al recargar ni al deshacer; si el bot
  abre la partida (juegas con negras), espera solo el mínimo del rango.
- Durante la partida: sin ayudas por defecto. Opciones activables: deshacer jugada,
  pista (muestra la pieza a mover, no la casilla destino).
- Abandonar / ofrecer tablas. Fin por mate, ahogado, repetición, 50 jugadas, material insuficiente.
- Al terminar: botón **"Analizar partida"**.

### 1.2 Importar
- Pegar o subir un **PGN** (primera partida, línea principal; admite `[SetUp]`/`[FEN]`). Un
  FEN suelto no se importa: para eso está "Nueva partida desde FEN". Si el PGN trae `%clk`, se
  guarda el tiempo restante de cada jugada.
- El color del usuario se indica o se detecta comparando `PLAYER_NAME` con las cabeceras
  `White`/`Black`; si no se puede, la app pregunta.
- Mismo flujo de análisis que una partida jugada (las importadas siempre son analizables).

### 1.2b Sincronización con Lichess y Chess.com (Fase 6a)
- **Cuentas** (una por plataforma) en la pantalla **Ajustes**, guardadas en la base. Cambiar el
  usuario empieza de cero el rango de esa cuenta.
- **Sincronizar** (botón del Historial, sin sincronización periódica): la primera vez, los
  últimos `SYNC_MONTHS` (6) meses; después, solo las partidas posteriores a la más reciente
  importada. «Importar partidas más antiguas» (Ajustes) amplía el rango 6 meses hacia atrás.
- APIs públicas sin autenticación: Lichess `GET /api/games/user/{u}` (ndjson, `sort=dateAsc`,
  con `%clk`; una petición a la vez) y Chess.com (archivos mensuales, en serie). Ante HTTP 429,
  espera `SYNC_RETRY_WAIT_S` y reintenta una vez. `User-Agent` genérico, sin datos personales.
- Se leen de la más antigua a la más reciente y se guardan una a una: una sincronización
  cortada continúa donde se quedó; nunca se guarda una partida dos veces (plataforma + id).
  Errores de red o de la API: se guardan por cuenta (`last_error`) y se muestran; la otra
  cuenta sigue.
- Solo ajedrez normal (también desde posición); variantes y partidas contra la IA de Lichess
  se descartan. Color del usuario: el bando cuyo nombre es su usuario (sin distinguir
  mayúsculas). Se guardan origen, enlace, fecha de inicio, ritmo (bala, blitz, rápida,
  clásica, correspondencia), control de tiempo, rivales con su Elo y el reloj por jugada.
- **Cola de análisis en segundo plano:** las partidas sincronizadas se analizan solas, de una
  en una, **de la más reciente a la más antigua**. Una partida que el usuario abre se analiza
  en primer plano y pasa delante. Prioridad de motores: interactivo (explorar, "Ver por qué",
  "Pruébalo tú") > análisis abierto por el usuario > cola; la cola deja libres
  `QUEUE_RESERVED_ENGINES` (1) motores. Se puede pausar (persistente); `QUEUE_PAUSE_BETWEEN_S`
  añade un respiro entre partidas (Pi). Una partida que falla se reintenta una vez.
- **Historial:** filtros de origen (Lichess, Chess.com, PGN, contra el bot), ritmo, resultado
  (desde el lado del usuario), color y analizada o no, guardados en la URL; paginación (50).

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
  - Fila de acciones que crece por fases: **"Profundizar"** (nivel 2, Fase 4), **"Ver por
    qué" / "Ver la idea"** y **"Pruébalo tú"** (Fase 5, §5.4).
  - "Detalles del motor" plegado (recuerda su estado): % de victoria, Δ, evaluación y líneas.
  - **Nivel 1 — explicación simple** (1–2 frases, siempre visible).
  - **Nivel 2 — "Profundizar"**: amenazas, variante principal comentada, comparación con
    la mejor jugada, conceptos implicados.
  - **"Ver por qué"**: el tablero reproduce la secuencia hasta su consecuencia (Fase 5).
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
| ★       | Mejor       | Es la jugada nº 1 del motor o **igual de buena** (ver «Igual de buenas»).      |
| —       | Excelente   | Δ < 2                                                                          |
| —       | Buena       | Δ < 5                                                                          |
| ?!      | Imprecisión | Δ < 10                                                                         |
| ?       | Error       | Δ < 20                                                                         |
| ??      | Grave error | Δ ≥ 20                                                                         |
| ✗       | Oportunidad perdida | El rival acababa de cometer un error/grave error y la jugada no lo castiga (Δ respecto a la mejor ≥ 10 y la mejor habría ganado ventaja decisiva). |

**Igual de buenas.** Una jugada del MultiPV a Δ < 1 (`equal_max_delta`) de la mejor es igual
de buena: es ★ si se juega, y el panel la nombra («[[X]] es la mejor. También valía [[Y]]»; en
jugadas no-mejores, «La mejor era [[X]] (o [[Y]], igual de buena)»).

**Posiciones decididas** (win% de quien mueve > 85 o < 15). El win% se satura (≈ 97,5 % con
ventaja grande, 100 % con mate), así que jugadas muy distintas darían Δ = 0. Ahí se desempata
con la puntuación en centipeones (mate en n = 100 000 − 10·n): igual de buena si está a menos de
50 cp de la mejor; como mucho **Excelente** hasta 150 cp y como mucho **Buena** más allá (ganar
un peón en vez de una torre no es ★ aunque ambas «ganen»). Si Δ ya da una categoría peor, se
queda la peor. Umbrales en `config.py` (`decided_*`).

**Coherencia entre análisis.** La exploración usa las líneas guardadas del análisis cuando la
posición (o la línea guardada de su posición anterior) ya se analizó; "Pruébalo tú" usa el valor
guardado si el intento está en el MultiPV y, si no, busca el intento junto a la mejor guardada
(searchmoves) con los mismos límites que el análisis de la partida. Nunca se compara un valor de
una búsqueda corta con otro de la búsqueda del análisis.

### 3.1 Brillante (!!)
Todas deben cumplirse:
1. Es la mejor jugada o casi (Δ < 2).
2. Implica un **sacrificio real** (`app/analysis/sacrifice.py`, compartido con los hechos).
   Todo esto debe cumplirse:
   - **En prise de verdad:** tras la jugada el rival tiene una captura **legal** de una pieza
     propia cuyo SEE le gana ≥ 2 puntos (descontando lo que capturó la jugada). "Atacada" sin
     ganancia no cuenta (p. ej. un rey que solo puede tomar una pieza defendida: la captura
     sería ilegal). Regresión: 21.Nd6 de la partida contra Novato no es !!.
   - **Material de referencia resuelto:** el balance antes de la jugada con los cambios
     pendientes resueltos (quiescencia: capturas, promociones y, en jaque, todas las
     evasiones; profundidad configurable), nunca a mitad de un intercambio. La jugada pierde
     ≥ 2 puntos respecto a él al resolver las capturas tras la jugada.
   - **Hay alternativa:** alguna otra jugada legal conserva ese material. Si todas lo pierden
     —p. ej. en jaque con una pieza que no se puede salvar— no es sacrificio (regresión:
     8.Bd2 tras 7.Bxg6 Bb4+).
   - **Verificado con el motor:** cada captura legal de esa pieza deja al jugador con win%
     ≥ 45. La evaluación sale de la línea del motor donde se juega la captura (la línea de la
     jugada en el MultiPV previo, o una línea del MultiPV del rival tras la jugada). Si la
     captura no está en el MultiPV del rival (≥ 2 líneas), es peor para él que la última línea
     listada, cuya evaluación sirve de cota (Kasparov 24.Rxd4!!: el motor prefiere …Kb6).
     Si alguna captura no se puede comprobar, no es !!.
3. La posición **no** estaba ya totalmente ganada antes (win% previo < 90) y el jugador **no
   iba ya por debajo en material** (resuelto) antes de la jugada: una entrega que continúa una
   combinación propia no es una !! nueva (Kasparov–Topalov: solo 24.Rxd4 y 37.Rd7).
4. La posición resultante es al menos igualada para el jugador (win% posterior ≥ 45,
   configurable; p. ej. Kasparov–Topalov 1999, 24.Rxd4!!, ≈ 46 %).

### 3.2 Gran jugada (!)
Es la mejor jugada, no es la única jugada legal, ni una recaptura obvia (captura en la casilla
donde el rival acaba de capturar), ni un **mate en una**, ni la captura de una pieza que el rival
dejó en prise (gana material aun tras la mejor recaptura, por SEE: castigar un error obvio), y
la posición **no** estaba ya ganada (win% previo < 85: mantener una ventaja decisiva no es
notable). Esas quedan como ★. Además se cumple al menos una de estas condiciones:
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
- El material de una línea es el de su **punto de consecuencia** (§5.3: resuelto, nunca a
  mitad de un intercambio). "Gana / ganaba / pierde X" solo si ese punto está dentro de la
  línea y a ≤ 20 medias jugadas (lo que "Ver por qué" reproducirá) y —para jugadas buenas— si
  la línea deja al que mueve con ≥ 55 % de victoria (si no, suele ser un sacrificio rival a
  medias).
- Una pieza se nombra ("pierdes el caballo de c3") solo si explica la diferencia y el otro bando
  no recuperó más que peones.
- Doble ataque y clavada exigen que la pieza que ataca no se pueda ganar (SEE).
- Las amenazas nuevas de una jugada son las de la pieza movida o descubiertas por ella, y no se
  calculan si se respondía a un jaque.
- "Entrega", "sacrifica" o "material de menos" solo si existe el hecho `sacrifice` (la misma
  comprobación que §3.1: captura legal con SEE favorable al rival, verificada con el motor).
  El texto siempre nombra esa captura: «[[X]] entrega el caballo de f5: si [[gxf5]] lo
  captura, …». "Material de menos" exige que el balance resuelto al final de esa línea siga
  por debajo de la referencia; si no, «se recupera el material». Si la captura solo está
  acotada por el MultiPV: «…al rival le va peor que con su mejor respuesta, [[Y]]». Nunca
  «deja X atacado» sin captura legal favorable. Una pieza que no se podía salvar con ninguna
  jugada (p. ej. en jaque) nunca es «dejada sin defensa».

## 5. Explicaciones (`explain/`)

### 5.1 Niveles
- **Nivel 1 (simple):** 1–2 frases, lenguaje llano, sin jerga innecesaria ni cifras de
  evaluación, centrado en *la idea principal* (qué amenaza no viste, qué pieza quedó colgada,
  qué ganaba la mejor jugada):
  "Dejaste el caballo de f3 sin defensa; tras …[[Bxf3]] pierdes una pieza. Mejor era [[Be2]]."
- **Nivel 2 (profundizar):** 1 párrafo + variante comentada jugada a jugada, comparación
  hecha vs. mejor, concepto general aplicable ("antes de mover, revisa qué deja de defender la pieza").
- **Ver por qué / Ver la idea (Fase 5):** el tablero reproduce la secuencia hasta el punto de
  consecuencia (§5.4).

**Idea principal** (`explain/idea.py`), por prioridad:
- Errores (?!, ?, ??): mate permitido > mate perdido > **la mayor consecuencia de la
  refutación** en su punto de consecuencia (§5.3): pieza colgada o táctica permitida solo si
  explican ese material perdido (un peón atacado no es la idea si la línea pierde la dama);
  si no, «pierde la dama a cambio de un caballo» > material que ganaba la mejor > comentario
  posicional (debilidad del enroque, peones doblados/aislados solo en ?!; motivo de la mejor:
  enroque, desarrollo, amenaza, defensa). Si no hay hechos, una frase prudente sin motivo.
- Si en ? o ?? el material perdido es pequeño (≤ 2), se añade lo que dice la evaluación
  («…y la ventaja se esfuma», «…y la posición empeora claramente»).
- Oportunidad perdida (✗): mate perdido > material que ganaba la mejor (si la jugada hecha
  también ganaba algo, la diferencia: «ganaba dos peones más»).
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
1. **Solo plantillas deterministas** (`explain/templates.py`) para los niveles 1 y 2, calculadas
   bajo demanda (milisegundos; sin caché).
2. Jugadas **siempre en SAN inglés** (K, Q, R, B, N) y **marcadas como `[[Nf3]]`**; el validador
   de marcas (`explain/marks.py`) comprueba que cada una está en los hechos. Se conserva por si
   se retoma una IA (ROADMAP, "Ideas futuras").
3. **Frontend:** renderiza cada `[[SAN]]` como una jugada clicable que se muestra en el tablero.

### 5.3 Punto de consecuencia (`analysis/consequence.py`)
Función pura compartida por el texto de nivel 1 y "Ver por qué": dada una línea (posición +
jugadas UCI) devuelve el ply donde se materializa lo que hace mala (o buena) la jugada —mate,
coronación o un cambio de material **resuelto** (quiescencia; nunca a mitad de un
intercambio)— y el balance en ese punto (p. ej. "pierdes la dama a cambio de caballo"). El punto
es la **primera** posición tranquila que ya tiene el balance final (con un peón de tolerancia
si la diferencia es de una pieza o más) y desde la que el perdedor no recupera más que esa
tolerancia: los cambios menores posteriores no alargan la historia. En ?? y ? la idea principal
del nivel 1 es la mayor consecuencia de la refutación (mate > material perdido), no un hecho
menor.

### 5.4 Ver por qué (Fase 5, `explain/why.py`, `api/why.py`)
- **Qué línea:** jugadas que no son la mejor → la refutación tras la jugada hecha; "!" → la
  refutación de la segunda opción («¿y si en su lugar…?»); "!!" → la línea de la entrega; ★
  con explicación → la línea de la mejor. "Ver la solución" de "Pruébalo tú" → la línea de la
  mejor jugada.
- **Hasta dónde:** hasta el punto de consecuencia si la consecuencia va en el sentido que
  explica la jugada (en contra del que mueve en refutaciones y en la alternativa de la "!", a
  favor en la idea); si no, se trata como "sin consecuencia clara": unas 8 medias jugadas,
  terminando en una posición tranquila con el material igual que al empezar.
- **Extensión:** si la línea termina a mitad de un intercambio, su consecuencia no va seguida
  de 4 medias jugadas sin cambio de material (no aplica al mate) o, sin consecuencia, mide
  menos de 12, se pide al motor la continuación desde su última posición (0,2 s, una línea,
  `WHY_EXTEND_TIME_S`) hasta 20 medias jugadas. Cada búsqueda se guarda en `PositionAnalysis`
  con su propia clave de ajustes: la misma secuencia sale siempre igual. Sin motor se usa la
  línea guardada tal cual.
- **Frases por paso** (desde los hechos, piezas siempre respecto al usuario: «tu dama», «la
  torre rival»): mate con la pieza («El caballo rival da jaque mate») > captura, siempre con
  lo capturado («Tu torre recupera: captura la torre rival»; el rey o la pieza que captura a
  quien da jaque: «Tu rey captura el peón que daba jaque») > jaque > respuesta al jaque («tiene
  que moverse» solo si todas las jugadas legales son del rey; «se interpone», «se aparta») >
  coronación > amenaza que la secuencia ejecuta después (con flecha roja hasta entonces) >
  enroque > «va a e2». En una refutación de la jugada del usuario, sus jugadas posteriores son
  la mejor defensa del motor: «Tu mejor defensa: …» y estilo distinto en la secuencia.
- **Resumen:** material con lo perdido y lo ganado y el balance en peones («Pierdes la dama y
  el alfil a cambio de torre y caballo (unos 4 peones de diferencia)»); en ? y ?? con poco
  material, también lo que dice la evaluación; mate («Esta jugada permite mate inmediato»,
  «Das mate en 3»); sin consecuencia clara, comparación sin cifras con datos ya conocidos. Las
  comparaciones dejan claro que la alternativa era de quien movió y describen su situación
  («Con [[g6]] seguías en la partida (el rival algo mejor); ahora la partida queda perdida»; para
  el rival: «Con [[X]] el rival mantenía la igualdad; ahora quedas algo mejor»); lo mismo en el
  nivel 2 («con [[X]] ganabas un peón; con tu jugada, el material se mantiene»). Si la posición
  ya estaba decidida antes (win% < 15 o > 85) se dice delante («Tu posición ya estaba perdida,
  pero…»).
- **Reproducción:** automática (`WHY_STEP_MS`, 1 s), pausa, ◀ ▶ (también con el teclado),
  espacio, Esc; piezas que se deslizan, origen y destino resaltados, casilla de la consecuencia
  en rojo (errores) o verde (ideas). Controles en el sitio de la barra de navegación (bajo el
  tablero en móvil, al pie del panel en escritorio); frase del paso y tarjeta final en el
  panel (escritorio) o en una franja bajo el tablero (móvil). Nada tapa el tablero.
- **Pruébalo tú** (?!, ?, ??, ✗): posición anterior, sin la flecha de la mejor. Cualquier jugada
  igual de buena que la mejor (§3, misma búsqueda o valor guardado) es un acierto: «¡Bien visto!
  También valía [[X]]». Si no: «Intentar otra vez», «Ver por qué falla tu intento» y «Ver la
  solución».

## 6. API (orientativa)
Todas las rutas van bajo el prefijo `/api` (p. ej. `/api/games`), igual en desarrollo y en producción.

- `POST /games` crear partida (color, nivel) · `POST /games/{id}/moves` jugada del usuario → respuesta del motor
- `POST /games/import` (`{pgn, user_color?}`; 422 `color_required` si no se puede deducir)
- `POST /games/{id}/analysis` lanza análisis · `GET /games/{id}/analysis/stream` (SSE progreso)
- `GET /games/{id}/review` resumen + jugadas clasificadas
- `POST /analysis/evaluate` (`{fen, moves?, multipv?}`): evaluación bajo demanda con el pool de
  análisis; devuelve líneas (UCI + SAN), puntuación y mejor jugada.
- `GET /games/{id}/moves/{ply}/explanation?level=1|2` → `{ply, level, text, refs, annotations,
  idea}`: `text` con marcas `[[SAN]]` (null si no hay nada que decir), `refs` una por marca en
  orden (`{san, line, base, path}`: jugadas UCI desde la posición `base` de la partida, para
  mostrarla en el tablero), `annotations` (flechas/casillas con su papel).
- `GET /games/{id}/moves/{ply}/why?kind=refutation|idea|solution` → `{kind, tone, base_ply,
  start_fen, title, alternative, steps: [{index, label, san, uci, fen, color, caption, defense,
  consequence, arrows}], consequence_ply, summary, refs, step_ms}` (409 si la jugada no tiene
  esa secuencia).
- `POST /games/{id}/moves/{ply}/try` (`{uci}`) → `{uci, san, classification, correct, why}`:
  "Pruébalo tú" (la posición anterior ya está analizada: solo se evalúa el intento).
- `GET /games?source&platform&time_class&result&color&analysed&limit&offset` → `{items, total}`
  (historial filtrado, el más reciente primero).
- `GET/PUT /accounts` (usuarios de Lichess / Chess.com y su estado) · `GET /sync`,
  `POST /sync {older}` (sincronizar; progreso por cuenta) · `GET /queue`, `POST /queue/pause`,
  `POST /queue/resume` (cola de análisis).

## 7. Persistencia
SQLite: `Game` (con origen online, ritmo, Elo), `Move` (con reloj), `AnalysisJob` (con
intentos de la cola), `PositionAnalysis` (caché por posición + historia reversible + ajustes),
`ImportAccount` (cuentas sincronizadas y su rango), `AppSetting` (ajustes clave/valor). Migraciones con **Alembic**
(`backend/migrations/`), aplicadas al arrancar; una base anterior a Alembic se marca con la
revisión base y se migra.

## 8. Fuera de alcance (por ahora)
Multijugador, cuentas de usuario, exposición pública a internet, móvil nativo, entrenamiento de
modelos propios. El despliegue en una Raspberry Pi doméstica (LAN, Tailscale opcional) es un
objetivo final (ROADMAP Fase 7).
