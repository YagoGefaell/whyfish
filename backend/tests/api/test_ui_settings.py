"""Interface settings (phase 6.5): defaults, saving and validation."""

from fastapi.testclient import TestClient

from app.api.ui_settings import KEYS
from app.settings_store import set_setting


def test_defaults_then_saved(client: TestClient) -> None:
    assert client.get("/api/settings/ui").json() == {
        "color_mode": "system",
        "board": "brown",
        "pieces": "cburnett",
    }
    chosen = {"color_mode": "dark", "board": "slate", "pieces": "rhosgfx"}
    assert client.put("/api/settings/ui", json=chosen).json() == chosen
    assert client.get("/api/settings/ui").json() == chosen


def test_rejects_unknown_values(client: TestClient) -> None:
    bad = {"color_mode": "sepia", "board": "brown", "pieces": "cburnett"}
    assert client.put("/api/settings/ui", json=bad).status_code == 422
    bad = {"color_mode": "light", "board": "brown", "pieces": "merida"}
    assert client.put("/api/settings/ui", json=bad).status_code == 422


def test_stale_stored_value_falls_back_to_default(client: TestClient) -> None:
    db = client.app.state.db_engine  # type: ignore[attr-defined]
    set_setting(db, KEYS["board"], "marble")  # a board that no longer exists
    assert client.get("/api/settings/ui").json()["board"] == "brown"
