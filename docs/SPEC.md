# Especificación — whyfish

## 1. Flujos de usuario

### 1.1 Jugar
- Elegir color (blancas / negras / aleatorio) y nivel del bot.
- Nivel del bot: presets con nombre (p. ej. "Principiante ~800", "Club ~1500",
  "Fuerte ~2000", "Máximo"). Implementación: `UCI_LimitStrength` + `UCI_Elo` donde el
  motor lo permita; por debajo del Elo mínimo soportado, `Skill Level` y tiempo/profundidad
  reducidos. Calibración en `config.py`.
- Control de tiempo opcional (sin reloj por defecto: es una herramienta de aprendizaje).
- Durante la partida: sin ayudas por defecto. Opciones activables: deshacer jugada,
  pista (muestra la pieza a mover, no la casilla destino).
- Abandonar / ofrecer tablas. Fin por mate, ahogado, repetición, 50 jugadas, material insuficiente.
- Al terminar: botón **"Analizar partida"**.

### 1.2 Importar
- Pegar PGN o FEN, o (fase posterior) importar desde Lichess/Chess.com por usuario.
- Mismo flujo de análisis que una partida jugada.

### 1.3 Revisión (Game Review)
- Barra de evaluación + gráfica de evaluación a lo largo de la partida (clic → ir a jugada).
- Lista de jugadas con símbolo e icono de color por clasificación.
- Resumen: precisión por jugador, recuento por categoría, **3–5 momentos clave**
  (los mayores cambios de probabilidad de victoria) destacados para revisar primero.
- Al seleccionar una jugada:
  - Flecha de la jugada hecha y de la mejor jugada.
  - **Nivel 1 — explicación simple** (1–2 frases, siempre visible).
  - **Nivel 2 — "Profundizar"**: amenazas, variante principal comentada, comparación con
    la mejor jugada, conceptos implicados.
  - **Nivel 3 — "Pregunta al coach"**: chat sobre esa posición ("¿y si juego Nxe5?").
  - **"Pruébalo tú"**: en errores, repetir la posición e intentar encontrar la mejor jugada antes de verla.
  - Explorar variantes en el tablero (salir de la línea de la partida y volver).

## 2. Análisis con motor
- Por cada posición de la partida: evaluación con MultiPV = 3 a profundidad/tiempo
  configurable (por defecto ~0,5–1 s por posición o profundidad 18; ajustable).
- Análisis como **trabajo en segundo plano** con progreso vía SSE; resultados cacheados
  en SQLite por FEN + ajustes del motor.
- Normalizar todas las evaluaciones al punto de vista del jugador que mueve.
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
| 📖      | Teoría      | La posición resultante está en el libro de aperturas (dataset `lichess-org/chess-openings`). |
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
2. Implica un **sacrificio real**: el material del jugador baja tras la variante principal
   a corto plazo (≥ 2 puntos, o una pieza menor/torre que queda en prise) y no se recupera
   inmediatamente con una recaptura obvia.
3. La posición **no** estaba ya totalmente ganada antes (win% previo < 90).
4. La posición resultante es buena para el jugador (win% posterior ≥ 50 o mejora clara).

### 3.2 Gran jugada (!)
Es la mejor jugada y además:
- es **la única jugada buena**: la segunda opción del MultiPV es ≥ 10 puntos de win% peor; o
- cambia el resultado esperado (p. ej. de perdido a igualado, o de igualado a ganador).
No marcar como "!" si la jugada es la única legal o una recaptura obvia.

### 3.3 Precisión
Precisión por jugada a partir de Δ (fórmula tipo Lichess), media ponderada por la
volatilidad de la posición. Documentar la fórmula exacta en el código.

### 3.4 Tests de clasificación
`tests/fixtures/` contiene posiciones con la clasificación esperada: sacrificios
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
  descubierta, jaque doble, rayos X, desviación, sobrecarga, mate en N, promoción.
- `king_safety` (escudo de peones, columnas abiertas hacia el rey, atacantes cercanos).
- `pawn_structure` cambios: aislados, doblados, retrasados, pasados creados/perdidos.
- `piece_activity` (movilidad antes/después; piezas sin desarrollar en apertura).
- `phase` (apertura / medio juego / final) y `opening_name` si aplica.

Cada detector es una función pura con tests propios. Si un detector no está seguro, no
emite el hecho: **es preferible callar a afirmar algo falso**.

## 5. Explicaciones (`explain/`)

### 5.1 Niveles
- **Nivel 1 (simple):** 1–2 frases, lenguaje llano, centrado en *la idea*:
  "Dejaste el caballo de f3 sin defensa; tras …[[Bxf3]] pierdes una pieza. Mejor era [[Be2]]."
- **Nivel 2 (profundizar):** 1 párrafo + variante comentada jugada a jugada, comparación
  hecha vs. mejor, concepto general aplicable ("antes de mover, revisa qué deja de defender la pieza").
- **Nivel 3 (chat):** el LLM recibe la posición, los hechos y **herramientas**
  (`evaluate_position(fen)`, `analyze_move(fen, san)`, `get_threats(fen)`,
  `legal_moves(fen)`) y responde solo con datos obtenidos de ellas.

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
5. Caché por `(fen, move, level, provider, model, prompt_version)`.
6. Generación perezosa: nivel 1 para momentos clave al terminar el análisis; el resto bajo demanda.

### 5.3 Proveedores
Interfaz `LLMProvider` con `complete(messages, tools=None)` y `stream(...)`.
Implementaciones: Anthropic, OpenAI, Ollama, None. Configuración solo por `.env`.
Registrar tokens usados por partida en logs.

## 6. API (orientativa)
Todas las rutas van bajo el prefijo `/api` (p. ej. `/api/games`), igual en desarrollo y en producción.

- `POST /games` crear partida (color, nivel) · `POST /games/{id}/moves` jugada del usuario → respuesta del motor
- `POST /games/import` (PGN/FEN)
- `POST /games/{id}/analysis` lanza análisis · `GET /games/{id}/analysis/stream` (SSE progreso)
- `GET /games/{id}/review` resumen + jugadas clasificadas
- `GET /games/{id}/moves/{ply}/explanation?level=1|2`
- `POST /games/{id}/moves/{ply}/chat` (streaming)
- `GET /games` historial

## 7. Persistencia
SQLite: `Game`, `Move`, `PositionAnalysis` (cache por FEN+ajustes), `Explanation` (cache),
`ChatMessage`. Migraciones simples (Alembic o recreación en dev, decidir en fase 1).

## 8. Fuera de alcance (por ahora)
Multijugador, cuentas de usuario, exposición pública a internet, móvil nativo, entrenamiento de
modelos propios. El despliegue en una Raspberry Pi doméstica (LAN, Tailscale opcional) es un
objetivo final (ROADMAP Fase 8).
