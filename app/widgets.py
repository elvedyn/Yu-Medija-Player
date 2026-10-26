"""Reusable UI widgets."""

from __future__ import annotations

import re

from PyQt6.QtCore import QPointF, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QMouseEvent, QPainter, QPen
from PyQt6.QtWidgets import QLabel, QPushButton, QSlider


def qcolor(value, fallback: str = "#ffffff") -> QColor:
  """QColor from #rrggbb, named colors or CSS rgba(r,g,b,a) strings."""
  if isinstance(value, QColor):
    return QColor(value)
  text = str(value or "").strip()
  match = re.match(r"rgba?\(([^)]+)\)", text, re.IGNORECASE)
  if match:
    parts = [p.strip() for p in match.group(1).split(",")]
    try:
      r, g, b = (int(float(parts[0])), int(float(parts[1])), int(float(parts[2])))
      alpha = int(round(float(parts[3]) * 255)) if len(parts) > 3 else 255
      return QColor(r, g, b, max(0, min(255, alpha)))
    except (ValueError, IndexError):
      pass
  color = QColor(text)
  return color if color.isValid() else QColor(fallback)


class ElidedLabel(QLabel):
  """Single-line label that elides its text instead of forcing the window wider."""

  def __init__(self, text: str = "", parent=None):
    super().__init__(parent)
    self._full_text = text or ""
    self.setToolTip(self._full_text)
    self.setText(self._full_text)
    self.setMinimumWidth(0)

  def setFullText(self, text: str) -> None:
    self._full_text = text or ""
    self.setToolTip(self._full_text)
    self._apply_elide()

  def fullText(self) -> str:
    return self._full_text

  def resizeEvent(self, event):
    super().resizeEvent(event)
    self._apply_elide()

  def _apply_elide(self) -> None:
    metrics = self.fontMetrics()
    available = max(24, self.width() - 2)
    super().setText(metrics.elidedText(self._full_text, Qt.TextElideMode.ElideRight, available))


class SeekSlider(QSlider):
  """Flat, modern slider: thin track, accent progress and a round thumb.

  Qt's Fusion style ignores border-radius on slider sub-controls, so the bar is
  painted manually. Click anywhere to jump, drag to scrub, hover highlights.
  """

  scrubbing = pyqtSignal(int)
  seek_committed = pyqtSignal(int)

  def __init__(
      self,
      orientation=Qt.Orientation.Horizontal,
      parent=None,
      track_height: int = 5,
      thumb_radius: int = 6,
      min_height: int = 26,
  ):
    super().__init__(orientation, parent)
    self.setObjectName("seek")
    self.setCursor(Qt.CursorShape.PointingHandCursor)
    self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    self.setMinimumHeight(min_height)
    self.setSingleStep(1000)
    self.setPageStep(5000)
    self._dragging = False
    self._hover = False
    self._accent = QColor("#f0a63c")
    self._track = QColor(255, 255, 255, 40)
    self._thumb = QColor("#f1f3f6")
    self._track_height = max(2, int(track_height))
    self._thumb_radius = max(3, int(thumb_radius))
    self.valueChanged.connect(lambda _v: self.update())

  # --- theming ---------------------------------------------------------

  def set_colors(self, accent: str, track: str, thumb: str) -> None:
    self._accent = qcolor(accent, "#f0a63c")
    self._track = qcolor(track, "#444444")
    self._thumb = qcolor(thumb, "#ffffff")
    self.update()

  @property
  def dragging(self) -> bool:
    return self._dragging

  # --- geometry --------------------------------------------------------

  def _track_rect(self) -> QRectF:
    rect = self.rect()
    margin = self._thumb_radius + 3
    width = max(1.0, rect.width() - 2 * margin)
    center_y = rect.center().y()
    return QRectF(
        margin,
        center_y - self._track_height / 2,
        width,
        float(self._track_height),
    )

  def _thumb_x(self, value: int | None = None) -> float:
    track = self._track_rect()
    span = self.maximum() - self.minimum()
    if span <= 0:
      return track.left()
    current = self.value() if value is None else value
    fraction = (current - self.minimum()) / span
    return track.left() + track.width() * max(0.0, min(1.0, fraction))

  def _value_at_x(self, x: float) -> int:
    track = self._track_rect()
    fraction = (x - track.left()) / max(1.0, track.width())
    fraction = max(0.0, min(1.0, fraction))
    return int(round(self.minimum() + fraction * (self.maximum() - self.minimum())))

  # --- painting --------------------------------------------------------

  def paintEvent(self, _event) -> None:
    painter = QPainter(self)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    track = self._track_rect()
    radius = track.height() / 2

    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(self._track)
    painter.drawRoundedRect(track, radius, radius)

    thumb_x = self._thumb_x()
    filled_width = max(0.0, thumb_x - track.left())
    if filled_width > 0:
      painter.setBrush(self._accent)
      filled = QRectF(track.left(), track.top(), filled_width, track.height())
      painter.drawRoundedRect(filled, radius, radius)

    active = self._hover or self._dragging
    thumb_radius = float(self._thumb_radius + (1 if active else 0))
    painter.setBrush(self._accent if active else self._thumb)
    pen = QPen(self._accent if active else self._thumb)
    pen.setWidthF(2.0)
    painter.setPen(pen)
    painter.drawEllipse(QPointF(thumb_x, track.center().y()), thumb_radius, thumb_radius)
    painter.end()

  # --- interaction -----------------------------------------------------

  def mousePressEvent(self, event: QMouseEvent):
    if event.button() != Qt.MouseButton.LeftButton or self.maximum() <= self.minimum():
      super().mousePressEvent(event)
      return
    self._dragging = True
    value = self._value_at_x(event.position().x())
    self.setValue(value)
    self.sliderPressed.emit()
    self.scrubbing.emit(value)
    self.update()
    event.accept()

  def mouseMoveEvent(self, event: QMouseEvent):
    self._hover = True
    if self._dragging and self.maximum() > self.minimum():
      value = self._value_at_x(event.position().x())
      if value != self.value():
        self.setValue(value)
        self.scrubbing.emit(value)
      self.update()
      event.accept()
      return
    super().mouseMoveEvent(event)
    self.update()

  def mouseReleaseEvent(self, event: QMouseEvent):
    if event.button() == Qt.MouseButton.LeftButton and self._dragging:
      value = self._value_at_x(event.position().x())
      self.setValue(value)
      self.seek_committed.emit(value)
      self.sliderReleased.emit()
      self._dragging = False
      self.update()
      event.accept()
      return
    super().mouseReleaseEvent(event)

  def enterEvent(self, event):
    self._hover = True
    self.update()
    super().enterEvent(event)

  def leaveEvent(self, event):
    self._hover = False
    self.update()
    super().leaveEvent(event)


def icon_btn(text: str, tip: str, width: int = 40, height: int = 38) -> QPushButton:
  """Create a compact control-bar button (text optional; icons set by window)."""
  btn = QPushButton(text)
  btn.setCursor(Qt.CursorShape.PointingHandCursor)
  btn.setToolTip(tip)
  btn.setFixedSize(width, height)
  # Space/Enter ne smiju aktivirati dugme umjesto play/pause prečice
  btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
  return btn
