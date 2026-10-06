"""Non-fatal global exception hooks for GUI apps (avoid silent abort)."""

from __future__ import annotations

import logging
import sys
import threading
import traceback
from typing import Any

_LOG = logging.getLogger("yu-medija-player")


def install_exception_hooks(parent_getter=None) -> None:
  """Install sys.excepthook + threading.excepthook that log and optionally alert."""

  def _report(exc_type, exc, tb, thread_name: str | None = None) -> None:
    text = "".join(traceback.format_exception(exc_type, exc, tb))
    _LOG.error("Unhandled exception%s:\n%s", f" in {thread_name}" if thread_name else "", text)
    try:
      from PyQt6.QtWidgets import QApplication, QMessageBox

      app = QApplication.instance()
      if app is None:
        return
      parent = parent_getter() if callable(parent_getter) else None
      summary = f"{exc_type.__name__}: {exc}"
      if thread_name:
        summary = f"[{thread_name}] {summary}"
      QMessageBox.warning(
          parent,
          "Yu Medija Player",
          "Something went wrong, but the player will keep running.\n\n"
          f"{summary}\n\n"
          "Details were written to the log / console.",
      )
    except Exception:
      pass

  def _sys_hook(exc_type, exc, tb):
    if issubclass(exc_type, KeyboardInterrupt):
      sys.__excepthook__(exc_type, exc, tb)
      return
    _report(exc_type, exc, tb)

  def _thread_hook(args: Any):
    # threading.ExceptHookArgs in 3.8+
    _report(args.exc_type, args.exc_value, args.exc_traceback, getattr(args.thread, "name", None))

  sys.excepthook = _sys_hook
  if hasattr(threading, "excepthook"):
    threading.excepthook = _thread_hook  # type: ignore[assignment]


def configure_logging() -> None:
  logging.basicConfig(
      level=logging.INFO,
      format="%(asctime)s %(levelname)s %(name)s: %(message)s",
  )
