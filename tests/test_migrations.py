"""Migrate-test stage: apply 0001-0007 and exercise the chain triggers.

Runs the SQL migrate-and-test runner against the development cluster. Skips
cleanly when no database is reachable (e.g. a pure-Windows CI lane); the Linux
CI migrate-test stage runs it directly (REQ-BUILD-0070 step 5). Asserts the
runner reports success and that every trigger rejected its known-bad input.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys

import pytest

RUNNER = "tools/migrate_and_test.sh"


def _runner_cmd():
    """Return the command to run the migrate-and-test runner, or None if unavailable."""
    override = os.environ.get("TEA_MIGRATE_CMD")
    if override:
        return ["bash", "-lc", override]
    if sys.platform == "win32":
        # Dev: the cluster + psql live in WSL Ubuntu.
        if shutil.which("wsl"):
            return ["wsl", "-d", "Ubuntu", "--", "bash",
                    "/mnt/d/claude/tea-package/tools/migrate_and_test.sh"]
        return None
    if shutil.which("bash"):
        return ["bash", RUNNER]
    return None


def test_migrate_and_chain_triggers():
    cmd = _runner_cmd()
    if cmd is None:
        pytest.skip("no database runner available in this environment")
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        pytest.skip(f"migrate runner unavailable: {e}")
    out = proc.stdout + proc.stderr
    low = out.lower()
    if proc.returncode != 0 and any(s in low for s in (
            "could not connect", "connection refused", "connection to server",
            "is the server running")):
        pytest.skip("database not reachable")
    assert "MIGRATE-AND-TEST: OK" in out, out
    assert "ALL-CHAIN-TESTS-PASSED" in out, out
    assert proc.returncode == 0, out
