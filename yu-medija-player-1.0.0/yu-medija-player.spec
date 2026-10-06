# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec — build on each OS for that OS."""

import os
import subprocess
import sys
from pathlib import Path

block_cipher = None
root = Path(SPECPATH)

datas = [
    (str(root / "icons"), "icons"),  # includes icons/controls/*.svg
    (str(root / "assets"), "assets"),
]

binaries = []


def _add_binary(src: Path, dest: str = ".") -> None:
  if src.is_file() or src.is_symlink():
    binaries.append((str(src), dest))


if sys.platform == "win32":
  # Expect libmpv-2.dll (or mpv-2.dll) in project root / libmpv / mpv before building.
  dll = None
  dll_dir = None
  for folder in (root, root / "libmpv", root / "mpv", root / "bin"):
    for name in ("libmpv-2.dll", "mpv-2.dll"):
      cand = folder / name
      if cand.is_file():
        dll, dll_dir = cand, folder
        break
    if dll:
      break
  if dll_dir is not None:
    # Bundle the whole DLL set from that folder (libmpv + runtime deps).
    for item in sorted(dll_dir.glob("*.dll")):
      _add_binary(item, ".")
  # Optional: ffprobe.exe next to the project for duration probing on Windows
  for name in ("ffprobe.exe", "ffmpeg.exe"):
    for folder in (root, root / "bin", root / "ffmpeg"):
      _add_binary(folder / name, ".")

elif sys.platform == "darwin":
  # Prefer a project-local copy, else Homebrew libmpv.
  dylib = None
  for folder in (
      root,
      root / "libmpv",
      Path("/opt/homebrew/lib"),
      Path("/usr/local/lib"),
  ):
    for name in ("libmpv.dylib", "libmpv.2.dylib"):
      cand = folder / name
      if cand.is_file() or cand.is_symlink():
        try:
          dylib = cand.resolve()
        except OSError:
          dylib = cand
        break
    if dylib:
      break
  if dylib is not None:
    _add_binary(dylib, ".")
    # Pull in non-system dylibs that libmpv links against (Homebrew ffmpeg etc.)
    try:
      out = subprocess.check_output(["otool", "-L", str(dylib)], text=True)
      for line in out.splitlines()[1:]:
        dep = line.strip().split(" (", 1)[0].strip()
        if not dep or dep.startswith("/usr/lib") or dep.startswith("/System/"):
          continue
        if "libmpv" in Path(dep).name:
          continue
        dep_path = Path(dep)
        if dep_path.is_file():
          _add_binary(dep_path, ".")
    except (OSError, subprocess.CalledProcessError):
      pass

else:
  # Linux — unchanged: bundle system libmpv.so.2 when present
  for cand in (
      Path("/usr/lib/x86_64-linux-gnu/libmpv.so.2"),
      Path("/usr/lib/libmpv.so.2"),
  ):
    if cand.is_file():
      binaries.append((str(cand), "."))
      break

# Optional tools/ (yt-dlp, ffprobe) shipped next to the frozen app
_tools = root / "tools"
if _tools.is_dir():
  for item in sorted(_tools.iterdir()):
    if item.name.startswith(".") or item.name.lower() == "readme.txt":
      continue
    if item.is_file():
      _add_binary(item, ".")

a = Analysis(
    ['player.py'],
    pathex=[str(root)],
    binaries=binaries,
    datas=datas,
    hiddenimports=[
        'PyQt6.QtMultimedia',
        'PyQt6.QtMultimediaWidgets',
        'PyQt6.QtOpenGLWidgets',
        'mpv',
        'app.mpv_bootstrap',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'matplotlib',
        'numpy',
        'pandas',
        'scipy',
        'PIL',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

icon_file = None
if sys.platform == 'win32':
    cand = root / 'icons' / 'yu-medija-player.ico'
    icon_file = str(cand) if cand.exists() else None
else:
    cand = root / 'icons' / 'yu-medija-player.png'
    icon_file = str(cand) if cand.exists() else None

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='yu-medija-player',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon_file,
)

if sys.platform == 'darwin':
    app = BUNDLE(
        exe,
        name='yu-medija-player.app',
        icon=str(root / 'icons' / 'yu-medija-player.png') if (root / 'icons' / 'yu-medija-player.png').exists() else None,
        bundle_identifier='com.yumedijaplayer.yu-medija-player',
        info_plist={
            'NSPrincipalClass': 'NSApplication',
            'NSHighResolutionCapable': True,
            'CFBundleName': 'YuMedijaPlayer',
            'CFBundleDisplayName': 'Yu Medija Player',
            'CFBundleShortVersionString': '1.0.0',
            'LSMinimumSystemVersion': '11.0',
        },
    )
