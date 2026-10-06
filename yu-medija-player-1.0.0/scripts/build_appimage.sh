#!/usr/bin/env bash
# Build an AppImage for Yu Medija Player (x86_64).
# Requires: ./scripts/build.sh (auto-runs), wget/curl, and fuse for running AppImages.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

VERSION="${VERSION:-1.0.0}"
ARCH="$(uname -m)"
case "$ARCH" in
  x86_64|amd64) ARCH_TAG="x86_64" ;;
  aarch64|arm64) ARCH_TAG="aarch64" ;;
  *) ARCH_TAG="$ARCH" ;;
esac

APPDIR="$ROOT/dist/yu-medija-player.AppDir"
OUT="$ROOT/dist/yu-medija-player-${VERSION}-${ARCH_TAG}.AppImage"
TOOLS="$ROOT/dist/tools"
mkdir -p "$TOOLS"

BIN=""
if [[ -x "$ROOT/dist/yu-medija-player" ]]; then
  BIN="$ROOT/dist/yu-medija-player"
else
  echo "→ Building binary first…"
  ./scripts/build.sh
  BIN="$ROOT/dist/yu-medija-player"
fi
test -n "$BIN" && test -x "$BIN"

echo "→ Assembling AppDir…"
rm -rf "$APPDIR"
mkdir -p \
  "$APPDIR/usr/bin" \
  "$APPDIR/usr/share/applications" \
  "$APPDIR/usr/share/icons/hicolor/256x256/apps"

install -m 755 "$BIN" "$APPDIR/usr/bin/yu-medija-player.real"
cat > "$APPDIR/usr/bin/yu-medija-player" <<'INNER'
#!/usr/bin/env bash
export QT_MEDIA_BACKEND="${QT_MEDIA_BACKEND:-ffmpeg}"
export LC_NUMERIC="${LC_NUMERIC:-C}"
export GST_PLUGIN_SYSTEM_PATH_1_0="${GST_PLUGIN_SYSTEM_PATH_1_0:-/usr/lib/x86_64-linux-gnu/gstreamer-1.0}"
export GST_PLUGIN_PATH="${GST_PLUGIN_PATH:-$GST_PLUGIN_SYSTEM_PATH_1_0}"
export GST_CURL_USERAGENT="${GST_CURL_USERAGENT:-VLC/3.0.21 LibVLC/3.0.21}"
exec "$(dirname "$(readlink -f "$0")")/yu-medija-player.real" "$@"
INNER
chmod +x "$APPDIR/usr/bin/yu-medija-player"
install -m 644 "$ROOT/icons/yu-medija-player-256.png" "$APPDIR/usr/share/icons/hicolor/256x256/apps/yu-medija-player.png"
cp "$APPDIR/usr/share/icons/hicolor/256x256/apps/yu-medija-player.png" "$APPDIR/yu-medija-player.png"

cat > "$APPDIR/yu-medija-player.desktop" <<INNER
[Desktop Entry]
Type=Application
Name=Yu Medija Player
Comment=Lightweight video player
Exec=yu-medija-player %F
Icon=yu-medija-player
Categories=AudioVideo;Video;Player;
Terminal=false
INNER
cp "$APPDIR/yu-medija-player.desktop" "$APPDIR/usr/share/applications/yu-medija-player.desktop"

cat > "$APPDIR/AppRun" <<'INNER'
#!/usr/bin/env bash
HERE="$(dirname "$(readlink -f "$0")")"
export QT_MEDIA_BACKEND="${QT_MEDIA_BACKEND:-ffmpeg}"
export LC_NUMERIC="${LC_NUMERIC:-C}"
export GST_PLUGIN_SYSTEM_PATH_1_0="${GST_PLUGIN_SYSTEM_PATH_1_0:-/usr/lib/x86_64-linux-gnu/gstreamer-1.0}"
export GST_PLUGIN_PATH="${GST_PLUGIN_PATH:-$GST_PLUGIN_SYSTEM_PATH_1_0}"
export GST_CURL_USERAGENT="${GST_CURL_USERAGENT:-VLC/3.0.21 LibVLC/3.0.21}"
exec "$HERE/usr/bin/yu-medija-player" "$@"
INNER
chmod +x "$APPDIR/AppRun"

APPIMAGETOOL="$TOOLS/appimagetool-$ARCH_TAG.AppImage"
if [[ ! -x "$APPIMAGETOOL" ]]; then
  echo "→ Downloading appimagetool…"
  URL="https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-${ARCH_TAG}.AppImage"
  if command -v curl >/dev/null; then
    curl -fsSL "$URL" -o "$APPIMAGETOOL"
  else
    wget -qO "$APPIMAGETOOL" "$URL"
  fi
  chmod +x "$APPIMAGETOOL"
fi

echo "→ Packing AppImage…"
ARCH="$ARCH_TAG" "$APPIMAGETOOL" "$APPDIR" "$OUT"
echo ""
echo "Done: $OUT"
echo "  chmod +x dist/yu-medija-player-${VERSION}-${ARCH_TAG}.AppImage"
echo "  ./dist/yu-medija-player-${VERSION}-${ARCH_TAG}.AppImage"
