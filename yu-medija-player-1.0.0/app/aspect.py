"""Video host with optional forced aspect ratio (16:9, 4:3, …)."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QWidget

# id -> (label, ratio or None, qt mode name)
ASPECT_MODES = [
  ("fit", "Fit (keep aspect)", None, "keep"),
  ("fill", "Fill (crop)", None, "fill"),
  ("stretch", "Stretch", None, "stretch"),
  ("16:9", "16:9", 16 / 9, "keep"),
  ("4:3", "4:3", 4 / 3, "keep"),
  ("21:9", "21:9", 21 / 9, "keep"),
  ("1:1", "1:1", 1.0, "keep"),
]


def aspect_choices() -> list[tuple[str, str]]:
  return [(m[0], m[1]) for m in ASPECT_MODES]


def aspect_info(mode_id: str) -> tuple[float | None, str]:
  for mid, _label, ratio, qt_mode in ASPECT_MODES:
    if mid == mode_id:
      return ratio, qt_mode
  return None, "keep"


class AspectVideoHost(QWidget):
  """Holds a video surface and letterboxes it to a forced ratio when needed."""

  def __init__(self, video_widget: QWidget | None = None, parent=None):
    super().__init__(parent)
    self.setObjectName("stage")
    self.setStyleSheet("background: #000;")
    if video_widget is None:
      from PyQt6.QtMultimediaWidgets import QVideoWidget

      video_widget = QVideoWidget(self)
      video_widget.setAspectRatioMode(Qt.AspectRatioMode.KeepAspectRatio)
    else:
      video_widget.setParent(self)
    self.video_widget = video_widget
    self._forced_ratio: float | None = None
    self._qt_mode = "keep"

  def set_aspect_mode(self, mode_id: str) -> None:
    ratio, qt_mode = aspect_info(mode_id)
    self._forced_ratio = ratio
    self._qt_mode = qt_mode
    # QVideoWidget-only aspect modes
    set_mode = getattr(self.video_widget, "setAspectRatioMode", None)
    if callable(set_mode):
      if qt_mode == "fill":
        set_mode(Qt.AspectRatioMode.KeepAspectRatioByExpanding)
      elif qt_mode == "stretch":
        set_mode(Qt.AspectRatioMode.IgnoreAspectRatio)
      else:
        set_mode(Qt.AspectRatioMode.KeepAspectRatio)
    self._layout_video()

  def replace_video_widget(self, new_widget: QWidget) -> QWidget:
    """Swap the embedded surface (used for safe libmpv VOD→live restarts)."""
    old = self.video_widget
    new_widget.setParent(self)
    self.video_widget = new_widget
    new_widget.show()
    self._layout_video()
    if old is not None and old is not new_widget:
      old.hide()
    return old

  def resizeEvent(self, event):
    super().resizeEvent(event)
    self._layout_video()

  def _layout_video(self) -> None:
    w, h = self.width(), self.height()
    if w <= 0 or h <= 0:
      return
    if not self._forced_ratio:
      self.video_widget.setGeometry(0, 0, w, h)
      return
    # Letterbox / pillarbox a frame with the forced ratio inside the host
    if (w / h) > self._forced_ratio:
      box_h = h
      box_w = max(1, int(round(h * self._forced_ratio)))
    else:
      box_w = w
      box_h = max(1, int(round(w / self._forced_ratio)))
    x = (w - box_w) // 2
    y = (h - box_h) // 2
    self.video_widget.setGeometry(x, y, box_w, box_h)
