"""SRT subtitle parsing + multi-language tracks."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

# Common language tags used in filenames: movie.en.srt, movie.bs.srt
_LANG_NAMES = {
  "en": "English",
  "eng": "English",
  "bs": "Bosanski",
  "bos": "Bosanski",
  "hr": "Hrvatski",
  "sr": "Srpski",
  "srb": "Srpski",
  "cnr": "Crnogorski",
  "me": "Crnogorski",
  "de": "Deutsch",
  "ger": "Deutsch",
  "fr": "Français",
  "es": "Español",
  "it": "Italiano",
  "pt": "Português",
  "ru": "Русский",
  "tr": "Türkçe",
  "ar": "العربية",
  "zh": "中文",
  "ja": "日本語",
  "ko": "한국어",
  "nl": "Nederlands",
  "pl": "Polski",
  "cs": "Čeština",
  "sk": "Slovenčina",
  "sl": "Slovenščina",
  "hu": "Magyar",
  "ro": "Română",
  "bg": "Български",
  "mk": "Македонски",
  "sq": "Shqip",
  "uk": "Українська",
}


@dataclass
class SubtitleCue:
  start_ms: int
  end_ms: int
  text: str


@dataclass
class SubtitleTrack:
  path: str
  label: str
  lang_code: str = ""
  cues: list[SubtitleCue] = field(default_factory=list)

  @property
  def cue_count(self) -> int:
    return len(self.cues)


def language_from_filename(path: str | Path, video_stem: str | None = None) -> tuple[str, str]:
  """Return (lang_code, display_label) from subtitle filename."""
  p = Path(path)
  name = p.stem  # e.g. movie.en or movie

  code = ""
  if video_stem:
    vs = Path(video_stem).stem if "." in str(video_stem) else video_stem
    # movie.en / movie.bs.forced
    if name.lower().startswith(vs.lower() + "."):
      rest = name[len(vs) + 1 :]
      code = rest.split(".")[0].lower()
    elif name.lower() == vs.lower():
      code = ""
  if not code:
    # fallback: last dotted token if 2–3 letters
    parts = name.split(".")
    if len(parts) >= 2 and 2 <= len(parts[-1]) <= 3 and parts[-1].isalpha():
      code = parts[-1].lower()

  if code in _LANG_NAMES:
    return code, _LANG_NAMES[code]
  if code:
    return code, code.upper()
  return "", p.name


def discover_sidecar_srts(video_path: str) -> list[Path]:
  """Find matching .srt next to video: movie.srt, movie.en.srt, movie.*.srt."""
  video = Path(video_path)
  parent = video.parent
  stem = video.stem
  found: list[Path] = []
  # exact stem.srt first
  exact = parent / f"{stem}.srt"
  if exact.exists():
    found.append(exact)
  # stem.*.srt
  for path in sorted(parent.glob(f"{stem}.*.srt")):
    if path not in found:
      found.append(path)
  return found


def parse_srt(path: str) -> list[SubtitleCue]:
  raw = Path(path).read_text(encoding="utf-8-sig", errors="replace")
  blocks = re.split(r"\n\s*\n", raw.strip(), flags=re.MULTILINE)
  cues: list[SubtitleCue] = []
  time_re = re.compile(
      r"(\d{1,2}):(\d{2}):(\d{2})[,.](\d{1,3})\s*-->\s*"
      r"(\d{1,2}):(\d{2}):(\d{2})[,.](\d{1,3})"
  )

  def to_ms(h, m, s, ms):
    ms = ms.ljust(3, "0")[:3]
    return (int(h) * 3600 + int(m) * 60 + int(s)) * 1000 + int(ms)

  for block in blocks:
    lines = [ln.strip("\ufeff") for ln in block.strip().splitlines() if ln.strip()]
    if len(lines) < 2:
      continue
    time_line = lines[0] if "-->" in lines[0] else (lines[1] if len(lines) > 1 else "")
    match = time_re.search(time_line)
    if not match:
      continue
    start = to_ms(*match.groups()[:4])
    end = to_ms(*match.groups()[4:])
    text_lines = lines[1:] if "-->" in lines[0] else lines[2:]
    text = "\n".join(text_lines).replace("<br>", "\n").replace("<br/>", "\n")
    text = re.sub(r"<[^>]+>", "", text)
    if text:
      cues.append(SubtitleCue(start, end, text))
  return cues


def load_track(path: str, video_stem: str | None = None) -> SubtitleTrack:
  code, label = language_from_filename(path, video_stem)
  cues = parse_srt(path)
  if not code and label == Path(path).name:
    label = "Default"
  display = f"{label}" if code or label == "Default" else Path(path).name
  return SubtitleTrack(path=path, label=display, lang_code=code, cues=cues)


def format_time(ms: int) -> str:
  if ms < 0:
    ms = 0
  total_sec = ms // 1000
  h, rem = divmod(total_sec, 3600)
  m, s = divmod(rem, 60)
  if h:
    return f"{h}:{m:02d}:{s:02d}"
  return f"{m:02d}:{s:02d}"
