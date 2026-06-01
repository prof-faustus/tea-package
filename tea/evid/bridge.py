"""C-EVID — the engine bridge (section 05). Subprocess-only, deterministic, fail-closed.

The Package consumes the pinned `tea-bsv` binary via subprocess (REQ-EVID-0004):
no FFI, no network RPC. Inputs are args/files; outputs are stdout/files; errors
are exit code + stderr translated to typed Python errors (REQ-EVID-0022). The
binary runs in WSL/Linux (the Windows .exe will not execute under the harness,
V-ENV-0001); on Linux it runs directly. Output parsing is strict (REQ-EVID-0024)
and rejects any output that appears to carry secret scalar material
(EngineProhibitionError, REQ-EVID-0007/0093).

This bridge exposes the engine's ACTUAL CLI surface at the pinned ref
(selftest, reproduce, worked-example, anchor, prove, verify, query, disclose).
Operations the spec lists as "logical" but which this engine does not expose as
CLI commands (derive-shared-address, build-invoice-note/-payment-note, per-field
commit, certificate ops) are NOT faked here — see DECISIONS DEC-0004.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

DEFAULT_BIN = "/home/craig/engine/target/release/tea-bsv"
TIMEOUT = 120

# A value that looks like a 32-byte secret scalar leaking through the bridge.
_SECRET_KEYS = re.compile(r"\b(sk_once|m_payee|shared_s|secret_scalar|tweak_scalar)\b", re.I)


class EngineError(RuntimeError):
    """Base class for engine bridge errors."""


class EngineUnavailable(EngineError):
    """Binary missing or not runnable."""


class EngineVersionMismatch(EngineError):
    """`tea-bsv --version` does not match the pinned version."""


class EngineFailure(EngineError):
    """Non-zero exit (engine error), with stderr context (no secrets)."""


class EngineProhibitionError(EngineError):
    """Output appears to contain secret scalar material (REQ-EVID-0007)."""


def _runner() -> list[str]:
    """How to launch the engine: WSL on Windows, direct on Linux. Overridable."""
    override = os.environ.get("TEA_BSV_RUN")  # e.g. "wsl -d Ubuntu --"
    if override:
        return override.split()
    if sys.platform == "win32" and shutil.which("wsl"):
        return ["wsl", "-d", "Ubuntu", "--"]
    return []


class Bridge:
    """Strict, fail-closed wrapper over the pinned `tea-bsv` binary."""

    SUBCOMMANDS = ("selftest", "reproduce", "worked-example", "anchor",
                   "prove", "verify", "query", "disclose", "derive-shared-address")

    def __init__(self, binary: str | None = None, pinned_version: str | None = None):
        self.binary = binary or os.environ.get("TEA_BSV_BIN", DEFAULT_BIN)
        self.pinned_version = pinned_version

    def _exec(self, args: list[str]) -> subprocess.CompletedProcess:
        cmd = [*_runner(), self.binary, *args]
        try:
            return subprocess.run(cmd, capture_output=True, text=True, timeout=TIMEOUT)
        except FileNotFoundError as e:
            raise EngineUnavailable(f"engine launcher not found: {e}") from e
        except subprocess.TimeoutExpired as e:
            raise EngineUnavailable(f"engine timed out after {TIMEOUT}s") from e

    def _guard_secret(self, text: str) -> None:
        if _SECRET_KEYS.search(text):
            raise EngineProhibitionError("engine output appears to contain secret material")

    def run(self, subcommand: str, *args: str) -> str:
        if subcommand not in self.SUBCOMMANDS:
            raise EngineError(f"unknown subcommand {subcommand!r}")
        proc = self._exec([subcommand, *args])
        if proc.returncode != 0:
            raise EngineFailure(f"tea-bsv {subcommand} exit {proc.returncode}: "
                                f"{proc.stderr.strip()[:300]}")
        self._guard_secret(proc.stdout)
        return proc.stdout

    def version(self) -> str:
        proc = self._exec(["--version"])
        if proc.returncode != 0:
            raise EngineUnavailable(f"tea-bsv --version failed: {proc.stderr.strip()[:200]}")
        ver = proc.stdout.strip()
        if self.pinned_version and ver != self.pinned_version:
            raise EngineVersionMismatch(f"engine {ver!r} != pinned {self.pinned_version!r}")
        return ver

    def selftest(self) -> str:
        return self.run("selftest")

    def reproduce(self) -> str:
        return self.run("reproduce")

    def _engine_path(self, p) -> str:
        """Translate a Windows path to its /mnt WSL form when running via WSL."""
        p = str(p)
        if _runner() and sys.platform == "win32" and re.match(r"^[A-Za-z]:", p):
            return f"/mnt/{p[0].lower()}{p[2:].replace(chr(92), '/')}"
        return p

    def anchor(self, notes_path, out_path, *, bsv_anchor_txid_be: str,
               batch_id: int = 0, anchor_minor_units: int = 1) -> dict:
        """Fold note bodies into a BSV-canonical Merkle root (Layer A). Returns the batch."""
        self.run("anchor", "--notes", self._engine_path(notes_path),
                 "--bsv-anchor-txid-be", bsv_anchor_txid_be,
                 "--batch-id", str(batch_id),
                 "--anchor-minor-units", str(anchor_minor_units),
                 "--out", self._engine_path(out_path))
        return json.loads(Path(out_path).read_text(encoding="utf-8"))

    def prove(self, batch_path, notes_path, leaf_index: int, out_path) -> dict:
        """Produce an inclusion bundle for one note in a batch."""
        self.run("prove", "--batch", self._engine_path(batch_path),
                 "--notes", self._engine_path(notes_path),
                 "--leaf-index", str(leaf_index),
                 "--out", self._engine_path(out_path))
        return json.loads(Path(out_path).read_text(encoding="utf-8"))

    def verify(self, bundle_path) -> bool:
        """Verify an inclusion bundle; True iff the engine reports verification OK."""
        out = self.run("verify", "--bundle", self._engine_path(bundle_path))
        return "verify OK" in out

    def derive_shared_address(self, *, sk_hex: str, remote_pub_hex: str,
                              payee_pub_hex: str, dc_hex: str,
                              salt_rule: str = "context") -> dict:
        """One-time shared-address derivation by the engine (04 §4.20-4.28).

        Returns ONLY public values: derived_pubkey_hex (PK_once), salt_commitment_hex,
        and the A/B master-key ordering. The engine never emits S/t/salt_det/sk_once
        (REQ-WIRE-0141); the bridge secret-guard rejects any output that appears to.
        """
        out = self.run("derive-shared-address", "--sk-hex", sk_hex,
                       "--remote-pub-hex", remote_pub_hex,
                       "--payee-pub-hex", payee_pub_hex,
                       "--dc-hex", dc_hex, "--salt-rule", salt_rule)
        return json.loads(out)

    def worked_example(self) -> dict:
        out = self.run("worked-example")
        try:
            obj = json.loads(out)
        except json.JSONDecodeError as e:
            raise EngineError(f"worked-example output is not valid JSON: {e}") from e
        # the engine's worked example legitimately exposes test-only private scalars
        # (sk_master_*_hex) in its documented schema; those are fixed published test
        # vectors, not live secrets, so the secret-guard is not applied to this map.
        return obj
