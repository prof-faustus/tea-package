"""Prohibition-gate self-tests (TEST-BUILD-0001..0006, REQ-BUILD-0022/0064/0092).

Each prohibited class has a known-bad fixture that the gate MUST catch and a
known-good counterpart it MUST pass. A gate that passes a known-bad fixture is
itself a BLOCKER. The empty-tree and clean-repo cases prove the Stage-0 exit
gate (prohibition gate green on the tree).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.prohibition_gate import (  # noqa: E402
    scan_text, scan_lockfile, scan_tree,
)

FIX = Path(__file__).resolve().parent / "fixtures" / "prohibition"


def _classes(findings):
    return {f.klass for f in findings}


def test_build_0001_op_return_caught():
    text = (FIX / "bad_op_return.txt").read_text(encoding="utf-8")
    assert "OP_RETURN" in _classes(scan_text("wallet/script_builder.py", text))


def test_build_0002_p2sh_caught():
    text = (FIX / "bad_p2sh.txt").read_text(encoding="utf-8")
    assert "P2SH" in _classes(scan_text("wallet/script_builder.py", text))


def test_build_0003_btc_import_caught():
    text = (FIX / "bad_btc_import.py").read_text(encoding="utf-8")
    assert "BTC" in _classes(scan_text("services/evid_bridge.py", text))


def test_build_0003b_btc_lockfile_caught():
    text = (FIX / "bad_btc_lockfile.txt").read_text(encoding="utf-8")
    assert "BTC" in _classes(scan_lockfile("requirements.txt", text))


def test_build_0004_timelock_caught():
    text = (FIX / "bad_timelock_builder.py").read_text(encoding="utf-8")
    assert "TIMELOCK" in _classes(scan_text("wallet/locking_script_builder.py", text))


def test_build_0005_branching_cert_caught():
    text = (FIX / "bad_branching_cert_builder.py").read_text(encoding="utf-8")
    assert "BRANCHING" in _classes(scan_text("wallet/certificate_builder.py", text))


def test_build_0006_secret_in_record_caught():
    text = (FIX / "bad_secret_in_record_encoder.py").read_text(encoding="utf-8")
    assert "SECRET_IN_RECORD" in _classes(scan_text("wire/canonical_encoder.py", text))


def test_good_builder_is_clean():
    text = (FIX / "good_clean_builder.py").read_text(encoding="utf-8")
    # builder + encoder classification, yet no prohibited construct present
    assert scan_text("wallet/script_builder_and_encoder.py", text) == []


def test_empty_tree_passes(tmp_path):
    assert scan_tree(tmp_path) == []


def test_repo_tree_is_clean():
    """Stage-0 exit gate: the prohibition gate is green on the actual tree."""
    repo = Path(__file__).resolve().parents[1]
    findings = scan_tree(repo)
    assert findings == [], "prohibition gate findings:\n" + "\n".join(str(f) for f in findings)
