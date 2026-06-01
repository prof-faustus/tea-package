"""Engine/session construction for the GL library, scoped to the `gl` schema."""
from __future__ import annotations

import os

from sqlalchemy import create_engine
from python_accounting.config import config
from python_accounting.database.session import get_session

DEV_DSN = "postgresql+psycopg2://tea:tea@127.0.0.1:5455/tea"


def dsn() -> str:
    raw = os.environ.get("TEA_DB_DSN", DEV_DSN)
    if raw.startswith("postgresql://"):
        raw = raw.replace("postgresql://", "postgresql+psycopg2://", 1)
    return raw


def make_engine(url: str | None = None):
    """Engine whose connections default to the `gl` schema (REQ-DATA-0003)."""
    url = url or dsn()
    config.configure_database(url)
    return create_engine(url, connect_args={"options": "-csearch_path=gl"})


def session_for(engine):
    return get_session(engine)
