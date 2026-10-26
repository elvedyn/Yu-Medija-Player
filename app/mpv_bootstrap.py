"""Locate bundled / system libmpv before python-mpv is imported.

Windows: add the folder containing libmpv-2.dll / mpv-2.dll via add_dll_directory + PATH.
macOS: point ctypes.util.find_library("mpv") at a known dylib (bundle or Homebrew).
Linux: no-op (system libmpv via the normal loader).
"""

from __future__ import annotations

import ctypes.util
import os
import sys
from pathlib import Path


_PREPARED = False


def _candidate_dirs() -> list[Path]:
  dirs: list[Path] = []
  # Frozen (PyInstaller onefile extracts to _MEIPASS; onedir next to exe)
  if getattr(sys, "frozen", False):
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
      dirs.append(Path(meipass))
    dirs.append(Path(sys.executable).resolve().parent)
  # Source / project tree
  try:
    from app.resources import app_root

    root = app_root()
  except Exception:
    root = Path(__file__).resolve().parent.parent
  dirs.extend(
      [
          root,
          root / "libmpv",
          root / "mpv",
          root / "bin",
      ]
  )
  if sys.platform == "darwin":
    dirs.extend(
        [
            Path("/opt/homebrew/lib"),
            Path("/usr/local/lib"),
        ]
    )
  # de-dupe, keep order
  seen: set[str] = set()
  out: list[Path] = []
  for d in dirs:
    key = str(d)
    if key not in seen:
      seen.add(key)
      out.append(d)
  return out


def _find_windows_dll() -> Path | None:
  names = ("libmpv-2.dll", "mpv-2.dll", "mpv-1.dll")
  for folder in _candidate_dirs():
    for name in names:
      cand = folder / name
      if cand.is_file():
        return cand
  return None


def _find_macos_dylib() -> Path | None:
  names = ("libmpv.dylib", "libmpv.2.dylib", "libmpv.1.dylib")
  for folder in _candidate_dirs():
    for name in names:
      cand = folder / name
      if cand.is_file() or cand.is_symlink():
        try:
          return cand.resolve()
        except OSError:
          return cand
  return None


def prepare_mpv_library() -> Path | None:
  """Ensure the dynamic linker can see libmpv. Safe to call more than once."""
  global _PREPARED
  if _PREPARED:
    return None
  _PREPARED = True

  if sys.platform == "win32":
    dll = _find_windows_dll()
    if dll is None:
      return None
    folder = str(dll.parent)
    try:
      os.add_dll_directory(folder)
    except (AttributeError, OSError):
      pass
    path = os.environ.get("PATH", "")
    if folder.lower() not in path.lower():
      os.environ["PATH"] = folder + os.pathsep + path
    return dll

  if sys.platform == "darwin":
    dylib = _find_macos_dylib()
    if dylib is None:
      return None
    # Hardened runtime often ignores DYLD_*; patch find_library instead.
    target = str(dylib)
    original = ctypes.util.find_library

    def _find(name: str):  # noqa: ANN001
      if name in ("mpv", "libmpv"):
        return target
      return original(name)

    ctypes.util.find_library = _find  # type: ignore[assignment]
    # Also preload so dependents resolve from the same prefix when possible
    try:
      ctypes.CDLL(target, mode=ctypes.RTLD_GLOBAL)
    except OSError:
      pass
    return dylib

  # Linux: bez "dev" symlinka (libmpv.so) find_library("mpv") ne nađe ništa,
  # a distribucije često imaju samo soname (libmpv.so.2).
  if ctypes.util.find_library("mpv"):
    return None
  target = _find_linux_libmpv()
  if target is None:
    return None
  resolved = str(target)
  original = ctypes.util.find_library

  def _find(name: str):  # noqa: ANN001
    if name in ("mpv", "libmpv"):
      return resolved
    return original(name)

  ctypes.util.find_library = _find  # type: ignore[assignment]
  try:
    ctypes.CDLL(resolved, mode=ctypes.RTLD_GLOBAL)
  except OSError:
    return None
  return target


def _find_linux_libmpv() -> Path | None:
  """Pronađi libmpv preko ldconfig keša ili poznatih lib foldera."""
  names = ("libmpv.so.2", "libmpv.so.1", "libmpv.so")

  # ldconfig -p zna gdje je biblioteka i na 64-bitnim „lib64“ sistemima
  import subprocess

  try:
    out = subprocess.run(
        ["ldconfig", "-p"], capture_output=True, text=True, timeout=5
    ).stdout
    for line in out.splitlines():
      if "libmpv.so" in line:
        _, _, path = line.partition("=>")
        cand = Path(path.strip().split(" (")[0])
        if cand.is_file():
          return cand
  except (OSError, subprocess.SubprocessError):
    pass

  for folder in _candidate_dirs():
    for name in names:
      cand = folder / name
      if cand.is_file():
        return cand

  for folder in (
      Path("/usr/lib"),
      Path("/usr/lib64"),
      Path("/usr/lib/x86_64-linux-gnu"),
      Path("/usr/lib/aarch64-linux-gnu"),
      Path("/usr/local/lib"),
  ):
    for name in names:
      cand = folder / name
      if cand.is_file():
        return cand
  return None
