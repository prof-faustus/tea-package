# Build status — TEA Package

Tracks progress against the build-order exit gates
(`00-overview/04-build-order-for-implementer.md`). A stage is COMPLETE only when
its exit gate is green. No stage proceeds on an unverified lower layer.

| Stage | Scope | Exit gate | Status |
|---|---|---|---|
| 0 | environment, gates, engine | prohibition gate green on the tree; engine selftest/reproduce green; DB reachable | **in progress** |
| 1 | canonical serialization + chain | canonical vectors reproduce byte-for-byte; chain append/verify/immutability green | pending |
| 2 | GL integration | TEST-INT-0001..0014; reports tie out and balance | pending |
| 3 | master keys, derivation, salt | TEST-WIRE/PROP/EVID derivation set; worked vector reproduces | pending |
| 4 | certificate authority | TEST-SEC-0120..0132, TEST-EVID-0013; cert vector reproduces | pending |
| 5 | wallet, node, matching | TEST-WALLET/E2E/REORG | pending |
| 6 | tokens, messaging, disclosure, API, UI | TEST-TOKEN/E2E/API; OpenAPI snapshot | pending |
| 7 | deployment, VM, ops, acceptance | acceptance cold-up green (no network); coverage + requirements-coverage floors met | pending |

## Stage 0 detail

- [x] Repo scaffold + git + CI skeleton (prohibition gate runs first).
- [x] Layer-1 prohibition gate (`tools/prohibition_gate.py`) + known-bad
      self-tests (TEST-BUILD-0001..0006) + clean-tree assertion. **10/10 pass.**
- [x] Toolchains/locks/component versions pinned (`build/manifest.json`).
- [x] Engine integrated: built at pinned ref `52834be`; `selftest` 5/5 +
      `reproduce` 3/3 **green** (executed in WSL); `TEA_BSV_BIN` resolved from
      workspace `[[bin]]`; contract snapshot captured under `contract/`.
- [~] PostgreSQL 16 + pgcrypto reachable (install/configure running in WSL).
- [ ] Stage 0 exit gate verified.
