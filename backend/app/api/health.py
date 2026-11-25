from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel

from app.api.deps import get_engine_state
from app.engine.state import EngineState
from app.engine.stockfish import EngineUnavailableError

router = APIRouter()


class EngineHealth(BaseModel):
    status: Literal["ok", "unavailable"]
    name: str | None = None
    detail: str | None = None


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    engine: EngineHealth


@router.get("/health")
async def health(
    response: Response,
    engine_state: Annotated[EngineState, Depends(get_engine_state)],
) -> HealthResponse:
    engine = engine_state.engine
    if engine is None:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return HealthResponse(
            status="degraded",
            engine=EngineHealth(status="unavailable", detail=engine_state.error),
        )
    try:
        await engine.ping()
    except EngineUnavailableError as exc:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return HealthResponse(
            status="degraded",
            engine=EngineHealth(status="unavailable", name=engine.name, detail=str(exc)),
        )
    return HealthResponse(status="ok", engine=EngineHealth(status="ok", name=engine.name))
