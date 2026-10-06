#!/usr/bin/env bash
# Uninstall user-local Linux install (new + legacy names)
set -euo pipefail
PREFIX="${PREFIX:-$HOME/.local}"

rm -f "$PREFIX/bin/yu-medija-player" "$PREFIX/bin/yu-medija-player.real"
rm -f "$PREFIX/share/applications/yu-medija-player.desktop"
rm -f "$PREFIX/share/icons/hicolor/256x256/apps/yu-medija-player.png"
rm -rf "$PREFIX/share/yu-medija-player"

# Legacy names (Lumen / Frame / etvideo)
rm -f "$PREFIX/bin/lumen" "$PREFIX/bin/lumen.real"
rm -f "$PREFIX/bin/frame" "$PREFIX/bin/frame.real"
rm -f "$PREFIX/bin/etvideo"
rm -f "$PREFIX/share/applications/lumen.desktop"
rm -f "$PREFIX/share/applications/frame.desktop"
rm -f "$PREFIX/share/icons/hicolor/256x256/apps/lumen.png"
rm -f "$PREFIX/share/icons/hicolor/256x256/apps/frame.png"
rm -rf "$PREFIX/share/lumen" "$PREFIX/share/frame"

echo "Yu Medija Player (and legacy lumen/frame/etvideo) removed from $PREFIX"
