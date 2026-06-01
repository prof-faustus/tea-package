# Build / environment decisions

Recorded decisions for the TEA Package build. Each entry: the decision, the
rationale, and the date. Decisions that the spec leaves to the implementer
(the build-order Appendix B and the runbook "decisions to make") are recorded
here as they are taken.

## DEC-0001 — Development host topology (2026-06-01)

**Decision.** The Package repository lives on the Windows filesystem at
`D:\claude\tea-package` (edited with Windows-native tooling; visible to WSL at
`/mnt/d/claude/tea-package`). The **runtime substrate is WSL2 Ubuntu 24.04**: the
evidence engine binary, PostgreSQL 16, and the Package's engine-/DB-touching
Python all run in WSL/Linux. Pure-Python checks (e.g. the prohibition gate) also
run under Windows Python 3.12 (Anaconda; spec requires 3.11+, satisfied).

**Rationale.** The freshly-built engine `tea-bsv.exe` will not execute to
completion under the harness's Windows process shells (V-ENV-0001), whereas the
Linux build runs cleanly in WSL. WSL/Linux is also the spec's deployment
substrate (section 09 docker-compose), so running the engine and DB there is the
*deployed* execution path, not a workaround that relaxes a requirement. The
engine bridge (C-EVID) invokes `TEA_BSV_BIN` in WSL; input/output files live on
the shared `/mnt/d` path so both sides see them.

**Rationale (continued).** This matches the spec's PostgreSQL 16 requirement
exactly (16.x in WSL) without Docker on the host; the docker-compose Linux image
is authored as the demonstrable/production target in Stage 7.

**Reversibility.** Moving the whole build into a Linux container/VM later is a
configuration change (the spec's deployment target), not a code change; the
Package code is OS-agnostic Python + SQL + a subprocess bridge to the engine.

## DEC-0002 — Engine pinned ref (2026-06-01)

**Decision.** The engine `triple-entry-evidence-bsv` is pinned at commit
`52834be3c040785095d63090f1e0347ced817516` (repo
`prof-faustus/triple-entry-evidence-bsv`), built with the engine's pinned Rust
stable toolchain. The binary name `tea-bsv` is read from the engine workspace
`crates/cli/Cargo.toml` `[[bin]]` entry and exported as `TEA_BSV_BIN`
(REQ-EVID-0030); it is never hardcoded into Package code.

**Rationale.** REQ-BUILD-0003 / REQ-EVID-0099 require a pinned ref recorded in
`core.component_version`; this is the current HEAD of the authoritative engine
repo, verified locally to build and to pass `selftest`/`reproduce`. See
`VERIFY-LOG.md` V-ENGINE-0001.
