"""Main player window."""

from __future__ import annotations

import os
import sys
import time
from datetime import datetime
from pathlib import Path

from app.qt_backend import configure_linux_media_backend

configure_linux_media_backend()

from PyQt6.QtCore import QDate, QEvent, QLocale, QPoint, QThread, QTimer, QUrl, Qt, pyqtSignal
from PyQt6.QtGui import QAction, QActionGroup, QCursor, QDesktopServices, QIcon, QKeySequence
from PyQt6.QtMultimedia import QAudioOutput, QMediaMetaData, QMediaPlayer
from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSlider,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app import APP_NAME, ORG_NAME, __version__
from app.aspect import AspectVideoHost, aspect_choices
from app.m3u import (
    PlaylistEntry,
    group_entries,
    load_playlist,
    looks_like_playlist_url,
)
from app.media_info import probe_duration_ms, probe_stream_languages
from app.mpv_player import MpvAudioOutput, MpvPlayer, MpvVideoWidget, looks_like_live, mpv_available
from app.control_icons import apply_icon
from app.resources import icon_path
from app.settings import AppSettings
from app.settings_dialog import SettingsDialog
from app.srt import (
    SubtitleCue,
    SubtitleTrack,
    discover_sidecar_srts,
    format_time,
    load_track,
)
from app.styles import app_stylesheet, get_theme, theme_choices
from app.subtitle_search_dialog import SubtitleSearchDialog
from app.url_dialog import UrlDialog
from app.widgets import SeekSlider, icon_btn
from app.ytdlp import download as ytdlp_download, is_youtube_url, needs_ytdlp, resolve_play_url
from app.exception_hook import configure_logging, install_exception_hooks
from app.updates import UpdateCheckWorker, UpdateInfo, is_newer

SPEED_PRESETS = [0.25, 0.50, 0.75, 1.0, 1.25, 1.50, 1.75]
VIDEO_FILTER = "Video Files (*.mp4 *.mkv *.avi *.webm *.mov *.m4v);;All Files (*)"
PLAYLIST_FILTER = "Playlists (*.m3u *.m3u8);;All Files (*)"
VIDEO_EXTENSIONS = {".mp4", ".mkv", ".avi", ".webm", ".mov", ".m4v", ".mpg", ".mpeg", ".wmv", ".flv", ".ts", ".m2ts"}
PLAYLIST_EXTENSIONS = {".m3u", ".m3u8"}
MENU_CHANNEL_CAP = 200


class _DurationProbeWorker(QThread):
  finished_ok = pyqtSignal(int)

  def __init__(self, target: str, referer: str | None = None):
    super().__init__()
    self.target = target
    self.referer = referer

  def run(self):
    try:
      ms = probe_duration_ms(self.target, referer=self.referer)
    except Exception:
      ms = 0
    self.finished_ok.emit(int(ms or 0))


class _ResolveWorker(QThread):
  finished_ok = pyqtSignal(str, str)  # resolved_url, title
  failed = pyqtSignal(str)

  def __init__(self, url: str, title: str):
    super().__init__()
    self.url = url
    self.title = title

  def run(self):
    try:
      play_url = resolve_play_url(self.url)
      self.finished_ok.emit(play_url, self.title)
    except Exception as exc:  # noqa: BLE001
      self.failed.emit(str(exc))


class _DownloadWorker(QThread):
  finished_ok = pyqtSignal(str)
  failed = pyqtSignal(str)

  def __init__(self, url: str, dest_dir: str):
    super().__init__()
    self.url = url
    self.dest_dir = dest_dir

  def run(self):
    try:
      path = ytdlp_download(self.url, self.dest_dir)
      self.finished_ok.emit(path)
    except Exception as exc:  # noqa: BLE001
      self.failed.emit(str(exc))


def resolve_cli_path(arg: str) -> Path | None:
  """Resolve CLI / file-manager paths (plain path or file:// URL)."""
  raw = arg.strip().strip('"').strip("'")
  if not raw or raw.startswith("-"):
    return None
  if raw.startswith("file:"):
    local = QUrl(raw).toLocalFile()
    if not local:
      return None
    path = Path(local)
  else:
    path = Path(raw).expanduser()
  try:
    path = path.resolve(strict=False)
  except OSError:
    return None
  return path if path.is_file() else None


class VideoPlayer(QMainWindow):
  def __init__(self):
    super().__init__()
    self.settings = AppSettings()
    self.setWindowTitle(APP_NAME)
    self.setMinimumSize(800, 520)

    geo = self.settings.geometry
    if geo:
      self.restoreGeometry(geo)
    else:
      self.setGeometry(100, 100, 1120, 720)

    self.sub_tracks: list[SubtitleTrack] = []
    self._active_track: int = -1  # -1 = off
    self._current_cue_idx = -1
    self._was_playing_before_seek = False
    self._controls_visible = True
    self._video_path: str | None = None
    self._source_url: str | None = None  # original remote / YT URL
    self._play_url: str | None = None  # actual URL/path fed to QMediaPlayer
    self._playlist_entries: list[PlaylistEntry] = []
    self._playlist_by_group: dict = {}
    self._playlist_source_url: str | None = None
    self._http_referer: str | None = None
    self._http_error_retries = 0
    self._last_error_msg = ""
    self._last_error_ts = 0.0
    self._error_box_open = False
    self._category_menus: list[QMenu] = []
    self._hidden_groups: set[str] = set()
    self._probe_langs: dict[str, list[str]] = {"audio": [], "subtitle": []}
    self._net_worker: QThread | None = None
    self._duration_worker: QThread | None = None
    self._probe_gen = 0  # ignore stale ffprobe results after channel switch
    self._pending_seek_ms: int | None = None
    self._use_mpv = False
    self._duration_ms = 0
    self._speed_idx = SPEED_PRESETS.index(1.0)
    self._seek_lock = False
    self._seek_target = 0
    self._playlist_index = -1
    self._folder_files: list[str] = []
    self._folder_index = -1
    self._update_worker: QThread | None = None
    self._suppress_auto_next = False
    rate = self.settings.playback_rate
    if rate in SPEED_PRESETS:
      self._speed_idx = SPEED_PRESETS.index(rate)

    self._hide_timer = QTimer(self)
    self._hide_timer.setSingleShot(True)
    self._hide_timer.timeout.connect(self._hide_controls)

    self._status_timer = QTimer(self)
    self._status_timer.setSingleShot(True)
    self._status_timer.timeout.connect(lambda: self.status_label.setText(""))

    # MKV/ffmpeg often delay duration — light poll + ffprobe fallback
    self._duration_timer = QTimer(self)
    self._duration_timer.setInterval(400)
    self._duration_timer.timeout.connect(self._probe_duration_tick)
    self._duration_attempts = 0

    # Fullscreen auto-hide: poll cursor (QVideoWidget native surface eats mouse events)
    self._cursor_timer = QTimer(self)
    self._cursor_timer.setInterval(180)
    self._cursor_timer.timeout.connect(self._poll_fullscreen_cursor)
    self._last_cursor_pos: QPoint | None = None

    self._build_ui()
    self._build_menus()
    self._set_app_icon()
    self._apply_style()
    self._wire_player()
    self._setup_shortcuts()
    self._apply_speed()
    self._update_download_button()
    self._apply_volume_from_settings()
    self._apply_aspect_mode(self.settings.aspect_mode)
    self.setAcceptDrops(True)
    self._sync_repeat_ui()
    self._apply_sub_delay()
    if self._use_mpv and hasattr(self.media_player, "set_hardware_decoding"):
      self.media_player.set_hardware_decoding(self.settings.hardware_decoding)
    # QVideoWidget (native) često ne prosljeđuje tipke — filter hvata Space globalno za ovaj prozor
    QApplication.instance().installEventFilter(self)
    self.setMouseTracking(True)
    QTimer.singleShot(1500, self._maybe_check_updates_startup)

  def eventFilter(self, obj, event):
    if event.type() == QEvent.Type.KeyPress and self.isActiveWindow():
      if event.key() == Qt.Key.Key_Space and not event.isAutoRepeat():
        self.toggle_play()
        return True
    if event.type() == QEvent.Type.MouseMove and self.isActiveWindow() and self.isFullScreen():
      self._bump_controls()
    return super().eventFilter(obj, event)

  def _set_app_icon(self):
    path = icon_path("yu-medija-player.png", "yu-medija-player-256.png", "yu-medija-player.ico")
    if path:
      self.setWindowIcon(QIcon(str(path)))

  # --- UI --------------------------------------------------------------

  def _build_ui(self):
    central = QWidget()
    self.setCentralWidget(central)
    root = QVBoxLayout(central)
    root.setContentsMargins(0, 0, 0, 0)
    root.setSpacing(0)

    self.stage = QStackedWidget()
    self.stage.setObjectName("stage")
    self.stage.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    self.welcome = QLabel(
        f"{APP_NAME}\n\nOpen a video to start\nFile → Open  ·  O\nFile → Open YT URL  ·  Ctrl+U"
    )
    self.welcome.setObjectName("welcome")
    self.welcome.setAlignment(Qt.AlignmentFlag.AlignCenter)
    self.stage.addWidget(self.welcome)
    self._use_mpv = bool(mpv_available())
    if self._use_mpv:
      surface = MpvVideoWidget()
      self.video_host = AspectVideoHost(surface)
    else:
      self.video_host = AspectVideoHost()
    self.video_widget = self.video_host.video_widget
    self.stage.addWidget(self.video_host)
    self.stage.setCurrentWidget(self.welcome)
    root.addWidget(self.stage, 1)

    self.subtitle_label = QLabel("")
    self.subtitle_label.setObjectName("subtitle")
    self.subtitle_label.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)
    self.subtitle_label.setWordWrap(True)
    self.subtitle_label.hide()
    root.addWidget(self.subtitle_label)

    self.controls = QFrame()
    self.controls.setObjectName("controls")
    controls_col = QVBoxLayout(self.controls)
    controls_col.setContentsMargins(16, 12, 16, 14)
    controls_col.setSpacing(8)

    progress_row = QHBoxLayout()
    progress_row.setSpacing(10)
    self.time_current = QLabel("00:00")
    self.time_current.setObjectName("timeLabel")
    self.time_current.setFixedWidth(54)
    progress_row.addWidget(self.time_current)

    self.position_slider = SeekSlider()
    self.position_slider.setRange(0, 0)
    self.position_slider.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    self.position_slider.sliderPressed.connect(self._seek_pressed)
    self.position_slider.scrubbing.connect(self._seek_preview)
    self.position_slider.seek_committed.connect(self._seek_commit)
    self.position_slider.sliderReleased.connect(self._seek_released)
    progress_row.addWidget(self.position_slider, 1)

    self.time_total = QLabel("00:00")
    self.time_total.setObjectName("timeLabel")
    self.time_total.setFixedWidth(54)
    self.time_total.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    progress_row.addWidget(self.time_total)

    self.status_label = QLabel("")
    self.status_label.setObjectName("statusLabel")
    self.status_label.setMinimumWidth(80)
    progress_row.addWidget(self.status_label)
    controls_col.addLayout(progress_row)

    btn_row = QHBoxLayout()
    btn_row.setSpacing(6)

    # Open lives in File > Open (Ctrl+O / O) — no duplicate on the bar
    self.btn_shot = icon_btn("", "Screenshot (P)", 40)
    self.btn_shot.clicked.connect(self.take_screenshot)
    btn_row.addWidget(self.btn_shot)

    self.btn_dl = icon_btn("", "Download YouTube video (Ctrl+D)", 40)
    self.btn_dl.clicked.connect(self.download_current)
    self.btn_dl.hide()
    btn_row.addWidget(self.btn_dl)

    btn_row.addSpacing(8)

    self.btn_prev = icon_btn("", "Previous (B)", 40)
    self.btn_prev.clicked.connect(self.play_previous)
    btn_row.addWidget(self.btn_prev)

    self.btn_back = icon_btn("", "Seek back (←)", 40)
    self.btn_back.clicked.connect(lambda: self._skip(-self._seek_step_ms()))
    btn_row.addWidget(self.btn_back)

    self.btn_play = icon_btn("", "Play / Pause (Space)", 44)
    self.btn_play.setObjectName("playBtn")
    self.btn_play.clicked.connect(self.toggle_play)
    btn_row.addWidget(self.btn_play)

    self.btn_fwd = icon_btn("", "Seek forward (→)", 40)
    self.btn_fwd.clicked.connect(lambda: self._skip(self._seek_step_ms()))
    btn_row.addWidget(self.btn_fwd)

    self.btn_next = icon_btn("", "Next (N)", 40)
    self.btn_next.clicked.connect(self.play_next)
    btn_row.addWidget(self.btn_next)

    btn_row.addSpacing(8)

    self.btn_repeat = icon_btn("", "Repeat: Off (Ctrl+R)", 40)
    self.btn_repeat.clicked.connect(self.cycle_repeat_mode)
    btn_row.addWidget(self.btn_repeat)

    btn_row.addSpacing(8)

    self.btn_speed_down = icon_btn("", "Slower ( [ )", 36)
    self.btn_speed_down.setObjectName("speedBtn")
    self.btn_speed_down.clicked.connect(self.speed_down)
    btn_row.addWidget(self.btn_speed_down)

    self.btn_speed = QPushButton("1.00x")
    self.btn_speed.setObjectName("speedLabel")
    self.btn_speed.setCursor(Qt.CursorShape.PointingHandCursor)
    self.btn_speed.setToolTip("Reset to 1.00x (R)")
    self.btn_speed.setFixedSize(62, 36)
    self.btn_speed.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    self.btn_speed.clicked.connect(self.reset_speed)
    btn_row.addWidget(self.btn_speed)

    self.btn_speed_up = icon_btn("", "Faster ( ] )", 36)
    self.btn_speed_up.setObjectName("speedBtn")
    self.btn_speed_up.clicked.connect(self.speed_up)
    btn_row.addWidget(self.btn_speed_up)

    btn_row.addSpacing(8)
    btn_row.addStretch(1)

    self.btn_mute = icon_btn("", "Mute / Unmute (M)", 40)
    self.btn_mute.setObjectName("muteBtn")
    self.btn_mute.setCheckable(True)
    self.btn_mute.clicked.connect(self.toggle_mute)
    btn_row.addWidget(self.btn_mute)

    self.volume_slider = QSlider(Qt.Orientation.Horizontal)
    self.volume_slider.setObjectName("volume")
    self.volume_slider.setRange(0, 100)
    self.volume_slider.setFixedWidth(110)
    self.volume_slider.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    self.volume_slider.valueChanged.connect(self.set_volume)
    btn_row.addWidget(self.volume_slider)

    self.volume_label = QLabel("40%")
    self.volume_label.setObjectName("timeLabel")
    self.volume_label.setFixedWidth(36)
    btn_row.addWidget(self.volume_label)

    btn_row.addSpacing(8)
    self.btn_fullscreen = icon_btn("", "Fullscreen (F)", 40)
    self.btn_fullscreen.clicked.connect(self.toggle_fullscreen)
    btn_row.addWidget(self.btn_fullscreen)

    controls_col.addLayout(btn_row)
    root.addWidget(self.controls)

    if self._use_mpv:
      # libmpv: VLC-like embedded subtitle/audio switching (no Qt freeze)
      self.media_player = MpvPlayer(self.video_widget, parent=self)
      self.audio_output = MpvAudioOutput(self.media_player, parent=self)
      self.media_player.surfaceChanged.connect(self._on_mpv_surface_changed)
    else:
      self.media_player = QMediaPlayer()
      self.audio_output = QAudioOutput()
      self.media_player.setAudioOutput(self.audio_output)
      self.media_player.setVideoOutput(self.video_widget)
    self._volume_before_mute = 40

  def _build_menus(self):
    file_menu = self.menuBar().addMenu("&File")
    self._add_action(file_menu, "Open Video…", "Ctrl+O", self.open_file)
    self._add_action(file_menu, "Open YT URL…", "Ctrl+U", self.open_url_dialog)
    self._add_action(file_menu, "Open M3U Playlist…", "Ctrl+P", self.open_playlist_file)
    self._recent_menu = file_menu.addMenu("Open Recent")
    self._recent_menu.aboutToShow.connect(self._populate_recent_menu)
    self._close_playlist_act = QAction("Close Playlist", self)
    self._close_playlist_act.triggered.connect(self.close_playlist)
    self._close_playlist_act.setEnabled(False)
    file_menu.addAction(self._close_playlist_act)
    file_menu.addSeparator()
    self._add_action(file_menu, "Open Subtitles…", "Ctrl+S", self.open_subtitles)
    self._add_action(file_menu, "Search OpenSubtitles…", "Ctrl+Shift+S", self.search_opensubtitles)
    self._add_action(file_menu, "Screenshot…", "P", self.take_screenshot)
    self._dl_menu_act = QAction("Download YT Video…", self)
    self._dl_menu_act.setShortcut(QKeySequence("Ctrl+D"))
    self._dl_menu_act.triggered.connect(self.download_current)
    self._dl_menu_act.setVisible(False)
    file_menu.addAction(self._dl_menu_act)
    file_menu.addSeparator()
    self._add_action(file_menu, "Settings…", "Ctrl+,", self.open_settings)
    file_menu.addSeparator()
    self._add_action(file_menu, "Quit", "Ctrl+Q", self.close)

    play_menu = self.menuBar().addMenu("&Playback")
    self._add_action(play_menu, "Play / Pause\tSpace", "", self.toggle_play)
    self._add_action(play_menu, "Seek Back", "Left", lambda: self._skip(-self._seek_step_ms()))
    self._add_action(play_menu, "Seek Forward", "Right", lambda: self._skip(self._seek_step_ms()))
    play_menu.addSeparator()
    self._add_action(play_menu, "Slower", "[", self.speed_down)
    self._add_action(play_menu, "Faster", "]", self.speed_up)
    self._add_action(play_menu, "Normal Speed", "R", self.reset_speed)
    play_menu.addSeparator()
    self._add_action(play_menu, "Mute", "M", self.toggle_mute)

    # Top-level Subtitles / Audio (not under Playback)
    self._sub_menu = self.menuBar().addMenu("&Subtitles")
    self._sub_menu.aboutToShow.connect(self._populate_subtitle_menu)
    # Delay actions are appended inside _fill_subtitle_menu
    self._audio_menu = self.menuBar().addMenu("&Audio")
    self._audio_menu.aboutToShow.connect(self._populate_audio_menu)

    view_menu = self.menuBar().addMenu("&View")
    self._add_action(view_menu, "Fullscreen", "F", self.toggle_fullscreen)
    view_menu.addSeparator()

    aspect_menu = view_menu.addMenu("Aspect ratio")
    self._aspect_group = QActionGroup(self)
    self._aspect_group.setExclusive(True)
    for mode_id, label in aspect_choices():
      act = QAction(label, self, checkable=True)
      act.setData(mode_id)
      act.setChecked(mode_id == self.settings.aspect_mode)
      act.triggered.connect(
          lambda checked, mid=mode_id: self._set_aspect_mode(mid) if checked else None
      )
      self._aspect_group.addAction(act)
      aspect_menu.addAction(act)

    view_menu.addSeparator()
    theme_menu = view_menu.addMenu("Theme")
    self._theme_group = QActionGroup(self)
    self._theme_group.setExclusive(True)
    for theme_id, label in theme_choices():
      act = QAction(label, self, checkable=True)
      act.setData(theme_id)
      act.setChecked(theme_id == self.settings.theme_id)
      act.triggered.connect(lambda checked, tid=theme_id: self._set_theme(tid) if checked else None)
      self._theme_group.addAction(act)
      theme_menu.addAction(act)

    # Shown only while an M3U playlist is loaded (replaces old Tools menu)
    self._playlist_groups_menu = self.menuBar().addMenu("Playlist groups")
    self._playlist_groups_menu.menuAction().setVisible(False)

    self._help_menu = self.menuBar().addMenu("&Help")
    self._add_action(self._help_menu, f"About {APP_NAME}", "", self.show_about)
    self._add_action(self._help_menu, "Check for updates…", "", lambda: self.check_for_updates(manual=True))

  def _add_action(self, menu, text, shortcut, slot):
    act = QAction(text, self)
    if shortcut:
      act.setShortcut(QKeySequence(shortcut))
    act.triggered.connect(slot)
    menu.addAction(act)
    if shortcut and shortcut not in {"Ctrl+O", "Ctrl+S", "Ctrl+,", "Ctrl+Q"}:
      # Also register global shortcuts that menus might not catch when focused elsewhere
      pass
    return act

  def _apply_style(self):
    self.setStyleSheet(
        app_stylesheet(self.settings.theme_id, self.settings.subtitle_font_size)
    )
    self._refresh_control_icons()

  def _refresh_control_icons(self):
    """Tint control icons to the active theme (text / accent_text / accent)."""
    if not hasattr(self, "btn_play"):
      return
    theme = get_theme(self.settings.theme_id)
    text = theme.text
    muted = theme.muted
    accent = theme.accent
    accent_text = theme.accent_text

    apply_icon(self.btn_shot, "screenshot", text)
    apply_icon(self.btn_dl, "download", text)
    apply_icon(self.btn_prev, "prev", text)
    apply_icon(self.btn_back, "seek_back", text)
    apply_icon(self.btn_fwd, "seek_forward", text)
    apply_icon(self.btn_next, "next", text)
    self._sync_repeat_ui()
    apply_icon(self.btn_speed_down, "speed_down", text)
    apply_icon(self.btn_speed_up, "speed_up", text)

    playing = (
        hasattr(self, "media_player")
        and self.media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState
    )
    apply_icon(self.btn_play, "pause" if playing else "play", accent_text)
    self.btn_play.setToolTip("Pause (Space)" if playing else "Play (Space)")

    is_muted = False
    if hasattr(self, "audio_output"):
      try:
        is_muted = bool(self.audio_output.isMuted()) or self.volume_slider.value() == 0
      except Exception:
        is_muted = self.btn_mute.isChecked()
    else:
      is_muted = self.btn_mute.isChecked()
    apply_icon(self.btn_mute, "volume_mute" if is_muted else "volume", accent if is_muted else text)
    self.btn_mute.setToolTip("Unmute (M)" if is_muted else "Mute (M)")

    fs = self.isFullScreen()
    apply_icon(self.btn_fullscreen, "fullscreen_exit" if fs else "fullscreen", text)
    self.btn_fullscreen.setToolTip("Exit fullscreen (Esc)" if fs else "Fullscreen (F)")

    # Dim disabled speed buttons via muted tint
    if not self.btn_speed_down.isEnabled():
      apply_icon(self.btn_speed_down, "speed_down", muted)
    if not self.btn_speed_up.isEnabled():
      apply_icon(self.btn_speed_up, "speed_up", muted)

  def _set_theme(self, theme_id: str):
    self.settings.theme_id = theme_id
    self.settings.sync()
    self._apply_style()
    for act in self._theme_group.actions():
      act.setChecked(act.data() == theme_id)
    self._flash_status(f"Theme: {theme_id.replace('_', ' ')}")

  def _set_aspect_mode(self, mode_id: str):
    self.settings.aspect_mode = mode_id
    self.settings.sync()
    self._apply_aspect_mode(mode_id)
    for act in self._aspect_group.actions():
      act.setChecked(act.data() == mode_id)
    label = next((lbl for mid, lbl in aspect_choices() if mid == mode_id), mode_id)
    self._flash_status(f"Aspect: {label}")

  def _apply_aspect_mode(self, mode_id: str | None = None):
    mode_id = mode_id or self.settings.aspect_mode
    self.video_host.set_aspect_mode(mode_id)

  def _wire_player(self):
    self.media_player.positionChanged.connect(self.position_changed)
    self.media_player.durationChanged.connect(self.duration_changed)
    self.media_player.playbackStateChanged.connect(self._on_state_changed)
    self.media_player.errorOccurred.connect(self._on_error)
    self.media_player.mediaStatusChanged.connect(self._on_media_status)
    self.media_player.metaDataChanged.connect(self._on_meta_data)
    self.media_player.tracksChanged.connect(self._on_tracks_changed)

  def _setup_shortcuts(self):
    # Space se hvata u keyPressEvent (pouzdanije od QAction + fokusiranih dugmadi)
    for key, slot in [
        (Qt.Key.Key_F, self.toggle_fullscreen),
        (Qt.Key.Key_Escape, self._exit_fullscreen),
        (Qt.Key.Key_Left, lambda: self._skip(-self._seek_step_ms())),
        (Qt.Key.Key_Right, lambda: self._skip(self._seek_step_ms())),
        (Qt.Key.Key_M, self.toggle_mute),
        (Qt.Key.Key_O, self.open_file),
        (Qt.Key.Key_S, self.open_subtitles),
        (Qt.Key.Key_C, self.show_subtitle_menu),
        (Qt.Key.Key_P, self.take_screenshot),
        (Qt.Key.Key_BracketLeft, self.speed_down),
        (Qt.Key.Key_BracketRight, self.speed_up),
        (Qt.Key.Key_R, self.reset_speed),
        (Qt.Key.Key_N, self.play_next),
        (Qt.Key.Key_B, self.play_previous),
        (Qt.Key.Key_PageDown, self.play_next),
        (Qt.Key.Key_PageUp, self.play_previous),
        (Qt.Key.Key_Equal, lambda: self.adjust_subtitle_delay(100)),
        (Qt.Key.Key_Minus, lambda: self.adjust_subtitle_delay(-100)),
    ]:
      act = QAction(self)
      act.setShortcut(QKeySequence(key))
      act.setShortcutContext(Qt.ShortcutContext.WindowShortcut)
      act.triggered.connect(slot)
      self.addAction(act)

  def keyPressEvent(self, event):
    if event.key() == Qt.Key.Key_Space and not event.isAutoRepeat():
      self.toggle_play()
      event.accept()
      return
    super().keyPressEvent(event)

  def _seek_step_ms(self) -> int:
    return self.settings.seek_step_sec * 1000

  def _flash_status(self, text: str, ms: int = 2500):
    self.status_label.setText(text)
    if self.settings.low_power:
      # No status clear timer — leave text until replaced
      return
    self._status_timer.start(ms)

  def _apply_volume_from_settings(self):
    vol = self.settings.volume if self.settings.remember_volume else 40
    self._volume_before_mute = max(vol, 1)
    self.volume_slider.blockSignals(True)
    self.volume_slider.setValue(vol)
    self.volume_slider.blockSignals(False)
    self.audio_output.setVolume(vol / 100.0)
    self.audio_output.setMuted(False)
    self.btn_mute.setChecked(False)
    self.volume_label.setText(f"{vol}%")
    if hasattr(self, "_refresh_mute_icon"):
      self._refresh_mute_icon()

  def open_settings(self):
    dlg = SettingsDialog(self.settings, self)
    if dlg.exec():
      dlg.apply()
      self._apply_style()
      self._apply_aspect_mode(self.settings.aspect_mode)
      for act in self._theme_group.actions():
        act.setChecked(act.data() == self.settings.theme_id)
      for act in self._aspect_group.actions():
        act.setChecked(act.data() == self.settings.aspect_mode)
      if self.settings.remember_volume:
        self.volume_slider.setValue(self.settings.volume)
      if self._use_mpv and hasattr(self.media_player, "set_hardware_decoding"):
        self.media_player.set_hardware_decoding(self.settings.hardware_decoding)
      self._apply_sub_delay()
      self._sync_repeat_ui()
      self._flash_status("Settings saved")
    else:
      self._apply_style()
      for act in self._theme_group.actions():
        act.setChecked(act.data() == self.settings.theme_id)

  def show_about(self):
    box = QMessageBox(self)
    box.setWindowTitle(f"About {APP_NAME}")
    box.setIcon(QMessageBox.Icon.Information)
    box.setTextFormat(Qt.TextFormat.RichText)
    box.setText(
        f"<b>{APP_NAME}</b> {__version__}<br><br>"
        "A lightweight cross-platform video player.<br>"
        "Linux · Windows · macOS<br><br>"
        '<a href="https://yumedija.com">https://yumedija.com</a><br><br>'
        "Built with Python &amp; PyQt6."
    )
    box.setStandardButtons(QMessageBox.StandardButton.Ok)
    box.exec()

  # --- speed -----------------------------------------------------------

  def speed_down(self):
    if self._speed_idx > 0:
      self._speed_idx -= 1
      self._apply_speed()
      self._bump_controls()

  def speed_up(self):
    if self._speed_idx < len(SPEED_PRESETS) - 1:
      self._speed_idx += 1
      self._apply_speed()
      self._bump_controls()

  def reset_speed(self):
    self._speed_idx = SPEED_PRESETS.index(1.0)
    self._apply_speed()
    self._bump_controls()

  def _apply_speed(self):
    rate = SPEED_PRESETS[self._speed_idx]
    self.media_player.setPlaybackRate(rate)
    self.settings.playback_rate = rate
    self.btn_speed.setText(f"{rate:.2f}x")
    self.btn_speed.setProperty("active", rate != 1.0)
    self.btn_speed.style().unpolish(self.btn_speed)
    self.btn_speed.style().polish(self.btn_speed)
    self.btn_speed_down.setEnabled(self._speed_idx > 0)
    self.btn_speed_up.setEnabled(self._speed_idx < len(SPEED_PRESETS) - 1)
    if hasattr(self, "_refresh_control_icons"):
      theme = get_theme(self.settings.theme_id)
      apply_icon(
          self.btn_speed_down,
          "speed_down",
          theme.text if self.btn_speed_down.isEnabled() else theme.muted,
      )
      apply_icon(
          self.btn_speed_up,
          "speed_up",
          theme.text if self.btn_speed_up.isEnabled() else theme.muted,
      )

  # --- files -----------------------------------------------------------

  def open_file(self):
    start = self.settings.last_dir or ""
    file_name, _ = QFileDialog.getOpenFileName(self, "Open Video", start, VIDEO_FILTER)
    if file_name:
      self.load_video(file_name)

  def load_video(self, file_name: str, autoplay: bool = True) -> bool:
    """Open a video path (from dialog or file-manager / CLI)."""
    self._remember_resume_position()
    path = resolve_cli_path(file_name)
    if path is None:
      # Plain path that may not yet be normalized
      candidate = Path(file_name).expanduser()
      if candidate.is_file():
        path = candidate.resolve()
      else:
        QMessageBox.warning(self, APP_NAME, f"File not found:\n{file_name}")
        return False
    file_name = str(path)

    self.settings.last_dir = str(Path(file_name).parent)
    self.settings.push_recent(file_name)
    self._rebuild_folder_list(file_name)
    self._playlist_index = -1
    self._video_path = file_name
    self._source_url = None
    self._play_url = file_name
    self._pending_seek_ms = None
    self._probe_langs = probe_stream_languages(file_name)
    self._duration_ms = 0
    self._duration_attempts = 0
    self._probe_gen += 1
    self.position_slider.setRange(0, 0)
    self.time_current.setText("00:00")
    self.time_total.setText("LIVE" if looks_like_live(file_name) else "--:--")
    self.stage.setCurrentWidget(self.video_host)
    self.media_player.setSource(QUrl.fromLocalFile(file_name))
    name = Path(file_name).name
    self.setWindowTitle(f"{APP_NAME} — {name}")
    self._flash_status("")
    self._update_download_button()
    if self.settings.auto_load_srt:
      self._auto_load_srt(file_name)
    else:
      self._clear_subtitles()
    if autoplay:
      self.media_player.play()
    self._bump_controls()
    self.raise_()
    self.activateWindow()
    # Immediate probe (MKV often has duration in container even if Qt says 0)
    QTimer.singleShot(50, self._refresh_duration)
    self._duration_timer.start()
    QTimer.singleShot(400, self._try_resume_position)
    return True

  def open_url_dialog(self):
    dlg = UrlDialog(theme_id=self.settings.theme_id, parent=self)
    if dlg.exec() and dlg.url():
      self.open_url(dlg.url())

  def open_url(self, url: str) -> None:
    url = url.strip()
    if not url:
      return
    if not url.startswith(("http://", "https://")):
      # Treat as local playlist/video path
      path = Path(url).expanduser()
      if path.suffix.lower() in PLAYLIST_EXTENSIONS:
        self.load_playlist_source(str(path))
      else:
        self.load_video(str(path))
      return
    if looks_like_playlist_url(url):
      self.load_playlist_source(url)
      return
    title = url
    self.play_stream(url, title)

  def open_playlist_file(self):
    start = self.settings.last_dir or ""
    file_name, _ = QFileDialog.getOpenFileName(
        self, "Open M3U Playlist", start, PLAYLIST_FILTER
    )
    if file_name:
      self.settings.last_dir = str(Path(file_name).parent)
      self.load_playlist_source(file_name)

  def load_playlist_source(self, source: str) -> None:
    src = source.strip()
    if src.startswith(("http://", "https://")):
      self._playlist_source_url = src
      self._http_referer = src
    else:
      self._playlist_source_url = None
      self._http_referer = None
    try:
      entries = load_playlist(source)
    except Exception as exc:  # noqa: BLE001
      QMessageBox.warning(self, "Playlist", str(exc))
      return
    if not entries:
      QMessageBox.information(self, "Playlist", "No entries found in playlist.")
      return
    self._playlist_entries = entries
    self._playlist_by_group = dict(group_entries(entries))
    self._playlist_index = -1
    self._folder_files = []
    self._folder_index = -1
    self.settings.push_recent(source)
    self._close_playlist_act.setEnabled(True)
    self._rebuild_category_menus()
    self._flash_status(f"Playlist: {len(entries)} item(s)")
    self.setWindowTitle(f"{APP_NAME} — Playlist")

  def close_playlist(self):
    self._playlist_entries = []
    self._playlist_by_group = {}
    self._playlist_source_url = None
    self._http_referer = None
    self._hidden_groups.clear()
    self._close_playlist_act.setEnabled(False)
    self._clear_category_menus()
    self._flash_status("Playlist closed")

  def _clear_category_menus(self):
    self._playlist_groups_menu.clear()
    self._playlist_groups_menu.menuAction().setVisible(False)
    self._category_menus.clear()

  def _rebuild_category_menus(self):
    """Flat group list — click opens channels (no hover auto-submenu)."""
    self._playlist_groups_menu.clear()
    self._category_menus.clear()
    if not self._playlist_entries:
      self._playlist_groups_menu.menuAction().setVisible(False)
      return
    self._playlist_groups_menu.menuAction().setVisible(True)
    groups = self._playlist_by_group or dict(group_entries(self._playlist_entries))
    self._playlist_by_group = groups
    visible = [(n, items) for n, items in groups.items() if n not in self._hidden_groups]
    for group_name, items in visible:
      label = group_name if len(group_name) <= 36 else group_name[:35] + "…"
      act = QAction(f"{label}  ({len(items)})", self)
      # Pass group name only — copying tens of thousands of entries into every
      # lambda freezes the UI when rebuilding menus on large M3Us.
      act.triggered.connect(lambda _c=False, n=group_name: self._open_group_popup_by_name(n))
      self._playlist_groups_menu.addAction(act)

    self._playlist_groups_menu.addSeparator()
    if visible:
      hide_menu = self._playlist_groups_menu.addMenu("Hide group")
      for group_name, _items in visible:
        h = QAction(group_name, self)
        h.triggered.connect(lambda _c=False, n=group_name: self._hide_group(n))
        hide_menu.addAction(h)
    if self._hidden_groups:
      show_menu = self._playlist_groups_menu.addMenu("Show hidden group")
      for name in sorted(self._hidden_groups):
        if name not in groups:
          continue
        s = QAction(name, self)
        s.triggered.connect(lambda _c=False, n=name: self._show_group(n))
        show_menu.addAction(s)
      show_all = QAction("Show all groups", self)
      show_all.triggered.connect(self._show_all_groups)
      self._playlist_groups_menu.addAction(show_all)

  def _open_group_popup_by_name(self, group_name: str) -> None:
    items = list((self._playlist_by_group or {}).get(group_name) or [])
    self._open_group_popup(group_name, items)

  def _open_group_popup(self, group_name: str, items: list):
    menu = QMenu(self)
    menu.setTitle(group_name)
    menu.setToolTipsVisible(True)
    shown = items[:MENU_CHANNEL_CAP]
    for entry in shown:
      act = QAction(entry.title, self)
      act.setToolTip(entry.url)
      act.triggered.connect(
          lambda _c=False, u=entry.url, tit=entry.title: self.play_playlist_entry(u, tit)
      )
      menu.addAction(act)
    if len(items) > MENU_CHANNEL_CAP:
      menu.addSeparator()
      note = QAction(f"…and {len(items) - MENU_CHANNEL_CAP} more", self)
      note.setEnabled(False)
      menu.addAction(note)
    menu.addSeparator()
    hide = QAction("Hide this group", self)
    hide.triggered.connect(lambda: self._hide_group(group_name))
    menu.addAction(hide)
    # Open at cursor — click only, not hover cascade
    menu.exec(QCursor.pos())

  def _hide_group(self, name: str):
    self._hidden_groups.add(name)
    self._rebuild_category_menus()
    self._flash_status(f"Hidden: {name}")

  def _show_group(self, name: str):
    self._hidden_groups.discard(name)
    self._rebuild_category_menus()
    self._flash_status(f"Shown: {name}")

  def _show_all_groups(self):
    self._hidden_groups.clear()
    self._rebuild_category_menus()
    self._flash_status("All groups shown")

  def play_stream(self, url: str, title: str = "") -> None:
    """Play a remote stream / YT / IPTV URL."""
    url = url.strip()
    if not url:
      return
    title = title or url
    # Let the playlist menu close before we start loading.
    QTimer.singleShot(0, lambda u=url, t=title: self._play_stream_now(u, t))

  def _play_stream_now(self, url: str, title: str) -> None:
    self._remember_resume_position()
    self._clear_subtitles()
    self._video_path = None
    self._source_url = url
    if url.startswith(("http://", "https://")):
      self.settings.push_recent(url)
    self._play_url = None
    self._pending_seek_ms = None
    self._probe_langs = {"audio": [], "subtitle": []}
    self._duration_ms = 0
    self._duration_attempts = 0
    self._probe_gen += 1
    self._http_error_retries = 0
    self._last_error_msg = ""
    self.position_slider.setRange(0, 0)
    self.time_current.setText("00:00")
    self.time_total.setText("--:--")
    self.setWindowTitle(f"{APP_NAME} — {title}")
    self._update_download_button()

    if url.startswith(("http://", "https://")) and needs_ytdlp(url):
      self._flash_status("Fetching stream…")
      self._start_resolve(url, title)
      return

    self._play_resolved(url, title)

  def _start_resolve(self, url: str, title: str):
    if self._net_worker and self._net_worker.isRunning():
      self._flash_status("Busy…")
      return
    self._net_worker = _ResolveWorker(url, title)
    self._net_worker.finished_ok.connect(self._on_resolve_ok)
    self._net_worker.failed.connect(self._on_resolve_fail)
    self._net_worker.start()

  def _on_resolve_ok(self, play_url: str, title: str):
    self._play_resolved(play_url, title)

  def _on_resolve_fail(self, message: str):
    self._flash_status("Resolve failed")
    QMessageBox.warning(self, "Open YT URL", message)

  def _on_mpv_surface_changed(self, widget) -> None:
    """Keep window reference in sync after VOD→live surface swap."""
    self.video_widget = widget

  def _play_resolved(self, play_url: str, title: str):
    self.stage.setCurrentWidget(self.video_host)
    path = Path(play_url)
    self._play_url = play_url
    self._pending_seek_ms = None
    self._http_error_retries = 0
    self._last_error_msg = ""
    if path.is_file():
      self._video_path = str(path)
      self._probe_langs = probe_stream_languages(str(path))
      self.media_player.setSource(QUrl.fromLocalFile(str(path)))
    else:
      self._video_path = None
      # Direct HTTP(S) VOD / IPTV (e.g. .mkv series links from M3U)
      if play_url.startswith(("http://", "https://")):
        os.environ.setdefault("GST_CURL_USERAGENT", "VLC/3.0.21 LibVLC/3.0.21")
        if self._http_referer:
          os.environ["GST_CURL_REFERRER"] = self._http_referer
        elif "GST_CURL_REFERRER" in os.environ:
          del os.environ["GST_CURL_REFERRER"]
        if self._use_mpv and hasattr(self.media_player, "set_http_headers"):
          self.media_player.set_http_headers(referer=self._http_referer)
      qurl = QUrl.fromUserInput(play_url)
      if not qurl.isValid():
        qurl = QUrl(play_url)
      self.media_player.setSource(qurl)
    # setSource already starts playback for mpv; play() is a no-op resume
    self.media_player.play()
    self._flash_status(title if len(title) < 48 else title[:45] + "…")
    self._bump_controls()
    if self._is_live_playback() or looks_like_live(play_url):
      # Never run the duration timer/ffprobe path for live — the final sync
      # probe_duration_ms() call freezes the GUI for up to ~30s.
      self._duration_timer.stop()
      self._duration_ms = 0
      self.time_total.setText("LIVE")
      self.position_slider.setRange(0, 0)
    else:
      QTimer.singleShot(50, self._refresh_duration)
      self._duration_timer.start()
      self._start_duration_probe()

  def _probe_target(self) -> str | None:
    if self._video_path:
      return self._video_path
    if self._play_url and (
        self._play_url.startswith(("http://", "https://")) or Path(self._play_url).is_file()
    ):
      return self._play_url
    if self._source_url and self._source_url.startswith(("http://", "https://")):
      return self._source_url
    return None

  def _is_live_playback(self) -> bool:
    """True when the current (or about-to-play) source is live IPTV/HLS."""
    if self._use_mpv and hasattr(self.media_player, "is_live") and self.media_player.is_live():
      return True
    for candidate in (self._play_url, self._source_url):
      if candidate and looks_like_live(candidate):
        return True
    return False

  def _start_duration_probe(self):
    target = self._probe_target()
    if not target:
      return
    # Live IPTV: never ffprobe — it blocks/wrongly invents a short duration.
    if looks_like_live(target) or self._is_live_playback():
      self._duration_ms = 0
      self.time_total.setText("LIVE")
      self.position_slider.setRange(0, 0)
      self._duration_timer.stop()
      return
    # Local files are probed quickly by existing tick; remote needs ffprobe UA
    if not target.startswith(("http://", "https://")):
      return
    if self._duration_worker and self._duration_worker.isRunning():
      return
    gen = self._probe_gen
    worker = _DurationProbeWorker(target, referer=self._http_referer)
    self._duration_worker = worker
    worker.finished_ok.connect(lambda ms, g=gen: self._on_duration_probed(ms, g))
    worker.finished.connect(worker.deleteLater)
    worker.start()

  def _flush_pending_seek(self) -> None:
    if self._pending_seek_ms is None:
      return
    if self._effective_duration() <= 0:
      return
    pos = self._pending_seek_ms
    self._pending_seek_ms = None
    QTimer.singleShot(80, lambda: self._seek_to(pos, resume=True))

  def _on_duration_probed(self, ms: int, gen: int | None = None):
    # Drop results from a previous channel/movie after the user already switched.
    if gen is not None and gen != self._probe_gen:
      return
    if ms > 0:
      self._apply_duration(ms, "ffprobe-http")
      self._flush_pending_seek()

  def _update_download_button(self):
    yt = bool(self._source_url and is_youtube_url(self._source_url))
    self.btn_dl.setVisible(yt)
    self.btn_dl.setEnabled(yt)
    if hasattr(self, "_dl_menu_act"):
      self._dl_menu_act.setVisible(yt)
      self._dl_menu_act.setEnabled(yt)

  def download_current(self):
    url = self._source_url
    if not url or not is_youtube_url(url):
      QMessageBox.information(
          self,
          "Download",
          "Download is only available for YouTube videos.\n"
          "Open a YouTube URL first (File → Open YT URL).",
      )
      return
    dest = str(Path.home() / "Downloads")
    if self.settings.ask_download_path:
      chosen = QFileDialog.getExistingDirectory(self, "Download folder", dest)
      if not chosen:
        return
      dest = chosen
    if self._net_worker and self._net_worker.isRunning():
      self._flash_status("Busy…")
      return
    self._flash_status("Downloading…")
    self.btn_dl.setEnabled(False)
    self._net_worker = _DownloadWorker(url, dest)
    self._net_worker.finished_ok.connect(self._on_download_ok)
    self._net_worker.failed.connect(self._on_download_fail)
    self._net_worker.start()

  def _on_download_ok(self, dest_dir: str):
    self._update_download_button()
    self._flash_status(f"Saved to {Path(dest_dir).name}")
    QMessageBox.information(self, "Download", f"Download finished:\n{dest_dir}")

  def _on_download_fail(self, message: str):
    self._update_download_button()
    self._flash_status("Download failed")
    QMessageBox.warning(self, "Download", message)

  def open_path_args(self, args: list[str]) -> None:
    """Handle paths passed by the OS / file manager (mp4 click, drag, CLI)."""
    videos: list[str] = []
    playlists: list[str] = []
    urls: list[str] = []
    subs: list[str] = []
    for arg in args:
      raw = arg.strip().strip('"').strip("'")
      if raw.startswith(("http://", "https://")):
        urls.append(raw)
        continue
      path = resolve_cli_path(arg)
      if path is None:
        continue
      if path.is_dir():
        for child in sorted(path.iterdir()):
          if child.is_file() and child.suffix.lower() in VIDEO_EXTENSIONS:
            videos.append(str(child.resolve()))
        continue
      ext = path.suffix.lower()
      if ext == ".srt":
        subs.append(str(path))
      elif ext in PLAYLIST_EXTENSIONS:
        playlists.append(str(path))
      elif ext in VIDEO_EXTENSIONS:
        videos.append(str(path))
      elif path.is_file() and not videos:
        videos.append(str(path))

    if playlists:
      self.load_playlist_source(playlists[0])
    elif urls:
      self.open_url(urls[0])
    elif videos:
      self.load_video(videos[0], autoplay=True)
    for srt in subs:
      self._add_subtitle_track(srt, select=False)
    if subs and self.sub_tracks:
      self._set_active_track(len(self.sub_tracks) - 1)

  def open_subtitles(self):
    start = self.settings.last_dir or ""
    files, _ = QFileDialog.getOpenFileNames(
        self,
        "Open Subtitles (multi-language)",
        start,
        "Subtitles (*.srt);;All Files (*)",
    )
    if not files:
      return
    for path in files:
      self._add_subtitle_track(path, select=False)
    # Select last added
    if self.sub_tracks:
      self._set_active_track(len(self.sub_tracks) - 1)
      labels = ", ".join(t.label for t in self.sub_tracks)
      self._flash_status(f"Subtitles: {labels}")

  def show_subtitle_menu(self):
    """Keyboard shortcut (C) — same entries as Subtitles menu."""
    menu = QMenu(self)
    self._fill_subtitle_menu(menu)
    menu.exec(QCursor.pos())

  def _populate_subtitle_menu(self):
    self._sub_menu.clear()
    self._fill_subtitle_menu(self._sub_menu)

  def _fill_subtitle_menu(self, menu: QMenu):
    off = menu.addAction("External: Off")
    off.setCheckable(True)
    off.setChecked(self._active_track < 0)
    off.triggered.connect(lambda: self._set_active_track(-1))

    if self.sub_tracks:
      for i, track in enumerate(self.sub_tracks):
        label = f"External: {track.label}  ({track.cue_count})"
        act = menu.addAction(label)
        act.setCheckable(True)
        act.setChecked(i == self._active_track)
        act.triggered.connect(lambda checked, idx=i: self._set_active_track(idx))

    emb = self.media_player.subtitleTracks()
    if emb:
      menu.addSeparator()
      emb_off = menu.addAction("Embedded: Off")
      emb_off.setCheckable(True)
      emb_off.setChecked(self.media_player.activeSubtitleTrack() < 0)
      emb_off.triggered.connect(lambda: self._set_embedded_subtitle(-1))
      for i, meta in enumerate(emb):
        act = menu.addAction(f"Embedded: {self._meta_track_label(meta, i, 'Subtitle')}")
        act.setCheckable(True)
        act.setChecked(i == self.media_player.activeSubtitleTrack())
        act.triggered.connect(lambda checked, idx=i: self._set_embedded_subtitle(idx))

    menu.addSeparator()
    menu.addAction("Add subtitle files…", self.open_subtitles)
    menu.addAction("Search OpenSubtitles…", self.search_opensubtitles)
    if self.sub_tracks:
      menu.addAction("Clear external", self._clear_subtitles)

    menu.addSeparator()
    delay = int(self.settings.subtitle_delay_ms)
    lab = menu.addAction(f"Delay: {delay:+d} ms")
    lab.setEnabled(False)
    act_p = menu.addAction("Delay +100 ms")
    act_p.setShortcut(QKeySequence("="))
    act_p.triggered.connect(lambda: self.adjust_subtitle_delay(100))
    act_m = menu.addAction("Delay −100 ms")
    act_m.setShortcut(QKeySequence("-"))
    act_m.triggered.connect(lambda: self.adjust_subtitle_delay(-100))
    menu.addAction("Reset Delay").triggered.connect(
        lambda: self.adjust_subtitle_delay(0, absolute=True)
    )


  def _meta_track_label(self, meta: QMediaMetaData, index: int, kind: str) -> str:
    """Human label for embedded audio/subtitle — prefer real language names."""
    title = (meta.stringValue(QMediaMetaData.Key.Title) or "").strip()
    desc = (meta.stringValue(QMediaMetaData.Key.Description) or "").strip()
    lang_raw = self._meta_language_code(meta)

    # ffprobe fallback (Qt often reports "Default" for every track)
    probe_key = "audio" if kind.lower().startswith("audio") else "subtitle"
    probed = ""
    probed_title = ""
    plist = self._probe_langs.get(probe_key) or []
    if 0 <= index < len(plist) and plist[index]:
      raw = plist[index]
      if "|" in raw:
        probed, probed_title = raw.split("|", 1)
      elif raw.startswith("|"):
        probed_title = raw[1:]
      else:
        probed = raw

    lang_code = lang_raw or probed
    lang_name = self._language_display_name(lang_code)

    # Ignore useless container titles
    junk = {"", "default", "track", "subtitle", "audio", "und", "unknown", "null"}
    nice_title = ""
    for candidate in (title, desc, probed_title):
      if candidate and candidate.strip().lower() not in junk:
        # If title is just a language code/name we already show, skip
        if lang_name and candidate.strip().lower() in {
            lang_name.lower(),
            lang_code.lower(),
        }:
          continue
        nice_title = candidate.strip()
        break

    if lang_name and nice_title:
      return f"{lang_name} — {nice_title}"
    if lang_name:
      return lang_name
    if nice_title:
      return nice_title
    return f"{kind} {index + 1}"

  def _meta_language_code(self, meta: QMediaMetaData) -> str:
    # stringValue
    s = (meta.stringValue(QMediaMetaData.Key.Language) or "").strip()
    if s:
      return s
    # value() may be QLocale
    try:
      val = meta.value(QMediaMetaData.Key.Language)
    except Exception:
      return ""
    if val is None:
      return ""
    if isinstance(val, QLocale):
      # bcp47LanguageTag e.g. en-US
      try:
        tag = val.bcp47Name()
      except Exception:
        tag = ""
      return (tag or "").split("-")[0]
    text = str(val).strip()
    if text.lower() in ("default", "und", "unknown", ""):
      return ""
    return text

  def _language_display_name(self, code: str) -> str:
    if not code:
      return ""
    raw = code.strip().replace("_", "-")
    lower = raw.lower()
    if lower in ("und", "unk", "unknown", "default", "null", "zxx", "mis"):
      return ""

    # Common 3-letter / alias fixes QLocale sometimes misses
    aliases = {
        "eng": "en",
        "ger": "de",
        "deu": "de",
        "fre": "fr",
        "fra": "fr",
        "spa": "es",
        "ita": "it",
        "por": "pt",
        "rus": "ru",
        "tur": "tr",
        "chi": "zh",
        "zho": "zh",
        "jpn": "ja",
        "kor": "ko",
        "ara": "ar",
        "hin": "hi",
        "dut": "nl",
        "nld": "nl",
        "pol": "pl",
        "cze": "cs",
        "ces": "cs",
        "slo": "sk",
        "slk": "sk",
        "slv": "sl",
        "hrv": "hr",
        "bos": "bs",
        "srp": "sr",
        "scc": "sr",
        "scr": "hr",
        "alb": "sq",
        "sqi": "sq",
        "mac": "mk",
        "mkd": "mk",
        "rum": "ro",
        "ron": "ro",
        "gre": "el",
        "ell": "el",
        "may": "ms",
        "msa": "ms",
        "ice": "is",
        "isl": "is",
        "heb": "he",
        "per": "fa",
        "fas": "fa",
        "ukr": "uk",
        "hun": "hu",
        "fin": "fi",
        "swe": "sv",
        "nor": "no",
        "dan": "da",
    }
    lookup = aliases.get(lower, lower)
    if len(lookup) > 3 and "-" in lookup:
      lookup = lookup.split("-", 1)[0]

    loc = QLocale(lookup)
    if loc.language() != QLocale.Language.C:
      name = loc.nativeLanguageName() or QLocale.languageToString(loc.language())
      if name and name not in ("C", "Default"):
        return name[:1].upper() + name[1:] if name else ""

    # English fallback names for codes QLocale maps poorly
    en_names = {
        "bs": "Bosnian",
        "hr": "Croatian",
        "sr": "Serbian",
        "cnr": "Montenegrin",
        "sq": "Albanian",
        "mk": "Macedonian",
    }
    if lookup in en_names:
      return en_names[lookup]
    # Last resort: show uppercase code
    return lookup.upper() if 2 <= len(lookup) <= 3 else ""

  def _set_embedded_subtitle(self, index: int):
    """Switch embedded softsubs like VLC (libmpv sid / Qt track API)."""
    # Prefer one subtitle source: turn off external overlay when using embedded
    if index >= 0 and self._active_track >= 0:
      self._active_track = -1
      self._current_cue_idx = -1
      self.subtitle_label.hide()
      self.subtitle_label.setText("")
    try:
      self.media_player.setActiveSubtitleTrack(index)
    except Exception as exc:  # noqa: BLE001
      self._flash_status(f"Subtitle switch failed: {exc}")
      return
    if index >= 0:
      tracks = self.media_player.subtitleTracks()
      label = (
          self._meta_track_label(tracks[index], index, "Subtitle")
          if index < len(tracks)
          else str(index + 1)
      )
      self._flash_status(f"Subtitle: {label}")
    else:
      self._flash_status("Embedded subtitles off")
    self._refresh_sub_tooltip()

  def _populate_audio_menu(self):
    self._audio_menu.clear()
    tracks = self.media_player.audioTracks()
    if not tracks:
      act = QAction("(no audio tracks detected)", self)
      act.setEnabled(False)
      self._audio_menu.addAction(act)
      return
    group = QActionGroup(self._audio_menu)
    group.setExclusive(True)
    active = self.media_player.activeAudioTrack()
    for i, meta in enumerate(tracks):
      act = QAction(self._meta_track_label(meta, i, "Audio"), self, checkable=True)
      act.setChecked(i == active)
      act.triggered.connect(lambda checked, idx=i: self._set_audio_track(idx) if checked else None)
      group.addAction(act)
      self._audio_menu.addAction(act)

  def _set_audio_track(self, index: int):
    try:
      self.media_player.setActiveAudioTrack(index)
    except Exception:
      return
    tracks = self.media_player.audioTracks()
    label = self._meta_track_label(tracks[index], index, "Audio") if 0 <= index < len(tracks) else str(index)
    self._flash_status(f"Audio: {label}")

  def _on_tracks_changed(self):
    self._set_cc_active(
        self._active_track >= 0 or self.media_player.activeSubtitleTrack() >= 0
    )
    self._refresh_sub_tooltip()

  def search_opensubtitles(self):
    key = self.settings.opensubtitles_api_key
    if not key:
      QMessageBox.information(
          self,
          "OpenSubtitles",
          "Add a free API key in Settings → Subtitles.\n\n"
          "Create one at:\nhttps://www.opensubtitles.com/en/consumers",
      )
      self.open_settings()
      return
    dlg = SubtitleSearchDialog(
        api_key=key,
        video_path=self._video_path,
        languages=self.settings.opensubtitles_languages,
        theme_id=self.settings.theme_id,
        parent=self,
    )
    if dlg.exec() and dlg.downloaded_path:
      if self._add_subtitle_track(dlg.downloaded_path, select=True):
        self._flash_status(f"Downloaded: {Path(dlg.downloaded_path).name}")
      else:
        QMessageBox.warning(self, "Subtitles", "Downloaded file could not be loaded.")

  def _auto_load_srt(self, video_path: str):
    self._clear_subtitles(update_ui=False)
    paths = discover_sidecar_srts(video_path)
    for path in paths:
      self._add_subtitle_track(str(path), select=False)
    if self.sub_tracks:
      self._set_active_track(0)
      self._flash_status(
          "Subs: " + " · ".join(t.label for t in self.sub_tracks)
      )
    else:
      self._set_cc_active(False)

  def _add_subtitle_track(self, path: str, select: bool = True) -> bool:
    # Skip duplicates
    resolved = str(Path(path).resolve())
    for i, track in enumerate(self.sub_tracks):
      if str(Path(track.path).resolve()) == resolved:
        if select:
          self._set_active_track(i)
        return True
    video_stem = Path(self._video_path).stem if self._video_path else None
    try:
      track = load_track(path, video_stem)
    except OSError:
      return False
    if not track.cues:
      return False
    # Unique label if collision
    base = track.label
    labels = {t.label for t in self.sub_tracks}
    if base in labels:
      track.label = f"{base} ({Path(path).name})"
    self.sub_tracks.append(track)
    if self._use_mpv and hasattr(self.media_player, "add_external_subtitle") and select:
      if self.media_player.add_external_subtitle(resolved):
        self._active_track = -1
        self.subtitle_label.hide()
        self.subtitle_label.setText("")
        self._flash_status(f"Subtitle: {track.label}")
        self._refresh_sub_tooltip()
        return True
    if select:
      self._set_active_track(len(self.sub_tracks) - 1)
    else:
      self._set_cc_active(True)
      self._refresh_sub_tooltip()
    return True

  def _set_active_track(self, index: int):
    if index < -1 or index >= len(self.sub_tracks):
      index = -1
    self._active_track = index
    self._current_cue_idx = -1
    self.subtitle_label.hide()
    self.subtitle_label.setText("")
    # External overlay on → turn off player softsubs
    if index >= 0:
      try:
        self.media_player.setActiveSubtitleTrack(-1)
      except Exception:
        pass
    active = index >= 0
    self._set_cc_active(active)
    self._refresh_sub_tooltip()
    if active:
      t = self.sub_tracks[index]
      self._flash_status(f"Subtitle: {t.label}")
    else:
      self._flash_status("Subtitles off")
    self._update_subtitle(self.media_player.position())

  def _clear_subtitles(self, update_ui: bool = True):
    self.sub_tracks = []
    self._active_track = -1
    self._current_cue_idx = -1
    self.subtitle_label.hide()
    self.subtitle_label.setText("")
    self._set_cc_active(False)
    self._refresh_sub_tooltip()
    if update_ui:
      self._flash_status("Subtitles cleared")

  def _active_cues(self) -> list[SubtitleCue]:
    if 0 <= self._active_track < len(self.sub_tracks):
      return self.sub_tracks[self._active_track].cues
    return []

  def _refresh_sub_tooltip(self):
    # CC button removed — status flash is enough
    return

  def _set_cc_active(self, active: bool):
    return

  def take_screenshot(self):
    fmt = self.settings.screenshot_format
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    pos = format_time(self.media_player.position()).replace(":", "-")
    stem = Path(self._video_path).stem if self._video_path else "screenshot"
    default_dir = Path(self._video_path).parent if self._video_path else Path.home() / "Pictures"
    if not default_dir.exists():
      default_dir = Path.home()
    default_path = str(default_dir / f"{stem}_{pos}_{stamp}.{fmt}")

    if self.settings.screenshot_ask_path:
      filt = "PNG (*.png);;JPEG (*.jpg *.jpeg)" if fmt == "png" else "JPEG (*.jpg *.jpeg);;PNG (*.png)"
      file_name, _ = QFileDialog.getSaveFileName(self, "Save Screenshot", default_path, filt)
      if not file_name:
        return
    else:
      file_name = default_path

    if self._use_mpv and hasattr(self.media_player, "screenshot_to_file"):
      if self.media_player.screenshot_to_file(file_name):
        self._flash_status(f"Saved {Path(file_name).name}")
      else:
        QMessageBox.warning(self, "Screenshot", "Could not save screenshot.")
      return

    image = None
    sink = getattr(self.video_widget, "videoSink", lambda: None)()
    if sink is not None:
      frame = sink.videoFrame()
      if frame.isValid():
        image = frame.toImage()
    if image is None or image.isNull():
      image = self.video_widget.grab().toImage()
    if image is None or image.isNull():
      QMessageBox.warning(self, "Screenshot", "No frame available. Play the video and try again.")
      return
    if image.save(file_name):
      self._flash_status(f"Saved {Path(file_name).name}")
    else:
      QMessageBox.warning(self, "Screenshot", "Could not save screenshot.")

  def _on_error(self, error, error_string=""):
    # Ignore aborted previous stream while switching channels/movies
    if self._use_mpv and getattr(self.media_player, "_switching", False):
      return
    msg = (error_string or self.media_player.errorString() or str(error)).strip()
    if not msg:
      msg = "Unknown playback error."
    if msg == "Playback failed" and self._play_url:
      # Live/network hiccup — soft reload instead of killing the session
      self._flash_status("Reconnecting…")
      if self._use_mpv and hasattr(self.media_player, "is_live") and self.media_player.is_live():
        play_url = self._play_url
        def _re():
          qurl = QUrl.fromUserInput(play_url)
          if not qurl.isValid():
            qurl = QUrl(play_url)
          self.media_player.setSource(qurl)
          self.media_player.play()
        QTimer.singleShot(500, _re)
      return
    now = time.monotonic()
    if msg == self._last_error_msg and (now - self._last_error_ts) < 1.5:
      return
    self._last_error_msg = msg
    self._last_error_ts = now

    play_url = self._play_url or ""
    is_http = play_url.startswith(("http://", "https://"))
    pos = int(self.media_player.position() or 0)
    if is_http and pos > 5000 and self._http_error_retries < 2:
      self._http_error_retries += 1
      saved = pos
      self._flash_status("Stream hiccup — reconnecting…")

      def retry():
        qurl = QUrl.fromUserInput(play_url)
        if not qurl.isValid():
          qurl = QUrl(play_url)
        self.media_player.stop()
        self.media_player.setSource(qurl)
        self.media_player.play()
        QTimer.singleShot(900, lambda: self._seek_to(saved, resume=True))

      QTimer.singleShot(400, retry)
      return

    self.stage.setCurrentWidget(self.welcome)
    self.welcome.setText(f"Cannot play this video\n\n{msg}")
    if self._error_box_open:
      return
    self._error_box_open = True

    def show_dialog():
      QMessageBox.warning(self, "Playback Error", msg)
      self._error_box_open = False

    QTimer.singleShot(0, show_dialog)

  # --- playback --------------------------------------------------------

  def toggle_play(self):
    if self.media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
      self.media_player.pause()
    else:
      self.media_player.play()
    self._bump_controls()

  def _on_state_changed(self, state):
    playing = state == QMediaPlayer.PlaybackState.PlayingState
    theme = get_theme(self.settings.theme_id)
    apply_icon(self.btn_play, "pause" if playing else "play", theme.accent_text)
    self.btn_play.setToolTip("Pause (Space)" if playing else "Play (Space)")
    if playing:
      self._bump_controls()
    else:
      self._show_controls()

  def _skip(self, delta_ms: int):
    pos = max(0, self.media_player.position() + delta_ms)
    self._seek_to(pos, resume=None)
    self._bump_controls()

  def toggle_mute(self):
    if self.audio_output.isMuted():
      self.audio_output.setMuted(False)
      self.btn_mute.setChecked(False)
      restore = self._volume_before_mute if self._volume_before_mute > 0 else 40
      if self.volume_slider.value() == 0:
        self.volume_slider.blockSignals(True)
        self.volume_slider.setValue(restore)
        self.volume_slider.blockSignals(False)
        self.audio_output.setVolume(restore / 100.0)
        self.volume_label.setText(f"{restore}%")
    else:
      self._volume_before_mute = max(self.volume_slider.value(), 1)
      self.audio_output.setMuted(True)
      self.btn_mute.setChecked(True)
    self._refresh_mute_icon()
    self._bump_controls()

  def _refresh_mute_icon(self):
    theme = get_theme(self.settings.theme_id)
    is_muted = bool(self.audio_output.isMuted()) or self.volume_slider.value() == 0
    apply_icon(self.btn_mute, "volume_mute" if is_muted else "volume", theme.accent if is_muted else theme.text)
    self.btn_mute.setToolTip("Unmute (M)" if is_muted else "Mute (M)")

  def set_volume(self, volume: int):
    self.audio_output.setVolume(volume / 100.0)
    self.volume_label.setText(f"{volume}%")
    if self.settings.remember_volume:
      self.settings.volume = volume
    if volume > 0:
      self._volume_before_mute = volume
      if self.audio_output.isMuted():
        self.audio_output.setMuted(False)
        self.btn_mute.setChecked(False)
    else:
      self.audio_output.setMuted(True)
      self.btn_mute.setChecked(True)
    self._refresh_mute_icon()

  def toggle_fullscreen(self):
    if self.isFullScreen():
      self.showNormal()
      self.menuBar().show()
      self._cursor_timer.stop()
      self._hide_timer.stop()
      self._last_cursor_pos = None
      self._show_controls()
    else:
      self.showFullScreen()
      self.menuBar().hide()
      self._last_cursor_pos = QCursor.pos()
      self._cursor_timer.start()
      self._show_controls()
      # Always schedule auto-hide when entering fullscreen (if enabled)
      if self.settings.hide_controls_fullscreen:
        self._hide_timer.start(1800)
    theme = get_theme(self.settings.theme_id)
    fs = self.isFullScreen()
    apply_icon(self.btn_fullscreen, "fullscreen_exit" if fs else "fullscreen", theme.text)
    self.btn_fullscreen.setToolTip("Exit fullscreen (Esc)" if fs else "Fullscreen (F)")

  def _exit_fullscreen(self):
    if self.isFullScreen():
      self.showNormal()
      self.menuBar().show()
      self._cursor_timer.stop()
      self._hide_timer.stop()
      self._last_cursor_pos = None
      self._show_controls()
      theme = get_theme(self.settings.theme_id)
      apply_icon(self.btn_fullscreen, "fullscreen", theme.text)
      self.btn_fullscreen.setToolTip("Fullscreen (F)")
      self.menuBar().show()
      self._cursor_timer.stop()
      self._hide_timer.stop()
      self._last_cursor_pos = None
      self._show_controls()

  def _poll_fullscreen_cursor(self):
    """Detect mouse move over native video surface where Qt events are unreliable."""
    if not self.isFullScreen() or not self.settings.hide_controls_fullscreen:
      return
    pos = QCursor.pos()
    if self._last_cursor_pos is None:
      self._last_cursor_pos = pos
      return
    if pos != self._last_cursor_pos:
      self._last_cursor_pos = pos
      self._bump_controls()

  # --- seek ------------------------------------------------------------

  def _effective_duration(self) -> int:
    d = int(self.media_player.duration() or 0)
    if d > 0:
      return d
    return max(0, int(self._duration_ms or 0))

  def _apply_duration(self, duration: int, source: str = "") -> None:
    duration = int(duration or 0)
    if self._use_mpv and hasattr(self.media_player, "is_live") and self.media_player.is_live():
      self._duration_ms = 0
      self.time_total.setText("LIVE")
      if not self.position_slider.dragging:
        self.position_slider.setRange(0, 0)
      return
    if duration <= 0:
      return
    # Ignore tiny/bogus values; keep the larger known duration
    if duration < 1000:
      return
    if self._duration_ms > 0 and duration < self._duration_ms * 0.5:
      return
    changed = duration != self._duration_ms or self.position_slider.maximum() != duration
    self._duration_ms = duration
    if not self.position_slider.dragging:
      self.position_slider.setRange(0, duration)
    self.time_total.setText(format_time(duration))
    if changed and source:
      self._duration_timer.stop()
    # HTTP MKV: seek may have been queued before duration was known
    if changed:
      self._flush_pending_seek()

  def _duration_from_metadata(self) -> int:
    try:
      value = self.media_player.metaData().value(QMediaMetaData.Key.Duration)
    except Exception:
      return 0
    if value is None:
      return 0
    # Qt may give QTime or int/ms
    if hasattr(value, "msecsSinceStartOfDay"):
      return int(value.msecsSinceStartOfDay())
    try:
      ms = int(value)
      return ms if ms > 0 else 0
    except (TypeError, ValueError):
      return 0

  def _refresh_duration(self) -> None:
    if self._is_live_playback():
      self._duration_ms = 0
      self.time_total.setText("LIVE")
      if not self.position_slider.dragging:
        self.position_slider.setRange(0, 0)
      self._duration_timer.stop()
      return
    d = int(self.media_player.duration() or 0)
    if d <= 0:
      d = self._duration_from_metadata()
    if d > 0:
      self._apply_duration(d, "player")
      return
    # Fallback: ffprobe (local MKV or remote HTTP VOD via background worker)
    target = self._probe_target()
    if target and self._duration_attempts >= 2:
      if target.startswith(("http://", "https://")):
        self._start_duration_probe()
      else:
        # Local only — fast. Never sync-ffprobe remote URLs here.
        probed = probe_duration_ms(target)
        if probed > 0:
          self._apply_duration(probed, "ffprobe")

  def _probe_duration_tick(self) -> None:
    # Live: stop immediately — duration stays unknown by design.
    if self._is_live_playback():
      self._duration_timer.stop()
      self._duration_ms = 0
      self.time_total.setText("LIVE")
      self.position_slider.setRange(0, 0)
      return
    self._duration_attempts += 1
    self._refresh_duration()
    if self._duration_ms > 0 or self._duration_attempts >= 30:
      self._duration_timer.stop()
      if self._duration_ms <= 0:
        target = self._probe_target()
        if not target:
          return
        # NEVER call probe_duration_ms() for HTTP on the GUI thread — ffprobe
        # can block for ~30s and freeze menus / playlist group switching.
        if target.startswith(("http://", "https://")):
          self._start_duration_probe()
          return
        probed = probe_duration_ms(target)
        if probed > 0:
          self._apply_duration(probed, "ffprobe")
        else:
          self.time_total.setText("??:??")
          self._flash_status("Duration unknown — sudo apt install ffmpeg")

  def _on_media_status(self, status):
    if status in (
        QMediaPlayer.MediaStatus.LoadedMedia,
        QMediaPlayer.MediaStatus.BufferedMedia,
        QMediaPlayer.MediaStatus.BufferingMedia,
    ):
      self._refresh_duration()
    elif status == QMediaPlayer.MediaStatus.EndOfMedia:
      self._on_end_of_media()

  def _on_meta_data(self):
    self._refresh_duration()

  def _seek_pressed(self):
    self._was_playing_before_seek = (
        self.media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState
    )
    # Ne pauziraj tokom scrub-a — pause+play na MKV često vrati na 0
    self._seek_lock = True
    self._hide_timer.stop()
    self._show_controls()
    if self.position_slider.maximum() <= 0:
      self._refresh_duration()

  def _seek_preview(self, position: int):
    self.time_current.setText(format_time(position))
    self._update_subtitle(position)

  def _seek_to(self, position: int, resume: bool | None = None) -> None:
    """Reliable seek — lock UI updates, set position, verify."""
    duration = self._effective_duration()
    position = int(position)
    if duration <= 0:
      # Duration not ready yet (common for HTTP MKV) — probe + queue seek
      self._pending_seek_ms = max(0, position)
      self._start_duration_probe()
      self._flash_status("Getting duration…")
      self.time_current.setText(format_time(position))
      return
    position = max(0, min(position, duration))

    if resume is None:
      resume = (
          self.media_player.playbackState()
          == QMediaPlayer.PlaybackState.PlayingState
          or self._was_playing_before_seek
      )

    self._seek_lock = True
    self._seek_target = position
    self.position_slider.setValue(position)
    self.time_current.setText(format_time(position))
    self._update_subtitle(position)

    # HTTP VOD often reports !seekable until buffered — still try setPosition
    if not self.media_player.isSeekable():
      self._flash_status("Seeking…")

    self.media_player.setPosition(position)
    QTimer.singleShot(80, lambda: self._finish_seek(resume))
    # Extra retry for flaky HTTP MKV range seeks
    if self._play_url and str(self._play_url).startswith(("http://", "https://")):
      QTimer.singleShot(350, lambda: self._retry_http_seek(position, resume))

  def _retry_http_seek(self, position: int, resume: bool) -> None:
    if self.position_slider.dragging:
      return
    pos = self.media_player.position()
    if position > 2000 and pos < 800:
      self.media_player.setPosition(position)
      if resume:
        self.media_player.play()

  def _finish_seek(self, resume: bool) -> None:
    target = self._seek_target
    if abs(self.media_player.position() - target) > 1500:
      self.media_player.setPosition(target)
    if resume:
      self.media_player.play()
    QTimer.singleShot(200, self._verify_seek)

  def _verify_seek(self) -> None:
    target = self._seek_target
    pos = self.media_player.position()
    if target > 3000 and pos < 800:
      self.media_player.setPosition(target)
      if self._was_playing_before_seek:
        self.media_player.play()
    self._seek_lock = False
    self._was_playing_before_seek = False

  def _seek_commit(self, position: int):
    self._seek_to(position, resume=self._was_playing_before_seek)

  def _seek_released(self):
    self._bump_controls()

  def position_changed(self, position: int):
    if (
        self._seek_lock
        or self.position_slider.dragging
        or self.position_slider.isSliderDown()
    ):
      return
    duration = self._effective_duration()
    if duration > 0 and self.position_slider.maximum() != duration:
      self.position_slider.setRange(0, duration)
      self.time_total.setText(format_time(duration))
    self.position_slider.setValue(position)
    self.time_current.setText(format_time(position))
    self._update_subtitle(position)

  def duration_changed(self, duration: int):
    self._apply_duration(duration, "signal")

  def _update_subtitle(self, position_ms: int):
    cues = self._active_cues()
    if not cues:
      self.subtitle_label.hide()
      self.subtitle_label.setText("")
      return
    position_ms = int(position_ms) - int(self.settings.subtitle_delay_ms)
    if 0 <= self._current_cue_idx < len(cues):
      cue = cues[self._current_cue_idx]
      if cue.start_ms <= position_ms <= cue.end_ms:
        return
      self._current_cue_idx = -1
      self.subtitle_label.hide()
      self.subtitle_label.setText("")
    for i, cue in enumerate(cues):
      if cue.start_ms <= position_ms <= cue.end_ms:
        self._current_cue_idx = i
        self.subtitle_label.setText(cue.text)
        self.subtitle_label.show()
        return
      if cue.start_ms > position_ms:
        break
    self._current_cue_idx = -1
    self.subtitle_label.hide()
    self.subtitle_label.setText("")

  # --- chrome ----------------------------------------------------------

  def _bump_controls(self):
    self._show_controls()
    if self.settings.hide_controls_fullscreen and self.isFullScreen():
      self._hide_timer.start(2500)

  def _show_controls(self):
    if not self._controls_visible:
      self.controls.show()
      self._controls_visible = True
    self.setCursor(Qt.CursorShape.ArrowCursor)

  def _hide_controls(self):
    if not self.isFullScreen() or not self.settings.hide_controls_fullscreen:
      return
    # Hide while playing; if paused, still hide after idle so FS stays clean
    self.controls.hide()
    self._controls_visible = False
    self.setCursor(Qt.CursorShape.BlankCursor)

  def mouseMoveEvent(self, event):
    self._bump_controls()
    super().mouseMoveEvent(event)

  def mouseDoubleClickEvent(self, event):
    self.toggle_fullscreen()
    super().mouseDoubleClickEvent(event)


  # --- release features: repeat / next / resume / recent / dnd / updates ---

  def play_playlist_entry(self, url: str, title: str = "") -> None:
    """Play an M3U entry and remember its index for Next/Prev."""
    url = url.strip()
    idx = -1
    for i, entry in enumerate(self._playlist_entries):
      if entry.url == url:
        idx = i
        break
    self._playlist_index = idx
    self.play_stream(url, title)

  def cycle_repeat_mode(self) -> None:
    order = ["off", "one", "all"]
    cur = self.settings.repeat_mode
    try:
      nxt = order[(order.index(cur) + 1) % len(order)]
    except ValueError:
      nxt = "off"
    self.settings.repeat_mode = nxt
    self.settings.sync()
    self._sync_repeat_ui()
    labels = {"off": "Repeat Off", "one": "Repeat One", "all": "Repeat All"}
    self._flash_status(labels.get(nxt, nxt))

  def _sync_repeat_ui(self) -> None:
    mode = self.settings.repeat_mode
    theme = get_theme(self.settings.theme_id)
    text = theme.text
    accent = theme.accent
    if not hasattr(self, "btn_repeat"):
      return
    if mode == "one":
      apply_icon(self.btn_repeat, "repeat_one", accent)
      tip = "Repeat One (Ctrl+R)"
    elif mode == "all":
      apply_icon(self.btn_repeat, "repeat", accent)
      tip = "Repeat All (Ctrl+R)"
    else:
      apply_icon(self.btn_repeat, "repeat", text)
      tip = "Repeat Off (Ctrl+R)"
    self.btn_repeat.setToolTip(tip)
    if hasattr(self, "_repeat_act"):
      labels = {"off": "Repeat: Off", "one": "Repeat: One", "all": "Repeat: All"}
      self._repeat_act.setText(labels.get(mode, "Repeat: Off"))

  def _rebuild_folder_list(self, file_name: str) -> None:
    try:
      folder = Path(file_name).resolve().parent
      files = sorted(
          str(p.resolve())
          for p in folder.iterdir()
          if p.is_file() and p.suffix.lower() in VIDEO_EXTENSIONS
      )
    except OSError:
      files = [file_name]
    self._folder_files = files
    try:
      self._folder_index = files.index(str(Path(file_name).resolve()))
    except ValueError:
      self._folder_index = 0 if files else -1

  def play_next(self) -> None:
    self._navigate_relative(+1)

  def play_previous(self) -> None:
    self._navigate_relative(-1)

  def _navigate_relative(self, delta: int) -> None:
    # Prefer M3U playlist when loaded
    if self._playlist_entries:
      if self._playlist_index < 0:
        # Try match current URL
        cur = self._source_url or self._play_url or ""
        for i, e in enumerate(self._playlist_entries):
          if e.url == cur:
            self._playlist_index = i
            break
      n = len(self._playlist_entries)
      if n == 0:
        return
      if self._playlist_index < 0:
        idx = 0 if delta > 0 else n - 1
      else:
        idx = self._playlist_index + delta
        if idx < 0 or idx >= n:
          if self.settings.repeat_mode == "all":
            idx = idx % n
          else:
            self._flash_status("End of playlist")
            return
      entry = self._playlist_entries[idx]
      self._playlist_index = idx
      self.play_stream(entry.url, entry.title)
      return
    # Local folder siblings
    if not self._folder_files and self._video_path:
      self._rebuild_folder_list(self._video_path)
    files = self._folder_files
    if not files:
      self._flash_status("Nothing to skip to")
      return
    idx = self._folder_index
    if idx < 0:
      idx = 0
    nxt = idx + delta
    if nxt < 0 or nxt >= len(files):
      if self.settings.repeat_mode == "all":
        nxt = nxt % len(files)
      else:
        self._flash_status("End of folder")
        return
    self._folder_index = nxt
    self.load_video(files[nxt], autoplay=True)

  def _on_end_of_media(self) -> None:
    if self._suppress_auto_next:
      return
    if self._is_live_playback():
      return
    mode = self.settings.repeat_mode
    if mode == "one":
      self.media_player.setPosition(0)
      self.media_player.play()
      return
    if mode == "all" or self.settings.autoplay_next:
      QTimer.singleShot(50, self.play_next)
      return
    # Repeat off and autoplay off: stop at end

  def _remember_resume_position(self) -> None:
    if not self.settings.resume_playback:
      return
    path = self._video_path
    if not path or not Path(path).is_file():
      return
    if self._is_live_playback() or looks_like_live(path):
      return
    pos = int(self.media_player.position())
    dur = int(self._effective_duration() or self.media_player.duration() or 0)
    if dur > 0 and dur < 120_000:
      return  # under ~2 min
    if dur > 0 and pos >= max(0, dur - 10_000):
      # Near end — clear so next open starts fresh
      self.settings.set_resume_position(path, 0)
      return
    if pos < 5_000:
      return
    self.settings.set_resume_position(path, pos)

  def _try_resume_position(self) -> None:
    if not self.settings.resume_playback:
      return
    path = self._video_path
    if not path or not Path(path).is_file():
      return
    if self._is_live_playback() or looks_like_live(path):
      return
    pos = self.settings.get_resume_position(path)
    if pos < 5_000:
      return
    dur = int(self._effective_duration() or self.media_player.duration() or 0)
    if dur > 0 and dur < 120_000:
      return
    if dur > 0 and pos >= max(0, dur - 10_000):
      return
    self._flash_status(f"Resuming at {format_time(pos)}")
    self._seek_to(pos, resume=True)

  def _populate_recent_menu(self) -> None:
    menu = self._recent_menu
    menu.clear()
    items = self.settings.recent_items
    if not items:
      empty = menu.addAction("(empty)")
      empty.setEnabled(False)
    else:
      for item in items:
        label = item
        if item.startswith(("http://", "https://")):
          label = item if len(item) < 72 else item[:69] + "…"
        else:
          label = Path(item).name
        act = menu.addAction(label)
        act.setToolTip(item)
        act.triggered.connect(lambda _=False, s=item: self._open_recent(s))
      menu.addSeparator()
      clear = menu.addAction("Clear Recent")
      clear.triggered.connect(self._clear_recent)

  def _open_recent(self, item: str) -> None:
    item = item.strip()
    if not item:
      return
    if item.startswith(("http://", "https://")):
      self.open_url(item)
      return
    path = Path(item)
    if path.suffix.lower() in PLAYLIST_EXTENSIONS:
      self.load_playlist_source(str(path))
    else:
      self.load_video(str(path))

  def _clear_recent(self) -> None:
    self.settings.recent_items = []
    self.settings.sync()
    self._flash_status("Recent cleared")

  def adjust_subtitle_delay(self, delta_ms: int, absolute: bool = False) -> None:
    if absolute:
      self.settings.subtitle_delay_ms = int(delta_ms)
    else:
      self.settings.subtitle_delay_ms = int(self.settings.subtitle_delay_ms) + int(delta_ms)
    self.settings.sync()
    self._apply_sub_delay()
    self._flash_status(f"Subtitle delay: {self.settings.subtitle_delay_ms:+d} ms")

  def _apply_sub_delay(self) -> None:
    if self._use_mpv and hasattr(self.media_player, "set_sub_delay"):
      self.media_player.set_sub_delay(self.settings.subtitle_delay_ms)
    # Refresh overlay cue for current position
    try:
      self._current_cue_idx = -1
      self._update_subtitle(self.media_player.position())
    except Exception:
      pass

  def dragEnterEvent(self, event) -> None:
    md = event.mimeData()
    if md is not None and (md.hasUrls() or md.hasText()):
      event.acceptProposedAction()
    else:
      super().dragEnterEvent(event)

  def dropEvent(self, event) -> None:
    md = event.mimeData()
    paths: list[str] = []
    if md is not None and md.hasUrls():
      for url in md.urls():
        if url.isLocalFile():
          paths.append(url.toLocalFile())
        else:
          s = url.toString()
          if s.startswith(("http://", "https://")):
            paths.append(s)
    elif md is not None and md.hasText():
      text = md.text().strip()
      if text:
        paths.append(text)
    if paths:
      self.open_path_args(paths)
      event.acceptProposedAction()
    else:
      super().dropEvent(event)

  def _maybe_check_updates_startup(self) -> None:
    if not self.settings.check_updates_startup:
      return
    today = QDate.currentDate().toString(Qt.DateFormat.ISODate)
    if self.settings.last_update_check == today:
      return
    self.check_for_updates(manual=False)

  def check_for_updates(self, manual: bool = False) -> None:
    if self._update_worker and self._update_worker.isRunning():
      if manual:
        self._flash_status("Update check already running…")
      return
    if manual:
      self._flash_status("Checking for updates…")
    self._update_worker = UpdateCheckWorker(parent=self)
    self._update_worker.finished_ok.connect(
        lambda info, m=manual: self._on_update_info(info, manual=m)
    )
    self._update_worker.failed.connect(
        lambda err, m=manual: self._on_update_fail(err, manual=m)
    )
    self._update_worker.start()

  def _on_update_fail(self, err: str, manual: bool = False) -> None:
    if manual:
      QMessageBox.information(
          self,
          "Updates",
          "Could not check for updates right now.\n\n" + (err or "Network error"),
      )
    # silent fail for startup

  def _on_update_info(self, info: object, manual: bool = False) -> None:
    today = QDate.currentDate().toString(Qt.DateFormat.ISODate)
    self.settings.last_update_check = today
    self.settings.sync()
    if not isinstance(info, UpdateInfo):
      return
    if not is_newer(info.version, __version__):
      if manual:
        QMessageBox.information(
            self,
            "Updates",
            f"You are up to date.\n\nCurrent version: {__version__}",
        )
      return
    self._show_update_dialog(info)

  def _show_update_dialog(self, info: UpdateInfo) -> None:
    notes = (info.notes or "").strip() or "A newer version is available."
    released = f"<br>Released: {info.released}" if info.released else ""
    msg = QMessageBox(self)
    msg.setWindowTitle("Update available")
    msg.setIcon(QMessageBox.Icon.Information)
    msg.setTextFormat(Qt.TextFormat.RichText)
    msg.setText(
        f"<b>{APP_NAME} {info.version}</b> is available "
        f"(you have {__version__}).{released}<br><br>{notes}"
    )
    download_btn = msg.addButton("Download", QMessageBox.ButtonRole.AcceptRole)
    msg.addButton(QMessageBox.StandardButton.Close)
    msg.exec()
    if msg.clickedButton() is download_btn:
      url = self._download_url_for_os(info)
      QDesktopServices.openUrl(QUrl(url))

  def _download_url_for_os(self, info: UpdateInfo) -> str:
    dls = info.downloads or {}
    key = "linux_appimage"
    if sys.platform.startswith("win"):
      key = "windows"
    elif sys.platform == "darwin":
      key = "macos"
    else:
      # Prefer .deb when that key exists
      key = "linux_deb" if dls.get("linux_deb") else "linux_appimage"
    return dls.get(key) or info.url or "https://yumedija.com/#download"


  def closeEvent(self, event):
    self._remember_resume_position()
    if self._use_mpv and hasattr(self.media_player, "shutdown"):
      try:
        self.media_player.shutdown()
      except Exception:
        pass
    app = QApplication.instance()
    if app is not None:
      app.removeEventFilter(self)
    self.settings.geometry = self.saveGeometry()
    if self.settings.remember_volume:
      self.settings.volume = self.volume_slider.value()
    self.settings.sync()
    super().closeEvent(event)


def run(argv: list[str] | None = None):
  argv = list(sys.argv if argv is None else argv)
  configure_logging()
  app = QApplication(argv)
  app.setApplicationName(APP_NAME)
  app.setOrganizationName(ORG_NAME)
  app.setStyle("Fusion")
  path = icon_path("yu-medija-player.png", "yu-medija-player-256.png", "yu-medija-player.ico")
  if path:
    app.setWindowIcon(QIcon(str(path)))
  window_holder: dict[str, VideoPlayer | None] = {"w": None}
  install_exception_hooks(lambda: window_holder["w"])
  window = VideoPlayer()
  window_holder["w"] = window
  window.show()
  # Paths after the program name (from file manager: yu-medija-player /path/to/video.mp4)
  cli_args = argv[1:]
  if cli_args:
    # Defer so the window is visible before playback starts
    QTimer.singleShot(0, lambda: window.open_path_args(cli_args))
  return app.exec()
