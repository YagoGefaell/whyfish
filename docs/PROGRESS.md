# Progreso

_Claude Code mantiene este archivo al final de cada sesión._

## Fase actual
Fase 1 — **completada** (2026-11-25). Siguiente: Fase 2 (motor de análisis y clasificación).

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
  - Tablas: el bot no las acepta antes de la jugada `DRAW_MIN_FULLMOVE` (20), sin consultar
    al motor; la respuesta indica el motivo (`declined_reason`: `too_early` | `position`).
  - Nueva partida desde FEN (campo opcional en el formulario). El backend valida formato,
    legalidad (`board.is_valid()`) y que no esté terminada; mensajes en español. Si en la FEN
    mueve el bot, juega primero. PGN con `[SetUp "1"]` y `[FEN "..."]`. La lista de jugadas
    numera según la FEN (turno y número de jugada).
  - Tests: backend 91 unitarios + 9 integración; frontend 27.

## Pendiente / siguiente paso
- Probar la UI a mano en el navegador (arrastrar y soltar, promoción) — no automatizado.
- Fase 2: plan a proponer.

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
- **Tablas:** el bot acepta solo desde la jugada 20 (`DRAW_MIN_FULLMOVE`, número de jugada del
  tablero; en partidas desde FEN cuenta el de la FEN) y si su evaluación (su punto de vista) es
  ≤ +0,3 (`DRAW_ACCEPT_MAX_CP`).
- **Partida desde FEN:** posición legal y no terminada, validada en el backend; FEN vacío =
  posición inicial normal.
- **Deshacer:** quita tu última jugada y la respuesta del bot; solo en partidas en curso.
  **Pista:** casilla de la pieza a mover (búsqueda a fuerza completa, `HINT_TIME_S`). Ambas se
  activan al crear la partida, se cuentan y se anotan en el PGN (`[Assists "undo:N hint:N"]`).
- **El servidor manda:** python-chess valida; chess.js solo para vista previa/promoción.
- **BD sin migraciones:** `create_all` al arrancar; Alembic antes de la Fase 8. Cambiar el
  esquema implica borrar `data/whyfish.db` hasta entonces.
- **Reloj:** descartado (eliminado de SPEC §1.1).
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
- Elo de Principiante/Novato aproximado y sin calibrar.
- SQLite se usa con sesión síncrona dentro de endpoints async: bloquea el event loop unos ms
  por petición. Aceptable para un solo usuario; revisar si molesta en la Fase 2 (SSE).
- Starlette avisa de que `httpx` está deprecado para `TestClient` en favor de `httpx2`.
  Cambio pendiente (en esta sesión no se aplicó); de momento solo es un warning.
- Revisar la subida a TypeScript 7 cuando typescript-eslint lo soporte.
- Si un ping vence por timeout, python-chess cancela el comando y el protocolo puede quedar
  inconsistente; hoy se reporta 503, pero no hay reinicio automático del motor.
- Con `--reload`, cada recarga del backend reinicia Stockfish (aceptable en dev).
