"""Fake Lichess and Chess.com public APIs for the e2e tests (standard library only).

    python3 e2e/fake_platforms.py 8766

Lichess under /lichess, Chess.com under /chesscom; two recent games of user "e2euser" each.
"""

import json
import sys
from datetime import UTC, datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

USER = "e2euser"
MOVES = (
    "1. e4 { [%clk 0:03:00] } 1... e5 { [%clk 0:02:58] } 2. Qh5 { [%clk 0:02:55] } "
    "2... Nc6 { [%clk 0:02:50] } 3. Bc4 { [%clk 0:02:40] } 3... Nf6 { [%clk 0:00:20] } "
    "4. Qxf7# { [%clk 0:02:20] } 1-0"
)


def pgn(white: str, black: str, start: datetime) -> str:
    return (
        f'[Event "e2e"]\n[White "{white}"]\n[Black "{black}"]\n[Result "1-0"]\n'
        f'[UTCDate "{start:%Y.%m.%d}"]\n[UTCTime "{start:%H:%M:%S}"]\n'
        f'[TimeControl "180+2"]\n\n{MOVES}\n'
    )


def lichess_games() -> list[dict[str, object]]:
    now = datetime.now(UTC)
    games = []
    for i, (white, black, speed) in enumerate(
        [(USER, "rival1", "blitz"), ("rival2", USER, "bullet")]
    ):
        start = now - timedelta(days=3 + i)
        games.append(
            {
                "id": f"e2eLi{i}",
                "variant": "standard",
                "speed": speed,
                "createdAt": int(start.timestamp() * 1000),
                "players": {
                    "white": {"user": {"name": white}, "rating": 1500 + i},
                    "black": {"user": {"name": black}, "rating": 1600 + i},
                },
                "clock": {"initial": 180, "increment": 2},
                "pgn": pgn(white, black, start),
            }
        )
    return games


def chesscom_month() -> tuple[tuple[int, int], list[dict[str, object]]]:
    start = datetime.now(UTC) - timedelta(days=2)
    game = {
        "uuid": "e2eCc0",
        "url": "https://www.chess.com/game/live/e2eCc0",
        "rules": "chess",
        "time_class": "rapid",
        "time_control": "600",
        "end_time": int(start.timestamp()) + 600,
        "white": {"username": USER, "rating": 1400, "result": "win"},
        "black": {"username": "rival3", "rating": 1450, "result": "checkmated"},
        "pgn": pgn(USER, "rival3", start),
    }
    return (start.year, start.month), [game]


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args: object) -> None:  # quiet
        pass

    def send(self, status: int, body: str, content_type: str = "application/json") -> None:
        data = body.encode()
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:  # noqa: N802
        path = self.path.split("?")[0]
        if path == "/health":
            return self.send(200, "ok", "text/plain")
        if path.startswith(f"/lichess/api/games/user/{USER}"):
            lines = "\n".join(json.dumps(g) for g in lichess_games()) + "\n"
            return self.send(200, lines, "application/x-ndjson")
        base = f"/chesscom/pub/player/{USER}/games"
        (year, month), games = chesscom_month()
        if path == f"{base}/archives":
            url = f"https://api.chess.com/pub/player/{USER}/games/{year}/{month:02d}"
            return self.send(200, json.dumps({"archives": [url]}))
        if path == f"{base}/{year}/{month:02d}":
            return self.send(200, json.dumps({"games": games}))
        return self.send(404, json.dumps({"message": "not found"}))


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8766
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
