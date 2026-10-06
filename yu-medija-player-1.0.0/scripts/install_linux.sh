#!/usr/bin/env bash
# Lightweight Linux installer for Yu Medija Player (user-local, no root by default).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PREFIX="${PREFIX:-$HOME/.local}"
BIN_DIR="$PREFIX/bin"
APP_DIR="$PREFIX/share/yu-medija-player"
DESKTOP_DIR="$PREFIX/share/applications"
ICON_DIR="$PREFIX/share/icons/hicolor/256x256/apps"

echo "Installing Yu Medija Player → $PREFIX"

mkdir -p "$BIN_DIR" "$APP_DIR" "$DESKTOP_DIR" "$ICON_DIR"

write_launcher() {
  local dest="$1"
  local real="$2"
  cat > "$dest" <<INNER
#!/usr/bin/env bash
export QT_MEDIA_BACKEND="\${QT_MEDIA_BACKEND:-ffmpeg}"
export LC_NUMERIC="\${LC_NUMERIC:-C}"
export GST_PLUGIN_SYSTEM_PATH_1_0="\${GST_PLUGIN_SYSTEM_PATH_1_0:-/usr/lib/x86_64-linux-gnu/gstreamer-1.0}"
export GST_PLUGIN_PATH="\${GST_PLUGIN_PATH:-\$GST_PLUGIN_SYSTEM_PATH_1_0}"
export GST_CURL_USERAGENT="\${GST_CURL_USERAGENT:-VLC/3.0.21 LibVLC/3.0.21}"
exec "$real" "\$@"
INNER
  chmod +x "$dest"
}

if [[ -x "$ROOT/dist/yu-medija-player" ]]; then
  install -m 755 "$ROOT/dist/yu-medija-player" "$BIN_DIR/yu-medija-player.real"
  write_launcher "$BIN_DIR/yu-medija-player" "$BIN_DIR/yu-medija-player.real"
  echo "Installed binary: $BIN_DIR/yu-medija-player"
else
  cat > "$BIN_DIR/yu-medija-player" <<INNER
#!/usr/bin/env bash
export QT_MEDIA_BACKEND="\${QT_MEDIA_BACKEND:-ffmpeg}"
export LC_NUMERIC="\${LC_NUMERIC:-C}"
export GST_PLUGIN_SYSTEM_PATH_1_0="\${GST_PLUGIN_SYSTEM_PATH_1_0:-/usr/lib/x86_64-linux-gnu/gstreamer-1.0}"
export GST_CURL_USERAGENT="\${GST_CURL_USERAGENT:-VLC/3.0.21 LibVLC/3.0.21}"
exec python3 "$ROOT/player.py" "\$@"
INNER
  chmod +x "$BIN_DIR/yu-medija-player"
  echo "Installed source launcher: $BIN_DIR/yu-medija-player"
  echo "(Build first with ./scripts/build.sh for a standalone binary.)"
fi

install -m 644 "$ROOT/icons/yu-medija-player-256.png" "$ICON_DIR/yu-medija-player.png"
install -m 644 "$ROOT/packaging/linux/yu-medija-player.desktop" "$DESKTOP_DIR/yu-medija-player.desktop"

sed -i "s|^Exec=.*|Exec=$BIN_DIR/yu-medija-player %F|" "$DESKTOP_DIR/yu-medija-player.desktop"
sed -i "s|^Icon=.*|Icon=$ICON_DIR/yu-medija-player.png|" "$DESKTOP_DIR/yu-medija-player.desktop"

rm -f "$DESKTOP_DIR/lumen.desktop" "$DESKTOP_DIR/frame.desktop" "$DESKTOP_DIR/etvideo.desktop"

if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database "$DESKTOP_DIR" >/dev/null 2>&1 || true
fi

echo "Done. Start with: yu-medija-player"
echo "App menu name: Yu Medija Player"
