# Build / environment decisions

Recorded decisions for the TEA Package build. Each entry: the decision, the
rationale, and the date. Decisions that the spec leaves to the implementer
(the build-order Appendix B and the runbook "decisions to make") are recorded
here as they are taken.

## DEC-0001 — Development host topology (2026-06-01)

**Decision.** The Package repository lives on the Windows filesystem at
`D:\claude\tea-package`. Python 3.12 (Anaconda) is the Package runtime (spec
requires 3.11+, satisfied). The evidence engine is consumed as the native
Windows binary `tea-bsv.exe` built from the pinned engine repo. PostgreSQL 16
runs in WSL2 Ubuntu 24.04 and is reachable from the Windows host at
`localhost:5432`.

**Rationale.** This uses the toolchains already installed (no Docker on the
host) while matching the spec's PostgreSQL 16 requirement exactly. The
docker-compose Linux deployment substrate (section 09) is authored as the
demonstrable/production target in Stage 7; the development topology here does
not relax any spec requirement — it is the substrate on which the gates run.

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
