"""Privilege-based immutability (REQ-DATA-0141/0068, REQ-BUILD-0062).

The application DB role `tea_app` (migration 0016) has been REVOKED UPDATE/DELETE
on the append-only evidence tables. This asserts the second, independent mechanism
behind the immutability triggers: even bypassing the trigger, the app role simply
cannot UPDATE/DELETE evid.canonical_record or evid.audit_chain at the privilege
layer. Skips when the role/DB is unavailable.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
pytest.importorskip("sqlalchemy")
from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.exc import ProgrammingError  # noqa: E402

APP_DSN = "postgresql+psycopg2://tea_app:tea_app@127.0.0.1:5455/tea"


def _app_engine_or_skip():
    try:
        eng = create_engine(APP_DSN)
        with eng.connect() as c:
            c.execute(text("SELECT 1 FROM evid.canonical_record LIMIT 1"))
        return eng
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"tea_app role / DB unavailable (run the migrate runner incl. 0016): {e}")


def test_app_role_can_select_but_not_mutate_append_only():
    eng = _app_engine_or_skip()
    with eng.connect() as c:
        # SELECT is allowed
        c.execute(text("SELECT count(*) FROM evid.canonical_record"))
        c.execute(text("SELECT count(*) FROM evid.audit_chain"))

    # UPDATE on the append-only canonical_record is denied at the privilege layer
    with eng.begin() as c:
        with pytest.raises(ProgrammingError) as ei:
            c.execute(text("UPDATE evid.canonical_record SET logical_key='x' WHERE id=-1"))
        assert "permission denied" in str(ei.value).lower()

    # DELETE on the append-only audit_chain is denied
    with eng.begin() as c:
        with pytest.raises(ProgrammingError) as ei:
            c.execute(text("DELETE FROM evid.audit_chain WHERE seq=-1 AND entity_id=-1"))
        assert "permission denied" in str(ei.value).lower()
