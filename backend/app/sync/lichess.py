"""Lichess public API: the games of a user (https://lichess.org/api#tag/Games).

One request at a time (Lichess asks for it); on HTTP 429 wait and retry once. Games come in
ascending date order so that an interrupted sync can resume from the last one stored.
"""

import asyncio
import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

import httpx

from app.models.game import Platform, TimeClass
from app.sync.types import OnlineGame, SyncError

_SPEEDS = {
    "ultraBullet": TimeClass.BULLET,
    "bullet": TimeClass.BULLET,
    "blitz": TimeClass.BLITZ,
    "rapid": TimeClass.RAPID,
    "classical": TimeClass.CLASSICAL,
    "correspondence": TimeClass.CORRESPONDENCE,
}
# Standard chess only (also from a custom position); variants are skipped.
_VARIANTS = {"standard", "fromPosition"}


def _ms(moment: datetime) -> int:
    return int(moment.astimezone(UTC).timestamp() * 1000)


def parse_game(data: dict[str, Any], base_url: str) -> OnlineGame | None:
    """One ndjson line; None for variants, games without moves or without two players."""
    if data.get("variant") not in _VARIANTS or not data.get("pgn"):
        return None
    speed = _SPEEDS.get(str(data.get("speed")))
    players = data.get("players", {})
    white, black = players.get("white", {}), players.get("black", {})
    white_name = white.get("user", {}).get("name")
    black_name = black.get("user", {}).get("name")
    if speed is None or not white_name or not black_name:
        return None  # e.g. a game against Lichess' AI (no user)
    clock = data.get("clock")
    control = f"{clock['initial']}+{clock['increment']}" if clock else None
    created = datetime.fromtimestamp(int(data["createdAt"]) / 1000, UTC)
    return OnlineGame(
        platform=Platform.LICHESS,
        external_id=str(data["id"]),
        url=f"{base_url.rstrip('/')}/{data['id']}",
        pgn=str(data["pgn"]),
        played_at=created,
        time_class=speed,
        time_control=control,
        white=str(white_name),
        black=str(black_name),
        white_elo=white.get("rating"),
        black_elo=black.get("rating"),
    )


async def fetch_games(
    client: httpx.AsyncClient,
    base_url: str,
    username: str,
    since: datetime | None,
    until: datetime | None,
    retry_wait_s: float,
) -> AsyncIterator[OnlineGame]:
    """Games of `username` started in [since, until) (aware UTC), oldest first."""
    params: dict[str, str] = {
        "pgnInJson": "true",
        "clocks": "true",
        "opening": "true",
        "sort": "dateAsc",
    }
    if since is not None:
        params["since"] = str(_ms(since))
    if until is not None:
        params["until"] = str(_ms(until) - 1)
    url = f"{base_url.rstrip('/')}/api/games/user/{username}"
    for attempt in range(2):
        async with client.stream(
            "GET", url, params=params, headers={"Accept": "application/x-ndjson"}
        ) as response:
            if response.status_code == 429 and attempt == 0:
                await asyncio.sleep(retry_wait_s)
                continue
            if response.status_code == 404:
                raise SyncError(f"Lichess no conoce al usuario «{username}».")
            if response.status_code != 200:
                raise SyncError(f"Lichess respondió con el error {response.status_code}.")
            async for line in response.aiter_lines():
                if not line.strip():
                    continue
                game = parse_game(json.loads(line), base_url)
                if game is not None:
                    yield game
            return
    raise SyncError("Lichess limita las peticiones: inténtalo dentro de un rato.")
