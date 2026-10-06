"""Background update check against https://yumedija.com/version.json."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from PyQt6.QtCore import QObject, QThread, pyqtSignal

DEFAULT_UPDATE_URL = "https://yumedija.com/version.json"


@dataclass(frozen=True)
class UpdateInfo:
  version: str
  released: str = ""
  notes: str = ""
  url: str = "https://yumedija.com/#download"
  downloads: dict[str, str] | None = None


def parse_version(v: str) -> tuple[int, ...]:
  parts: list[int] = []
  for chunk in (v or "").strip().lstrip("vV").split("."):
    num = ""
    for ch in chunk:
      if ch.isdigit():
        num += ch
      else:
        break
    parts.append(int(num) if num else 0)
  return tuple(parts) if parts else (0,)


def is_newer(remote: str, local: str) -> bool:
  return parse_version(remote) > parse_version(local)


def fetch_update_info(url: str = DEFAULT_UPDATE_URL, timeout: float = 6.0) -> UpdateInfo:
  req = urllib.request.Request(url, headers={"User-Agent": "YuMedijaPlayer/1.0"})
  with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
    raw = resp.read().decode("utf-8", errors="replace")
  data: dict[str, Any] = json.loads(raw)
  ver = str(data.get("version") or "").strip()
  if not ver:
    raise ValueError("version.json missing version")
  downloads = data.get("downloads") if isinstance(data.get("downloads"), dict) else {}
  return UpdateInfo(
      version=ver,
      released=str(data.get("released") or ""),
      notes=str(data.get("notes") or ""),
      url=str(data.get("url") or "https://yumedija.com/#download"),
      downloads={str(k): str(v) for k, v in downloads.items()},
  )


class UpdateCheckWorker(QThread):
  finished_ok = pyqtSignal(object)  # UpdateInfo
  failed = pyqtSignal(str)

  def __init__(self, url: str = DEFAULT_UPDATE_URL, parent: QObject | None = None):
    super().__init__(parent)
    self.url = url

  def run(self) -> None:
    try:
      info = fetch_update_info(self.url)
      self.finished_ok.emit(info)
    except (urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError, OSError) as exc:
      self.failed.emit(str(exc))
    except Exception as exc:  # noqa: BLE001
      self.failed.emit(str(exc))
