"""Interface settings (phase 6.5): colour mode, board and piece set, stored in AppSetting."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy import Engine as DbEngine

from app.config import UI
from app.settings_store import get_setting, set_setting

router = APIRouter()

ColorMode = Literal["system", "light", "dark"]
BoardTheme = Literal["brown", "blue", "gray", "wood", "slate"]
PieceSet = Literal["cburnett", "mpchess", "chessnut", "rhosgfx"]

COLOR_MODES: tuple[str, ...] = ("system", "light", "dark")
BOARDS: tuple[str, ...] = ("brown", "blue", "gray", "wood", "slate")
PIECE_SETS: tuple[str, ...] = ("cburnett", "mpchess", "chessnut", "rhosgfx")

KEYS = {"color_mode": "ui_color_mode", "board": "ui_board", "pieces": "ui_pieces"}


class UiSettings(BaseModel):
    color_mode: ColorMode
    board: BoardTheme
    pieces: PieceSet


def get_db(request: Request) -> DbEngine:
    db: DbEngine = request.app.state.db_engine
    return db


Db = Annotated[DbEngine, Depends(get_db)]


def _pick(db: DbEngine, key: str, default: str, allowed: tuple[str, ...]) -> str:
    """A stored value, or the default if missing or no longer valid (e.g. a removed board)."""
    value = get_setting(db, key, default)
    return value if value in allowed else default


def read_ui_settings(db: DbEngine) -> UiSettings:
    return UiSettings.model_validate(
        {
            "color_mode": _pick(db, KEYS["color_mode"], UI.color_mode, COLOR_MODES),
            "board": _pick(db, KEYS["board"], UI.board, BOARDS),
            "pieces": _pick(db, KEYS["pieces"], UI.pieces, PIECE_SETS),
        }
    )


@router.get("/settings/ui")
def get_ui_settings(db: Db) -> UiSettings:
    return read_ui_settings(db)


@router.put("/settings/ui")
def put_ui_settings(body: UiSettings, db: Db) -> UiSettings:
    set_setting(db, KEYS["color_mode"], body.color_mode)
    set_setting(db, KEYS["board"], body.board)
    set_setting(db, KEYS["pieces"], body.pieces)
    return read_ui_settings(db)
