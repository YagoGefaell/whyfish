# whyfish

Aplicación web local para jugar al ajedrez contra Stockfish y aprender de cada partida:
al terminar, la app analiza la partida, clasifica cada jugada (??, ?, ?!, !, !!) y explica
*por qué*, con explicaciones sencillas en las que se puede profundizar.

Principio central: **Stockfish calcula, el código extrae hechos, el LLM solo redacta.**
La app funciona sin LLM (explicaciones por plantilla).

## Documentación
- [docs/SPEC.md](docs/SPEC.md) — especificación funcional y técnica.
- [docs/ROADMAP.md](docs/ROADMAP.md) — fases de desarrollo.
- [docs/PROGRESS.md](docs/PROGRESS.md) — estado actual.

## Stack
Backend Python 3.12 + FastAPI + python-chess + SQLite · Frontend React + Vite + TypeScript ·
Motor Stockfish local.

## Requisitos
- Python 3.12 + [uv](https://docs.astral.sh/uv/)
- Node ≥ 24 + [pnpm](https://pnpm.io/)
- [Stockfish](https://stockfishchess.org/download/) (binario local)

## Puesta en marcha
```sh
cp .env.example .env      # y ajusta STOCKFISH_PATH (ruta absoluta)
make install
make dev                  # backend en :8000, frontend en http://localhost:5173
```

Abre http://localhost:5173, elige color y nivel y juega. Las partidas se guardan en
`data/whyfish.db` (SQLite; el esquema se migra solo al arrancar) y se pueden retomar desde
**Historial** o recargando la página. Al terminar, **Analizar partida** abre la revisión
(también desde el Historial). **Importar** acepta un PGN pegado o un archivo `.pgn`.

Revisión: ← → Inicio Fin para moverte, clic en la gráfica o en los momentos clave; mueve una
pieza en el tablero para explorar una variante (Esc para volver).

Otros comandos (`make help` para la lista):
- `make test` — tests rápidos (motor falso + Vitest).
- `make test-integration` — tests contra el Stockfish real (partida completa contra cada nivel).
- `make analyze PGN=partida.pgn` — analiza un PGN con Stockfish e imprime la clasificación de
  cada jugada (opciones: `ARGS="--time 1 --perspective black"`).
- `make test-e2e` — pruebas en navegador (Playwright, escritorio y móvil) con base y puertos
  propios (8765/5180); capturas en `frontend/e2e-artifacts/`. La primera vez: `make install-e2e`.
- `make lint`, `make fmt`.

La revisión de una partida terminada se obtiene por API: `POST /api/games/{id}/analysis`
(progreso en `GET /api/games/{id}/analysis/stream`, SSE) y `GET /api/games/{id}/review`.
Todas las rutas del backend van bajo `/api`. `GET /api/health` devuelve el estado y la versión de Stockfish.
