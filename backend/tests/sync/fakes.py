"""Fake Lichess / Chess.com responses for the sync tests (httpx.MockTransport, no network)."""

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import httpx


def pgn(white: str, black: str, *, clocks: bool = True, extra: str = "") -> str:
    """A short real game (scholar's mate) with %clk comments."""

    def c(t: str) -> str:
        return f" {{ [%clk {t}] }}" if clocks else ""

    moves = (
        f"1. e4{c('0:03:00')} 1... e5{c('0:02:58')} 2. Qh5{c('0:02:55')} 2... Nc6{c('0:02:50')} "
        f"3. Bc4{c('0:02:40')} 3... Nf6{c('0:00:20')} 4. Qxf7#{c('0:02:20')} 1-0"
    )
    return (
        f'[Event "Test"]\n[White "{white}"]\n[Black "{black}"]\n[Result "1-0"]\n'
        f'[TimeControl "180+2"]\n{extra}\n{moves}\n'
    )


def ms(moment: datetime) -> int:
    return int(moment.astimezone(UTC).timestamp() * 1000)


def lichess_game(
    game_id: str,
    created: datetime,
    white: str = "Yago",
    black: str = "Rival",
    *,
    variant: str = "standard",
    speed: str = "blitz",
) -> dict[str, Any]:
    return {
        "id": game_id,
        "variant": variant,
        "speed": speed,
        "createdAt": ms(created),
        "players": {
            "white": {"user": {"name": white}, "rating": 1500},
            "black": {"user": {"name": black}, "rating": 1600},
        },
        "clock": {"initial": 180, "increment": 2},
        "pgn": pgn(white, black),
    }


def chesscom_game(
    uuid: str,
    start: datetime,
    white: str = "yago",
    black: str = "rival",
    *,
    rules: str = "chess",
    time_class: str = "rapid",
) -> dict[str, Any]:
    header = f'[UTCDate "{start:%Y.%m.%d}"]\n[UTCTime "{start:%H:%M:%S}"]'
    return {
        "uuid": uuid,
        "url": f"https://www.chess.com/game/live/{uuid}",
        "rules": rules,
        "time_class": time_class,
        "time_control": "600",
        "end_time": int(start.astimezone(UTC).timestamp()) + 600,
        "white": {"username": white, "rating": 1400, "result": "win"},
        "black": {"username": black, "rating": 1450, "result": "checkmated"},
        "pgn": pgn(white, black, extra=header),
    }


@dataclass
class FakePlatforms:
    """Serves the games below; records the requests. `fail` / `limit_once` simulate errors."""

    lichess: list[dict[str, Any]] = field(default_factory=list)
    chesscom: dict[tuple[int, int], list[dict[str, Any]]] = field(default_factory=dict)
    requests: list[httpx.Request] = field(default_factory=list)
    fail: set[str] = field(default_factory=set)  # "lichess" / "chesscom": network error
    limit_once: set[str] = field(default_factory=set)  # answer 429 once

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        host = "lichess" if "lichess" in request.url.host else "chesscom"
        if host in self.fail:
            raise httpx.ConnectError("offline", request=request)
        if host in self.limit_once:
            self.limit_once.discard(host)
            return httpx.Response(429)
        path = request.url.path
        if host == "lichess":
            since = int(request.url.params.get("since", 0))
            until = int(request.url.params.get("until", 2**62))
            games = sorted(self.lichess, key=lambda g: g["createdAt"])
            lines = [json.dumps(g) for g in games if since <= g["createdAt"] <= until]
            return httpx.Response(200, text="\n".join(lines) + "\n")
        if path.endswith("/games/archives"):
            months = sorted(self.chesscom)
            urls = [f"https://api.chess.com{path[:-9]}/{y}/{m:02d}" for y, m in months]
            return httpx.Response(200, json={"archives": urls})
        year, month = (int(p) for p in path.rstrip("/").split("/")[-2:])
        return httpx.Response(200, json={"games": self.chesscom.get((year, month), [])})

    def client_factory(self) -> Callable[[], httpx.AsyncClient]:
        return lambda: httpx.AsyncClient(transport=httpx.MockTransport(self.handler))
