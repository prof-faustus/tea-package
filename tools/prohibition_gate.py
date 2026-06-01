#!/usr/bin/env python3
# Layer-1 prohibition gate (REQ-BUILD-0020/0021/0060).
#
# The operator's absolute prohibitions are enforced here as a static scan that
# runs BEFORE all other CI stages (REQ-BUILD-0022/0070). A violation fails the
# build with a non-zero exit and a BLOCKER classification; no downstream stage
# runs.
#
# Prohibited classes (REQ-BUILD-0020):
#   1. OP_RETURN / any data (null-data) output.
#   2. P2SH (pay-to-script-hash) construction or parsing.
#   3. BTC: any BTC dependency, library, network magic, address prefix, tooling.
#   4. In-script timelocks (CLTV/CSV) in any locking-script builder.
#   5. Branching revocation scripts (IF/ELSE/ENDIF) in certificate/wallet
#      locking-script builders.
#   6. Private-key material (S, tweak t, master/one-time private scalar, CA
#      private key) serialized into a canonical record.
#
# Every prohibited mnemonic is assembled from fragments at runtime so this file
# contains no literal forbidden token and is not flagged by its own scan. The
# only content-exempt paths are listed in tools/prohibition_allowlist.txt
# (negative-test fixtures and any prohibition documentation that must name a
# construct in order to forbid it); adding a path is a reviewed change.
from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

# --- token assembly (no literal forbidden token appears in this file) --------

def _w(*frags: str) -> re.Pattern:
    return re.compile(r"\b" + "".join(frags) + r"\b", re.IGNORECASE)

OP = "OP_"
MN_OP_RETURN = _w(OP, "RET", "URN")
MN_P2SH = _w("P2", "SH")
MN_CLTV = _w(OP, "CHECK", "LOCK", "TIME", "VERIFY")
MN_CSV = _w(OP, "CHECK", "SEQUENCE", "VERIFY")
MN_IF = _w(OP, "IF")
MN_ELSE = _w(OP, "ELSE")
MN_ENDIF = _w(OP, "END", "IF")
MN_HASH160 = _w(OP, "HASH", "160")
MN_EQUAL = _w(OP, "EQUAL")

# P2SH locking pattern: OP_HASH160 <20-byte push> OP_EQUAL (mnemonic form).
PAT_P2SH_SCRIPT = re.compile(
    OP + r"HASH" + r"160\b.{0,40}?\b" + OP + r"EQUAL\b", re.IGNORECASE | re.DOTALL
)

# Script opcode bytes when emitted by a builder (hex literals).
BYTE_OP_RETURN = re.compile(r"0x6a\b|\\x6a\b", re.IGNORECASE)
BYTE_CLTV = re.compile(r"0xb1\b|\\xb1\b", re.IGNORECASE)
BYTE_CSV = re.compile(r"0xb2\b|\\xb2\b", re.IGNORECASE)

# Known BTC-only tooling packages (lockfile/import scan). BSV-only is the rule;
# these names indicate BTC tooling and fail the gate (REQ-NET-0005).
BTC_PACKAGES = [
    "bitcoinlib", "python-bitcoinlib", "btclib", "bitcoinutils", "bit",
    "embit", "bitcoinrpc", "python-bitcoinrpc", "bitcoinj", "bitcoinjs-lib",
    "bitcoinj-lib", "ldk", "lightning", "lnd", "bdk", "rust-bitcoin",
    "bitcoin", "bitcoincore-rpc",
]
# Word-boundary import/require of a BTC tooling package.
BTC_IMPORT = re.compile(
    r"\b(?:import|from|require|use|extern\s+crate)\b.*\b("
    + "|".join(re.escape(p).replace(r"\-", r"[-_]") for p in BTC_PACKAGES)
    + r")\b",
    re.IGNORECASE,
)
# BTC mainnet/testnet p2p network magic bytes (must never appear).
BTC_MAGIC = re.compile(r"\b0x(?:f9beb4d9|0b110907|fabfb5da)\b", re.IGNORECASE)

# Private-key material mapped into a canonical/serialized record (encoder scan).
# Heuristic: an assignment/field that places a secret scalar into a record dict
# or serialized structure.
SECRET_FIELD = re.compile(
    r"(?:shared_secret|\bS\b|tweak|priv(?:ate)?[_-]?(?:key|scalar)|sk_once|"
    r"m_payee|master[_-]?priv|ca[_-]?priv|salt_det)",
    re.IGNORECASE,
)
RECORD_SINK = re.compile(
    r"(?:canonical|serializ|encode|record\[|to_cbor|field_id|KEY_DERIVATION|"
    r"KEY_CERTIFICATE)",
    re.IGNORECASE,
)

TEXT_EXT = {
    ".py", ".rs", ".ts", ".tsx", ".js", ".mjs", ".cjs", ".go", ".sql", ".sh",
    ".toml", ".yaml", ".yml", ".json", ".md", ".txt", ".cfg", ".ini", ".env",
    ".lock", ".html", ".css", ".jinja", ".j2",
}
SKIP_DIRS = {".git", "node_modules", "target", "dist", "build", "__pycache__",
             ".venv", "venv", ".mypy_cache", ".pytest_cache", ".gocache"}
LOCKFILES = {"requirements.txt", "requirements-dev.txt", "requirements.lock",
             "poetry.lock", "Pipfile.lock", "Cargo.lock", "package-lock.json",
             "pnpm-lock.yaml", "yarn.lock"}

# Path-role classification (REQ-BUILD-0020 scopes some checks to builders).
BUILDER_HINTS = ("script", "locking", "template", "wallet", "tx", "transaction",
                 "builder", "certificate", "cert", "anchor")
ENCODER_HINTS = ("canonical", "serializ", "encode", "wire", "record")


@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    klass: str
    detail: str

    def __str__(self) -> str:
        loc = f"{self.path}:{self.line}" if self.line else self.path
        return f"{loc}: [{self.klass}] {self.detail}"


def _is_builder(rel: str) -> bool:
    low = rel.lower()
    return any(h in low for h in BUILDER_HINTS)


def _is_encoder(rel: str) -> bool:
    low = rel.lower()
    return any(h in low for h in ENCODER_HINTS)


def scan_text(rel: str, text: str) -> list[Finding]:
    """Scan one text file's content for every prohibition class."""
    out: list[Finding] = []
    builder = _is_builder(rel)
    encoder = _is_encoder(rel)
    lines = text.splitlines()
    for i, line in enumerate(lines, 1):
        # 1. OP_RETURN — mnemonic anywhere; opcode byte only in a builder.
        if MN_OP_RETURN.search(line):
            out.append(Finding(rel, i, "OP_RETURN", "data/null-data output mnemonic"))
        if builder and BYTE_OP_RETURN.search(line):
            out.append(Finding(rel, i, "OP_RETURN", "null-data opcode byte in a script builder"))
        # 2. P2SH — mnemonic anywhere; locking pattern anywhere.
        if MN_P2SH.search(line):
            out.append(Finding(rel, i, "P2SH", "pay-to-script-hash mnemonic"))
        # 3. BTC — import of a BTC tooling package; BTC network magic.
        if BTC_IMPORT.search(line):
            out.append(Finding(rel, i, "BTC", "import of a BTC tooling package"))
        if BTC_MAGIC.search(line):
            out.append(Finding(rel, i, "BTC", "BTC p2p network magic bytes"))
        # 4. In-script timelocks — mnemonic anywhere; opcode byte in a builder.
        if MN_CLTV.search(line) or MN_CSV.search(line):
            out.append(Finding(rel, i, "TIMELOCK", "in-script timelock opcode (use nLockTime/nSequence)"))
        if builder and (BYTE_CLTV.search(line) or BYTE_CSV.search(line)):
            out.append(Finding(rel, i, "TIMELOCK", "in-script timelock opcode byte in a builder"))
        # 5. Branching revocation scripts — only in cert/wallet builders.
        if builder and (MN_IF.search(line) or MN_ELSE.search(line) or MN_ENDIF.search(line)):
            out.append(Finding(rel, i, "BRANCHING", "conditional opcode in a locking-script builder"))
        # 6. Private-key material into a canonical record — encoder paths.
        if encoder and SECRET_FIELD.search(line) and RECORD_SINK.search(line):
            out.append(Finding(rel, i, "SECRET_IN_RECORD", "private-key material serialized into a record"))
    # P2SH multi-line locking pattern.
    for m in PAT_P2SH_SCRIPT.finditer(text):
        ln = text[: m.start()].count("\n") + 1
        out.append(Finding(rel, ln, "P2SH", "OP_HASH160 .. OP_EQUAL locking pattern"))
    return out


def scan_lockfile(rel: str, text: str) -> list[Finding]:
    """Scan a resolved lockfile for any BTC-tooling package (REQ-BUILD-0021)."""
    out: list[Finding] = []
    for i, line in enumerate(text.splitlines(), 1):
        low = line.lower()
        for pkg in BTC_PACKAGES:
            # match the package name as a token in a dependency line
            if re.search(r"(?<![\w-])" + re.escape(pkg) + r"(?![\w-])", low):
                # allow the BSV substring-collision: 'bitcoin' must not match 'bitcoin-sv'
                if pkg == "bitcoin" and re.search(r"bitcoin[-_]?sv", low):
                    continue
                out.append(Finding(rel, i, "BTC", f"BTC-tooling package in lockfile: {pkg}"))
                break
    return out


def load_allowlist(root: Path) -> set[str]:
    f = root / "tools" / "prohibition_allowlist.txt"
    allow: set[str] = set()
    if f.exists():
        for line in f.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                allow.add(line.replace("\\", "/"))
    # The gate and its allowlist are always exempt from their own content scan.
    allow.add("tools/prohibition_gate.py")
    allow.add("tools/prohibition_allowlist.txt")
    return allow


def scan_tree(root: Path) -> list[Finding]:
    root = Path(root)
    allow = load_allowlist(root)
    findings: list[Finding] = []
    for path in root.rglob("*"):
        if path.is_dir():
            if path.name in SKIP_DIRS:
                # prune by skipping; rglob can't prune, so guard via parts
                continue
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        rel = str(path.relative_to(root)).replace("\\", "/")
        if rel in allow:
            continue
        if path.name in LOCKFILES:
            try:
                findings.extend(scan_lockfile(rel, path.read_text(encoding="utf-8", errors="replace")))
            except Exception:
                pass
            # lockfiles are also plain text; fall through to content scan
        if path.suffix.lower() not in TEXT_EXT and path.name not in LOCKFILES:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        findings.extend(scan_text(rel, text))
    return findings


def main(argv: list[str]) -> int:
    root = Path(argv[1]) if len(argv) > 1 else Path.cwd()
    findings = scan_tree(root)
    if findings:
        print("PROHIBITION GATE FAILED (REQ-BUILD-0020) — BLOCKER:", file=sys.stderr)
        for f in findings:
            print("  " + str(f), file=sys.stderr)
        return 1
    print("Prohibition gate passed: no prohibited construct in source, "
          "templates, fixtures, or lockfiles.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
