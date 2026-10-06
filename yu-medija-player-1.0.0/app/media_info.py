"""Duration helpers — MKV/Qt often report 0 until probed."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

# IPTV / VOD servers often block default ffprobe UA
_HTTP_UA = "VLC/3.0.21 LibVLC/3.0.21"

def find_ffprobe() -> str | None:
  """Locate ffprobe on PATH, next to the frozen exe, or under the app root."""
  for name in ("ffprobe", "ffprobe.exe"):
    found = shutil.which(name)
    if found:
      return found
  import sys

  bases: list[Path] = []
  if getattr(sys, "frozen", False):
    exe = Path(sys.executable).resolve()
    bases.append(exe.parent)
    if exe.parent.name == "MacOS":
      contents = exe.parent.parent
      bases.extend([contents / "Resources", contents / "MacOS" / "tools", contents / "Frameworks"])
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
      bases.append(Path(meipass))
  try:
    from app.resources import app_root

    root = app_root()
    bases.extend([root, root / "tools", root / "bin"])
  except Exception:
    bases.append(Path(__file__).resolve().parent.parent)
  for base in bases:
    for name in ("ffprobe.exe", "ffprobe", "ffmpeg.exe", "ffmpeg"):
      cand = base / name
      if cand.is_file():
        # Prefer real ffprobe; ffmpeg is last-resort for duration only
        if name.startswith("ffprobe"):
          return str(cand)
  # ffmpeg-named fallbacks (duration via ffmpeg -i)
  for base in bases:
    for name in ("ffmpeg.exe", "ffmpeg"):
      cand = base / name
      if cand.is_file():
        return str(cand)
  return None


def find_ffmpeg() -> str | None:
  for name in ("ffmpeg", "ffmpeg.exe"):
    found = shutil.which(name)
    if found:
      return found
  probe = find_ffprobe()
  if probe and Path(probe).name.lower().startswith("ffmpeg"):
    return probe
  import sys

  bases: list[Path] = []
  if getattr(sys, "frozen", False):
    bases.append(Path(sys.executable).resolve().parent)
  try:
    from app.resources import app_root

    bases.append(app_root())
  except Exception:
    pass
  for base in bases:
    for name in ("ffmpeg.exe", "ffmpeg"):
      cand = base / name
      if cand.is_file():
        return str(cand)
  return None


# Text-based subtitle codecs we can extract to SRT (avoids Qt crash on track switch)
_TEXT_SUB_CODECS = {
    "subrip",
    "srt",
    "ass",
    "ssa",
    "webvtt",
    "mov_text",
    "text",
    "timed_text",
    "ttml",
    "dvb_teletext",
    "arib_caption",
}


def _is_remote(path: str) -> bool:
  return path.startswith(("http://", "https://"))


def _http_header_block(referer: str | None) -> str | None:
  if not referer:
    return None
  ref = referer.strip()
  if not ref:
    return None
  return f"Referer: {ref}\r\n"


def probe_duration_ms(path: str, referer: str | None = None) -> int:
  """Return media duration in ms, or 0 if unavailable (local file or http URL)."""
  if not path:
    return 0
  if not _is_remote(path) and not Path(path).is_file():
    return 0
  for probe in (_ffprobe_duration_ms, _gst_discoverer_duration_ms):
    if _is_remote(path) and probe is _gst_discoverer_duration_ms:
      continue
    if probe is _ffprobe_duration_ms:
      ms = probe(path, referer=referer)
    else:
      ms = probe(path)
    if ms > 0:
      return ms
  return 0


def _ffprobe_streams(path: str, referer: str | None = None) -> list[dict]:
  ffprobe = find_ffprobe()
  if not ffprobe or not Path(ffprobe).name.lower().startswith("ffprobe"):
    return []
  remote = _is_remote(path)
  cmd = [
      ffprobe,
      "-v",
      "error",
      "-show_entries",
      "stream=index,codec_type,codec_name:stream_tags=language,title,handler_name",
      "-of",
      "json",
  ]
  if remote:
    cmd.extend(["-user_agent", _HTTP_UA, "-analyzeduration", "30M", "-probesize", "30M"])
    header = _http_header_block(referer)
    if header:
      cmd.extend(["-headers", header])
  cmd.append(path)
  try:
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=45 if remote else 15,
        check=False,
    )
  except (OSError, subprocess.TimeoutExpired):
    return []
  if result.returncode != 0 or not (result.stdout or "").strip():
    return []
  try:
    data = json.loads(result.stdout)
  except json.JSONDecodeError:
    return []
  return list(data.get("streams") or [])


def probe_stream_languages(path: str, referer: str | None = None) -> dict[str, list[str]]:
  """
  Return language tags from the container via ffprobe.
  Keys: 'audio', 'subtitle' — values are lists aligned with stream order
  of that codec type (best-effort).
  """
  empty: dict[str, list[str]] = {"audio": [], "subtitle": []}
  if not path:
    return empty
  if not _is_remote(path) and not Path(path).is_file():
    return empty

  out: dict[str, list[str]] = {"audio": [], "subtitle": []}
  for stream in _ffprobe_streams(path, referer=referer):
    codec_type = str(stream.get("codec_type") or "")
    if codec_type not in ("audio", "subtitle"):
      continue
    tags = stream.get("tags") or {}
    lang = str(tags.get("language") or "").strip()
    title = str(tags.get("title") or tags.get("handler_name") or "").strip()
    if lang and lang.lower() not in ("und", "unk", "unknown"):
      label = lang if not title else f"{lang}|{title}"
    elif title:
      label = f"|{title}"
    else:
      label = ""
    out[codec_type].append(label)
  return out


def list_subtitle_streams(path: str, referer: str | None = None) -> list[dict]:
  """
  Subtitle streams in file/URL order (same order as Qt subtitleTracks()).
  Each dict: stream_index, subtitle_ordinal, codec, language, title, text.
  """
  if not path:
    return []
  if not _is_remote(path) and not Path(path).is_file():
    return []
  out: list[dict] = []
  ordinal = 0
  for stream in _ffprobe_streams(path, referer=referer):
    if str(stream.get("codec_type") or "") != "subtitle":
      continue
    codec = str(stream.get("codec_name") or "").lower()
    tags = stream.get("tags") or {}
    try:
      idx = int(stream.get("index"))
    except (TypeError, ValueError):
      continue
    out.append(
        {
            "stream_index": idx,
            "subtitle_ordinal": ordinal,
            "codec": codec,
            "language": str(tags.get("language") or "").strip(),
            "title": str(tags.get("title") or tags.get("handler_name") or "").strip(),
            # Unknown codec: still try extract (better than freeze)
            "text": codec in _TEXT_SUB_CODECS or not codec,
        }
    )
    ordinal += 1
  return out


def _ffmpeg_input_args(path: str, referer: str | None = None) -> list[str]:
  args: list[str] = []
  if _is_remote(path):
    args.extend(["-user_agent", _HTTP_UA, "-analyzeduration", "50M", "-probesize", "50M"])
    header = _http_header_block(referer)
    if header:
      args.extend(["-headers", header])
  return args


def extract_subtitle_to_srt(
    path: str,
    stream_index: int | None,
    dest_path: str,
    referer: str | None = None,
    subtitle_ordinal: int | None = None,
) -> str:
  """
  Extract one subtitle stream to an SRT file via ffmpeg (local path or http URL).
  Prefer container stream_index; fall back to 0:s:ordinal (Qt menu order).
  """
  ffmpeg = shutil.which("ffmpeg")
  if not ffmpeg:
    raise RuntimeError("ffmpeg not found — install: sudo apt install ffmpeg")
  dest = Path(dest_path)
  dest.parent.mkdir(parents=True, exist_ok=True)
  if dest.is_file():
    try:
      dest.unlink()
    except OSError:
      pass

  if stream_index is not None:
    map_spec = f"0:{stream_index}"
  elif subtitle_ordinal is not None:
    map_spec = f"0:s:{subtitle_ordinal}"
  else:
    raise RuntimeError("No subtitle stream selected")

  codec = ""
  if stream_index is not None:
    for stream in _ffprobe_streams(path, referer=referer):
      try:
        if int(stream.get("index")) == stream_index:
          codec = str(stream.get("codec_name") or "").lower()
          break
      except (TypeError, ValueError):
        continue
  sub_codec = "copy" if codec in ("subrip", "srt") else "srt"
  remote = _is_remote(path)
  timeout = 300 if remote else 180

  def _run(codec_flag: str) -> subprocess.CompletedProcess[str]:
    cmd = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        *_ffmpeg_input_args(path, referer),
        "-i",
        path,
        "-map",
        map_spec,
        "-c:s",
        codec_flag,
        "-vn",
        "-an",
        str(dest),
    ]
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )

  try:
    result = _run(sub_codec)
  except subprocess.TimeoutExpired as exc:
    raise RuntimeError("Subtitle extract timed out") from exc
  except OSError as exc:
    raise RuntimeError(f"Could not run ffmpeg: {exc}") from exc

  if result.returncode != 0 or not dest.is_file() or dest.stat().st_size < 8:
    if sub_codec == "copy":
      try:
        if dest.is_file():
          dest.unlink()
      except OSError:
        pass
      try:
        result = _run("srt")
      except subprocess.TimeoutExpired as exc:
        raise RuntimeError("Subtitle extract timed out") from exc
    if result.returncode != 0 or not dest.is_file() or dest.stat().st_size < 8:
      if stream_index is not None and subtitle_ordinal is not None:
        return extract_subtitle_to_srt(
            path,
            None,
            str(dest),
            referer=referer,
            subtitle_ordinal=subtitle_ordinal,
        )
      err = (result.stderr or result.stdout or "extract failed").strip()
      raise RuntimeError(err[:240] or "Could not extract subtitle track")
  return str(dest)


def _parse_duration_seconds(text: str) -> float:
  text = (text or "").strip()
  if not text or text.upper() == "N/A":
    return 0.0
  try:
    return float(text.splitlines()[0].strip())
  except ValueError:
    return 0.0


def _parse_ffmpeg_stderr_duration(text: str) -> float:
  # Duration: 01:23:45.67
  match = re.search(
      r"Duration:\s*(\d+):(\d{2}):(\d{2})\.(\d+)",
      text or "",
  )
  if not match:
    return 0.0
  hours, minutes, seconds = int(match.group(1)), int(match.group(2)), int(match.group(3))
  frac = match.group(4)[:3].ljust(3, "0")
  return hours * 3600 + minutes * 60 + seconds + int(frac) / 1000.0


def _ffprobe_duration_ms(path: str, referer: str | None = None) -> int:
  """Return 0 when ffprobe/ffmpeg are missing — caller falls back to mpv duration."""
  raw = find_ffprobe()
  ffprobe = raw if raw and Path(raw).name.lower().startswith("ffprobe") else None
  ffmpeg = find_ffmpeg() if not ffprobe else (find_ffmpeg() or None)
  if not ffprobe:
    ffmpeg = find_ffmpeg()
  if not ffprobe and not ffmpeg:
    return 0

  remote = _is_remote(path)
  timeout = 30 if remote else 12
  user_agents = [_HTTP_UA, "Mozilla/5.0", "YuMedijaPlayer/1.0"] if remote else [_HTTP_UA]
  header_block = _http_header_block(referer) if remote else None

  if ffprobe:
    for ua in user_agents:
      cmd = [
          ffprobe,
          "-v",
          "error",
          "-show_entries",
          "format=duration",
          "-of",
          "default=noprint_wrappers=1:nokey=1",
      ]
      if remote:
        cmd.extend(
            [
                "-user_agent",
                ua,
                "-analyzeduration",
                "50M",
                "-probesize",
                "50M",
                "-rw_timeout",
                "20000000",
            ]
        )
        if header_block:
          cmd.extend(["-headers", header_block])
      cmd.append(path)
      try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        seconds = _parse_duration_seconds(result.stdout)
        if seconds > 0:
          return int(seconds * 1000)
      except (OSError, ValueError, subprocess.TimeoutExpired):
        continue

  # Fallback: ffmpeg -i prints Duration on stderr even when stdout is empty
  if ffmpeg:
    for ua in user_agents[:1]:
      cmd = [ffmpeg, "-hide_banner"]
      if remote:
        cmd.extend(["-user_agent", ua, "-analyzeduration", "50M", "-probesize", "50M"])
        if header_block:
          cmd.extend(["-headers", header_block])
      cmd.extend(["-i", path])
      try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        seconds = _parse_ffmpeg_stderr_duration(result.stderr)
        if seconds > 0:
          return int(seconds * 1000)
      except (OSError, ValueError, subprocess.TimeoutExpired):
        continue
  return 0


def _gst_discoverer_duration_ms(path: str) -> int:
  tool = shutil.which("gst-discoverer-1.0")
  if not tool:
    return 0
  try:
    result = subprocess.run(
        [tool, "-v", path],
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    text = (result.stdout or "") + (result.stderr or "")
    match = re.search(
        r"Duration:\s*(?:(\d+):)?(\d{1,2}):(\d{2})\.(\d+)",
        text,
    )
    if not match:
      return 0
    hours = int(match.group(1) or 0)
    minutes = int(match.group(2))
    seconds = int(match.group(3))
    frac = match.group(4)[:3].ljust(3, "0")
    return ((hours * 3600 + minutes * 60 + seconds) * 1000) + int(frac)
  except (OSError, ValueError, subprocess.TimeoutExpired):
    return 0
