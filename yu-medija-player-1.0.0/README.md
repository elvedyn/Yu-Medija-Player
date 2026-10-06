# Yu Medija Player

Lightweight cross-platform video player (**Linux · Windows · macOS**).  
Built to stay small: no effects pipeline, no background workers, QSS themes only.

## Run

```bash
pip install -r requirements.txt
python3 player.py
```

Or after install:

```bash
./scripts/build.sh
./scripts/install_linux.sh
yu-medija-player
```

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
**CC** button or **C** → switch language / Off / add more.  
**S** / File → Open Subtitles → multi-select several `.srt` files.

## Themes

**View → Theme** or **Settings** — Cinema Dark, Midnight Teal, Graphite, Paper Light, Cloud Light.  
**Low power mode** (default): no auto-hide timers.

## Keyboard

| Key | Action |
|-----|--------|
| `Space` | Play / Pause |
| `O` | Open video |
| `S` | Open subtitles (multi) |
| `C` | Subtitle language menu |
| `←` `→` | Seek |
| `[` `]` | Speed |
| `M` | Mute |
| `P` | Screenshot |
| `F` | Fullscreen |
| `Ctrl+,` | Settings |

## Install (Linux local)

```bash
./scripts/build.sh
./scripts/install_linux.sh    # → ~/.local + app menu
```

## Remove old `lumen` / `frame` / `etvideo` install

```bash
./scripts/uninstall_linux.sh
# or manually:
# rm -f ~/.local/bin/lumen ~/.local/bin/lumen.real ~/.local/bin/frame ~/.local/bin/etvideo
# rm -f ~/.local/share/applications/lumen.desktop ~/.local/share/applications/frame.desktop
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
sudo dpkg -i ./dist/yu-medija-player_1.0.0_amd64.deb
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
yu-medija-player.spec
```
