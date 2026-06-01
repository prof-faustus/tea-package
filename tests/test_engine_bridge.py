"""Engine-bridge contract test (REQ-EVID-0040/0041/0043).

Runs the pinned `tea-bsv` through C-EVID and pins its surface: version,
selftest/reproduce gates, and the deterministic worked-example as a committed
contract vector. A silent engine change is caught here at the contract boundary.
Skips cleanly when the engine is not runnable in this environment.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tea.evid.bridge import Bridge, EngineError  # noqa: E402

VEC = Path(__file__).resolve().parents[1] / "vectors" / "engine_worked_example_v1.json"


def _bridge_or_skip():
    b = Bridge()
    try:
        return b, b.version()
    except EngineError as e:
        pytest.skip(f"engine not runnable here: {e}")


def test_version_selftest_reproduce():
    b, ver = _bridge_or_skip()
    assert ver.startswith("tea-bsv")
    assert "selftest passed" in b.selftest()
    assert "reproduce passed" in b.reproduce()


def test_worked_example_contract_vector():
    b, _ = _bridge_or_skip()
    got = b.worked_example()
    if not VEC.exists():
        VEC.write_text(json.dumps(got, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        pytest.skip("pinned worked-example vector created; re-run asserts against it")
    want = json.loads(VEC.read_text(encoding="utf-8"))
    assert got == want, "engine worked-example drifted from the pinned contract vector"
    # spot-check the documented schema is present (deterministic derivation values)
    for k in ("shared_s_hex", "k_master_hex", "l_inv_hex", "l_pay_hex", "body_hex"):
        assert k in got
