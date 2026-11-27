"""Chess.com published-data API: monthly archives of a user's games
(https://www.chess.com/news/view/published-data-api).

Requests are sequential (parallel ones may be rate limited); on HTTP 429 wait and retry once.
Months are read oldest first, and games within a month by end time, so that an interrupted
sync can resume from the last game stored.
"""

import asyncio
import io
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

import chess.pgn
import httpx

from app.models.game import Platform, TimeClass
from app.sync.types import OnlineGame, SyncError

_CLASSES = {
    "bullet": TimeClass.BULLET,
    "blitz": TimeClass.BLITZ,
    "rapid": TimeClass.RAPID,
    "daily": TimeClass.CORRESPONDENCE,
}


def _start(pgn: str, end_time: int) -> datetime:
    """Start of the game from the PGN's UTCDate/UTCTime; the end time if missing."""
    headers = chess.pgn.read_headers(io.StringIO(pgn))
    if headers is not None:
        date, time = headers.get("UTCDate"), headers.get("UTCTime")
        if date and time:
            try:
                moment = datetime.strptime(f"{date} {time}", "%Y.%m.%d %H:%M:%S")
                return moment.replace(tzinfo=UTC)
            except ValueError:
                pass
    return datetime.fromtimestamp(end_time, UTC)


def parse_game(data: dict[str, Any]) -> OnlineGame | None:
    """One game of a monthly archive; None for variants and games without a PGN."""
    if data.get("rules") != "chess" or not data.get("pgn"):
        return None
    time_class = _CLASSES.get(str(data.get("time_class")))
    white, black = data.get("white", {}), data.get("black", {})
    if time_class is None or not white.get("username") or not black.get("username"):
        return None
    url = str(data.get("url", ""))
    return OnlineGame(
        platform=Platform.CHESSCOM,
        external_id=str(data.get("uuid") or url),
        url=url,
        pgn=str(data["pgn"]),
        played_at=_start(str(data["pgn"]), int(data.get("end_time", 0))),
        time_class=time_class,
        time_control=data.get("time_control"),
        white=str(white["username"]),
        black=str(black["username"]),
        white_elo=white.get("rating"),
        black_elo=black.get("rating"),
    )


async def _get(client: httpx.AsyncClient, url: str, retry_wait_s: float) -> httpx.Response:
    for attempt in range(2):
        response = await client.get(url)
        if response.status_code == 429 and attempt == 0:
            await asyncio.sleep(retry_wait_s)
            continue
        return response
    raise SyncError("Chess.com limita las peticiones: inténtalo dentro de un rato.")


def _next(year: int, month: int) -> tuple[int, int]:
    return (year + 1, 1) if month == 12 else (year, month + 1)


def _month(url: str) -> tuple[int, int] | None:
    parts = url.rstrip("/").split("/")
    try:
        return int(parts[-2]), int(parts[-1])
    except (IndexError, ValueError):
        return None


async def fetch_games(
    client: httpx.AsyncClient,
    base_url: str,
    username: str,
    since: datetime | None,
    until: datetime | None,
    retry_wait_s: float,
) -> AsyncIterator[OnlineGame]:
    """Games of `username` started in [since, until) (aware UTC), oldest first."""
    base = f"{base_url.rstrip('/')}/pub/player/{username.lower()}"
    response = await _get(client, f"{base}/games/archives", retry_wait_s)
    if response.status_code == 404:
        raise SyncError(f"Chess.com no conoce al usuario «{username}».")
    if response.status_code != 200:
        raise SyncError(f"Chess.com respondió con el error {response.status_code}.")
    months = sorted(m for m in map(_month, response.json().get("archives", [])) if m)
    for year, month in months:
        # A game is in the archive of the month it ended: it may have started the month before.
        if since is not None and (year, month) < (since.year, since.month):
            continue
        # ...and one that started before `until` may have ended the month after.
        if until is not None and (year, month) > _next(until.year, until.month):
            continue
        page = await _get(client, f"{base}/games/{year}/{month:02d}", retry_wait_s)
        if page.status_code != 200:
            raise SyncError(f"Chess.com respondió con el error {page.status_code}.")
        games = sorted(page.json().get("games", []), key=lambda g: int(g.get("end_time", 0)))
        for data in games:
            game = parse_game(data)
            if game is None:
                continue
            if since is not None and game.played_at < since:
                continue
            if until is not None and game.played_at >= until:
                continue
            yield game
