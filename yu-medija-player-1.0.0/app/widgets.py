"""Reusable UI widgets."""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QMouseEvent
from PyQt6.QtWidgets import QPushButton, QSlider, QStyle, QStyleOptionSlider


class SeekSlider(QSlider):
  """Precise seek: click anywhere + drag by mouse X."""

  scrubbing = pyqtSignal(int)
  seek_committed = pyqtSignal(int)

  def __init__(self, orientation=Qt.Orientation.Horizontal, parent=None):
    super().__init__(orientation, parent)
    self.setObjectName("seek")
    self.setCursor(Qt.CursorShape.PointingHandCursor)
    self.setMouseTracking(True)
    self.setMinimumHeight(28)
    self.setSingleStep(1000)
    self.setPageStep(5000)
    self._dragging = False

  @property
  def dragging(self) -> bool:
    return self._dragging

  def _value_at_x(self, x: float) -> int:
    opt = QStyleOptionSlider()
    self.initStyleOption(opt)
    groove = self.style().subControlRect(
        QStyle.ComplexControl.CC_Slider,
        opt,
        QStyle.SubControl.SC_SliderGroove,
        self,
    )
    handle = self.style().subControlRect(
        QStyle.ComplexControl.CC_Slider,
        opt,
        QStyle.SubControl.SC_SliderHandle,
        self,
    )
    span = max(1, groove.width() - handle.width())
    pos = x - groove.x() - handle.width() / 2
    pos = max(0.0, min(float(span), pos))
    return QStyle.sliderValueFromPosition(
        self.minimum(), self.maximum(), int(round(pos)), span, opt.upsideDown
    )

  def mousePressEvent(self, event: QMouseEvent):
    if event.button() != Qt.MouseButton.LeftButton or self.maximum() <= self.minimum():
      super().mousePressEvent(event)
      return
    self._dragging = True
    value = self._value_at_x(event.position().x())
    self.setValue(value)
    self.sliderPressed.emit()
    self.scrubbing.emit(value)
    event.accept()

  def mouseMoveEvent(self, event: QMouseEvent):
    if self._dragging and self.maximum() > self.minimum():
      value = self._value_at_x(event.position().x())
      if value != self.value():
        self.setValue(value)
        self.scrubbing.emit(value)
      event.accept()
      return
    super().mouseMoveEvent(event)

  def mouseReleaseEvent(self, event: QMouseEvent):
    if event.button() == Qt.MouseButton.LeftButton and self._dragging:
      value = self._value_at_x(event.position().x())
      self.setValue(value)
      # Emit while still marked dragging so UI ignores stale position=0
      self.seek_committed.emit(value)
      self.sliderReleased.emit()
      self._dragging = False
      event.accept()
      return
    super().mouseReleaseEvent(event)


def icon_btn(text: str, tip: str, width: int = 40) -> QPushButton:
  """Create a compact control-bar button (text optional; icons set by window)."""
  btn = QPushButton(text)
  btn.setCursor(Qt.CursorShape.PointingHandCursor)
  btn.setToolTip(tip)
  btn.setFixedSize(width, 36)
  # Space/Enter ne smiju aktivirati dugme umjesto play/pause prečice
  btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
  return btn
