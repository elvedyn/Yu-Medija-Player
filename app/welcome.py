"""Modern start screen: primary actions, recent media and format hints."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.resources import icon_path

MAX_RECENT = 5


class WelcomeScreen(QWidget):
  """Landing view shown when nothing is playing."""

  open_video = pyqtSignal()
  open_playlist = pyqtSignal()
  open_url = pyqtSignal()
  open_settings = pyqtSignal()
  open_recent = pyqtSignal(str)

  def __init__(self, app_name: str, version: str, parent=None):
    super().__init__(parent)
    self.setObjectName("welcome")
    self._app_name = app_name

    outer = QVBoxLayout(self)
    outer.setContentsMargins(28, 28, 28, 24)
    outer.setSpacing(0)

    card = QWidget(self)
    card.setObjectName("heroCard")
    card.setMaximumWidth(560)
    card.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
    column = QVBoxLayout(card)
    column.setContentsMargins(8, 8, 8, 8)
    column.setSpacing(0)

    self.icon_label = QLabel(card)
    self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    pm = self._load_icon()
    if pm is not None:
      self.icon_label.setPixmap(pm)
      column.addWidget(self.icon_label)
      column.addSpacing(14)

    self.title_label = QLabel(app_name, card)
    self.title_label.setObjectName("heroTitle")
    self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    column.addWidget(self.title_label)

    column.addSpacing(6)
    self.sub_label = QLabel("Your video, playlist and IPTV companion", card)
    self.sub_label.setObjectName("heroSub")
    self.sub_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    column.addWidget(self.sub_label)

    column.addSpacing(22)

    self.btn_open = QPushButton("Open video", card)
    self.btn_open.setObjectName("heroPrimary")
    self.btn_open.setCursor(Qt.CursorShape.PointingHandCursor)
    self.btn_open.setToolTip("Open a video file (Ctrl+O)")
    self.btn_open.setMinimumWidth(240)
    self.btn_open.clicked.connect(self.open_video.emit)
    column.addWidget(self.btn_open, 0, Qt.AlignmentFlag.AlignHCenter)

    column.addSpacing(10)

    secondary = QHBoxLayout()
    secondary.setSpacing(8)
    secondary.addStretch(1)
    self.btn_playlist = self._secondary("Open playlist", "Load an M3U/M3U8 playlist (Ctrl+P)", card)
    self.btn_playlist.clicked.connect(self.open_playlist.emit)
    secondary.addWidget(self.btn_playlist)
    self.btn_url = self._secondary("Stream URL", "Play a direct stream or playlist URL (Ctrl+U)", card)
    self.btn_url.clicked.connect(self.open_url.emit)
    secondary.addWidget(self.btn_url)
    self.btn_settings = self._secondary("Settings", "Preferences (Ctrl+,)", card)
    self.btn_settings.clicked.connect(self.open_settings.emit)
    secondary.addWidget(self.btn_settings)
    secondary.addStretch(1)
    column.addLayout(secondary)

    column.addSpacing(14)
    self.message = QLabel("", card)
    self.message.setObjectName("heroError")
    self.message.setWordWrap(True)
    self.message.setAlignment(Qt.AlignmentFlag.AlignCenter)
    self.message.hide()
    column.addWidget(self.message)

    column.addSpacing(20)

    self.recent_title = QLabel("RECENT", card)
    self.recent_title.setObjectName("heroSection")
    column.addWidget(self.recent_title)
    column.addSpacing(6)
    self.recent_box = QVBoxLayout()
    self.recent_box.setSpacing(2)
    column.addLayout(self.recent_box)
    self._recent_widgets: list[QWidget] = []
    self._set_recent_visible(False)

    column.addSpacing(18)
    self.hint = QLabel(
        "Drag & drop video, subtitle (.srt / .vtt) or .m3u files anywhere in this window.",
        card,
    )
    self.hint.setObjectName("heroHint")
    self.hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
    self.hint.setWordWrap(True)
    column.addWidget(self.hint)

    column.addSpacing(4)
    self.formats = QLabel(
        "MKV · MP4 · AVI · WebM · MOV · TS · MPEG · WMV — plus every FFmpeg format",
        card,
    )
    self.formats.setObjectName("heroHint")
    self.formats.setAlignment(Qt.AlignmentFlag.AlignCenter)
    self.formats.setWordWrap(True)
    column.addWidget(self.formats)

    outer.addStretch(1)
    outer.addWidget(card, 0, Qt.AlignmentFlag.AlignHCenter)
    outer.addStretch(2)

    self.version_label = QLabel(f"v{version}", self)
    self.version_label.setObjectName("heroVersion")
    self.version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    outer.addWidget(self.version_label)

  # --- messages / recent ------------------------------------------------

  def show_message(self, text: str) -> None:
    """Show a playback error banner without losing the start screen."""
    self.message.setText(text or "")
    self.message.setVisible(bool(text))

  def clear_message(self) -> None:
    self.message.clear()
    self.message.hide()

  # --- helpers ---------------------------------------------------------

  def _load_icon(self) -> QPixmap | None:
    path = icon_path("yu-medija-player-256.png", "yu-medija-player.png", "yu-medija-player-512.png")
    if not path:
      return None
    pm = QPixmap(str(path))
    if pm.isNull():
      return None
    return pm.scaled(
        88,
        88,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )

  def _secondary(self, text: str, tip: str, parent: QWidget) -> QPushButton:
    btn = QPushButton(text, parent)
    btn.setObjectName("heroSecondary")
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setToolTip(tip)
    return btn

  def _set_recent_visible(self, visible: bool) -> None:
    self.recent_title.setVisible(visible)

  def set_recent(self, items: list[str]) -> None:
    for widget in self._recent_widgets:
      self.recent_box.removeWidget(widget)
      widget.deleteLater()
    self._recent_widgets = []

    entries = [item for item in (items or []) if item][:MAX_RECENT]
    for item in entries:
      btn = QPushButton(self._recent_label(item), self)
      btn.setObjectName("recentItem")
      btn.setCursor(Qt.CursorShape.PointingHandCursor)
      btn.setToolTip(item)
      btn.clicked.connect(lambda _=False, value=item: self.open_recent.emit(value))
      self.recent_box.addWidget(btn)
      self._recent_widgets.append(btn)
    self._set_recent_visible(bool(entries))

  def _recent_label(self, item: str) -> str:
    if item.startswith(("http://", "https://")):
      label = item
    else:
      name = Path(item).name or item
      parent = Path(item).parent.name
      label = f"{name}   —   {parent}" if parent else name
    return label if len(label) <= 62 else label[:59] + "…"

  def set_icon_visible(self, visible: bool) -> None:
    self.icon_label.setVisible(visible)
