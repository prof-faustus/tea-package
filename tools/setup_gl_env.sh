#!/usr/bin/env bash
# Create a WSL Python venv for the Package and install the GL library + driver,
# then introspect the library API. Run in WSL:
#   wsl -d Ubuntu -- bash /mnt/d/claude/tea-package/tools/setup_gl_env.sh
set -euo pipefail

VENV="$HOME/teavenv"
if [ ! -d "$VENV" ]; then
  python3 -m venv "$VENV"
fi
"$VENV/bin/pip" install -q --upgrade pip >/tmp/gl_pip.log 2>&1 || true
echo "=== installing python-accounting + psycopg ==="
"$VENV/bin/pip" install -q python-accounting "psycopg[binary]" psycopg2-binary >>/tmp/gl_pip.log 2>&1 \
  || { echo "PIP_FAIL"; tail -20 /tmp/gl_pip.log; exit 1; }
echo "=== pip show ==="
"$VENV/bin/pip" show python-accounting 2>/dev/null | grep -E "^(Name|Version|Requires):" || true
echo "=== introspect ==="
"$VENV/bin/python" /mnt/d/claude/tea-package/tools/gl_probe.py
