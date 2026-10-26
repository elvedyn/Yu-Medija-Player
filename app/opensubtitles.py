"""OpenSubtitles.com REST API client (stdlib only)."""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from app import APP_NAME, __version__

API_BASE = "https://api.opensubtitles.com/api/v1"
USER_AGENT = f"{APP_NAME} v{__version__}"

# Strip common release tags from filenames for better search
_TAG_RE = re.compile(
    r"\b("
    r"480p|720p|1080p|2160p|4k|8k|hdr|dv|sdr|"
    r"bluray|blu-ray|bdrip|brrip|webrip|web-dl|webdl|hdtv|dvdrip|hdrip|"
    r"x264|x265|h264|h265|hevc|avc|aac|ac3|dts|truehd|"
    r"yify|yts|rarbg|ettv|eztv|sparks|amiable|ntb|flix|"
    r"proper|repack|extended|unrated|directors\.cut|remux"
    r")\b",
    re.I,
)


@dataclass
class SubtitleHit:
  file_id: int
  title: str
  language: str
  hearing_impaired: bool
  download_count: int
  rating: float
  release: str
  movie_name: str


def query_from_video_path(path: str | None) -> str:
  if not path:
    return ""
  name = Path(path).stem
  name = name.replace(".", " ").replace("_", " ").replace("-", " ")
  name = _TAG_RE.sub(" ", name)
  name = re.sub(r"\s+", " ", name).strip()
  # Drop trailing season/episode noise like S01E02 keep it — useful for search
  return name


def _request(
    method: str,
    path: str,
    api_key: str,
    body: dict | None = None,
    params: dict | None = None,
) -> dict:
  if not api_key.strip():
    raise RuntimeError(
        "OpenSubtitles API key missing.\n"
        "Get a free key at https://www.opensubtitles.com/en/consumers\n"
        "then paste it in Settings → Subtitles."
    )
  url = f"{API_BASE}{path}"
  if params:
    url += "?" + urllib.parse.urlencode(params, doseq=True)
  data = None
  headers = {
      "Api-Key": api_key.strip(),
      "User-Agent": USER_AGENT,
      "Accept": "application/json",
      "Content-Type": "application/json",
  }
  if body is not None:
    data = json.dumps(body).encode("utf-8")
  req = urllib.request.Request(url, data=data, headers=headers, method=method)
  try:
    with urllib.request.urlopen(req, timeout=25) as resp:
      raw = resp.read().decode("utf-8", errors="replace")
      return json.loads(raw) if raw else {}
  except urllib.error.HTTPError as exc:
    detail = exc.read().decode("utf-8", errors="replace")
    try:
      payload = json.loads(detail)
      msg = payload.get("message") or payload.get("error") or detail
    except json.JSONDecodeError:
      msg = detail or str(exc)
    raise RuntimeError(f"OpenSubtitles HTTP {exc.code}: {msg}") from exc
  except urllib.error.URLError as exc:
    raise RuntimeError(f"Network error: {exc.reason}") from exc


def search_subtitles(
    api_key: str,
    query: str,
    languages: str = "en",
    page: int = 1,
) -> list[SubtitleHit]:
  query = query.strip()
  if not query:
    return []
  params = {
      "query": query,
      "languages": languages.replace(" ", ""),
      "page": str(page),
      "order_by": "download_count",
      "order_direction": "desc",
  }
  payload = _request("GET", "/subtitles", api_key, params=params)
  hits: list[SubtitleHit] = []
  for item in payload.get("data") or []:
    attrs = item.get("attributes") or {}
    files = attrs.get("files") or []
    if not files:
      continue
    file_id = files[0].get("file_id")
    if not file_id:
      continue
    feature = attrs.get("feature_details") or {}
    hits.append(
        SubtitleHit(
            file_id=int(file_id),
            title=str(attrs.get("release") or files[0].get("file_name") or query),
            language=str(attrs.get("language") or ""),
            hearing_impaired=bool(attrs.get("hearing_impaired")),
            download_count=int(attrs.get("download_count") or 0),
            rating=float(attrs.get("ratings") or 0),
            release=str(attrs.get("release") or ""),
            movie_name=str(
                feature.get("title")
                or feature.get("movie_name")
                or attrs.get("feature_details", {}).get("parent_title")
                or ""
            ),
        )
    )
  return hits


def download_subtitle(api_key: str, file_id: int, dest_path: str) -> str:
  payload = _request("POST", "/download", api_key, body={"file_id": int(file_id)})
  link = payload.get("link")
  if not link:
    raise RuntimeError("Download link missing from OpenSubtitles response.")
  req = urllib.request.Request(
      link,
      headers={"User-Agent": USER_AGENT},
      method="GET",
  )
  with urllib.request.urlopen(req, timeout=40) as resp:
    data = resp.read()
  dest = Path(dest_path)
  dest.parent.mkdir(parents=True, exist_ok=True)
  dest.write_bytes(data)
  return str(dest)
