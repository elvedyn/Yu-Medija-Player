#!/usr/bin/env python3
"""Launcher — works from project root on any OS: python3 player.py"""

from app.qt_backend import configure_linux_media_backend

configure_linux_media_backend()

from app.window import run

if __name__ == "__main__":
  raise SystemExit(run())
