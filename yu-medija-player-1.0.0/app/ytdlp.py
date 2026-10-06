"""Thin wrapper around system yt-dlp (no Python package dependency)."""

from __future__ import annotations

import hashlib
import shutil
import subprocess
from pathlib import Path

# QMediaPlayer needs one muxed file — YouTube often only offers separate DASH
# streams, so we fall back to a short cache download + ffmpeg merge via yt-dlp.

# Prefer a single muxed file (progressive). Avoid bv+ba for -g (two URLs).
_PLAY_FORMATS = (
    "b",
    "best",
    "18/22/17",
)

# For cache download / merge
_DOWNLOAD_FORMAT = "bv*[height<=1080]+ba/b"


class YtDlpError(RuntimeError):
  pass


def _cache_dir() -> Path:
  """Platform cache dir for yt-dlp stream merges (never a bare ~/.cache)."""
  import os
  import sys
  import tempfile

  candidates: list[Path] = []
  if sys.platform == "win32":
    base = Path(os.environ.get("LOCALAPPDATA") or (Path.home() / "AppData" / "Local"))
    candidates.append(base / "YuMedijaPlayer" / "cache" / "streams")
  elif sys.platform == "darwin":
    candidates.append(Path.home() / "Library" / "Caches" / "YuMedijaPlayer" / "streams")
  else:
    xdg = os.environ.get("XDG_CACHE_HOME")
    root = Path(xdg) if xdg else (Path.home() / ".cache")
    candidates.append(root / "yu-medija-player" / "streams")

  try:
    from PyQt6.QtCore import QStandardPaths

    loc = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.CacheLocation)
    if loc:
      p = Path(loc)
      # Generic cache root → nest under our app id
      if p.name.lower() in {"cache", ".cache"}:
        p = p / "yu-medija-player"
      candidates.append(p / "streams")
  except Exception:
    pass

  candidates.append(Path(tempfile.gettempdir()) / "yu-medija-player-streams")
  for preferred in candidates:
    try:
      preferred.mkdir(parents=True, exist_ok=True)
      return preferred
    except OSError:
      continue
  return candidates[-1]


def _tool_search_dirs() -> list[Path]:
  import sys
  dirs: list[Path] = []
  if getattr(sys, "frozen", False):
    exe = Path(sys.executable).resolve()
    dirs.append(exe.parent)
    # macOS .app/Contents/MacOS → Resources / Frameworks / tools
    if exe.parent.name == "MacOS":
      contents = exe.parent.parent
      dirs.extend([contents / "Resources", contents / "Frameworks", contents / "MacOS" / "tools"])
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
      dirs.append(Path(meipass))
  try:
    from app.resources import app_root
    root = app_root()
  except Exception:
    root = Path(__file__).resolve().parent.parent
  dirs.extend([root, root / "tools", root / "bin", root / "libmpv"])
  out: list[Path] = []
  seen: set[str] = set()
  for d in dirs:
    key = str(d)
    if key not in seen:
      seen.add(key)
      out.append(d)
  return out


def find_ytdlp() -> str | None:
  names = ("yt-dlp", "yt-dlp.exe", "youtube-dl", "youtube-dl.exe")
  for folder in _tool_search_dirs():
    for name in names:
      cand = folder / name
      if cand.is_file():
        return str(cand)
  candidates: list[str] = []
  for name in names:
    path = shutil.which(name)
    if path:
      candidates.append(path)
  for extra in (
      Path.home() / ".local" / "bin" / "yt-dlp",
      Path("/usr/local/bin/yt-dlp"),
  ):
    if extra.is_file() and str(extra) not in candidates:
      candidates.insert(0, str(extra))
  return candidates[0] if candidates else None


def missing_ytdlp_message() -> str:
  return (
      "yt-dlp was not found.\n\n"
      "Install it, or place yt-dlp / yt-dlp.exe next to the app (or in a tools/ folder).\n\n"
      "• https://github.com/yt-dlp/yt-dlp/releases\n"
      "• Linux: sudo apt install yt-dlp   or   pipx install yt-dlp\n"
      "• macOS: brew install yt-dlp"
  )


def _require_bin() -> str:
  path = find_ytdlp()
  if not path:
    raise YtDlpError(missing_ytdlp_message())
  return path


def is_youtube_url(url: str) -> bool:
  u = (url or "").strip().lower()
  if not u.startswith(("http://", "https://")):
    return False
  try:
    from urllib.parse import urlparse
    host = (urlparse(u).hostname or "").lower()
  except Exception:
    return False
  return (
      host in (
          "youtube.com",
          "www.youtube.com",
          "m.youtube.com",
          "youtu.be",
          "music.youtube.com",
      )
      or host.endswith(".youtube.com")
  )


def needs_ytdlp(url: str) -> bool:
  """True when QMediaPlayer likely cannot open the URL directly."""
  u = url.strip().lower()
  if not u.startswith(("http://", "https://")):
    return False
  if any(u.split("?", 1)[0].endswith(ext) for ext in (
      ".mp4", ".mkv", ".webm", ".mov", ".m4v", ".mp3", ".aac", ".flac",
      ".ts", ".m3u8",
  )):
    return False
  if is_youtube_url(u):
    return True
  hosts = (
      "vimeo.com", "dailymotion.com", "twitch.tv", "facebook.com",
      "instagram.com", "tiktok.com", "twitter.com", "x.com",
      "reddit.com", "soundcloud.com",
  )
  try:
    from urllib.parse import urlparse
    host = urlparse(u).hostname or ""
  except Exception:
    host = ""
  if any(host == h or host.endswith("." + h) for h in hosts):
    return True
  if "/watch" in u or "v=" in u:
    return True
  return False


def _run(cmd: list[str], timeout: float | None) -> subprocess.CompletedProcess[str]:
  try:
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
  except subprocess.TimeoutExpired as exc:
    raise YtDlpError("yt-dlp timed out.") from exc
  except OSError as exc:
    raise YtDlpError(f"Could not run yt-dlp: {exc}") from exc


def _get_direct_urls(bin_path: str, url: str, fmt: str, timeout: float) -> list[str]:
  cmd = [
      bin_path,
      "-f", fmt,
      "-g",
      "--no-playlist",
      "--no-warnings",
      url.strip(),
  ]
  proc = _run(cmd, timeout)
  if proc.returncode != 0:
    return []
  return [ln.strip() for ln in (proc.stdout or "").splitlines() if ln.strip().startswith("http")]


def _cache_key(url: str) -> str:
  return hashlib.sha1(url.strip().encode("utf-8")).hexdigest()[:16]


def _download_for_play(bin_path: str, url: str, timeout: float) -> str:
  """Download + merge into cache; return local file path."""
  cache = _cache_dir()
  key = _cache_key(url)
  # Reuse existing cache hit
  for existing in cache.glob(f"{key}.*"):
    if existing.is_file() and existing.stat().st_size > 1024:
      return str(existing)

  outtmpl = str(cache / f"{key}.%(ext)s")
  cmd = [
      bin_path,
      "-f", _DOWNLOAD_FORMAT,
      "--no-playlist",
      "--no-warnings",
      "--merge-output-format", "mp4",
      "-o", outtmpl,
      "--print", "after_move:filepath",
      url.strip(),
  ]
  proc = _run(cmd, timeout if timeout > 0 else None)
  if proc.returncode != 0:
    # Retry without merge-output-format (webm ok)
    cmd = [
        bin_path,
        "-f", _DOWNLOAD_FORMAT,
        "--no-playlist",
        "--no-warnings",
        "-o", outtmpl,
        "--print", "after_move:filepath",
        url.strip(),
    ]
    proc = _run(cmd, timeout if timeout > 0 else None)
  printed = [ln.strip() for ln in (proc.stdout or "").splitlines() if ln.strip()]
  if proc.returncode != 0:
    err = (proc.stderr or "").strip() or "Download failed."
    hint = ""
    if "format is not available" in err.lower() or "player response" in err.lower():
      hint = (
          "\n\nTip: update yt-dlp:\n"
          "  sudo apt update && sudo apt install yt-dlp\n"
          "  or:  pipx upgrade yt-dlp"
      )
    raise YtDlpError(f"yt-dlp failed:\n{err}{hint}")

  for line in reversed(printed):
    p = Path(line)
    if p.is_file():
      return str(p)
  for existing in sorted(cache.glob(f"{key}.*"), key=lambda p: p.stat().st_mtime, reverse=True):
    if existing.is_file() and existing.stat().st_size > 1024:
      return str(existing)
  raise YtDlpError("yt-dlp finished but no output file was found.")


def resolve_play_url(url: str, timeout: float = 180.0) -> str:
  """
  Return a playable source for QMediaPlayer: direct http(s) URL or local path.
  YouTube often has no progressive formats — then we cache a merged file.
  """
  bin_path = _require_bin()
  url = url.strip()

  for fmt in _PLAY_FORMATS:
    lines = _get_direct_urls(bin_path, url, fmt, min(timeout, 60.0))
    # Exactly one URL = muxed progressive stream QMediaPlayer can play
    if len(lines) == 1:
      return lines[0]

  # Separate DASH A/V (or format missing) → download & merge locally
  return _download_for_play(bin_path, url, timeout)


def download(url: str, dest_dir: str, timeout: float = 0) -> str:
  """Download with yt-dlp into dest_dir. Returns the destination directory."""
  bin_path = _require_bin()
  out_dir = Path(dest_dir).expanduser()
  out_dir.mkdir(parents=True, exist_ok=True)
  outtmpl = str(out_dir / "%(title).200B [%(id)s].%(ext)s")
  cmd = [
      bin_path,
      "-f", _DOWNLOAD_FORMAT,
      "--no-playlist",
      "--no-warnings",
      "--merge-output-format", "mp4",
      "-o", outtmpl,
      url.strip(),
  ]
  proc = _run(cmd, timeout if timeout > 0 else None)
  if proc.returncode != 0:
    # Fallback without forced mp4 merge
    cmd = [
        bin_path,
        "-f", _DOWNLOAD_FORMAT,
        "--no-playlist",
        "--no-warnings",
        "-o", outtmpl,
        url.strip(),
    ]
    proc = _run(cmd, timeout if timeout > 0 else None)
  if proc.returncode != 0:
    err = (proc.stderr or "").strip() or "Download failed."
    raise YtDlpError(f"yt-dlp download failed:\n{err}")
  return str(out_dir)
