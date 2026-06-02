"""TEA Package REST API — operator-facing read/verify surface (section 03).

A focused, dependency-light FastAPI app over the evidence layer: liveness/readiness,
per-entity audit-chain verification, and evidence retrieval (canonical record +
chain entry + note projection). Money/posting endpoints are added with the GL
service; this surface exposes the cryptographic-evidence reads that already exist.
"""
from __future__ import annotations

import os

from fastapi import FastAPI, HTTPException
from sqlalchemy import create_engine, text

from tea.evid.bridge import Bridge, EngineError

app = FastAPI(
    title="TEA Package API",
    version="0.1.0",
    description="Triple-entry verifiable accounting — evidence read/verify surface. "
                "BSV-only; no prohibited constructs.",
)


def _dsn() -> str:
    raw = os.environ.get("TEA_DB_DSN", "postgresql+psycopg2://tea:tea@127.0.0.1:5455/tea")
    return raw.replace("postgresql://", "postgresql+psycopg2://", 1) if raw.startswith("postgresql://") else raw


def _engine():
    return create_engine(_dsn())


@app.get("/healthz", tags=["health"])
def healthz() -> dict:
    """Liveness: the process is up."""
    return {"status": "ok"}


@app.get("/readyz", tags=["health"])
def readyz() -> dict:
    """Readiness: the engine binary and the database are reachable (REQ-ARCH-0059)."""
    checks: dict[str, str] = {}
    try:
        checks["engine"] = Bridge().version()
    except EngineError as e:
        checks["engine"] = f"unavailable: {e}"
    try:
        with _engine().connect() as c:
            c.execute(text("SELECT 1"))
        checks["db"] = "ok"
    except Exception as e:  # noqa: BLE001
        checks["db"] = f"unavailable: {e}"
    ready = checks["db"] == "ok" and not checks["engine"].startswith("unavailable")
    return {"ready": ready, "checks": checks}


@app.get("/entities/{entity_id}/chain/verify", tags=["evidence"])
def verify_chain(entity_id: int) -> dict:
    """Walk the entity's audit hash chain (REQ-DATA-0045); intact iff no broken seq."""
    with _engine().connect() as c:
        broken = c.execute(text("SELECT evid.fn_verify_chain(:e)"), {"e": entity_id}).scalar()
    return {"entity_id": entity_id, "intact": broken is None, "first_broken_seq": broken}


@app.get("/evidence/{canonical_id}", tags=["evidence"])
def get_evidence(canonical_id: int) -> dict:
    """Return the canonical record + its audit-chain entry + note projection (public only)."""
    with _engine().connect() as c:
        rec = c.execute(text(
            "SELECT entity_id, record_type, logical_key, encode(canonical_sha256,'hex') sha, "
            "schema_version FROM evid.canonical_record WHERE id=:i"), {"i": canonical_id}).first()
        if rec is None:
            raise HTTPException(status_code=404, detail="canonical record not found")
        chain = c.execute(text(
            "SELECT seq, encode(entry_hash,'hex') eh FROM evid.audit_chain "
            "WHERE canonical_id=:i"), {"i": canonical_id}).first()
        note = c.execute(text(
            "SELECT id, note_type, status, encode(l_tag,'hex') l FROM evid.note "
            "WHERE canonical_id=:i"), {"i": canonical_id}).first()
    return {
        "canonical_id": canonical_id,
        "entity_id": rec.entity_id,
        "record_type": rec.record_type,
        "logical_key": rec.logical_key,
        "canonical_sha256": rec.sha,
        "schema_version": rec.schema_version,
        "chain": {"seq": chain.seq, "entry_hash": chain.eh} if chain else None,
        "note": {"id": note.id, "note_type": note.note_type, "status": note.status,
                 "l_tag": note.l} if note else None,
    }
