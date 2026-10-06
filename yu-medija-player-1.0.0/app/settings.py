"""Persistent settings via QSettings (native per OS)."""

from __future__ import annotations

from PyQt6.QtCore import QByteArray, QSettings

from app import APP_NAME, ORG_NAME

# Previous org/app pairs — migrate once so users keep volume, theme, keys, etc.
_LEGACY_SETTINGS = (
    ("ETVideoPlayer", "ET Video Player"),
    ("LumenPlayer", "Lumen"),
    ("LumenPlayer", "ET Video Player"),
    ("FramePlayer", "Frame"),
    ("FramePlayer", "Frame Player"),
)


def _migrate_legacy_settings(dest: QSettings) -> None:
  """Copy keys from an older install if the new settings store is empty."""
  if dest.allKeys():
    return
  for org, app in _LEGACY_SETTINGS:
    src = QSettings(org, app)
    keys = src.allKeys()
    if not keys:
      continue
    for key in keys:
      dest.setValue(key, src.value(key))
    dest.sync()
    break


class AppSettings:
  def __init__(self) -> None:
    self._q = QSettings(ORG_NAME, APP_NAME)
    _migrate_legacy_settings(self._q)

  # --- playback ---
  @property
  def volume(self) -> int:
    return int(self._q.value("playback/volume", 40))

  @volume.setter
  def volume(self, value: int) -> None:
    self._q.setValue("playback/volume", max(0, min(100, int(value))))

  @property
  def remember_volume(self) -> bool:
    return self._q.value("playback/remember_volume", True, type=bool)

  @remember_volume.setter
  def remember_volume(self, value: bool) -> None:
    self._q.setValue("playback/remember_volume", bool(value))

  @property
  def seek_step_sec(self) -> int:
    return int(self._q.value("playback/seek_step_sec", 5))

  @seek_step_sec.setter
  def seek_step_sec(self, value: int) -> None:
    self._q.setValue("playback/seek_step_sec", max(1, min(60, int(value))))

  @property
  def playback_rate(self) -> float:
    return float(self._q.value("playback/rate", 1.0))

  @playback_rate.setter
  def playback_rate(self, value: float) -> None:
    self._q.setValue("playback/rate", float(value))

  # --- subtitles ---
  @property
  def auto_load_srt(self) -> bool:
    return self._q.value("subs/auto_load", True, type=bool)

  @auto_load_srt.setter
  def auto_load_srt(self, value: bool) -> None:
    self._q.setValue("subs/auto_load", bool(value))

  @property
  def subtitle_font_size(self) -> int:
    return int(self._q.value("subs/font_size", 18))

  @subtitle_font_size.setter
  def subtitle_font_size(self, value: int) -> None:
    self._q.setValue("subs/font_size", max(12, min(48, int(value))))

  @property
  def opensubtitles_api_key(self) -> str:
    return str(self._q.value("subs/opensubtitles_api_key", ""))

  @opensubtitles_api_key.setter
  def opensubtitles_api_key(self, value: str) -> None:
    self._q.setValue("subs/opensubtitles_api_key", value.strip())

  @property
  def opensubtitles_languages(self) -> str:
    return str(self._q.value("subs/opensubtitles_languages", "en"))

  @opensubtitles_languages.setter
  def opensubtitles_languages(self, value: str) -> None:
    self._q.setValue("subs/opensubtitles_languages", value.strip() or "en")

  # --- screenshots ---
  @property
  def screenshot_format(self) -> str:
    fmt = str(self._q.value("shot/format", "png")).lower()
    return fmt if fmt in {"png", "jpg"} else "png"

  @screenshot_format.setter
  def screenshot_format(self, value: str) -> None:
    self._q.setValue("shot/format", value if value in {"png", "jpg"} else "png")

  @property
  def screenshot_ask_path(self) -> bool:
    return self._q.value("shot/ask_path", True, type=bool)

  @screenshot_ask_path.setter
  def screenshot_ask_path(self, value: bool) -> None:
    self._q.setValue("shot/ask_path", bool(value))

  # --- ui ---
  @property
  def hide_controls_fullscreen(self) -> bool:
    return self._q.value("ui/hide_controls_fs", True, type=bool)

  @hide_controls_fullscreen.setter
  def hide_controls_fullscreen(self, value: bool) -> None:
    self._q.setValue("ui/hide_controls_fs", bool(value))

  @property
  def theme_id(self) -> str:
    from app.styles import DEFAULT_THEME, THEMES
    val = str(self._q.value("ui/theme", DEFAULT_THEME))
    return val if val in THEMES else DEFAULT_THEME

  @theme_id.setter
  def theme_id(self, value: str) -> None:
    self._q.setValue("ui/theme", value)

  @property
  def low_power(self) -> bool:
    """Skip non-essential UI timers (status text clear only)."""
    return self._q.value("ui/low_power", True, type=bool)

  @low_power.setter
  def low_power(self, value: bool) -> None:
    self._q.setValue("ui/low_power", bool(value))

  @property
  def aspect_mode(self) -> str:
    val = str(self._q.value("ui/aspect_mode", "fit"))
    from app.aspect import ASPECT_MODES
    ids = {m[0] for m in ASPECT_MODES}
    return val if val in ids else "fit"

  @aspect_mode.setter
  def aspect_mode(self, value: str) -> None:
    self._q.setValue("ui/aspect_mode", value)

  @property
  def last_dir(self) -> str:
    return str(self._q.value("ui/last_dir", ""))

  @last_dir.setter
  def last_dir(self, value: str) -> None:
    self._q.setValue("ui/last_dir", value)

  @property
  def geometry(self) -> QByteArray | None:
    val = self._q.value("ui/geometry")
    return val if isinstance(val, QByteArray) else None

  @geometry.setter
  def geometry(self, value: QByteArray) -> None:
    self._q.setValue("ui/geometry", value)


  @property
  def ask_download_path(self) -> bool:
    return self._q.value("download/ask_path", True, type=bool)

  @ask_download_path.setter
  def ask_download_path(self, value: bool) -> None:
    self._q.setValue("download/ask_path", bool(value))

  @property
  def repeat_mode(self) -> str:
    val = str(self._q.value("playback/repeat", "off"))
    return val if val in {"off", "one", "all"} else "off"

  @repeat_mode.setter
  def repeat_mode(self, value: str) -> None:
    self._q.setValue("playback/repeat", value if value in {"off", "one", "all"} else "off")

  @property
  def shuffle(self) -> bool:
    return self._q.value("playback/shuffle", False, type=bool)

  @shuffle.setter
  def shuffle(self, value: bool) -> None:
    self._q.setValue("playback/shuffle", bool(value))

  @property
  def autoplay_next(self) -> bool:
    return self._q.value("playback/autoplay_next", True, type=bool)

  @autoplay_next.setter
  def autoplay_next(self, value: bool) -> None:
    self._q.setValue("playback/autoplay_next", bool(value))

  @property
  def resume_playback(self) -> bool:
    return self._q.value("playback/resume", True, type=bool)

  @resume_playback.setter
  def resume_playback(self, value: bool) -> None:
    self._q.setValue("playback/resume", bool(value))

  @property
  def hardware_decoding(self) -> bool:
    return self._q.value("playback/hwdec", False, type=bool)

  @hardware_decoding.setter
  def hardware_decoding(self, value: bool) -> None:
    self._q.setValue("playback/hwdec", bool(value))

  @property
  def subtitle_delay_ms(self) -> int:
    return int(self._q.value("subs/delay_ms", 0))

  @subtitle_delay_ms.setter
  def subtitle_delay_ms(self, value: int) -> None:
    self._q.setValue("subs/delay_ms", int(value))

  @property
  def recent_items(self) -> list[str]:
    raw = self._q.value("ui/recent", [])
    if isinstance(raw, str):
      return [raw] if raw else []
    try:
      return [str(x) for x in list(raw)][:10]
    except Exception:
      return []

  @recent_items.setter
  def recent_items(self, value: list[str]) -> None:
    # Keep last 10 unique, newest first
    out: list[str] = []
    for item in value:
      s = str(item).strip()
      if not s or s in out:
        continue
      out.append(s)
      if len(out) >= 10:
        break
    self._q.setValue("ui/recent", out)

  def push_recent(self, item: str) -> None:
    s = (item or "").strip()
    if not s:
      return
    items = [s] + [x for x in self.recent_items if x != s]
    self.recent_items = items[:10]
    self.sync()

  def resume_map(self) -> dict[str, int]:
    raw = self._q.value("playback/resume_map", {})
    if not isinstance(raw, dict):
      return {}
    out: dict[str, int] = {}
    for k, v in raw.items():
      try:
        out[str(k)] = int(v)
      except (TypeError, ValueError):
        continue
    return out

  def set_resume_position(self, path: str, ms: int) -> None:
    key = str(path)
    data = self.resume_map()
    if ms <= 0:
      data.pop(key, None)
    else:
      data[key] = int(ms)
      # Cap map size
      if len(data) > 200:
        # drop arbitrary extras
        for old in list(data.keys())[:-200]:
          data.pop(old, None)
    self._q.setValue("playback/resume_map", data)

  def get_resume_position(self, path: str) -> int:
    return int(self.resume_map().get(str(path), 0) or 0)

  @property
  def check_updates_startup(self) -> bool:
    return self._q.value("ui/check_updates_startup", True, type=bool)

  @check_updates_startup.setter
  def check_updates_startup(self, value: bool) -> None:
    self._q.setValue("ui/check_updates_startup", bool(value))

  @property
  def last_update_check(self) -> str:
    return str(self._q.value("ui/last_update_check", ""))

  @last_update_check.setter
  def last_update_check(self, value: str) -> None:
    self._q.setValue("ui/last_update_check", str(value))

  def sync(self) -> None:
    self._q.sync()
