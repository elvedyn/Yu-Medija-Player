#!/usr/bin/env bash
# Instaliraj Yu Medija Player AppImage za trenutnog korisnika (bez root-a).
#
#   ./scripts/install_appimage.sh [putanja/do/fajl.AppImage]
#
# Bez argumenta uzima najnoviji AppImage iz dist/ ili sa Desktop/Downloads.
#
# Uradi:
#   1) kopira AppImage u ~/Applications/yu-medija-player.AppImage (+ chmod +x)
#   2) instalira ikone u ~/.local/share/icons/hicolor/<velicina>/apps/
#   3) pise ~/.local/share/applications/yu-medija-player.desktop
#      (ime fajla MORA biti yu-medija-player jer aplikacija prijavljuje
#       _KDE_NET_WM_DESKTOP_FILE=yu-medija-player — tako se taskbar ikona veze)
#   4) osvjezi bazu desktop fajlova (update-desktop-database + kbuildsycoca)
#   5) postavi ga kao podrazumijevanog igraca za video i playliste (xdg-mime)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

APP_DIR="${APP_DIR:-$HOME/Applications}"
TARGET="$APP_DIR/yu-medija-player.AppImage"
DESKTOP_NAME="yu-medija-player.desktop"
DESKTOP_DIR="$HOME/.local/share/applications"
ICON_DIR="$HOME/.local/share/icons/hicolor"

find_appimage() {
  local candidates=()
  local d
  for d in "$ROOT/dist" "$HOME/Desktop" "$HOME/Downloads"; do
    [[ -d "$d" ]] || continue
    while IFS= read -r f; do
      # appimagetool je alat, ne aplikacija
      [[ "$(basename "$f")" == *appimagetool* ]] && continue
      candidates+=("$f")
    done < <(find "$d" -maxdepth 1 -name '*.AppImage' -type f 2>/dev/null)
  done
  [[ ${#candidates[@]} -gt 0 ]] || return 1
  ls -t "${candidates[@]}" | head -1
}

SRC="${1:-}"
if [[ -z "$SRC" ]]; then
  if ! SRC="$(find_appimage)"; then
    echo "ERROR: nema AppImage fajla. Prvo: ./scripts/build_appimage.sh" >&2
    exit 1
  fi
fi
[[ -f "$SRC" ]] || { echo "ERROR: ne postoji: $SRC" >&2; exit 1; }
SRC="$(readlink -f "$SRC")"

echo "→ Izvor: $SRC"

# 1) Kopija na stabilnu putanju (UI se ne kvari kad se dist/ obrise)
mkdir -p "$APP_DIR"
if [[ "$SRC" != "$TARGET" ]]; then
  install -m 755 "$SRC" "$TARGET"
fi
chmod +x "$TARGET"
echo "→ Aplikacija: $TARGET"

# 2) Ikone
icon_count=0
if [[ -d "$ROOT/icons" ]]; then
  for f in "$ROOT"/icons/yu-medija-player-*.png; do
    [[ -f "$f" ]] || continue
    size="$(basename "$f" | sed -n 's/^yu-medija-player-\([0-9]\+\)\.png$/\1/p')"
    [[ -n "$size" ]] || continue
    mkdir -p "$ICON_DIR/${size}x${size}/apps"
    install -m 644 "$f" "$ICON_DIR/${size}x${size}/apps/yu-medija-player.png"
    icon_count=$((icon_count + 1))
  done
fi
echo "→ Ikona instalirano: $icon_count (hicolor)"

# 3) Desktop fajl
mkdir -p "$DESKTOP_DIR"
cat > "$DESKTOP_DIR/$DESKTOP_NAME" <<DESKTOP
[Desktop Entry]
Type=Application
Version=1.0
Name=Yu Medija Player
GenericName=Video Player
Comment=Lightweight video player with m3u playlist and subtitle support
Exec="$TARGET" %F
TryExec=$TARGET
Icon=yu-medija-player
Terminal=false
Categories=AudioVideo;Video;Player;Qt;
Keywords=video;player;media;film;movie;m3u;playlist;subtitle;plejer;
StartupNotify=true
StartupWMClass=yu-medija-player
MimeType=video/mp4;video/x-matroska;video/x-m4v;video/x-msvideo;video/x-ms-wmv;video/x-ms-asf;video/x-ms-wm;video/x-ms-asx;video/x-flv;video/webm;video/ogg;video/quicktime;video/mpeg;video/mp2t;video/3gpp;video/3gpp2;video/x-ms-vob;video/dvd;video/x-f4v;video/x-mpeg;video/x-mpeg2;video/x-ogm+ogg;video/x-theora+ogg;video/divx;video/av1;video/vp8;video/vp9;video/vnd.dlna.mpeg-tts;audio/x-mpegurl;audio/mpegurl;application/vnd.apple.mpegurl;application/x-mpegurl;application/x-m3u;text/x-m3u;application/x-subrip;application/x-ass;text/x-ssa;
DESKTOP

# 4) Osvjezi baze
command -v update-desktop-database >/dev/null && \
  update-desktop-database "$DESKTOP_DIR" >/dev/null 2>&1 || true
for k in kbuildsycoca6 kbuildsycoca5; do
  if command -v "$k" >/dev/null; then
    "$k" --noincremental >/dev/null 2>&1 || true
    break
  fi
done
if command -v gtk-update-icon-cache >/dev/null; then
  gtk-update-icon-cache -qtf "$ICON_DIR" >/dev/null 2>&1 || true
fi

# 5) Podrazumijevani igrac za video i playliste
DEFAULT_TYPES=(
  video/mp4 video/x-matroska video/x-msvideo video/x-ms-wmv video/x-ms-asf
  video/x-m4v video/x-flv video/webm video/ogg video/quicktime video/mpeg
  video/mp2t video/3gpp video/3gpp2 video/x-ms-vob video/x-f4v video/x-mpeg
  video/x-mpeg2 video/x-ogm+ogg video/x-theora+ogg video/divx video/dvd
  video/x-ms-asx video/x-ms-wm video/av1 video/vp8 video/vp9
  audio/x-mpegurl audio/mpegurl application/vnd.apple.mpegurl application/x-mpegurl
  application/x-m3u text/x-m3u
)

if command -v xdg-mime >/dev/null; then
  applied=0
  for t in "${DEFAULT_TYPES[@]}"; do
    if xdg-mime default "$DESKTOP_NAME" "$t" 2>/dev/null; then
      applied=$((applied + 1))
    fi
  done
  echo "→ Podrazumijevani za $applied MIME tipova"
else
  echo "NOTE: nema xdg-mime — postavi rucno u Sistem → Aplikacije → Default Applications"
fi

# gio kao dodatni sloj (GNOME/XFCE)
if command -v gio >/dev/null; then
  for t in video/mp4 video/x-matroska video/mp2t audio/x-mpegurl; do
    gio mime "$t" "$DESKTOP_NAME" >/dev/null 2>&1 || true
  done
fi

echo ""
echo "Gotovo. Provjera:"
if command -v xdg-mime >/dev/null; then
  printf '  video/mp4  -> %s\n' "$(xdg-mime query default video/mp4)"
  printf '  .mkv       -> %s\n' "$(xdg-mime query default video/x-matroska)"
  printf '  .ts        -> %s\n' "$(xdg-mime query default video/mp2t)"
  printf '  .m3u       -> %s\n' "$(xdg-mime query default audio/x-mpegurl)"
fi
echo ""
echo "Pokretanje:   $TARGET"
echo "Uklanjanje:   rm -f \"$TARGET\" \"$DESKTOP_DIR/$DESKTOP_NAME\""
