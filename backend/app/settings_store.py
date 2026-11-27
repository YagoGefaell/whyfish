"""App settings changed from the UI, stored in the database (AppSetting key/value)."""

from sqlalchemy import Engine as DbEngine
from sqlmodel import Session

from app.models.sync import AppSetting

QUEUE_PAUSED = "queue_paused"


def get_setting(db: DbEngine, key: str, default: str) -> str:
    with Session(db) as session:
        row = session.get(AppSetting, key)
        return row.value if row is not None else default


def set_setting(db: DbEngine, key: str, value: str) -> None:
    with Session(db) as session:
        row = session.get(AppSetting, key)
        if row is None:
            row = AppSetting(key=key, value=value)
        row.value = value
        session.add(row)
        session.commit()
