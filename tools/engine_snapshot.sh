#!/usr/bin/env bash
# Capture the engine contract snapshot (REQ-EVID-0040) from the runnable
# (WSL/Linux) engine binary into the Package repo. Run inside WSL:
#   wsl -d Ubuntu -- bash /mnt/d/claude/tea-package/tools/engine_snapshot.sh
set -euo pipefail

BIN="${TEA_BSV_BIN:-$HOME/engine/target/release/tea-bsv}"
OUT="/mnt/d/claude/tea-package/contract"
mkdir -p "$OUT/help"

"$BIN" --version > "$OUT/engine_version.txt"
"$BIN" --help    > "$OUT/help/_top.txt"
for s in selftest reproduce worked-example anchor prove verify query disclose; do
  "$BIN" "$s" --help > "$OUT/help/$s.txt" 2>&1 || true
done

echo "binary: $BIN"
echo "sha256: $(sha256sum "$BIN" | cut -d' ' -f1)"
echo "version: $(cat "$OUT/engine_version.txt")"
echo "snapshot files:"
ls -1 "$OUT" "$OUT/help"
