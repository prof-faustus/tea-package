"""Bootstrap python-accounting into the `gl` schema and record its version.

REQ-DATA-0020 (create_all into gl), REQ-DATA-0140 (record exact version). The GL
tables are placed in the `gl` schema by connecting with search_path=gl, so the
library is used unmodified (REQ-DATA-0003). Run after migrations 0001-0008.

    python tools/gl_bootstrap.py            # uses TEA_DB_DSN or the dev default
"""
from __future__ import annotations

import os
import sys

from sqlalchemy import create_engine, text
import python_accounting
from python_accounting.config import config
from python_accounting.models import Base

DEV_DSN = "postgresql+psycopg2://tea:tea@127.0.0.1:5455/tea"


def dsn() -> str:
    raw = os.environ.get("TEA_DB_DSN", DEV_DSN)
    # normalise a generic postgresql:// DSN to the psycopg2 driver the library needs
    if raw.startswith("postgresql://"):
        raw = raw.replace("postgresql://", "postgresql+psycopg2://", 1)
    return raw


def gl_version() -> str:
    # python_accounting exposes no __version__; read the installed distribution.
    try:
        from importlib.metadata import version
        return version("python-accounting")
    except Exception:  # noqa: BLE001
        return "unknown"


def main() -> int:
    url = dsn()
    ver = gl_version()
    # Land all GL tables in the `gl` schema (REQ-DATA-0003: library unmodified).
    engine = create_engine(url, connect_args={"options": "-csearch_path=gl"})
    config.configure_database(url)

    Base.metadata.create_all(engine)

    with engine.connect() as conn:
        tables = [r[0] for r in conn.execute(text(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema='gl' ORDER BY table_name"))]
        # record the exact library version (REQ-DATA-0140)
        conn.execute(text(
            "UPDATE core.component_version SET version=:v, "
            "notes='python-accounting create_all into gl (REQ-DATA-0020)', applied_at=now() "
            "WHERE component='python-accounting'"), {"v": ver})
        conn.execute(text(
            "INSERT INTO core.component_version(component, version, notes) "
            "VALUES ('python-accounting', :v, 'create_all into gl') "
            "ON CONFLICT (component) DO UPDATE SET version=:v, applied_at=now()"),
            {"v": ver})
        conn.commit()

    print(f"python-accounting version: {ver}")
    print(f"GL tables created in schema gl: {len(tables)}")
    print("  " + ", ".join(tables))
    if not tables:
        print("GL-BOOTSTRAP-FAIL: no tables created", file=sys.stderr)
        return 1
    print("GL-BOOTSTRAP-OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
