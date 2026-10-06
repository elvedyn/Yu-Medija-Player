#!/usr/bin/env bash
# Create a simple macOS .dmg from dist/yu-medija-player.app (run on macOS after PyInstaller).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APP="$ROOT/dist/yu-medija-player.app"
OUT="$ROOT/dist/yu-medija-player-1.0.0.dmg"
if [[ ! -d "$APP" ]]; then
  echo "Missing dist/yu-medija-player.app — build with PyInstaller on macOS first."
  exit 1
fi
hdiutil create -volname "Yu Medija Player" -srcfolder "$APP" -ov -format UDZO "$OUT"
echo "Created $OUT"
