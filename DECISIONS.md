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
`0ea91a4732eb4d83a328eaa8904a2c458318db01` (repo
`prof-faustus/triple-entry-evidence-bsv`, branch `main`; advanced from the
original `52834be` per DEC-0004 to add `derive-shared-address`), built with the
engine's pinned Rust stable toolchain. The binary name `tea-bsv` is read from the engine workspace
`crates/cli/Cargo.toml` `[[bin]]` entry and exported as `TEA_BSV_BIN`
(REQ-EVID-0030); it is never hardcoded into Package code.

**Rationale.** REQ-BUILD-0003 / REQ-EVID-0099 require a pinned ref recorded in
`core.component_version`; this is the current HEAD of the authoritative engine
repo, verified locally to build and to pass `selftest`/`reproduce`. See
`VERIFY-LOG.md` V-ENGINE-0001.

## DEC-0003 — Development database version (2026-06-01)

**Decision.** Local development runs against a **user-owned PostgreSQL 18.4**
cluster (`tools/pg_user_cluster.sh`, `127.0.0.1:5455`, `pgcrypto` enabled). The
spec-pinned **PostgreSQL 16** is honoured in the deploy/CI image (`postgres:16`,
section 09 docker-compose) and in the Stage-7 acceptance cold-up.

**Rationale.** The environment cannot provide pg16 non-interactively: the Docker
daemon is unresponsive (a wedged `docker pull postgres:16`) and passwordless
`sudo` is unavailable, so neither a `postgres:16` container nor an
`apt install postgresql-16` cluster can be completed. Only pg18 server binaries
are installed, which a user can `initdb` without sudo. pg18 is a superset of the
SQL the Package uses; all migrations/triggers are kept to the 16/18-portable
subset, and pg16-specific behaviour is validated in Stage 7 against `postgres:16`.

**Follow-up (operator).** When `sudo`/Docker are available, switch dev to a
`postgres:16` container (or native pg16 cluster) by pointing `TEA_DB_DSN` at it —
no Package code changes. The earlier hung `apt`/`docker pull` root processes need
the operator's `sudo` to reap.

## DEC-0004 — Engine CLI surface gap for Stages 3–4 (2026-06-01) — OPEN [DECIDE]

**Finding (verified, not assumed).** The pinned engine `52834be`
(`crates/cli/src/main.rs`) exposes exactly: `selftest, reproduce, worked-example,
anchor, prove, verify, query, disclose`. It does **not** expose
`derive-shared-address`, `derive-shared-privkey`, `build-invoice-note`,
`build-payment-note`, a per-field `commit`, or the certificate operations
(`issue`/`revoke`/`verify-certificate`). Stage 3 (master-key shared-address
derivation, 04 §4.20–4.28) and Stage 4 (certificate authority, 10 §10.20–10.26)
require those operations to be performed **by the engine** — the Package MUST NOT
reimplement the EC/HKDF/tweak crypto (REQ-EVID-0002/0097) and MUST NOT modify the
engine source (REQ-EVID-0002).

**Why this is a decision, not something to guess.** Three options materially
change the work and only the operator can choose:
1. **Extend the engine** repo (`prof-faustus/triple-entry-evidence-bsv`) with the
   missing CLI commands that expose its existing `bsvcurve`/`tea`/`disclosure`
   crates (ECDH, HKDF, additive tweak `M + t·G`, per-field commit, certificate
   signing). This is engine-owned work; it does not reimplement primitives in the
   Package, but it does mean the engine ref advances past `52834be`.
2. **Point to a newer engine ref** that already exposes these operations.
3. **Proceed on the supported surface first** — build Stage 5 (anchor/prove/
   verify/disclose, which the engine DOES expose) and defer Stages 3–4 until the
   engine exposes derivation/certificate ops.

**Resolution (operator chose option 1 — extend the engine).** Engine advanced to
`0ea91a4` adding `derive-shared-address` (additive-tweak one-time-address
derivation) by exposing existing `bsvcurve` primitives — no new crypto. Stage 3
derivation is now built and proven (`tests/test_derivation.py`: payee and payer
independently derive the same PK_once for both salt rules; deterministic;
context-bound; public-only output). **Still pending** on the same authorised
track: `build-invoice-note`/`-payment-note`, per-field `commit`, and the
certificate ops (`issue`/`revoke`/`verify-certificate`) for note construction
(Stage 5) and the certificate authority (Stage 4) — to be added the same way.

## DEC-0005 — Git repositories are PUBLIC by default (2026-06-01)

**Decision.** Per the operator's instruction, every Git repository created for
this work is **public** — that is the default and the only visibility used unless
explicitly told otherwise for a specific repo. The TEA Package repo is published
public; future repos follow suit without asking.
