#!/usr/bin/env bash
# Stand up a USER-OWNED PostgreSQL cluster (no sudo, no docker) for development.
# Uses the installed server binaries to initdb a cluster in $HOME and run it on a
# free localhost port. Idempotent-ish: re-running restarts an existing cluster.
#   wsl -d Ubuntu -- bash /mnt/d/claude/tea-package/tools/pg_user_cluster.sh
set -euo pipefail

PGVER="$(ls /usr/lib/postgresql | sort -n | tail -1)"
PGBIN="/usr/lib/postgresql/${PGVER}/bin"
PGLIB="/usr/lib/postgresql/${PGVER}/lib"
DATADIR="$HOME/teadb"
PORT=5455
SOCK=/tmp

echo "server binaries: ${PGBIN} (v${PGVER})"
if [ ! -f "${PGLIB}/pgcrypto.so" ] && [ ! -f "${PGLIB}/pgcrypto--"*.sql ] 2>/dev/null; then
  # pgcrypto control file location check (extension SQL lives in share/)
  if ! ls /usr/share/postgresql/${PGVER}/extension/pgcrypto.control >/dev/null 2>&1; then
    echo "PGCRYPTO_MISSING: contrib not installed for v${PGVER}"; exit 3
  fi
fi

if [ ! -d "${DATADIR}/base" ]; then
  echo "=== initdb (user-owned, trust auth on localhost) ==="
  "${PGBIN}/initdb" -D "${DATADIR}" -U tea --auth-local=trust --auth-host=trust -E UTF8 >/tmp/initdb.log 2>&1
  {
    echo "port = ${PORT}"
    echo "listen_addresses = 'localhost'"
    echo "unix_socket_directories = '${SOCK}'"
  } >> "${DATADIR}/postgresql.conf"
fi

echo "=== start cluster ==="
"${PGBIN}/pg_ctl" -D "${DATADIR}" -l "${DATADIR}/server.log" -w -t 30 start 2>/dev/null || \
  "${PGBIN}/pg_ctl" -D "${DATADIR}" status

export PGHOST="${SOCK}"
"${PGBIN}/psql" -p ${PORT} -U tea -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='tea'" | grep -q 1 \
  || "${PGBIN}/createdb" -p ${PORT} -U tea tea
"${PGBIN}/psql" -p ${PORT} -U tea -d tea -c "CREATE EXTENSION IF NOT EXISTS pgcrypto;"

echo -n "server_version: "; "${PGBIN}/psql" -p ${PORT} -U tea -d tea -tAc "SHOW server_version"
echo -n "pgcrypto: ";       "${PGBIN}/psql" -p ${PORT} -U tea -d tea -tAc "SELECT extname FROM pg_extension WHERE extname='pgcrypto'"
echo -n "digest: ";         "${PGBIN}/psql" -p ${PORT} -U tea -d tea -tAc "SELECT encode(digest('x','sha256'),'hex')"
echo -n "tcp-reachable@${PORT}: "; "${PGBIN}/psql" -h 127.0.0.1 -p ${PORT} -U tea -d tea -tAc "SELECT 'reachable'"
echo "DATADIR=${DATADIR} PORT=${PORT}"
