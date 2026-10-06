"""Resolve asset paths in source and PyInstaller builds."""

from __future__ import annotations

import sys
from pathlib import Path


def app_root() -> Path:
  if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
    return Path(sys._MEIPASS)
  return Path(__file__).resolve().parent.parent


def icon_path(*names: str) -> Path | None:
  root = app_root()
  candidates = [
      root / "icons" / name
      for name in names
  ] + [
      root / "assets" / name
      for name in names
  ]
  for path in candidates:
    if path.exists():
      return path
  return None


def control_icon_path(name: str) -> Path | None:
  """Resolve icons/controls/<name>.svg in source or PyInstaller bundle."""
  if not name.endswith(".svg"):
    name = f"{name}.svg"
  return icon_path(f"controls/{name}")

