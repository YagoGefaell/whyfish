from fastapi import Request

from app.engine.state import EngineState


def get_engine_state(request: Request) -> EngineState:
    state: EngineState = request.app.state.engine_state
    return state
