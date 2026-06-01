# Triple-Entry Verifiable Accounting Package (TEA Package)

Enterprise build implementing the specification set in
`../TEA Accounting/tea-bsv-spec/tea-bsv-spec/` (the contract). The spec is
authoritative; this code does not deviate from it. A requirement is *satisfied*
only when its behaviour is exhibited **and** its enumerated test passes in CI
(`00-INDEX.md` §0). Partial satisfaction is non-satisfaction.

## Absolute prohibitions (system-wide, CI-enforced)

- **No `OP_RETURN`.** No data/null-data outputs.
- **No `P2SH`** / pay-to-script-hash (recognition limited to the single
  allowlisted template-checker rejection path).
- **BSV only** — never BTC, never BTC tooling, never BTC code.
- **No in-script timelocks** (`OP_CHECKLOCKTIMEVERIFY`/`OP_CHECKSEQUENCEVERIFY`);
  timing is `nLockTime`/`nSequence` only.
- **No branching revocation scripts** (`OP_IF`/`OP_ELSE`/`OP_ENDIF`) in
  certificate/wallet locking-script builders.
- **No private-key material in canonical records.**

These are enforced at four independent layers (REQ-BUILD-0060..0064): CI static
gate, runtime template-checker, database guard, and encoder/bridge guard. The
CI static gate (Layer 1) is `tools/prohibition_gate.py` and runs before all
other checks.

## The engine

The triple-entry evidence engine `triple-entry-evidence-bsv` is consumed as the
pinned `tea-bsv` binary via subprocess (the bridge, section 05). The Package
never reimplements a primitive the engine provides and never modifies engine
source. Pinned ref and binary name are recorded in `build/manifest.json` and
resolved into `TEA_BSV_BIN` at integration time (REQ-EVID-0030) — never
hardcoded.

## Build order

Per `00-overview/04-build-order-for-implementer.md`. Stage status is tracked in
`docs/BUILD-STATUS.md`.

## Governance artifacts

- `DECISIONS.md` — recorded build/environment decisions.
- `VERIFY-LOG.md` — every external-fact verification, its source, and date.
- `docs/BUILD-STATUS.md` — stage-by-stage progress against the exit gates.
