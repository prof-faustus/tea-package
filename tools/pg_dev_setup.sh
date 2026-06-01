#!/usr/bin/env bash
# Create the Package 'tea' role/db + pgcrypto in an existing local cluster
# (development DB). Pass the port as $1 (default 5433). Run in WSL:
#   wsl -d Ubuntu -- sudo bash /mnt/d/claude/tea-package/tools/pg_dev_setup.sh 5433
set -euo pipefail
P="${1:-5433}"
PSQL="psql -p $P"

run_pg() { sudo -u postgres $PSQL "$@"; }

if ! run_pg -tAc "SELECT 1 FROM pg_roles WHERE rolname='tea'" | grep -q 1; then
  run_pg -c "CREATE ROLE tea LOGIN PASSWORD 'tea';"
fi
if ! run_pg -tAc "SELECT 1 FROM pg_database WHERE datname='tea'" | grep -q 1; then
  sudo -u postgres createdb -p "$P" -O tea tea
fi
run_pg -d tea -c "CREATE EXTENSION IF NOT EXISTS pgcrypto;"

echo -n "server_version: "; run_pg -d tea -tAc "SHOW server_version"
echo -n "pgcrypto: ";       run_pg -d tea -tAc "SELECT extname FROM pg_extension WHERE extname='pgcrypto'"
echo -n "digest: ";         run_pg -d tea -tAc "SELECT encode(digest('x','sha256'),'hex')"
echo -n "tea-login@$P: ";   PGPASSWORD=tea psql -h 127.0.0.1 -p "$P" -U tea -d tea -tAc "SELECT 'reachable'"
