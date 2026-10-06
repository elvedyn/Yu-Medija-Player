"""libmpv playback backend — reliable embedded audio/subtitle switching (VLC-like)."""

from __future__ import annotations

import locale
import re
import time
from dataclasses import dataclass
from typing import Any

# libmpv segfaults on non-C LC_NUMERIC (common with bs_BA / sr_RS locales)
try:
  locale.setlocale(locale.LC_NUMERIC, "C")
except locale.Error:
  pass

import sys

from PyQt6.QtCore import QMetaObject, QObject, QTimer, QUrl, Qt, pyqtSignal
from PyQt6.QtGui import QImage, QOpenGLContext
from PyQt6.QtMultimedia import QMediaPlayer
from PyQt6.QtWidgets import QWidget

# Resolve bundled libmpv (Windows DLL / macOS dylib) before python-mpv loads.
from app.mpv_bootstrap import prepare_mpv_library

prepare_mpv_library()

try:
  import mpv as _mpv
except Exception:  # noqa: BLE001
  _mpv = None

try:
  from PyQt6.QtOpenGLWidgets import QOpenGLWidget
except Exception:  # noqa: BLE001
  QOpenGLWidget = None  # type: ignore[misc, assignment]


def mpv_available() -> bool:
  if _mpv is None:
    return False
  try:
    locale.setlocale(locale.LC_NUMERIC, "C")
  except locale.Error:
    pass
  try:
    p = _mpv.MPV(vo="null", ao="null", idle=True, quiet=True)
    p.terminate()
    return True
  except Exception:
    return False


def looks_like_live(url: str) -> bool:
  """Heuristic: IPTV live / HLS live vs finite VOD files."""
  u = (url or "").strip().lower()
  if not u.startswith(("http://", "https://")):
    return False
  # Explicit VOD path markers (Xtream Codes etc.)
  if any(x in u for x in ("/movie/", "/series/", "/vod/", "/timeshift/")):
    return False
  path = u.split("?", 1)[0]
  if path.endswith((".mkv", ".mp4", ".avi", ".m4v", ".mov", ".mp3", ".m4a", ".flac")):
    return False
  if "/live/" in u or path.endswith(".ts") or "mode=live" in u:
    return True
  # Bare Xtream-style live: http://host/user/pass/<numeric_id>
  if re.search(r"https?://[^/]+/[^/]+/[^/]+/\d+/?(?:\.ts)?$", path):
    return True
  # HLS without VOD markers — often live IPTV
  if ".m3u8" in path:
    return True
  # Numeric stream id with no file extension (common live panel URLs)
  if re.search(r"/\d+$", path):
    return True
  return False


@dataclass
class TrackInfo:
  """Lightweight track label carrier (replaces QMediaMetaData for menus)."""

  title: str = ""
  language: str = ""
  codec: str = ""

  def stringValue(self, key) -> str:
    name = getattr(key, "name", str(key))
    if "Title" in name:
      return self.title
    if "Language" in name:
      return self.language
    if "Description" in name:
      return self.title
    return ""

  def value(self, key):
    return self.stringValue(key) or None


class MpvNativeVideoWidget(QWidget):
  """Native window surface for libmpv embedding via wid (X11 / Windows HWND)."""

  uses_opengl = False

  def __init__(self, parent=None):
    super().__init__(parent)
    self.setAttribute(Qt.WidgetAttribute.WA_NativeWindow, True)
    self.setAttribute(Qt.WidgetAttribute.WA_DontCreateNativeAncestors, True)
    self.setStyleSheet("background: #000;")
    self.setMinimumSize(160, 90)


class MpvGLVideoWidget(QOpenGLWidget if QOpenGLWidget is not None else QWidget):
  """macOS video surface using libmpv OpenGL render API (wid embedding is unreliable on Cocoa)."""

  uses_opengl = True

  def __init__(self, parent=None):
    super().__init__(parent)
    self.setStyleSheet("background: #000;")
    self.setMinimumSize(160, 90)
    self._mpv = None
    self._ctx = None
    self._gl_ready = False

  def attach_mpv(self, mpv_handle) -> None:
    self._mpv = mpv_handle
    if self._gl_ready and self._ctx is None:
      self._create_render_context()

  def initializeGL(self) -> None:  # noqa: N802
    self._gl_ready = True
    if self._mpv is not None and self._ctx is None:
      self._create_render_context()

  def _create_render_context(self) -> None:
    if _mpv is None or self._mpv is None or QOpenGLWidget is None:
      return
    import ctypes

    def get_proc_address(_ctx, name):  # noqa: ANN001
      if isinstance(name, bytes):
        name = name.decode("utf-8", errors="replace")
      glctx = QOpenGLContext.currentContext()
      if glctx is None:
        return 0
      addr = glctx.getProcAddress(name.encode("utf-8") if isinstance(name, str) else name)
      try:
        return int(addr)
      except (TypeError, ValueError):
        return ctypes.cast(addr, ctypes.c_void_p).value or 0

    try:
      self._ctx = _mpv.MpvRenderContext(
          self._mpv,
          "opengl",
          opengl_init_params={"get_proc_address": get_proc_address},
      )
      self._ctx.update_cb = self._on_mpv_render_update
    except Exception:
      self._ctx = None

  def _on_mpv_render_update(self) -> None:
    # Called from mpv's thread — schedule a Qt repaint on the GUI thread.
    QMetaObject.invokeMethod(self, "update", Qt.ConnectionType.QueuedConnection)

  def paintGL(self) -> None:  # noqa: N802
    if self._ctx is None:
      return
    ratio = float(self.devicePixelRatioF()) if hasattr(self, "devicePixelRatioF") else float(self.devicePixelRatio())
    w = max(1, int(self.width() * ratio))
    h = max(1, int(self.height() * ratio))
    fbo = int(self.defaultFramebufferObject())
    try:
      self._ctx.render(flip_y=True, opengl_fbo={"w": w, "h": h, "fbo": fbo})
      self._ctx.report_swap()
    except Exception:
      pass

  def cleanup(self) -> None:
    if self._ctx is not None:
      try:
        self._ctx.update_cb = None
        self._ctx.free()
      except Exception:
        pass
      self._ctx = None


def MpvVideoWidget(parent=None):
  """Factory: OpenGL render path on macOS, native wid elsewhere."""
  if sys.platform == "darwin" and QOpenGLWidget is not None:
    return MpvGLVideoWidget(parent)
  return MpvNativeVideoWidget(parent)


class MpvPlayer(QObject):
  """
  QMediaPlayer-shaped wrapper around libmpv.
  Embedded subtitle/audio track changes are instant and do not freeze.
  """

  positionChanged = pyqtSignal(int)
  durationChanged = pyqtSignal(int)
  playbackStateChanged = pyqtSignal(object)
  errorOccurred = pyqtSignal(object, str)
  mediaStatusChanged = pyqtSignal(object)
  metaDataChanged = pyqtSignal()
  tracksChanged = pyqtSignal()
  surfaceChanged = pyqtSignal(object)  # kept for API compat (no longer used on switch)
  _mpvEndFile = pyqtSignal(int)  # end-file reason, marshaled to GUI thread
  _mpvFileLoaded = pyqtSignal()

  def __init__(self, video_widget: QWidget, parent=None):
    super().__init__(parent)
    if _mpv is None:
      raise RuntimeError("python-mpv is not installed")
    self._widget = video_widget
    self._mpv: Any = None
    self._source = ""
    self._duration_ms = 0
    self._position_ms = 0
    self._state = QMediaPlayer.PlaybackState.StoppedState
    self._rate = 1.0
    self._volume = 0.4
    self._muted = False
    self._sub_ids: list[int] = []
    self._audio_ids: list[int] = []
    self._sub_metas: list[TrackInfo] = []
    self._audio_metas: list[TrackInfo] = []
    self._active_sub = -1
    self._active_audio = -1
    self._http_headers: list[str] = []
    self._live = False
    self._hwdec_local = False
    self._switching = False
    self._pending_source = ""
    self._reloading_live = False
    self._live_reload_at = 0.0
    self._gen = 0  # bumped only when creating/destroying an mpv instance
    self._load_token = 0  # bumped on every setSource to drop stale loads
    self._tick = QTimer(self)
    self._tick.setInterval(200)
    self._tick.timeout.connect(self._poll)
    # Marshal libmpv event-thread callbacks onto the Qt GUI thread.
    self._mpvEndFile.connect(self._handle_end_file)
    self._mpvFileLoaded.connect(self._on_file_loaded)
    # Create libmpv lazily after the widget has a real window id (after show).

  def _ensure_mpv(self) -> None:
    if self._mpv is not None:
      return
    try:
      locale.setlocale(locale.LC_NUMERIC, "C")
    except locale.Error:
      pass
    self._gen += 1
    gen = self._gen
    common = dict(
        keep_open="yes",
        idle="yes",
        osc="no",
        input_default_bindings="no",
        input_vo_keyboard="no",
        input_cursor="no",
        cursor_autohide="no",
        quiet=True,
        user_agent="VLC/3.0.21 LibVLC/3.0.21",
        sub_visibility="yes",
        # Software decode — hwdec often segfaults on VOD(MKV)→live(TS) switches
        hwdec="no",
        # cache=yes + cache-pause was freezing live IPTV after ~one HLS/TS
        # window (~20–30s): demuxer hit the end of buffered data and paused.
        cache="auto",
        cache_pause="no",
        cache_pause_initial="no",
        demuxer_readahead_secs=2,
        demuxer_max_bytes=52428800,
        demuxer_max_back_bytes=10485760,
        # Reconnect when IPTV HTTP/TS drops (otherwise live dies after ~one window)
        stream_lavf_o="reconnect=1,reconnect_streamed=1,reconnect_delay_max=5,reconnect_on_network_error=1",
    )
    use_gl = bool(getattr(self._widget, "uses_opengl", False))
    if use_gl:
      # macOS: libmpv OpenGL render API (wid/Cocoa embedding is unreliable)
      self._mpv = _mpv.MPV(vo="libmpv", **common)
      if hasattr(self._widget, "attach_mpv"):
        self._widget.attach_mpv(self._mpv)
    else:
      # Linux (X11) + Windows (HWND): embed into the native window id
      wid = int(self._widget.winId())
      self._mpv = _mpv.MPV(wid=str(wid), **common)

    @self._mpv.event_callback("end-file")
    def _on_end(event):  # noqa: ARG001
      # Runs on MPVEventHandlerThread — only emit Qt signals (thread-safe).
      if gen != self._gen or self._mpv is None or self._switching:
        return
      reason = getattr(getattr(event, "data", None), "reason", None)
      try:
        r = int(reason) if reason is not None else -1
      except (TypeError, ValueError):
        r = -1
      self._mpvEndFile.emit(r)

    @self._mpv.event_callback("file-loaded")
    def _on_loaded(event):  # noqa: ARG001
      if gen != self._gen or self._mpv is None:
        return
      self._mpvFileLoaded.emit()

  def _on_file_loaded(self) -> None:
    if self._mpv is None:
      return
    self._switching = False
    self._refresh_tracks()
    self.mediaStatusChanged.emit(QMediaPlayer.MediaStatus.LoadedMedia)
    self.mediaStatusChanged.emit(QMediaPlayer.MediaStatus.BufferedMedia)
    self.metaDataChanged.emit()
    self.tracksChanged.emit()
    self._sync_duration()
    if self._state == QMediaPlayer.PlaybackState.PlayingState:
      self._tick.start()

  def _handle_end_file(self, reason: int) -> None:
    """GUI-thread handler for libmpv end-file (ignore during channel switches)."""
    if self._mpv is None or self._switching or self._reloading_live:
      return
    # Live IPTV/HLS: EOF or network error after the first sliding window (~20–30s)
    # must reconnect, not freeze on the last frame (keep-open) like a finished VOD.
    if self._live and reason in (0, 4) and self._source:
      now = time.monotonic()
      if now - self._live_reload_at < 2.0:
        return
      self._live_reload_at = now
      self._reloading_live = True
      QTimer.singleShot(400, self._reload_live)
      return
    if reason == 0:
      self.mediaStatusChanged.emit(QMediaPlayer.MediaStatus.EndOfMedia)
    elif reason == 4:
      self.errorOccurred.emit(0, "Playback failed")

  def _reload_live(self) -> None:
    self._reloading_live = False
    if not self._live or not self._source or self._mpv is None or self._switching:
      return
    path = self._source
    try:
      if self._http_headers:
        try:
          self._mpv["http-header-fields"] = self._http_headers
        except Exception:
          pass
      self._mpv.command("loadfile", path, "replace")
      self._mpv.pause = False
      self._set_state(QMediaPlayer.PlaybackState.PlayingState)
      self._tick.start()
    except Exception as exc:  # noqa: BLE001
      self.errorOccurred.emit(0, str(exc))

  def set_http_headers(self, referer: str | None = None, user_agent: str | None = None) -> None:
    headers: list[str] = []
    if referer:
      headers.append(f"Referer: {referer}")
    self._http_headers = headers
    if self._mpv is None:
      return
    if user_agent:
      try:
        self._mpv["user-agent"] = user_agent
      except Exception:
        pass
    try:
      self._mpv["http-header-fields"] = headers
    except Exception:
      pass

  def setSource(self, url: QUrl | str) -> None:
    if isinstance(url, QUrl):
      if url.isLocalFile():
        path = url.toLocalFile()
      else:
        path = url.toString()
    else:
      path = str(url)

    self._source = path
    self._duration_ms = 0
    self._position_ms = 0
    self._active_sub = -1
    self._sub_ids = []
    self._audio_ids = []
    self._sub_metas = []
    self._audio_metas = []
    self._live = looks_like_live(path)
    self._apply_hwdec()
    self._reloading_live = False
    self.mediaStatusChanged.emit(QMediaPlayer.MediaStatus.LoadingMedia)
    self._switching = True
    self._tick.stop()
    self._pending_source = path
    self._load_token += 1
    token = self._load_token

    # Soft switch on the SAME libmpv instance + wid.
    # Recreating/terminating mpv on every channel change races inside libmpv
    # (mpv_set_option on a NULL handle → SIGSEGV) and was shutting the app down.
    self._ensure_mpv()
    self._restore_runtime_options()
    self._clear_vod_limits()
    self._soft_load(path, token)

  def _destroy_mpv(self) -> None:
    """Full shutdown (app close). Not used for channel switches."""
    self._tick.stop()
    self._gen += 1
    self._load_token += 1
    if hasattr(self._widget, "cleanup"):
      try:
        self._widget.cleanup()
      except Exception:
        pass
    mpv = self._mpv
    self._mpv = None
    if mpv is None:
      return
    try:
      mpv.terminate()
    except Exception:
      pass

  def _restore_runtime_options(self) -> None:
    if self._mpv is None:
      return
    try:
      self._mpv.speed = self._rate
    except Exception:
      pass
    try:
      self._mpv.volume = 0.0 if self._muted else self._volume * 100.0
    except Exception:
      pass
    if self._http_headers:
      try:
        self._mpv["http-header-fields"] = self._http_headers
      except Exception:
        pass
    # Keep HTTP reconnect enabled across soft switches
    try:
      self._mpv["stream-lavf-o"] = (
          "reconnect=1,reconnect_streamed=1,reconnect_delay_max=5,"
          "reconnect_on_network_error=1"
      )
    except Exception:
      pass

  def _clear_vod_limits(self) -> None:
    """Drop leftover VOD start/end/loop so the next live stream is not clipped."""
    if self._mpv is None:
      return
    for key, value in (
        ("start", "none"),
        ("end", "none"),
        ("length", "none"),
        ("ab-loop-a", "no"),
        ("ab-loop-b", "no"),
        ("loop-file", "no"),
    ):
      try:
        self._mpv[key] = value
      except Exception:
        pass
    try:
      self._mpv["force-seekable"] = "no" if self._live else "auto"
    except Exception:
      pass
    # Live: never pause on cache underrun / end-of-window; VOD can use defaults.
    try:
      self._mpv["cache-pause"] = False
    except Exception:
      pass
    try:
      if self._live:
        self._mpv["demuxer-seekable-cache"] = False
        self._mpv["demuxer-readahead-secs"] = 2
      else:
        self._mpv["demuxer-seekable-cache"] = "auto"
        self._mpv["demuxer-readahead-secs"] = 5
    except Exception:
      pass

  def _soft_load(self, path: str, token: int | None = None) -> None:
    if self._mpv is None:
      self._ensure_mpv()
    if token is not None and token != self._load_token:
      return
    try:
      if self._http_headers:
        try:
          self._mpv["http-header-fields"] = self._http_headers
        except Exception:
          pass
      # replace = tear down previous demuxer/codecs without destroying the handle
      self._mpv.command("loadfile", path, "replace")
      self._mpv.pause = False
      self._set_state(QMediaPlayer.PlaybackState.PlayingState)
      QTimer.singleShot(1500, lambda t=token: self._finish_switch_fallback(t))
    except Exception as exc:  # noqa: BLE001
      if token is not None and token != self._load_token:
        return
      self._switching = False
      self.errorOccurred.emit(0, str(exc))
      self.mediaStatusChanged.emit(QMediaPlayer.MediaStatus.InvalidMedia)

  def _finish_switch_fallback(self, token: int | None = None) -> None:
    if token is not None and token != self._load_token:
      return
    if not self._switching or self._mpv is None:
      return
    self._switching = False
    try:
      self._refresh_tracks()
      self._sync_duration()
      self.tracksChanged.emit()
    except Exception:
      pass
    if self._state == QMediaPlayer.PlaybackState.PlayingState:
      self._tick.start()

  def set_hardware_decoding(self, enabled: bool) -> None:
    """Enable hwdec=auto-safe for local/VOD only; live stays software."""
    self._hwdec_local = bool(enabled)
    self._apply_hwdec()

  def _apply_hwdec(self) -> None:
    if self._mpv is None:
      return
    use = bool(self._hwdec_local) and (not self._live)
    try:
      self._mpv["hwdec"] = "auto-safe" if use else "no"
    except Exception:
      pass

  def set_sub_delay(self, delay_ms: int) -> None:
    if self._mpv is None:
      return
    try:
      self._mpv["sub-delay"] = float(delay_ms) / 1000.0
    except Exception:
      pass

  def play(self) -> None:
    self._ensure_mpv()
    try:
      self._mpv.pause = False
      self._set_state(QMediaPlayer.PlaybackState.PlayingState)
      self._tick.start()
    except Exception as exc:  # noqa: BLE001
      self.errorOccurred.emit(0, str(exc))

  def pause(self) -> None:
    if self._mpv is None:
      return
    try:
      self._mpv.pause = True
      self._set_state(QMediaPlayer.PlaybackState.PausedState)
    except Exception:
      pass

  def stop(self) -> None:
    if self._mpv is None:
      return
    try:
      self._mpv.command("stop")
    except Exception:
      try:
        self._mpv.playlist_clear()
      except Exception:
        pass
    self._tick.stop()
    self._set_state(QMediaPlayer.PlaybackState.StoppedState)
    self._position_ms = 0
    self.positionChanged.emit(0)

  def playbackState(self) -> int:
    return self._state

  def position(self) -> int:
    return int(self._position_ms)

  def duration(self) -> int:
    return int(self._duration_ms)

  def setPosition(self, ms: int) -> None:
    if self._mpv is None or self._switching:
      return
    # Live IPTV usually has no duration — seeking there can upset libmpv.
    if self._duration_ms <= 0:
      return
    try:
      self._mpv.seek(max(0, ms) / 1000.0, reference="absolute")
      self._position_ms = max(0, int(ms))
      self.positionChanged.emit(self._position_ms)
    except Exception:
      pass

  def isSeekable(self) -> bool:
    return (not self._live) and self._duration_ms > 0

  def is_live(self) -> bool:
    return bool(self._live)

  def setPlaybackRate(self, rate: float) -> None:
    self._rate = float(rate)
    if self._mpv is None:
      return
    try:
      self._mpv.speed = self._rate
    except Exception:
      pass

  def errorString(self) -> str:
    return ""

  # --- audio volume (paired with MpvAudioOutput) ---------------------

  def set_volume_fraction(self, value: float) -> None:
    self._volume = max(0.0, min(1.0, float(value)))
    if self._mpv is None:
      return
    try:
      self._mpv.volume = 0.0 if self._muted else self._volume * 100.0
    except Exception:
      pass

  def set_muted(self, muted: bool) -> None:
    self._muted = bool(muted)
    self.set_volume_fraction(self._volume)

  # --- tracks ----------------------------------------------------------

  def _refresh_tracks(self) -> None:
    if self._mpv is None:
      return
    try:
      tracks = self._mpv.track_list or []
    except Exception:
      tracks = []
    self._sub_ids = []
    self._sub_metas = []
    self._audio_ids = []
    self._audio_metas = []
    active_sub = -1
    active_audio = -1
    for t in tracks:
      try:
        ttype = str(t.get("type") or "")
        tid = int(t.get("id"))
      except (TypeError, ValueError, AttributeError):
        continue
      title = str(t.get("title") or "").strip()
      lang = str(t.get("lang") or t.get("language") or "").strip()
      codec = str(t.get("codec") or "").strip()
      meta = TrackInfo(title=title, language=lang, codec=codec)
      selected = bool(t.get("selected"))
      if ttype in ("sub", "subtitle"):
        if selected:
          active_sub = len(self._sub_ids)
        self._sub_ids.append(tid)
        self._sub_metas.append(meta)
      elif ttype == "audio":
        if selected:
          active_audio = len(self._audio_ids)
        self._audio_ids.append(tid)
        self._audio_metas.append(meta)
    self._active_sub = active_sub
    self._active_audio = active_audio

  def subtitleTracks(self) -> list[TrackInfo]:
    self._refresh_tracks()
    return list(self._sub_metas)

  def audioTracks(self) -> list[TrackInfo]:
    self._refresh_tracks()
    return list(self._audio_metas)

  def activeSubtitleTrack(self) -> int:
    self._refresh_tracks()
    return self._active_sub

  def activeAudioTrack(self) -> int:
    self._refresh_tracks()
    return self._active_audio

  def setActiveSubtitleTrack(self, index: int) -> None:
    """Switch embedded/soft subtitles — same idea as VLC track menu."""
    self._ensure_mpv()
    self._refresh_tracks()
    try:
      if index is None or int(index) < 0:
        self._mpv.sid = False
        self._active_sub = -1
      else:
        idx = int(index)
        if idx >= len(self._sub_ids):
          return
        self._mpv.sid = self._sub_ids[idx]
        self._active_sub = idx
      # Force softsub visibility
      self._mpv["sub-visibility"] = True
    except Exception as exc:  # noqa: BLE001
      self.errorOccurred.emit(0, f"Subtitle switch failed: {exc}")
      return
    self.tracksChanged.emit()

  def setActiveAudioTrack(self, index: int) -> None:
    self._ensure_mpv()
    self._refresh_tracks()
    try:
      idx = int(index)
      if idx < 0 or idx >= len(self._audio_ids):
        return
      self._mpv.aid = self._audio_ids[idx]
      self._active_audio = idx
    except Exception as exc:  # noqa: BLE001
      self.errorOccurred.emit(0, f"Audio switch failed: {exc}")
      return
    self.tracksChanged.emit()

  def add_external_subtitle(self, path: str) -> bool:
    self._ensure_mpv()
    try:
      self._mpv.command("sub-add", path, "select")
      self._refresh_tracks()
      self.tracksChanged.emit()
      return True
    except Exception:
      return False

  def screenshot_image(self) -> QImage | None:
    self._ensure_mpv()
    try:
      # returns bytes flag + w + h + stride + data via screenshot-raw
      raw = self._mpv.screenshot_raw(includes="video")
    except Exception:
      return None
    if not raw:
      return None
    # python-mpv may return PIL Image — convert if needed
    try:
      from PIL.ImageQt import ImageQt

      return QImage(ImageQt(raw)).copy()
    except Exception:
      pass
    try:
      # Some versions return (size, data) — best effort skip
      return None
    except Exception:
      return None

  def screenshot_to_file(self, path: str) -> bool:
    self._ensure_mpv()
    try:
      self._mpv.command("screenshot-to-file", path, "video")
      return True
    except Exception:
      try:
        self._mpv.screenshot_to_file(path)
        return True
      except Exception:
        return False

  def metaData(self):
    return _EmptyMeta()

  def _sync_duration(self) -> None:
    if self._mpv is None:
      return
    # Live streams often report the HLS/DVR window (~20–60s) as "duration".
    # Publishing that makes the UI treat them like short VODs and they stop at EOF.
    if self._live:
      if self._duration_ms != 0:
        self._duration_ms = 0
        self.durationChanged.emit(0)
      return
    try:
      dur = self._mpv.duration
      if dur:
        ms = int(float(dur) * 1000)
        if ms > 0 and ms != self._duration_ms:
          self._duration_ms = ms
          self.durationChanged.emit(ms)
    except Exception:
      pass

  def _poll(self) -> None:
    if self._mpv is None or self._switching:
      return
    try:
      paused = bool(self._mpv.pause)
      if paused and self._state == QMediaPlayer.PlaybackState.PlayingState:
        self._set_state(QMediaPlayer.PlaybackState.PausedState)
      elif (not paused) and self._state != QMediaPlayer.PlaybackState.PlayingState:
        # keep playing unless stopped intentionally
        if self._state != QMediaPlayer.PlaybackState.StoppedState:
          self._set_state(QMediaPlayer.PlaybackState.PlayingState)
      pos = self._mpv.time_pos
      if pos is not None:
        ms = int(float(pos) * 1000)
        if abs(ms - self._position_ms) >= 100:
          self._position_ms = ms
          self.positionChanged.emit(ms)
      self._sync_duration()
    except Exception:
      pass

  def _set_state(self, state) -> None:
    if state == self._state:
      return
    self._state = state
    self.playbackStateChanged.emit(state)

  def shutdown(self) -> None:
    self._tick.stop()
    self._gen += 1
    self._load_token += 1
    self._switching = False
    if hasattr(self._widget, "cleanup"):
      try:
        self._widget.cleanup()
      except Exception:
        pass
    if self._mpv is not None:
      try:
        self._mpv.terminate()
      except Exception:
        pass
      self._mpv = None


class MpvAudioOutput(QObject):
  """Volume/mute shim so window.py can keep using audio_output.*."""

  def __init__(self, player: MpvPlayer, parent=None):
    super().__init__(parent)
    self._player = player
    self._volume = 0.4
    self._muted = False

  def setVolume(self, value: float) -> None:
    self._volume = float(value)
    self._player.set_volume_fraction(self._volume)

  def volume(self) -> float:
    return self._volume

  def setMuted(self, muted: bool) -> None:
    self._muted = bool(muted)
    self._player.set_muted(self._muted)

  def isMuted(self) -> bool:
    return self._muted


class _EmptyMeta:
  def value(self, key):  # noqa: ARG002
    return None

  def stringValue(self, key):  # noqa: ARG002
    return ""
