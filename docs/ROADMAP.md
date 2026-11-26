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

## Fase 5 — "Ver por qué"
Que el usuario **vea** la secuencia entera que lleva a la consecuencia de una jugada (SPEC §5.4).
- Botón "Ver por qué" en toda jugada que no sea la mejor (excelente, buena, ?!, ?, ??, ✗):
  reproduce la refutación del motor tras la jugada hecha. "Ver la idea" en !, !! y ★ con
  explicación: reproduce la línea de la mejor jugada.
- La secuencia llega **hasta el punto de consecuencia** (material perdido o ganado con los
  cambios resueltos, mate, coronación, pieza atrapada), nunca a mitad de un intercambio. Si la
  línea en caché es corta, se extiende con el motor (pool de análisis, tiempo corto) y se
  cachea. Límite de seguridad configurable (p. ej. 20 plies); si no hay consecuencia clara, se
  reproduce hasta que la evaluación se estabiliza y el texto lo dice con prudencia.
- Reproducción automática (~1 s por jugada, configurable) con pausa, ◀ ▶ y "Volver a la
  partida" (Esc); piezas que se deslizan, origen y destino resaltados, una frase por paso
  generada desde los hechos, flechas de amenazas que se ejecutan después, y el paso de la
  consecuencia destacado (rojo en errores, verde en jugadas buenas).
- Tarjeta final con el balance ("Pierdes la dama por un caballo", "Mate en 4"), "Repetir" y
  "Volver a la partida". La secuencia también como texto numerado con jugadas clicables.
- "Pruébalo tú" en ?!, ?, ?? y ✗: repetir la posición anterior y buscar la mejor; si acierta se
  felicita, si no se ofrece "Ver por qué" de su intento (endpoint de evaluación) o la solución.
  Con "Pruébalo tú" activo, la flecha de la mejor jugada se oculta.
- Backend: función pura de punto de consecuencia + frases por paso + resumen (tests con FEN
  fijos); `GET /api/games/{id}/moves/{ply}/why?kind=refutation|idea` →
  `{steps: [{san, uci, fen, caption, annotations}], consequence_ply, summary}`; extensión de la
  línea con el motor, cacheada.
- **Aceptación:** un fixture donde la jugada pierde la dama 3 jugadas después reproduce las 6+
  plies hasta la captura y la recaptura, con el resumen correcto; e2e con captura en mitad de la
  reproducción y en la tarjeta final, en escritorio y móvil.

## Fase 6 — Aprendizaje a largo plazo (opcional)
- Importar partidas desde Lichess/Chess.com.
- Estadísticas por patrón (tipo de error, fase, motivo táctico), aperturas problemáticas.
- Ejercicios generados a partir de los propios errores (repetición espaciada).

## Fase 7 — Despliegue en Raspberry Pi (opcional)
- Imagen Docker para ARM64 (o multi-arch) con frontend compilado servido por el backend.
- `compose.yaml` con `restart: unless-stopped` y volumen para la base SQLite.
- Stockfish para ARM (build oficial `linux-arm64`) dentro de la imagen.
- Límites de CPU y memoria del contenedor y ajustes del motor por `.env`.
- Acceso en la LAN; Tailscale opcional para acceder desde fuera. Sin exposición pública a internet.
- **Aceptación:** la app arranca sola en la Pi tras reiniciarla y es accesible desde otro
  dispositivo de la red.

## Ideas futuras (descartadas por ahora)
Las explicaciones son siempre por plantilla. Se conservan las marcas `[[SAN]]` y su validador
por si se retoma una IA.
- **Explicaciones con LLM** (antigua Fase 5): `LLMProvider` + Anthropic/OpenAI/Ollama, prompts
  versionados, marcas `[[SAN]]` validadas contra los hechos, reintento y degradación a
  plantilla, caché.
- **Coach interactivo** (antigua Fase 6): chat por jugada con herramientas
  (`evaluate_position`, `analyze_move`, `get_threats`, `legal_moves`), streaming, historial;
  "¿y si juego X?" respondido con la evaluación real de X.
