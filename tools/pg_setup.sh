#!/usr/bin/env bash
# Stand up PostgreSQL 16 + pgcrypto and the Package role/db (Stage 0 step 3).
# Idempotent. Run inside WSL:
#   wsl -d Ubuntu -- sudo bash /mnt/d/claude/tea-package/tools/pg_setup.sh
set -euo pipefail

echo "=== install postgresql-16 ==="
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq >/tmp/pg_apt.log 2>&1 || true
apt-get install -y postgresql-16 postgresql-contrib-16 >>/tmp/pg_apt.log 2>&1
echo "installed: $(ls /usr/lib/postgresql)"

echo "=== start cluster ==="
pg_ctlcluster 16 main start 2>/dev/null || service postgresql start 2>/dev/null || true
# allow host (Windows) connections on localhost
sleep 2

echo "=== role + db + pgcrypto ==="
# role 'tea'
if ! sudo -u postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='tea'" | grep -q 1; then
  sudo -u postgres psql -c "CREATE ROLE tea LOGIN PASSWORD 'tea';"
fi
# database 'tea'
if ! sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='tea'" | grep -q 1; then
  sudo -u postgres createdb -O tea tea
fi
sudo -u postgres psql -d tea -c "CREATE EXTENSION IF NOT EXISTS pgcrypto;"

echo "=== verify ==="
echo -n "server: "; sudo -u postgres psql -tAc "SHOW server_version" | tr -d '\n'; echo
echo -n "pgcrypto: "; sudo -u postgres psql -d tea -tAc "SELECT extname FROM pg_extension WHERE extname='pgcrypto'"
echo -n "digest test: "; sudo -u postgres psql -d tea -tAc "SELECT encode(digest('x','sha256'),'hex')"
echo -n "tea login reachable: "; PGPASSWORD=tea psql -h 127.0.0.1 -U tea -d tea -tAc "SELECT 'ok'" 2>/dev/null || echo "host-login not yet (will configure listen/hba if needed)"
