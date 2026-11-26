from fastapi.testclient import TestClient
from sqlmodel import Session

from app.explain.report import collect, pick, render
from tests.api.test_explanation import analysed
from tests.conftest import FakeEngine


def test_report_renders_the_analysed_games(client: TestClient, fake_engine: FakeEngine) -> None:
    analysed(client, fake_engine)
    with Session(client.app.state.db_engine) as session:  # type: ignore[attr-defined]
        items = collect(session)
    assert [i.facts.san for i in items] == ["f3", "e5", "g4", "Qh4#"]
    chosen, notes = pick(items)
    errors = dict(chosen)["Errores (?? y ?)"]
    assert [i.facts.san for i in errors] == ["g4"]
    page = render(chosen, notes, len(items))
    assert page.startswith("<!doctype html>")
    assert "<svg" in page and '<span class="mv">Qh4#</span>' in page
    assert 'class="used"' in page  # the facts used by the text are marked
