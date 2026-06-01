#!/usr/bin/env bash
# Stand up the Package's dedicated PostgreSQL 16 + pgcrypto as an isolated
# container (Stage 0 step 3). Mirrors the section-09 docker-compose DB service.
# Port 5544 on localhost avoids the existing 5432 occupant. Run in WSL:
#   wsl -d Ubuntu -- sudo bash /mnt/d/claude/tea-package/tools/pg_docker.sh
set -euo pipefail

NAME=tea-postgres
PORT=5544
IMAGE=postgres:16

if [ -n "$(docker ps -aq -f name=^${NAME}$)" ]; then
  echo "container ${NAME} exists; (re)starting"
  docker start "${NAME}" >/dev/null
else
  echo "=== pull + run ${IMAGE} ==="
  docker run -d --name "${NAME}" \
    -e POSTGRES_USER=tea -e POSTGRES_PASSWORD=tea -e POSTGRES_DB=tea \
    -p 127.0.0.1:${PORT}:5432 \
    "${IMAGE}" >/dev/null
fi

echo "=== wait for readiness ==="
for i in $(seq 1 30); do
  if docker exec "${NAME}" pg_isready -U tea -d tea >/dev/null 2>&1; then break; fi
  sleep 1
done

echo "=== enable pgcrypto + verify ==="
docker exec "${NAME}" psql -U tea -d tea -v ON_ERROR_STOP=1 -c "CREATE EXTENSION IF NOT EXISTS pgcrypto;"
echo -n "server_version: "; docker exec "${NAME}" psql -U tea -d tea -tAc "SHOW server_version"
echo -n "pgcrypto: ";       docker exec "${NAME}" psql -U tea -d tea -tAc "SELECT extname FROM pg_extension WHERE extname='pgcrypto'"
echo -n "digest test: ";    docker exec "${NAME}" psql -U tea -d tea -tAc "SELECT encode(digest('x','sha256'),'hex')"
echo "=== host reachability (from WSL) on 127.0.0.1:${PORT} ==="
PGPASSWORD=tea psql -h 127.0.0.1 -p ${PORT} -U tea -d tea -tAc "SELECT 'reachable'" 2>/dev/null \
  || docker exec "${NAME}" psql -U tea -d tea -tAc "SELECT 'reachable-in-container'"
