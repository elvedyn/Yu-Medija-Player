# Yu Medija Player

Lightweight cross-platform video player (**Linux · Windows · macOS**).
libmpv playback, M3U/IPTV playlists with groups, multi-language subtitles,
screenshots and 0.25×–4× speed — no background workers, no effects pipeline.

## Run

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python player.py
```

Or simply:

```bash
./run.sh                 # uses .venv when present
./run.sh movie.mkv       # open a file right away
```

> On Arch / CachyOS the system Python is “externally managed”, so the venv above is
> the supported way to install PyQt6. `requirements.txt` also lists `pyinstaller`,
> which is only needed for building binaries.

## Features

- **Plays most formats** — libmpv handles MKV, MP4, AVI, WebM, MOV, TS/M2TS, MPEG,
  WMV, FLV and everything FFmpeg supports; hardware decoding optional in Settings.
- **M3U / M3U8 playlists** with `group-title` / `#EXTGRP` groups. “Playlist groups”
  menu lists groups with item counts; groups can be hidden and restored.
- **Subtitles** — embedded tracks (VLC-style track menu) and external sidecar files
  in several languages, plus OpenSubtitles search, delay adjustment and font size.
- **Screenshots** — PNG/JPG of the current frame (`P`), saved next to the video or
  to a folder you pick.
- **Speed 0.25×–4×** — dropdown presets (0.25, 0.5, 0.75, 1, 1.25, 1.5, 1.75, 2,
  2.5, 3, 4) plus `[` / `]` stepping and `R` to reset. Speed is remembered.
- **Modern dark UI** — Cinema Dark, Midnight Teal, Graphite, Paper Light, Cloud Light.
- Drag & drop files/playlists, resume where you stopped, repeat/shuffle, aspect
  ratio modes, PiP-friendly fullscreen with auto-hiding controls.

## Multi-language subtitles

Name files next to the video:

```text
movie.mp4
movie.srt          → Default
movie.en.srt       → English
movie.bs.srt       → Bosanski
movie.hr.srt       → Hrvatski
movie.de.srt       → Deutsch
```

Auto-load picks all matching `movie*.srt`.
**CC** menu or **C** → switch language / Off / add more.
**S** / File → Open Subtitles → multi-select several `.srt` files.

## Themes

**View → Theme** or **Settings** — Cinema Dark, Midnight Teal, Graphite,
Paper Light, Cloud Light.

## Keyboard

| Key | Action |
|-----|--------|
| `Space` | Play / Pause |
| `Ctrl+O` / `O` | Open video |
| `Ctrl+P` | Open M3U playlist |
| `Ctrl+U` | Open stream URL |
| `S` | Open subtitles (multi) |
| `C` | Subtitle language menu |
| `←` `→` | Seek |
| `[` `]` | Speed down / up (0.25×–4×) |
| `R` | Reset speed to 1× |
| `M` | Mute |
| `P` | Screenshot |
| `N` / `B` | Next / previous |
| `F` | Fullscreen |
| `Ctrl+,` | Settings |

## Install (Linux local)

```bash
./scripts/build.sh
./scripts/install_linux.sh    # → ~/.local + app menu
```

## Build .deb

```bash
chmod +x scripts/*.sh
./scripts/build_deb.sh
```

Creates: `dist/yu-medija-player_1.0.0_amd64.deb`

Install:

```bash
sudo apt install ./dist/yu-medija-player_1.0.0_amd64.deb
# or
sudo dpkg -i dist/yu-medija-player_1.0.0_amd64.deb
```

Needs `dpkg-deb` (comes with `dpkg-dev` on Debian/Ubuntu/Mint).

## Build AppImage

```bash
./scripts/build_appimage.sh
```

Creates: `dist/yu-medija-player-1.0.0-x86_64.AppImage`

Run:

```bash
chmod +x dist/yu-medija-player-1.0.0-x86_64.AppImage
./dist/yu-medija-player-1.0.0-x86_64.AppImage
```

The script downloads `appimagetool` once into `dist/tools/`.

## Windows / macOS

- **Windows:** PyInstaller → compile `packaging/windows/yu-medija-player.iss` with Inno Setup
- **macOS:** `./scripts/build.sh` then `./scripts/make_dmg.sh`

## Linux codecs

```bash
sudo apt install libmpv2 ffmpeg gstreamer1.0-plugins-good gstreamer1.0-libav
```

Arch / CachyOS: `sudo pacman -S mpv ffmpeg`. Without libmpv the app falls back to Qt
Multimedia, which plays far fewer formats.

> Linux packages do **not** bundle libmpv: a library built for one distro cannot be
> loaded on another, so the AppImage and `.deb` use the system one (the `.deb` lists
> `libmpv2` in `Depends`, the AppImage expects `mpv` to be installed).

## Layout

```
app/              player code
icons/            app icon (yu-medija-player*)
packaging/        .desktop + Inno Setup
scripts/
  build.sh            PyInstaller binary
  build_deb.sh        .deb
  build_appimage.sh   AppImage
  install_linux.sh    user install
  uninstall_linux.sh  remove install (+ legacy names)
  make_icons.py       regenerate app icons (PNG 16–512 + .ico);
                      --style night|ember|noir|aurora, --preview <dir>
run.sh            dev launcher (uses .venv)
yu-medija-player.spec
```
