#!/usr/bin/env python3
"""Engine-build integration (REQ-BUILD-0010/0093/0094, REQ-EVID-0030/0040/0043).

Resolves the engine binary name from the engine workspace `Cargo.toml`
(`[[bin]]` name) into TEA_BSV_BIN — never hardcoded (REQ-EVID-0030) — runs
`selftest` and `reproduce` as preconditions to use (REQ-EVID-0043), records the
binary hash (REQ-BUILD-0082), and captures the contract snapshot
(version + help surfaces) committed for drift detection (REQ-EVID-0040/0041).

Usage:
    python tools/engine_build.py --engine <engine_repo_dir> [--build]

Writes:
    build/manifest.json                      (pinned ref, binary hash, bin name)
    contract/engine_version.txt              (`tea-bsv --version`)
    contract/help/<subcommand>.txt           (`--help` surfaces)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
TIMEOUT = 120

SUBCOMMANDS = [
    "selftest", "reproduce", "worked-example", "anchor", "prove", "verify",
    "query", "disclose",
]


def resolve_bin_name(engine: Path) -> str:
    """Read the [[bin]] name from the engine's cli crate Cargo.toml (REQ-EVID-0030)."""
    cli_toml = engine / "crates" / "cli" / "Cargo.toml"
    text = cli_toml.read_text(encoding="utf-8")
    m = re.search(r"\[\[bin\]\][^\[]*?name\s*=\s*\"([^\"]+)\"", text, re.DOTALL)
    if not m:
        raise SystemExit(f"could not resolve [[bin]] name from {cli_toml}")
    return m.group(1)


def bin_path(engine: Path, name: str) -> Path:
    exe = engine / "target" / "release" / (name + (".exe" if sys.platform == "win32" else ""))
    if not exe.exists():
        raise SystemExit(f"engine binary not found: {exe} (build the engine first)")
    return exe


def git_ref(engine: Path) -> str:
    return subprocess.run(
        ["git", "-C", str(engine), "rev-parse", "HEAD"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()


def run(exe: Path, args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [str(exe), *args], capture_output=True, text=True, cwd=str(cwd), timeout=TIMEOUT,
    )


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine", required=True, type=Path)
    ap.add_argument("--build", action="store_true", help="cargo build --release first")
    args = ap.parse_args(argv[1:])
    engine = args.engine.resolve()

    if args.build:
        print("building engine (cargo build --release) ...")
        subprocess.run(["cargo", "build", "--release"], cwd=str(engine), check=True)

    name = resolve_bin_name(engine)
    exe = bin_path(engine, name)
    ref = git_ref(engine)
    print(f"TEA_BSV_BIN = {name}  ({exe})")
    print(f"engine ref  = {ref}")

    # Preconditions to use (REQ-EVID-0043): selftest + reproduce must pass.
    st = run(exe, ["selftest"], engine)
    if st.returncode != 0:
        print(st.stdout); print(st.stderr, file=sys.stderr)
        raise SystemExit("engine selftest FAILED — blocks the build (REQ-EVID-0043)")
    print("selftest: pass")
    rp = run(exe, ["reproduce"], engine)
    if rp.returncode != 0:
        print(rp.stdout); print(rp.stderr, file=sys.stderr)
        raise SystemExit("engine reproduce FAILED — blocks the build (REQ-EVID-0043)")
    print("reproduce: pass")

    # Contract snapshot (REQ-EVID-0040): version + help surfaces.
    contract = REPO / "contract"
    (contract / "help").mkdir(parents=True, exist_ok=True)
    ver = run(exe, ["--version"], engine).stdout.strip()
    (contract / "engine_version.txt").write_text(ver + "\n", encoding="utf-8")
    top_help = run(exe, ["--help"], engine).stdout
    (contract / "help" / "_top.txt").write_text(top_help, encoding="utf-8")
    for sub in SUBCOMMANDS:
        h = run(exe, [sub, "--help"], engine).stdout
        (contract / "help" / f"{sub}.txt").write_text(h, encoding="utf-8")

    # Build manifest (REQ-BUILD-0050/0080).
    build = REPO / "build"
    build.mkdir(parents=True, exist_ok=True)
    manifest = {
        "engine": {
            "repo": "prof-faustus/triple-entry-evidence-bsv",
            "ref": ref,
            "bin_name": name,
            "bin_sha256": sha256(exe),
            "version": ver,
            "selftest": "pass",
            "reproduce": "pass",
        },
        "toolchains": {},
        "components": {},
    }
    (build / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"engine binary sha256 = {manifest['engine']['bin_sha256']}")
    print("wrote build/manifest.json and contract/ snapshot")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
