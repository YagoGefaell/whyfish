"""SPEC §3.5: classification of real positions with the real Stockfish (fixed depth).

Integration test (`make test-integration`, or `pytest tests/analysis` with Stockfish).
"""

import pytest

from app.config import Settings
from tests.analysis.real_fixtures import Fixture, classify_fixture, load_fixtures, start_engine

_settings = Settings()

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        _settings.stockfish_path is None or not _settings.stockfish_path.is_file(),
        reason="STOCKFISH_PATH not set or binary missing",
    ),
]

FIXTURES = load_fixtures()


def _param(f: Fixture) -> object:
    marks = [pytest.mark.xfail(reason=f.disputed, strict=False)] if f.disputed else []
    return pytest.param(f, id=f.id, marks=marks)


@pytest.mark.parametrize("fixture", [_param(f) for f in FIXTURES])
async def test_real_position(fixture: Fixture) -> None:
    engine = await start_engine(_settings)
    try:
        verdict = await classify_fixture(engine, fixture)
    finally:
        await engine.close()
    source = fixture.source
    assert verdict.classification is fixture.expected, (
        f"{source['game']} ({source['year']}), {source['move']}: expected {fixture.expected}, "
        f"got {verdict.classification} (win% {verdict.win_before:.1f} -> {verdict.win_after:.1f}, "
        f"Δ {verdict.delta:.1f}). {fixture.note}"
    )
