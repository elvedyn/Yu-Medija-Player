#!/usr/bin/env bash
# Build a .deb package for Yu Medija Player (amd64).
# Requires: ./scripts/build.sh first (or runs it), plus dpkg-deb.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

VERSION="${VERSION:-1.0.0}"
ARCH="${ARCH:-amd64}"
PKG_NAME="yu-medija-player"
PKG_DIR="$ROOT/dist/deb/${PKG_NAME}_${VERSION}_${ARCH}"
DEB_OUT="$ROOT/dist/${PKG_NAME}_${VERSION}_${ARCH}.deb"

BIN=""
if [[ -x "$ROOT/dist/yu-medija-player" ]]; then
  BIN="$ROOT/dist/yu-medija-player"
else
  echo "→ Building binary first…"
  ./scripts/build.sh
  BIN="$ROOT/dist/yu-medija-player"
fi

if [[ -z "$BIN" || ! -x "$BIN" ]]; then
  echo "ERROR: dist/yu-medija-player missing. Fix build, then re-run this script."
  exit 1
fi

echo "→ Assembling Debian package tree…"
rm -rf "$PKG_DIR"
mkdir -p \
  "$PKG_DIR/DEBIAN" \
  "$PKG_DIR/usr/bin" \
  "$PKG_DIR/usr/share/applications" \
  "$PKG_DIR/usr/share/icons/hicolor/256x256/apps" \
  "$PKG_DIR/usr/share/doc/$PKG_NAME"

install -m 755 "$BIN" "$PKG_DIR/usr/bin/yu-medija-player.real"
cat > "$PKG_DIR/usr/bin/yu-medija-player" <<'INNER'
#!/usr/bin/env bash
export QT_MEDIA_BACKEND="${QT_MEDIA_BACKEND:-ffmpeg}"
export LC_NUMERIC="${LC_NUMERIC:-C}"
export GST_PLUGIN_SYSTEM_PATH_1_0="${GST_PLUGIN_SYSTEM_PATH_1_0:-/usr/lib/x86_64-linux-gnu/gstreamer-1.0}"
export GST_PLUGIN_PATH="${GST_PLUGIN_PATH:-$GST_PLUGIN_SYSTEM_PATH_1_0}"
export GST_CURL_USERAGENT="${GST_CURL_USERAGENT:-VLC/3.0.21 LibVLC/3.0.21}"
exec "$(dirname "$(readlink -f "$0")")/yu-medija-player.real" "$@"
INNER
chmod 755 "$PKG_DIR/usr/bin/yu-medija-player"
install -m 644 "$ROOT/icons/yu-medija-player-256.png" "$PKG_DIR/usr/share/icons/hicolor/256x256/apps/yu-medija-player.png"
install -m 644 "$ROOT/packaging/linux/yu-medija-player.desktop" "$PKG_DIR/usr/share/applications/yu-medija-player.desktop"

YEAR="$(date +%Y)"
cat > "$PKG_DIR/usr/share/doc/$PKG_NAME/copyright" <<INNER
Yu Medija Player
Copyright (c) ${YEAR} YuMedijaPlayer
License: as provided with the project
INNER

SIZE_KB=$(du -sk "$PKG_DIR/usr" | awk '{print $1}')

cat > "$PKG_DIR/DEBIAN/control" <<INNER
Package: $PKG_NAME
Version: $VERSION
Section: video
Priority: optional
Architecture: $ARCH
Maintainer: YuMedijaPlayer <yu-medija-player@local>
Installed-Size: $SIZE_KB
Depends: libgl1, libx11-6, libxcb1, libmpv2
Recommends: ffmpeg
Description: Yu Medija Player — lightweight video player
 A small PyQt6 video player with themes, SRT multi-language
 subtitles, M3U playlists, and low CPU usage.
INNER

echo "→ Building $DEB_OUT"
rm -f "$DEB_OUT"
dpkg-deb --root-owner-group -Zgzip --build "$PKG_DIR" "$DEB_OUT"
echo ""
echo "Done: $DEB_OUT"
echo "Install with (use full path):"
echo "  sudo apt install ./dist/${PKG_NAME}_${VERSION}_${ARCH}.deb"
