#!/usr/bin/env bash
# Pokretanje iz projektnog foldera: koristi .venv ako postoji, inače sistemski python3.
set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")"

if [ -x .venv/bin/python ]; then
  PY=.venv/bin/python
else
  PY=python3
fi

if ! "$PY" -c "import PyQt6, mpv" >/dev/null 2>&1; then
  echo "Nedostaju zavisnosti. Instaliraj ih sa:" >&2
  echo "  python3 -m venv .venv && .venv/bin/pip install -r requirements.txt" >&2
  exit 1
fi

exec "$PY" player.py "$@"
