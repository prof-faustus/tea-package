#!/usr/bin/env bash
# Apply migrations 0001-0007 to a clean slate and run the chain trigger tests.
# Dev convenience against the user cluster; CI runs the equivalent via the
# migrate-test stage (REQ-BUILD-0070 step 5). Run in WSL:
#   wsl -d Ubuntu -- bash /mnt/d/claude/tea-package/tools/migrate_and_test.sh
set -euo pipefail

PGVER="$(ls /usr/lib/postgresql | sort -n | tail -1)"
PGBIN="/usr/lib/postgresql/${PGVER}/bin"
PORT="${TEA_DB_PORT:-5455}"
REPO=/mnt/d/claude/tea-package
PSQL="${PGBIN}/psql -v ON_ERROR_STOP=1 -h 127.0.0.1 -p ${PORT} -U tea -d tea"

echo "=== clean slate ==="
$PSQL -q -c "DROP SCHEMA IF EXISTS core,evid,wallet,msg,authz,ops,gl CASCADE;"

echo "=== apply migrations 0001-0008 ==="
for n in 0001 0002 0003 0004 0005 0006 0007 0008; do
  f=$(ls "${REPO}/migrations/${n}"_*.sql)
  $PSQL -q -f "$f"
  echo "  applied $(basename "$f")"
done

echo "=== applied ledger ==="
$PSQL -tAc "SELECT version FROM core.schema_migration ORDER BY version"

echo "=== chain trigger tests ==="
$PSQL -f "${REPO}/tests/sql/test_chain.sql"
echo "MIGRATE-AND-TEST: OK"
