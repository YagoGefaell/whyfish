# Roadmap

Cada fase termina con algo usable y comprobable. No empezar una fase sin cerrar la anterior
(tests en verde + `docs/PROGRESS.md` actualizado).

## Fase 0 — Esqueleto
- Monorepo `backend/` + `frontend/`, `uv`, `pnpm`, `Makefile`, `.env.example`, ruff/mypy/eslint.
- Wrapper de Stockfish: arranque, configuración, cierre limpio, healthcheck.
- **Aceptación:** `make dev` levanta ambos; `GET /api/health` devuelve versión de Stockfish; `make test` pasa.

## Fase 1 — Jugar contra el bot
- Tablero en React con drag & drop, promoción, último movimiento resaltado, girar tablero.
- Crear partida, niveles del bot, jugadas por API, detección de fin de partida.
- Deshacer jugada y pista (SPEC §1.1), desactivadas por defecto.
- Guardar partida en SQLite y exportar PGN.
- **Aceptación:** puedo jugar una partida completa contra cada nivel y descargar el PGN.

## Fase 2 — Motor de análisis y clasificación
- Análisis en segundo plano con MultiPV y pool de motores en paralelo (nº de motores y tiempo
  por posición configurables), progreso por SSE, caché por FEN.
- Conversión a win%, clasificación completa (SPEC §3, en el orden de evaluación definido), precisión, momentos clave.
- Fixtures de clasificación con tests.
- **Aceptación:** `pytest tests/analysis` pasa con los fixtures; analizar una partida de 40 jugadas
  tarda < 60 s con ajustes por defecto; endpoint `/review` devuelve todo.

## Fase 3 — Interfaz de revisión
- Barra y gráfica de evaluación, lista de jugadas con símbolos, resumen, momentos clave,
  flechas, navegación con teclado, exploración de variantes.
- Importar PGN/FEN.
- **Aceptación:** reviso una partida importada de principio a fin sin tocar la API a mano.

## Fase 3.5 — Rediseño de la revisión
- Tema oscuro sobrio (Inter local), insignias de clasificación en SVG propio, iconos con
  lucide-react, piezas cburnett (BSD), cero emojis; coherente en todas las pantallas.
- Revisión estilo "coach": Resumen primero (precisión, categorías, momentos clave,
  "Empezar revisión"), panel con frase corta + explicación, mejor jugada automática cuando la
  jugada no fue la mejor ("Ver línea" numerada), "Siguiente error" (N), detalles del motor
  plegados; gráfica en el panel; franjas de jugador con precisión; tablero que ocupa todo el
  alto; diseño móvil.
- **Aceptación:** capturas de Playwright (1920×1080, 1366×768, móvil) revisadas por el
  usuario; `make test-e2e` comprueba tablero ≥ 600 px en 1366×768, todo dentro de la ventana
  y el conjunto centrado.

## Fase 4 — Hechos y explicaciones por plantilla
- `analysis/facts.py` con todos los detectores de SPEC §4 y tests por detector.
- Plantillas de nivel 1 y 2 en español, con jugadas marcadas `[[SAN]]`.
- Frontend: render de las marcas `[[SAN]]` como jugadas clicables que se muestran en el tablero.
- **Aceptación:** cada jugada clasificada como ?!, ?, ??, ! o !! tiene explicación de nivel 1
  coherente sin LLM; revisión manual de 20 jugadas de fixtures sin afirmaciones falsas.

## Fase 5 — Explicaciones con LLM
- `LLMProvider` + Anthropic/OpenAI/Ollama, prompts versionados, jugadas marcadas `[[SAN]]` validadas contra los hechos,
  reintento, caché.
- **Aceptación:** cambiar `LLM_PROVIDER` en `.env` cambia el proveedor sin tocar código; un test
  con un proveedor fake que inventa una jugada demuestra que se detecta y se degrada a plantilla.

## Fase 6 — Coach interactivo
- Chat por jugada con herramientas (SPEC §5.1 nivel 3), streaming, historial.
- Modo "Pruébalo tú" en errores.
- **Aceptación:** pregunto "¿y si juego X?" y la respuesta usa la evaluación real de X.

## Fase 7 — Aprendizaje a largo plazo (opcional)
- Importar partidas desde Lichess/Chess.com.
- Estadísticas por patrón (tipo de error, fase, motivo táctico), aperturas problemáticas.
- Ejercicios generados a partir de los propios errores (repetición espaciada).

## Fase 8 — Despliegue en Raspberry Pi (opcional)
- Imagen Docker para ARM64 (o multi-arch) con frontend compilado servido por el backend.
- `compose.yaml` con `restart: unless-stopped` y volumen para la base SQLite.
- Stockfish para ARM (build oficial `linux-arm64`) dentro de la imagen.
- Límites de CPU y memoria del contenedor y ajustes del motor por `.env`.
- Acceso en la LAN; Tailscale opcional para acceder desde fuera. Sin exposición pública a internet.
- **Aceptación:** la app arranca sola en la Pi tras reiniciarla y es accesible desde otro
  dispositivo de la red.
