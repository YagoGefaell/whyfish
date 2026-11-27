"""An online game as both platforms describe it, before it is stored. Pure."""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class OnlineGame:
    platform: str  # Platform value
    external_id: str
    url: str
    pgn: str  # with %clk comments when the platform has them
    played_at: datetime  # start of the game (aware, UTC)
    time_class: str  # TimeClass value
    time_control: str | None
    white: str
    black: str
    white_elo: int | None
    black_elo: int | None


class SyncError(Exception):
    """A platform could not be read (user-facing, Spanish)."""
