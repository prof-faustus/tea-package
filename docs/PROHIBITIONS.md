# Absolute prohibitions and their four-layer enforcement

These are the operator's non-negotiable constraints (INDEX §0, REQ-BUILD-0020,
REQ-BUILD-0060..0064). They are not advisory, not waivable, and not subject to a
"reasonable exception." A violation fails the build with a non-zero exit and a
BLOCKER classification; no downstream stage runs.

## The prohibited classes

1. **OP_RETURN / data outputs.** No null-data output, no script-builder that
   emits the null-data opcode, no helper documented as producing a data output.
2. **P2SH (pay-to-script-hash).** No construction or parsing of pay-to-script-hash;
   no `OP_HASH160 <20> OP_EQUAL` template; no P2SH-range address encoding.
   Recognition is limited to the single allowlisted template-checker rejection
   path (REQ-NET, tested).
3. **BTC.** BSV only. No BTC dependency, library, network magic, address prefix,
   or tooling in any lockfile, import graph, or config.
4. **In-script timelocks.** No `OP_CHECKLOCKTIMEVERIFY` / `OP_CHECKSEQUENCEVERIFY`
   in any locking-script builder; timing is `nLockTime` / `nSequence` only
   (REQ-NET-0072).
5. **Branching revocation scripts.** No `OP_IF` / `OP_ELSE` / `OP_ENDIF` in any
   certificate or wallet locking-script builder; multi-party revocation is
   realised by threshold-key P2PKH or multiple P2PKH outpoints only (REQ-SEC-0126).
6. **Private-key material in canonical records.** No path may place `S`, a tweak
   scalar `t`, a master private scalar, a one-time private scalar, or a CA
   private key into a serialized record (REQ-WIRE-0141, REQ-SEC-0133).

## The four enforcement layers (REQ-BUILD-0060..0064)

| Layer | Mechanism | Where |
|---|---|---|
| 1 | **CI static gate** — source/lockfile/template scan, fails before tests | `tools/prohibition_gate.py` (this layer; self-tested by `tests/test_prohibition_gate.py`) |
| 2 | **Runtime template-checker** — every tx template checked against the closed allowed set before signing | built in Stage 5 (REQ-ARCH-0036, REQ-NET-0074) |
| 3 | **Database guard** — `wallet.fn_assert_allowed_script` rejects a forbidden locking script on INSERT/UPDATE | built in Stage 5 (REQ-DATA-0146/0189) |
| 4 | **Encoder/bridge guard** — the canonical encoder refuses to serialize key material; the bridge parser rejects engine output that appears to contain a secret | built in Stages 1/3 (REQ-WIRE-0141, REQ-SEC-0133, REQ-EVID-0007) |

A forbidden script must be **impossible to build, impossible to broadcast, and
impossible to persist** (REQ-BUILD-0023). Each layer is independently tested with
known-bad inputs; removing or weakening any layer fails the requirements-coverage
gate because a requirement would lose its test (REQ-BUILD-0064).
