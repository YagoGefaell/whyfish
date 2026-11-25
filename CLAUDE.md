# Chess Coach — contexto para Claude Code

## Qué es este proyecto
Aplicación web local para **jugar al ajedrez contra Stockfish y aprender de cada partida**.
Al terminar una partida, la app la analiza, clasifica cada jugada (estilo Game Review de
Chess.com) y da **una explicación sencilla por jugada en la que el usuario puede profundizar**.

El foco es **aprendizaje**, no puntuaciones: cada etiqueta (??, ?, ?!, !, !!) debe ir
acompañada de un *porqué* comprensible y verificable.

Documentos de referencia (léelos antes de empezar cualquier fase):
- `docs/SPEC.md` — especificación funcional y técnica (clasificación, explicaciones, arquitectura).
- `docs/ROADMAP.md` — fases de desarrollo con criterios de aceptación.
- `docs/PROGRESS.md` — estado actual. **Lo mantienes tú** al final de cada sesión.

## Principio central (no negociable)
**Stockfish calcula, el código extrae hechos, el LLM solo redacta.**
- El LLM nunca evalúa posiciones ni inventa jugadas o variantes.
- Todo lo que el LLM puede afirmar sale de un objeto `PositionFacts` / `MoveFacts`
  calculado con Stockfish + python-chess.
- Las jugadas en textos generados van marcadas como `[[Nf3]]`; el backend las extrae y
  valida contra los hechos. Si alguna no está en ellos, la explicación se regenera o se
  degrada a la plantilla determinista.
- La app debe funcionar **sin LLM** (explicaciones por plantilla). El LLM es una mejora.

## Stack
- **Backend:** Python 3.12, FastAPI, `python-chess` (motor vía `chess.engine`, async),
  SQLite con SQLModel, `pydantic-settings` para configuración, `pytest`.
- **Motor:** binario de Stockfish local (ruta en `.env`, `STOCKFISH_PATH`).
- **Frontend:** React + Vite + TypeScript, `chess.js` para reglas en cliente,
  tablero con `react-chessboard` (o `chessground` si se justifica), Tailwind.
- **LLM:** capa `LLMProvider` con implementaciones `anthropic`, `openai`, `ollama`
  y `none` (plantillas). Selección por `.env` (`LLM_PROVIDER`, `LLM_MODEL`, claves).
- **Gestión:** `uv` para Python, `pnpm` para el frontend. Un `Makefile`
  con `dev`, `test`, `lint` (sin justfile).

## Estructura
```
backend/
  app/
    api/          # routers FastAPI
    engine/       # wrapper Stockfish (pool, análisis, juego)
    analysis/     # clasificación de jugadas, extracción de hechos
    explain/      # plantillas, prompts, proveedores LLM, validación
    models/       # SQLModel
  tests/
    fixtures/     # PGN/FEN de prueba con resultados esperados
frontend/
  src/
    features/play/
    features/review/
    components/board/
docs/
```

## Convenciones
- Código, identificadores y commits en **inglés**; UI y explicaciones al usuario en **español**.
- Notación de jugadas: **SAN en inglés (K, Q, R, B, N) en todo el proyecto** — backend,
  `MoveFacts`, plantillas, prompts, UI. Nunca notación española (R = Rook, no Rey).
- Tipado estricto: `mypy --strict` en backend, `strict: true` en TS.
- Lógica de ajedrez pura (clasificación, hechos) **sin I/O**, testeable con FEN fijos.
  El motor se inyecta; en los tests unitarios se usa un fake con evaluaciones predefinidas.
- Toda constante ajustable (umbrales, profundidades, tiempos) en `app/config.py`, nunca dispersa.
- Ruff + mypy en backend, ESLint + Prettier en frontend.
- Nada de dependencias nuevas sin mencionarlo en el resumen de la sesión.

## Forma de trabajar
1. Trabaja **una fase del ROADMAP a la vez**. No adelantes trabajo de fases futuras.
2. Al empezar una fase: lee SPEC + ROADMAP + PROGRESS, propón un plan breve
   (archivos, decisiones, riesgos) y **espera mi OK** antes de escribir código.
3. Si una decisión de diseño no está cubierta en SPEC, plantéala con opciones y una
   recomendación; no la decidas en silencio.
4. Tests antes de dar algo por terminado. Los criterios de aceptación de la fase
   deben poder comprobarse con un comando.
5. Al cerrar la fase: actualiza `docs/PROGRESS.md` (hecho, pendiente, decisiones,
   deuda técnica) y dame un resumen de 5–10 líneas con cómo probarlo.
6. Si algo de SPEC resulta mala idea al implementarlo, dilo y propón el cambio en SPEC.
