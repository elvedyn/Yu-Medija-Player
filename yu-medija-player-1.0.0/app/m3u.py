"""M3U / M3U8 playlist parsing (local file or remote URL)."""

from __future__ import annotations

import re
import urllib.error
import urllib.request
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path

_HTTP_UA = "VLC/3.0.21 LibVLC/3.0.21"

_GROUP_ATTR_RE = re.compile(r'group-title\s*=\s*"([^"]*)"', re.I)
_TVG_NAME_RE = re.compile(r'tvg-name\s*=\s*"([^"]*)"', re.I)


@dataclass(frozen=True)
class PlaylistEntry:
  title: str
  url: str
  group: str


def _decode_bytes(data: bytes) -> str:
  for enc in ("utf-8-sig", "utf-8", "latin-1"):
    try:
      return data.decode(enc)
    except UnicodeDecodeError:
      continue
  return data.decode("utf-8", errors="replace")


def fetch_text(source: str, timeout: float = 25.0) -> str:
  """Load playlist text from a local path or http(s) URL."""
  raw = source.strip()
  if raw.startswith(("http://", "https://")):
    req = urllib.request.Request(
        raw,
        headers={"User-Agent": _HTTP_UA},
        method="GET",
    )
    try:
      with urllib.request.urlopen(req, timeout=timeout) as resp:
        return _decode_bytes(resp.read())
    except urllib.error.URLError as exc:
      raise RuntimeError(f"Could not fetch playlist:\n{exc.reason}") from exc
  path = Path(raw).expanduser()
  if not path.is_file():
    raise RuntimeError(f"Playlist not found:\n{path}")
  return _decode_bytes(path.read_bytes())


def parse_m3u(text: str) -> list[PlaylistEntry]:
  entries: list[PlaylistEntry] = []
  pending_title = ""
  pending_group = "Other"
  extgrp = "Other"

  for raw_line in text.splitlines():
    line = raw_line.strip()
    if not line:
      continue
    if line.startswith("#EXTM3U"):
      continue
    if line.upper().startswith("#EXTGRP:"):
      extgrp = line.split(":", 1)[1].strip() or "Other"
      pending_group = extgrp
      continue
    if line.startswith("#EXTINF:"):
      # #EXTINF:-1 tvg-id="..." group-title="Sport",Channel Name
      meta = line[8:]  # after #EXTINF:
      comma = meta.find(",")
      attrs = meta if comma < 0 else meta[:comma]
      title = (meta[comma + 1 :] if comma >= 0 else "").strip()
      gmatch = _GROUP_ATTR_RE.search(attrs)
      if gmatch:
        pending_group = gmatch.group(1).strip() or "Other"
      else:
        pending_group = extgrp or "Other"
      if not title:
        nmatch = _TVG_NAME_RE.search(attrs)
        title = nmatch.group(1).strip() if nmatch else "Untitled"
      pending_title = title
      continue
    if line.startswith("#"):
      continue

    url = line
    title = pending_title or url.rsplit("/", 1)[-1] or "Stream"
    group = pending_group or "Other"
    entries.append(PlaylistEntry(title=title, url=url, group=group))
    pending_title = ""
    pending_group = extgrp or "Other"

  return entries


def load_playlist(source: str) -> list[PlaylistEntry]:
  return parse_m3u(fetch_text(source))


def group_entries(entries: list[PlaylistEntry]) -> OrderedDict[str, list[PlaylistEntry]]:
  """Preserve first-seen category order, Other last if present."""
  groups: OrderedDict[str, list[PlaylistEntry]] = OrderedDict()
  other: list[PlaylistEntry] = []
  for entry in entries:
    g = entry.group.strip() or "Other"
    if g.lower() == "other":
      other.append(entry)
      continue
    groups.setdefault(g, []).append(entry)
  if other:
    groups["Other"] = other
  return groups


def looks_like_playlist_url(url: str) -> bool:
  u = url.strip().lower()
  if u.endswith((".m3u", ".m3u8")):
    return True
  return "m3u" in u and ("playlist" in u or "get.php" in u or "type=m3u" in u)
