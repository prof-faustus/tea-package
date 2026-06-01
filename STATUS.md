# Status — tea-package (Triple-Entry Verifiable Accounting Package)

_Last updated: 2026-06-01_

**Overall:** Prototype/partial

## What this is
A Python enterprise build implementing the TEA BSV specification set: a triple-entry verifiable accounting package that consumes the external `triple-entry-evidence-bsv` engine (pinned `tea-bsv` binary) via subprocess, posts to a general ledger through `python-accounting`, and ties GL postings to canonical CBOR records, an audit chain, and on-chain (Merkle/Layer-A) anchoring. BSV-only with CI-enforced prohibitions (no OP_RETURN, no P2SH, no in-script timelocks, no branching revocation scripts, no private keys in canonical records).

## Current state
- Implemented Python modules under `tea/` (`wire/` CBOR + records, `gl/` posting service, `evid/` engine bridge + lineage spine). Test suite present (`tests/`, 11 test files plus SQL fixtures).
- Stage progress per `docs/BUILD-STATUS.md`: Stage 0 (environment/gates/engine) COMPLETE; Stage 1 (canonical serialization + chain) exit gate MET; Stage 2 (GL integration) core MET; Stage 3 (derivation) partially built but not yet at exit gate. Stages 4–7 (certificate authority, wallet/node/matching, tokens/API/UI, deployment/acceptance) pending.
- Engine `selftest` 5/5 and `reproduce` 3/3 reported green when executed in WSL2 (VERIFY-LOG.md); the engine binary hangs under the Windows harness shells, so it is run via WSL/Linux (DEC-0001).
- Dev PostgreSQL is a user-owned pg18 cluster (`127.0.0.1:5455`) with pgcrypto confirmed; the spec pins pg16, honoured only in the deploy/CI image — pg16 could not be stood up here (DEC-0003). Open `[DECIDE]` items remain (notably DEC-0004 on missing engine commands for note construction / certificate authority).
- Several stages still pending; classified as prototype/partial because core lower layers work but the upper-stage feature set (CA, wallet, tokens, API, acceptance cold-up) is not yet built.

## Version control
- Git: yes, branch master, last commit `f4724c5 Stage 3: KEY_DERIVATION record layout + derive->record->address flow`, working tree clean.

## How to verify / build
- `pytest` (config in `pytest.ini`: `testpaths = tests`).
- `python tools/prohibition_gate.py` — Layer-1 BSV/prohibition static gate (runs first).
- Runtime deps in `requirements.txt` (python-accounting 1.0.1, SQLAlchemy 2.0.50); dev deps in `requirements-dev.txt`.
- Engine bridge requires `TEA_BSV_BIN` pointing at the runnable `tea-bsv` binary (built from the pinned engine ref); DB DSN per `.env.example` (`postgresql://tea:tea@127.0.0.1:5455/tea`).
