# Verification log

Every external fact the build relies on, its authoritative source, the
verification, and the date. No fact here is assumed; each is confirmed by
reading the source or by execution (HARD RULE: never assume).

## V-ENGINE-0001 — engine identity, build, and binary name (2026-06-01)

- **Repo / ref.** `prof-faustus/triple-entry-evidence-bsv`, HEAD
  `52834be3c040785095d63090f1e0347ced817516`, working tree clean. Source:
  `git rev-parse HEAD` in `D:\claude\triple-entry-evidence-bsv`. **Confirmed.**
- **Binary name (REQ-EVID-0030).** Resolved from the workspace, not hardcoded:
  `crates/cli/Cargo.toml` declares `[[bin]] name = "tea-bsv"` (package
  `tee-cli`). **Confirmed** by reading the file. Exported as `TEA_BSV_BIN`.
- **CLI surface.** Subcommands `selftest, reproduce, worked-example, anchor,
  prove, verify, query, disclose`, `clap` with `version`. Source:
  `crates/cli/src/main.rs`. **Confirmed** by reading the source; pinned by the
  contract snapshot (`tools/engine_build.py`, REQ-EVID-0040).
- **Build.** `cargo build --release` completes clean with the engine's pinned
  Rust stable toolchain (`rust-toolchain.toml` channel = stable;
  `rustc 1.96.0`). **Confirmed.**
- **selftest / reproduce (REQ-EVID-0043).** **CONFIRMED GREEN by execution** in
  WSL2 Ubuntu (the runnable Linux build, see V-ENV-0001):
  - `tea-bsv selftest` → `selftest passed: 5/5 checks` (BSV double-SHA256 vector;
    ECDH agreement + deterministic subkey derivation; sign/verify/leaf-hash chain;
    Merkle Layer-A inclusion; proofstore Layer-B query + adversarial, k=2).
  - `tea-bsv reproduce` → `reproduce passed: 3 committed vector(s) match`
    (`merkle.bsv_block.v1`; `tea.worked_example.v1`; `study.simstudy.v1` M=200,
    inclusion 64/64, selective 64/64, all in-scope faults detected).
  - `tea-bsv --version` → `tea-bsv 0.1.0`. Binary sha256
    `fd232e377cabd317dfca95bb8e50080a232bd439981af4f1e0e41201815b7473`.
  Contract snapshot (version + all 8 subcommand help surfaces) captured under
  `contract/` (REQ-EVID-0040). Numbers above are the actual printed output, not
  transcribed from memory.

## V-ENV-0001 — engine binary will not run under the Windows harness shells (2026-06-01)

- **Observation.** `tea-bsv.exe` hangs at startup on every invocation — including
  `--version` (the minimal `clap` path) — across PowerShell `&`, PowerShell
  `Start-Job`, MINGW bash, and `cmd /c`, both sandboxed and with the sandbox
  disabled. No stdout is produced (not even the first line); the process never
  exits and stuck processes accumulate. Confirmed by a hard-bounded job
  (`Wait-Job -Timeout`: `STILL-HUNG`).
- **Scope.** This is an execution-environment limitation of the harness's Windows
  process sandbox, not an engine defect: the same source builds clean, and
  `cargo`/`python`/`git` run normally. The engine logic is unchanged and pinned.
- **Resolution.** The engine is built and its `selftest`/`reproduce` gates are run
  in **WSL2 Ubuntu**, where Linux binaries execute cleanly. The Package consumes
  the engine via the bridge with `TEA_BSV_BIN` pointing at the runnable binary;
  the production/demo deployment runs the engine in a Linux container (section 09),
  so the Linux execution path is the deployed path. See DEC-0001.

## V-DB-0001 — Package development database (2026-06-01)

- **Reachable + pgcrypto: CONFIRMED.** A **user-owned** PostgreSQL cluster
  (`initdb`/`pg_ctl`, no sudo, no docker) runs at `127.0.0.1:5455`, database/role
  `tea`, trust auth on localhost. `CREATE EXTENSION pgcrypto` succeeds; a digest
  self-check returns the correct SHA-256 of `"x"`
  (`2d711642b726b04401627ca9fbac32f5c8530fb1903cc4db02258717921a4881`). Stood up
  by `tools/pg_user_cluster.sh`.
- **Version caveat (honest).** The cluster is **PostgreSQL 18.4**, not 16, because
  only pg18 server binaries are installed and the environment cannot provide pg16
  non-interactively: the Docker daemon is unresponsive (a wedged `docker pull`)
  and passwordless `sudo` is unavailable (`sudo -n` → "a password is required"),
  so neither `docker run postgres:16` nor `apt install postgresql-16` can be
  completed here. See DEC-0003.
- **Spec compliance.** The spec pins PostgreSQL **16**; that pin is honoured in the
  deploy/CI image (`postgres:16`, section 09 docker-compose), which is where the
  version actually ships and where the Stage-7 acceptance cold-up runs. The
  Package SQL is written to the 16/18-portable subset (standard DDL, `plpgsql`
  triggers, `pgcrypto`); any 16-specific behaviour is validated in Stage 7 against
  `postgres:16`.
- **Environment note.** Stuck root processes from the earlier `sudo apt-get
  update` (network-hung ~38 min) and `docker pull` remain; they are harmless to
  the user cluster and require the operator's `sudo` to reap.

Connection DSN (dev): `postgresql://tea:tea@127.0.0.1:5455/tea` (see `.env.example`).
