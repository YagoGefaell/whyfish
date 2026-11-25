# Progreso

_Claude Code mantiene este archivo al final de cada sesión._

## Fase actual
Fase 0 — **completada** (2026-11-25). Siguiente: Fase 1 (jugar contra el bot).

## Hecho
- Reorganización del repo: `CLAUDE.md` en raíz, docs en `docs/`, README y .gitignore.
- SPEC/ROADMAP/CLAUDE actualizados con las decisiones de abajo.
- Stockfish 19 (build oficial `linux-x86-64-universal`, selecciona AVX512-ICL en esta CPU)
  instalado en `~/.local/bin/stockfish`.
- **Backend** (`backend/`, uv, Python 3.12): FastAPI con `create_app()` y motor inyectable;
  `app/config.py` (pydantic-settings, lee `.env` de la raíz); `app/engine/stockfish.py`
  (`Engine` Protocol + `StockfishEngine`: arranque con timeout, `Threads`/`Hash`, ping,
  cierre limpio incluso si el proceso ya murió); `GET /health` → 200 con nombre/versión o
  503 con el motivo. ruff + `mypy --strict` limpios.
- **Tests backend:** 5 unitarios con `FakeEngine` + 3 de integración con Stockfish real
  (marcador `stockfish`, se saltan si falta el binario).
- **Frontend** (`frontend/`, pnpm): Vite + React 19 + TS `strict`, Tailwind v4, ESLint
  (typescript-eslint strictTypeChecked) + Prettier, Vitest + Testing Library. Página mínima
  que muestra el estado del motor vía `/api/health` (proxy Vite que quita el prefijo `/api`).
- `Makefile`: `install`, `dev`, `test`, `lint`, `fmt`, `help`. `.env.example`.
- Aceptación verificada: `make dev` levanta ambos; `/health` y `/api/health` devuelven
  `Stockfish 19`; `make test` y `make lint` pasan; Ctrl-C cierra motor y servidores sin errores.

## Pendiente / siguiente paso
- Fase 1: plan a proponer (tablero, partidas, niveles, SQLite/SQLModel, PGN, deshacer, pista).

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
  `/health` devuelve 503; rutas backend sin prefijo y Vite redirige `/api/*` quitando el prefijo;
  `make test` = pytest + Vitest, tests de integración con Stockfish se saltan si falta el binario.
- **Paquete de ajedrez:** se usa `chess` (nombre actual en PyPI); `python-chess` 1.999 es
  solo un alias de transición.
- **ESLint en vez de oxlint:** la plantilla actual de Vite trae oxlint; se sustituye por
  ESLint + Prettier según CLAUDE.md.
- **TypeScript fijado a ~6.0:** typescript-eslint 8.x aún no soporta TS 7 (peer `<6.1`).
- **jsdom fijado a ^29:** jsdom 30+ exige Node ≥ 24.15 (local: 24.14).
- `.env` se lee siempre de la raíz del repo; `STOCKFISH_PATH` debe ser ruta absoluta (no se expande `~`).

## Deuda técnica / dudas abiertas
- Starlette avisa de que `httpx` está deprecado para `TestClient` en favor de `httpx2`.
  Cambio pendiente (en esta sesión no se aplicó); de momento solo es un warning.
- Revisar la subida a TypeScript 7 cuando typescript-eslint lo soporte.
- Con `--reload`, cada recarga del backend reinicia Stockfish (aceptable en dev).
