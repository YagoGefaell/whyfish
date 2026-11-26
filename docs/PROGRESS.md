# Progreso

_Claude Code mantiene este archivo al final de cada sesión._

## Fase actual
Fase 3.5 (rediseño de la revisión) — **cerrada** (2026-11-25). Siguiente: Fase 4 (hechos y
explicaciones por plantilla): leer SPEC + ROADMAP + este archivo y proponer el plan.

## Hecho
- Reorganización del repo: `CLAUDE.md` en raíz, docs en `docs/`, README y .gitignore.
- SPEC/ROADMAP/CLAUDE actualizados con las decisiones de abajo.
- Stockfish 19 (build oficial `linux-x86-64-universal`, selecciona AVX512-ICL en esta CPU)
  instalado en `~/.local/bin/stockfish`.
- **Backend** (`backend/`, uv, Python 3.12): FastAPI con `create_app()` y motor inyectable;
  `app/config.py` (pydantic-settings, lee `.env` de la raíz); `app/engine/stockfish.py`
  (`Engine` Protocol + `StockfishEngine`: arranque con timeout, `Threads`/`Hash`, ping,
  cierre limpio incluso si el proceso ya murió); `GET /api/health` → 200 con nombre/versión o
  503 con el motivo. ruff + `mypy --strict` limpios.
- **Tests backend:** 5 unitarios con `FakeEngine` + 4 de integración con Stockfish real
  (marcador `stockfish`, se saltan si falta el binario).
- **Frontend** (`frontend/`, pnpm): Vite + React 19 + TS `strict`, Tailwind v4, ESLint
  (typescript-eslint strictTypeChecked) + Prettier, Vitest + Testing Library. Página mínima
  que muestra el estado del motor vía `/api/health` (proxy Vite sin reescritura).
- `Makefile`: `install`, `dev`, `test`, `lint`, `fmt`, `help`. `.env.example`.
- Aceptación verificada: `make dev` levanta ambos; `/api/health` (directo y vía Vite) devuelve
  `Stockfish 19`; `make test` y `make lint` pasan; Ctrl-C cierra motor y servidores sin errores.
- **Fix post-cierre:** pings concurrentes a `/api/health` (StrictMode de React duplica el fetch en dev)
  se cancelaban entre sí en python-chess → 500/503. Ahora `StockfishEngine` serializa todos los
  comandos UCI con un `asyncio.Lock`. Test de regresión con 5 pings concurrentes.
- Proyecto renombrado a **whyfish** (README, CLAUDE.md, SPEC, títulos, nombres de paquete).

### Fase 1 — Jugar contra el bot
- **Backend:**
  - `app/play/rules.py` (lógica pura: validar jugadas, fin de partida, deshacer, niveles→opciones
    UCI, aceptación de tablas, PGN); `app/play/service.py` (`GameRepository` para BD sin motor +
    `GameService` para comandos con motor inyectado); `app/models/game.py` (`Game`, `Move`);
    `app/db.py`; `app/api/games.py` + `schemas.py`.
  - Endpoints bajo `/api`: `GET /levels`, `GET|POST /games`, `GET /games/{id}`,
    `POST /games/{id}/moves|undo|hint|resign|draw`, `GET /games/{id}/pgn`.
  - Las lecturas (partida, historial, PGN) funcionan sin motor; los comandos dan 503 si no hay.
    Si el motor falla a mitad de jugada no se guarda nada.
  - Mutaciones de partida serializadas con un lock global (app de un solo usuario).
  - `/api/health` con el motor ocupado no hace ping: responde `ok` + `busy: true` si el proceso
    vive (resuelve la deuda de la Fase 0).
- **Frontend:** react-router (`/`, `/play/:id`, `/games`); tablero react-chessboard con
  arrastrar y soltar, diálogo de promoción propio, última jugada resaltada, rey en jaque, casilla
  de pista, girar tablero; lista de jugadas; controles (deshacer, pista, tablas, abandonar con
  confirmación, descargar PGN); historial. Movimiento optimista con chess.js y resincronización
  con la FEN del servidor.
- **Tests:** backend 67 unitarios (`make test`, ~2 s) + 9 de integración con Stockfish real
  (`make test-integration`, ~10 s; partida completa contra los 5 niveles + PGN válido; todas
  terminan en mate). Frontend 24 (Vitest). Recarga a mitad de partida cubierta en ambos:
  backend (app nueva sobre la misma BD → estado idéntico, incluso sin motor) y frontend
  (`/play/:id` reconstruye posición, turno, jugadas y ayudas usadas desde el servidor).
- Verificado a mano por API vía Vite con Stockfish real: crear, jugar, health durante búsqueda,
  pista, deshacer, tablas, PGN.
- **Ajustes de cierre (aprobados tras la revisión):**
  - Tablas: el bot no las acepta hasta que se hayan jugado `DRAW_MIN_MOVES` (20) jugadas
    completas en la propia partida, sin consultar al motor; la respuesta indica el motivo
    (`declined_reason`: `too_early` | `position`).
  - Nueva partida desde FEN (campo opcional en el formulario). El backend valida formato,
    legalidad (`board.is_valid()`) y que no esté terminada; mensajes en español. Si en la FEN
    mueve el bot, juega primero. PGN con `[SetUp "1"]` y `[FEN "..."]`. La lista de jugadas
    numera según la FEN (turno y número de jugada).
  - Tests: backend 94 unitarios + 9 integración; frontend 27.

### Fase 2 — Motor de análisis y clasificación
- **Lógica pura** (`app/analysis/`): `winprob.py` (win% y precisión Lichess, fórmulas
  documentadas), `material.py` (material, SEE con piezas clavadas/rayos X, piezas recién en
  prise), `book.py` (libro lichess-org/chess-openings, CC0, copiado en `app/analysis/data/`),
  `classify.py` (SPEC §3 en el orden acordado), `review.py` (revisión, resumen por jugador,
  momentos clave con perspectiva), `positions.py` (posiciones con historia reversible y clave
  de caché).
- **Motor y trabajo:** `engine/pool.py` (motores de análisis aparte del de juego, se arrancan
  por análisis y se cierran al terminar), `analysis/runner.py` (`AnalysisService`: un análisis a
  la vez, caché `PositionAnalysis`, progreso, análisis interrumpidos → fallidos al arrancar).
- **API:** `POST|GET /api/games/{id}/analysis`, `GET .../analysis/stream` (SSE nativo de
  FastAPI: `progress`, `done`, `failed`), `GET .../review`. La revisión se recalcula en cada
  petición desde la caché (ajustar umbrales no exige reanalizar).
- **CLI:** `make analyze PGN=…` imprime la tabla de jugadas clasificadas y el tiempo.
- **Tests:** 172 rápidos (`make test`); integración con Stockfish real (~50 s): 14 fixtures
  reales revisados por el usuario, a profundidad 16 + aceptación (Byrne–Fischer, 82 medias
  jugadas, **11,2 s** con ajustes por defecto vía API). `pytest tests/analysis` pasa entero.
- **Cierre (decisiones del usuario tras revisar los fixtures):** Teoría solo con Δ < 10;
  sacrificio también con una pieza que ya estaba en prise si podía salvarse y no se hizo;
  brillante con win% posterior ≥ 45; el mate en una nunca es "!". Profundidad de los fixtures
  bajada a 16 (los 14 dan lo mismo que a 20, 4× más rápido).
- Bugs encontrados y corregidos durante la fase: `POST /analysis` síncrono no podía crear la
  tarea (sin event loop); el 404 del SSE se lanzaba dentro del generador (demasiado tarde).

### Fase 3 — Interfaz de revisión
- **Migraciones con Alembic** (`backend/migrations/`): 0001 = esquema de las fases 1–2,
  0002 = partidas importadas. `init_db` marca con 0001 una base sin `alembic_version` y migra.
  Copia de seguridad previa en `data/backups/whyfish-2026-11-25-pre-alembic.db`; migración
  probada sobre una copia (partida 1 intacta). La base real se migra al próximo arranque.
- **Importar PGN:** `POST /api/games/import`, detección del color por `PLAYER_NAME`, 422
  `color_required` con los nombres; partidas importadas analizables siempre y no jugables.
- **Evaluación bajo demanda:** `POST /api/analysis/evaluate {fen, moves?, multipv?}` con el
  pool de análisis, ahora compartido y persistente (`PoolManager`: se arranca al usarse y se
  cierra tras `ANALYSIS_POOL_IDLE_S` sin uso). Respuesta solo con hechos (UCI, SAN, cp/mate,
  win%), pensada como herramienta del coach (Fase 6).
- **Frontend:** `/review/:id` (tablero con flechas e icono de clasificación en la casilla de
  destino, barra de evaluación vertical/horizontal, gráfica SVG clicable, lista, detalle con
  línea mejor y refutación clicables, hueco `MoveExplanation` con texto provisional, resumen y
  momentos clave), exploración de variantes con evaluación (debounce 250 ms + abort), teclado
  (← → Inicio Fin Esc), progreso del análisis por SSE, `/import`, botones "Analizar partida"
  al terminar y en el Historial, diseño móvil con pestañas.
- **Tests:** backend 203 rápidos + 24 integración; frontend 40 (Vitest); **e2e Playwright**
  (`make test-e2e`, escritorio + Pixel 7) con capturas en `frontend/e2e-artifacts/`.
- Bugs encontrados con el e2e: Playwright recarga el config en cada worker y borraba la base
  de prueba en uso (ahora la ruta se fija una vez y se pasa por entorno).

### Fase 3.5 — Rediseño de la revisión
- **Tema:** oscuro sobrio (tokens en `src/index.css`), Inter servida localmente, foco visible,
  contraste del texto secundario ≥ 5,4:1. Botones `.btn`, `.btn-primary`, `.btn-icon`, `.panel`.
- **Iconos:** `ClassBadge` (insignias SVG propias, color fijo por categoría), `lucide-react` para
  la interfaz; sin emojis en toda la app.
- **Piezas:** set cburnett de Wikimedia Commons (Colin M.L. Burnett), usado bajo **BSD** de su
  licencia triple; aviso en `frontend/src/assets/pieces/cburnett/LICENSE.md`. Ajustadas antes
  de la Fase 4 (ver abajo).
- **Revisión:** Resumen primero (posición final en el tablero, precisión, tabla de categorías
  con la columna del usuario destacada, momentos clave, "Empezar revisión"); panel con la
  gráfica arriba, pestañas, coach (insignia + "4… Bxf3 es una imprecisión", explicación
  provisional, "La mejor era X" + flecha verde automáticas si la jugada no fue la mejor,
  "Ver línea" numerada y clicable, "Detalles del motor" plegado que recuerda su estado), lista
  en dos columnas con insignias solo en !!, !, ?!, ?, ?? y ✗, navegación con "Siguiente error"
  (N) y ayuda de atajos. Tablero con franjas de jugador (usuario abajo, precisión a la
  derecha), resaltado de origen/destino en el color de la clasificación e insignia en la
  esquina, animación solo en pasos sueltos. Mientras se analiza, el tablero ya muestra la
  partida y el panel la barra de progreso.
- **Maquetación:** el tablero ocupa todo el alto disponible (616 px en 1366×768); tablero +
  panel centrados; en móvil, tablero a todo el ancho y panel debajo.
- **Cabecera de la app:** sin "Motor listo"; aviso discreto solo si el motor no responde.
- **Tests:** frontend 45 (Vitest); e2e en 1920×1080, 1366×768 y Pixel 7 con capturas y
  comprobaciones de tamaño y centrado.

### Ajuste del tablero (antes de la Fase 4)
- **Piezas al 100 % de la casilla**, sin escalado (el SVG trae su margen, como Lichess /
  chessground: pieza de 12,5 % con `background-size: cover`). Un solo componente `PieceImage`
  para la casilla, la pieza arrastrada y el diálogo de coronación.
- **Causa del descentrado:** react-chessboard mete la pieza en un div sin tamaño dentro de una
  casilla flex; el 100 % se resolvía contra el contenido y la pieza quedaba pegada arriba. Ahora
  el contenido de la casilla (`SQUARE_CONTENT`, en ambos `squareRenderer`) va fijado a sus bordes
  como grid estirado. Las coordenadas llevan `z-index` para seguir por encima de las piezas.
- **Arrastre:** sin el `scale(1.2)` por defecto de la librería; mismo tamaño que en reposo y el
  cursor en el centro (`snapCenterToCursor`). Fantasma en origen con opacidad 0,3, como Lichess.
- Los SVG llevan ahora `viewBox="0 0 45 45"` (anotado en su LICENSE.md).
- **e2e `board.spec.ts`** (solo en el proyecto desktop-1920, contextos con DPR 1 y 2): la pieza
  coincide con la casilla al píxel, la arrastrada mide lo mismo y queda centrada en el cursor,
  y el diálogo de coronación muestra la pieza centrada llenando el botón. Recortes 4×4 en
  `frontend/e2e-artifacts/board-*.png`. Lichess bloquea navegadores headless (Cloudflare), así
  que la comparación se hizo contra el CSS de chessground.

### Fase 4 — Hechos y explicaciones por plantilla (pendiente de revisión)
- **Hechos** (`analysis/facts.py` + `analysis/detectors/`): piezas colgadas (SEE), amenazas
  creadas y neutralizadas, mate en 1 como amenaza, doble ataque, clavada, ataque a la
  descubierta, jaque doble, resultado de cada línea (material cerrado con SEE, mate, capturas,
  coronación), estructura de peones, escudo del rey, desarrollo, fase. Con casillas. Sin motor:
  salen de las líneas MultiPV guardadas.
- **Explicaciones** (`explain/`): idea principal por prioridad (SPEC §5.1, con la regla de la
  gran jugada), plantillas de nivel 1 y 2 en español con `[[SAN]]`, referencia por marca
  (posición base + jugadas UCI), validación de marcas lista para la Fase 5, anotaciones (nivel 1
  ≤ 3, nivel 2 ≤ 6). ~8 ms por explicación: sin caché hasta la Fase 5.
- **API:** `GET /api/games/{id}/moves/{ply}/explanation?level=1|2`.
- **Frontend:** texto con jugadas clicables (se muestran en el tablero como variante, o se salta
  a la jugada si es de la partida), "Profundizar", flechas roja/ámbar y casillas marcadas.
- **Informe:** muestra fija de 20 (regla en `explain/report.py`), 19 de las partidas del usuario,
  con diagrama, textos y hechos usados marcados. Las partidas del usuario se leyeron de
  `data/whyfish.db` en solo lectura (SHA-1 comprobado antes y después) y se analizaron en una base
  temporal.
- **Tests:** backend 274 (29 de detectores, 37 de explicaciones, API, informe), frontend 45, e2e
  con captura `*-review-explanation.png`.

## Pendiente / siguiente paso
- **Fase 4 implementada, pendiente de la revisión del usuario** (no cerrar hasta su OK).
  Informe: `docs/reports/explanations-fase4.html` (regenerar con `make explain-report`).
  acciones del coach está preparada para "Profundizar" (Fase 4) y "Pruébalo tú" (Fase 6).

## Decisiones tomadas
- **Notación:** SAN en inglés (K, Q, R, B, N) en todo el proyecto (backend, MoveFacts,
  plantillas, prompts, UI). Explicaciones en español, jugadas en inglés.
- **Marcas de jugada:** el texto generado (LLM y plantillas) marca jugadas como `[[Nf3]]`;
  el backend las extrae y valida contra los hechos (fallo → reintento → plantilla); el frontend
  las renderiza como jugadas clicables en el tablero (Fase 4).
- **Rendimiento del análisis:** pool de motores en paralelo (Fase 2); nº de motores y tiempo
  por posición configurables en `config.py` / `.env`.
- **Orden de clasificación:** teoría → oportunidad perdida → brillante → gran jugada → mejor →
  umbrales de Δ.
- **Tareas:** `Makefile` (sin justfile).
- **Deshacer y pista:** en la Fase 1.
- **Fase 0:** un solo motor (pool en Fase 2); si Stockfish no arranca, la API arranca y
  `/api/health` devuelve 503;
  `make test` = pytest + Vitest, tests de integración con Stockfish se saltan si falta el binario.
- **Rutas bajo `/api`** (sustituye a la decisión inicial de rutas sin prefijo): el backend
  monta todo bajo `/api` y Vite hace proxy sin reescribir. Igual en dev y en producción.
- **Despliegue:** objetivo final una Raspberry Pi (ARM64) en la LAN, Tailscale opcional;
  nunca expuesta a internet. Nada de Docker/compose/despliegue hasta la Fase 8 (añadida al
  ROADMAP). Sin dependencias solo x86; todo ajuste de rendimiento del motor por `.env`.
- **Niveles** (Fase 1): Principiante ~800 (`Skill Level` 0, profundidad 1), Novato ~1100
  (`Skill Level` 3, profundidad 4), Club ~1500 (`UCI_Elo` 1500), Fuerte ~2000 (`UCI_Elo` 2000),
  Máximo (fuerza completa). Todos con tope `BOT_MOVETIME_S`. Opciones UCI temporales por
  búsqueda (python-chess las restaura).
- **Fin de partida:** triple repetición y 50 jugadas terminan la partida automáticamente, pero
  solo cuando han ocurrido de verdad (no al poder reclamarse con la siguiente jugada).
- **Tablas:** el bot acepta solo cuando se han jugado al menos 20 jugadas completas (40 medias
  jugadas) en la propia partida (`DRAW_MIN_MOVES`; en partidas desde FEN el número de jugada de
  la FEN no cuenta) y si su evaluación (su punto de vista) es ≤ +0,3 (`DRAW_ACCEPT_MAX_CP`).
- **Partida desde FEN:** posición legal y no terminada, validada en el backend; FEN vacío =
  posición inicial normal.
- **Deshacer:** quita tu última jugada y la respuesta del bot; solo en partidas en curso.
  **Pista:** casilla de la pieza a mover (búsqueda a fuerza completa, `HINT_TIME_S`). Ambas se
  activan al crear la partida, se cuentan y se anotan en el PGN (`[Assists "undo:N hint:N"]`).
- **El servidor manda:** python-chess valida; chess.js solo para vista previa/promoción.
- **BD sin migraciones:** `create_all` al arrancar; Alembic antes de la Fase 8. Cambiar el
  esquema implica borrar `data/whyfish.db` hasta entonces.
- **Reloj:** descartado (eliminado de SPEC §1.1).
- **Pruebas manuales aisladas:** nunca contra `data/whyfish.db` ni el `make dev` del usuario;
  base temporal (`DATABASE_URL`) y otro puerto, comprobando antes los puertos (CLAUDE.md).
- **Fase 2:** gran jugada = mejor jugada (no única ni recaptura obvia) con 2.ª opción ≥ 10
  peor o de otra categoría (ganado > 75, perdido < 25). Momentos clave centrados en el usuario
  (errores por Δ ≥ 5, luego ! y !!; nunca jugadas del bot), con parámetro de perspectiva.
  Brillante: cualquier pieza propia que quede en prise (SEE, neto de lo capturado) y antes no lo
  estuviera —o ya lo estuviera pero pudiera salvarse y no se hiciera—, o caída de material ≥ 2
  en un horizonte de 6 medias jugadas (se extiende si hay un intercambio en curso); win%
  posterior ≥ 45 (se quitó "o mejora clara", no definible). Teoría solo si Δ < 10 (el libro
  contiene trampas). El mate en una nunca es gran jugada (★). Δ desde el
  MultiPV si la jugada está entre las líneas; si no, evaluación de la posición siguiente; Δ ≥ 0.
  Posiciones terminales sin motor. Valores por defecto: 0,5 s/posición, MultiPV 3, pool
  = núcleos − 1 (1–4), 1 hilo y 32 MB por motor.
- **Repeticiones (viable, hecho):** el motor recibe la posición raíz desde la última jugada
  irreversible + las jugadas reversibles (python-chess envía `position fen … moves …`); la
  clave de caché es esa misma información, así que la caché sigue siendo por posición.
- **Fase 3:** Alembic ya (no esperar a la Fase 8); importar solo PGN; exploración CON
  evaluación del motor (endpoint reutilizable por el coach); Playwright para e2e con capturas
  en escritorio y móvil (Chromium, ~125 MB en `~/.cache/ms-playwright`). Pool de análisis
  compartido por análisis y evaluaciones; un análisis en curso hace esperar a las
  evaluaciones (cola de motores).
- **Fase 3.5 (UX):** Resumen antes de la revisión; la mejor jugada se muestra sola cuando la
  jugada no fue la mejor (excelente, buena, ?!, ?, ??, ✗) y nunca en ★, !, !!, libro; "Siguiente
  error" solo recorre errores del usuario; gráfica siempre en el panel; ceros de la tabla en
  gris tenue (~3:1, decisión consciente); jugadas sin clasificar resaltadas en blanco
  translúcido.
- **Tests de integración aparte:** marcador `integration`, `make test-integration`, tiempos de
  búsqueda reducidos; `make test` no los ejecuta.
- **Un comando UCI a la vez por motor:** todo acceso al motor pasa por el lock de
  `StockfishEngine`. Cualquier método nuevo (jugar, analizar) debe respetarlo.
- **Paquete de ajedrez:** se usa `chess` (nombre actual en PyPI); `python-chess` 1.999 es
  solo un alias de transición.
- **ESLint en vez de oxlint:** la plantilla actual de Vite trae oxlint; se sustituye por
  ESLint + Prettier según CLAUDE.md.
- **TypeScript fijado a ~6.0:** typescript-eslint 8.x aún no soporta TS 7 (peer `<6.1`).
- **jsdom fijado a ^29:** jsdom 30+ exige Node ≥ 24.15 (local: 24.14).
- `.env` se lee siempre de la raíz del repo; `STOCKFISH_PATH` debe ser ruta absoluta (no se expande `~`).

## Ideas futuras
- Nivel **"Personalizado"** con selector de Elo (1320–3190, rango de `UCI_Elo` en Stockfish 19).

## Deuda técnica / dudas abiertas
- **Corregido (2026-11-26): brillantes falsos.** 8.Bd2 en jaque (partida 6) y 5… Bd6 (partida 1)
  salían !!. El sacrificio se mide ahora con material resuelto por quiescencia y exige una
  alternativa que conserve el material (`app/analysis/sacrifice.py`, SPEC §3.1). Las !! que quedan
  en el fixture de Kasparov (25.Re7+, 26.Qxd4+, 28.Qc3, 29.Ra7, 30.Rxb7, 36.Bf1, 37.Rd7) y en
  Fischer (14…Qb6, 15…Nxc3) son piezas realmente ofrecidas dentro de la combinación, pero la
  tradición solo da !! a 24.Rxd4 y 17…Be6/11…Na4. Pendiente de decisión del usuario: ¿limitar a
  una !! por combinación (p. ej. no repetir si la jugada anterior propia ya fue !!)?
- Explicaciones genéricas en ?! posicionales sin hechos (el informe las marca "faltan hechos").
- Desviación, sobrecarga y rayos X sin detectar (SPEC §4).
- Elo de Principiante/Novato aproximado y sin calibrar.
- Fixture frágil: Kasparov 24.Rxd4 queda en ~46,3 % con umbral 45; otra versión de Stockfish
  podría cambiarlo. Si un fixture cambia tras actualizar el motor, revisar con el usuario.
- Insignias con "!!", "?!"… dibujadas como texto SVG: dependen de que cargue Inter (local).
- Las evaluaciones de exploración esperan si hay un análisis en curso usando todos los motores.
- Los tests rápidos del backend tardan ~13 s (cada app de prueba ejecuta las migraciones).
- Cabeceras PGN en las partidas jugadas: el `Event` es "whyfish" y la `Date` la de creación.
- El libro tarda ~1,8 s en cargarse la primera vez (después queda en memoria).
- SQLite se usa con sesión síncrona dentro de endpoints async: bloquea el event loop unos ms
  por petición. Aceptable para un solo usuario; revisar si molesta en la Fase 2 (SSE).
- Starlette avisa de que `httpx` está deprecado para `TestClient` en favor de `httpx2`.
  Cambio pendiente (en esta sesión no se aplicó); de momento solo es un warning.
- Revisar la subida a TypeScript 7 cuando typescript-eslint lo soporte.
- Si un ping vence por timeout, python-chess cancela el comando y el protocolo puede quedar
  inconsistente; hoy se reporta 503, pero no hay reinicio automático del motor.
- Con `--reload`, cada recarga del backend reinicia Stockfish (aceptable en dev).
