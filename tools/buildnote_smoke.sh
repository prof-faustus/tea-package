#!/usr/bin/env bash
# Build the engine and smoke-test build-note -> anchor -> prove -> verify with a
# REAL signed note. Run in WSL:
#   wsl -d Ubuntu -- bash /mnt/d/claude/tea-package/tools/buildnote_smoke.sh
set -euo pipefail
. "$HOME/.cargo/env" 2>/dev/null || true
cd "$HOME/engine"
cp /mnt/d/claude/triple-entry-evidence-bsv/crates/cli/src/main.rs crates/cli/src/main.rs
echo "=== build ==="; cargo build --release 2>&1 | tail -3
B="$HOME/engine/target/release/tea-bsv"
echo "=== selftest/reproduce ==="; "$B" selftest | tail -1; "$B" reproduce | tail -1

D=$(mktemp -d)
"$B" worked-example > "$D/we.json"
SKA=$(grep -oP '"sk_a_1_hex": "\K[0-9a-f]+' "$D/we.json")
PKB=$(grep -oP '"pk_b_1_hex": "\K[0-9a-f]+' "$D/we.json")
printf '[{"label":"InvID","value":"INV-1"},{"label":"Gross","value":"12100"}]' > "$D/fields.json"

echo "=== build-note (invoice) ==="
"$B" build-note --sk-hex "$SKA" --counterparty-pub-hex "$PKB" --note-id INV-1 \
    --kind invoice --fields-file "$D/fields.json" --out "$D/note.json"
echo "note fields_pub (labels only, values blank):"
grep -A6 fields_pub "$D/note.json" | head -8

printf '[%s]' "$(cat "$D/note.json")" > "$D/notes.json"
TXID=$(printf 'ab%.0s' {1..32})
echo "=== anchor -> prove -> verify ==="
"$B" anchor --notes "$D/notes.json" --bsv-anchor-txid-be "$TXID" --out "$D/batch.json"
"$B" prove --batch "$D/batch.json" --notes "$D/notes.json" --leaf-index 0 --out "$D/bundle.json"
"$B" verify --bundle "$D/bundle.json"
echo "BUILDNOTE-SMOKE-OK"
