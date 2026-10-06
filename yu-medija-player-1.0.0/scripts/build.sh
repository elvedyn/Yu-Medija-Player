#!/usr/bin/env bash
# Build Yu Medija Player binary for the current OS.
#
# On Debian/Mint/Ubuntu (PEP 668): prefers a venv. If python3-venv is missing,
# falls back to user pip with --break-system-packages (PyInstaller only).
# System PyQt6 from apt is reused when possible.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
mkdir -p "$ROOT/dist/tools"
export PATH="$HOME/.local/bin:$PATH"

PY=python3
PIP_FLAGS=()

have_pyqt() {
  "$PY" -c "from PyQt6.QtMultimedia import QMediaPlayer" >/dev/null 2>&1
}

bootstrap_get_pip() {
  local getpip="$ROOT/dist/tools/get-pip.py"
  if [[ ! -f "$getpip" ]]; then
    echo "→ Downloading get-pip.py…"
    if command -v curl >/dev/null; then
      curl -fsSL https://bootstrap.pypa.io/get-pip.py -o "$getpip"
    else
      wget -qO "$getpip" https://bootstrap.pypa.io/get-pip.py
    fi
  fi
  "$PY" "$getpip" "$@"
}

setup_env() {
  if python3 -m venv --help >/dev/null 2>&1; then
    if [[ ! -x "$ROOT/.venv/bin/python" ]] || ! "$ROOT/.venv/bin/python" -m pip --version >/dev/null 2>&1; then
      echo "→ Creating .venv (system-site-packages)…"
      rm -rf "$ROOT/.venv"
      if python3 -m venv --system-site-packages "$ROOT/.venv" 2>/tmp/yu-medija-player-venv.err; then
        if ! "$ROOT/.venv/bin/python" -m pip --version >/dev/null 2>&1; then
          bootstrap_get_pip --python "$ROOT/.venv/bin/python"
        fi
      else
        echo "NOTE: venv failed (need: sudo apt install python3.12-venv python3-pip)"
        cat /tmp/yu-medija-player-venv.err 2>/dev/null || true
        rm -rf "$ROOT/.venv"
      fi
    fi
  fi

  if [[ -x "$ROOT/.venv/bin/python" ]] && "$ROOT/.venv/bin/python" -m pip --version >/dev/null 2>&1; then
    PY="$ROOT/.venv/bin/python"
    echo "→ Using venv: $PY"
    return 0
  fi

  echo "→ Using user pip (--break-system-packages)…"
  PIP_FLAGS=(--user --break-system-packages)
  if ! python3 -m pip --version >/dev/null 2>&1; then
    bootstrap_get_pip --user --break-system-packages
  fi
  if ! python3 -m pip --version >/dev/null 2>&1; then
    echo ""
    echo "ERROR: cannot install pip automatically."
    echo "Run once:"
    echo "  sudo apt install python3-pip python3.12-venv"
    echo "Then re-run:  ./scripts/build.sh"
    exit 1
  fi
  PY=python3
}

setup_env

echo "→ Installing build deps…"
if have_pyqt; then
  echo "   System/venv PyQt6 OK — installing PyInstaller + python-mpv"
  "$PY" -m pip install "${PIP_FLAGS[@]}" -U "pyinstaller>=6.3.0" "python-mpv>=1.0.8"
else
  "$PY" -m pip install "${PIP_FLAGS[@]}" -U -r requirements.txt
fi

echo "→ Running PyInstaller…"
SPEC="yu-medija-player.spec"
"$PY" -m PyInstaller --noconfirm "$SPEC"

if [[ -x "$ROOT/dist/yu-medija-player" ]]; then
  echo ""
  echo "Build OK → dist/yu-medija-player"
  echo "Next:"
  echo "  ./scripts/install_linux.sh"
  echo "  ./scripts/build_deb.sh"
  echo "  ./scripts/build_appimage.sh"
else
  echo "ERROR: dist/yu-medija-player was not created."
  exit 1
fi
