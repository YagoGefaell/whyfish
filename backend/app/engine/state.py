"""Holds the running engine (or the reason it is unavailable) for the app's lifetime."""

from dataclasses import dataclass

from app.engine.stockfish import Engine


@dataclass
class EngineState:
    engine: Engine | None = None
    error: str | None = None
