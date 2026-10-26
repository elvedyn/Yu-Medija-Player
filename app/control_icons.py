"""Theme-tinted control-bar icons from bundled SVGs (no QtSvg dependency).

SVGs live under icons/controls/ and use fill/stroke="currentColor". We substitute
the theme color and rasterize via a tiny built-in painter for the known set so
frozen builds stay light (no PyQt6-Svg).
"""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap

from app.resources import app_root


def controls_dir() -> Path:
  return app_root() / "icons" / "controls"


def control_svg_path(name: str) -> Path | None:
  path = controls_dir() / f"{name}.svg"
  return path if path.is_file() else None


def _hex(color: str) -> QColor:
  c = QColor(color)
  if not c.isValid():
    c = QColor("#e8eaed")
  return c


def _paint_play(p: QPainter, r: QRectF) -> None:
  path = QPainterPath()
  path.moveTo(r.left() + r.width() * 0.32, r.top() + r.height() * 0.18)
  path.lineTo(r.left() + r.width() * 0.32, r.top() + r.height() * 0.82)
  path.lineTo(r.left() + r.width() * 0.82, r.center().y())
  path.closeSubpath()
  p.drawPath(path)


def _paint_pause(p: QPainter, r: QRectF) -> None:
  w = r.width()
  h = r.height()
  bar_w = w * 0.16
  gap = w * 0.14
  x1 = r.left() + w * 0.28
  x2 = r.center().x() + gap / 2
  y = r.top() + h * 0.18
  bh = h * 0.64
  p.drawRoundedRect(QRectF(x1, y, bar_w, bh), 1.5, 1.5)
  p.drawRoundedRect(QRectF(x2, y, bar_w, bh), 1.5, 1.5)


def _paint_seek_back(p: QPainter, r: QRectF) -> None:
  cx, cy = r.center().x(), r.center().y()
  w, h = r.width(), r.height()
  for dx in (-w * 0.06, w * 0.22):
    path = QPainterPath()
    path.moveTo(cx + dx + w * 0.12, cy - h * 0.28)
    path.lineTo(cx + dx - w * 0.18, cy)
    path.lineTo(cx + dx + w * 0.12, cy + h * 0.28)
    path.closeSubpath()
    p.drawPath(path)


def _paint_seek_forward(p: QPainter, r: QRectF) -> None:
  cx, cy = r.center().x(), r.center().y()
  w, h = r.width(), r.height()
  for dx in (-w * 0.22, w * 0.06):
    path = QPainterPath()
    path.moveTo(cx + dx - w * 0.12, cy - h * 0.28)
    path.lineTo(cx + dx + w * 0.18, cy)
    path.lineTo(cx + dx - w * 0.12, cy + h * 0.28)
    path.closeSubpath()
    p.drawPath(path)


def _paint_speed_down(p: QPainter, r: QRectF) -> None:
  w, h = r.width(), r.height()
  p.drawRoundedRect(
      QRectF(r.left() + w * 0.2, r.center().y() - h * 0.07, w * 0.6, h * 0.14),
      2,
      2,
  )


def _paint_speed_up(p: QPainter, r: QRectF) -> None:
  _paint_speed_down(p, r)
  w, h = r.width(), r.height()
  p.drawRoundedRect(
      QRectF(r.center().x() - w * 0.07, r.top() + h * 0.2, w * 0.14, h * 0.6),
      2,
      2,
  )


def _paint_volume(p: QPainter, r: QRectF) -> None:
  w, h = r.width(), r.height()
  # speaker body
  path = QPainterPath()
  path.moveTo(r.left() + w * 0.12, r.top() + h * 0.38)
  path.lineTo(r.left() + w * 0.28, r.top() + h * 0.38)
  path.lineTo(r.left() + w * 0.48, r.top() + h * 0.22)
  path.lineTo(r.left() + w * 0.48, r.top() + h * 0.78)
  path.lineTo(r.left() + w * 0.28, r.top() + h * 0.62)
  path.lineTo(r.left() + w * 0.12, r.top() + h * 0.62)
  path.closeSubpath()
  p.drawPath(path)
  pen = QPen(p.brush().color(), max(1.5, w * 0.07))
  pen.setCapStyle(Qt.PenCapStyle.RoundCap)
  p.setPen(pen)
  p.setBrush(Qt.BrushStyle.NoBrush)
  cx = r.left() + w * 0.52
  cy = r.center().y()
  p.drawArc(QRectF(cx - w * 0.08, cy - h * 0.14, w * 0.28, h * 0.28), -50 * 16, 100 * 16)
  p.drawArc(QRectF(cx - w * 0.02, cy - h * 0.26, w * 0.42, h * 0.52), -50 * 16, 100 * 16)


def _paint_volume_mute(p: QPainter, r: QRectF) -> None:
  w, h = r.width(), r.height()
  path = QPainterPath()
  path.moveTo(r.left() + w * 0.12, r.top() + h * 0.38)
  path.lineTo(r.left() + w * 0.28, r.top() + h * 0.38)
  path.lineTo(r.left() + w * 0.48, r.top() + h * 0.22)
  path.lineTo(r.left() + w * 0.48, r.top() + h * 0.78)
  path.lineTo(r.left() + w * 0.28, r.top() + h * 0.62)
  path.lineTo(r.left() + w * 0.12, r.top() + h * 0.62)
  path.closeSubpath()
  p.drawPath(path)
  pen = QPen(p.brush().color(), max(1.5, w * 0.08))
  pen.setCapStyle(Qt.PenCapStyle.RoundCap)
  p.setPen(pen)
  x0, y0 = r.left() + w * 0.58, r.top() + h * 0.35
  x1, y1 = r.left() + w * 0.88, r.top() + h * 0.65
  p.drawLine(QPointF(x0, y0), QPointF(x1, y1))
  p.drawLine(QPointF(x1, y0), QPointF(x0, y1))


def _paint_fullscreen(p: QPainter, r: QRectF) -> None:
  w = r.width()
  t = max(1.8, w * 0.1)
  pen = QPen(p.brush().color(), t)
  pen.setCapStyle(Qt.PenCapStyle.SquareCap)
  pen.setJoinStyle(Qt.PenJoinStyle.MiterJoin)
  p.setPen(pen)
  p.setBrush(Qt.BrushStyle.NoBrush)
  # four corners pointing out
  m = w * 0.18
  s = w * 0.22
  # TL
  p.drawLine(QPointF(r.left() + m, r.top() + m + s), QPointF(r.left() + m, r.top() + m))
  p.drawLine(QPointF(r.left() + m, r.top() + m), QPointF(r.left() + m + s, r.top() + m))
  # TR
  p.drawLine(QPointF(r.right() - m - s, r.top() + m), QPointF(r.right() - m, r.top() + m))
  p.drawLine(QPointF(r.right() - m, r.top() + m), QPointF(r.right() - m, r.top() + m + s))
  # BL
  p.drawLine(QPointF(r.left() + m, r.bottom() - m - s), QPointF(r.left() + m, r.bottom() - m))
  p.drawLine(QPointF(r.left() + m, r.bottom() - m), QPointF(r.left() + m + s, r.bottom() - m))
  # BR
  p.drawLine(QPointF(r.right() - m - s, r.bottom() - m), QPointF(r.right() - m, r.bottom() - m))
  p.drawLine(QPointF(r.right() - m, r.bottom() - m), QPointF(r.right() - m, r.bottom() - m - s))


def _paint_fullscreen_exit(p: QPainter, r: QRectF) -> None:
  w = r.width()
  t = max(1.8, w * 0.1)
  pen = QPen(p.brush().color(), t)
  pen.setCapStyle(Qt.PenCapStyle.SquareCap)
  p.setPen(pen)
  p.setBrush(Qt.BrushStyle.NoBrush)
  m = w * 0.18
  s = w * 0.22
  # corners pointing in
  p.drawLine(QPointF(r.left() + m, r.top() + m), QPointF(r.left() + m, r.top() + m + s))
  p.drawLine(QPointF(r.left() + m, r.top() + m + s), QPointF(r.left() + m + s, r.top() + m + s))
  p.drawLine(QPointF(r.right() - m, r.top() + m), QPointF(r.right() - m, r.top() + m + s))
  p.drawLine(QPointF(r.right() - m, r.top() + m + s), QPointF(r.right() - m - s, r.top() + m + s))
  p.drawLine(QPointF(r.left() + m, r.bottom() - m), QPointF(r.left() + m, r.bottom() - m - s))
  p.drawLine(QPointF(r.left() + m, r.bottom() - m - s), QPointF(r.left() + m + s, r.bottom() - m - s))
  p.drawLine(QPointF(r.right() - m, r.bottom() - m), QPointF(r.right() - m, r.bottom() - m - s))
  p.drawLine(QPointF(r.right() - m, r.bottom() - m - s), QPointF(r.right() - m - s, r.bottom() - m - s))


def _paint_screenshot(p: QPainter, r: QRectF) -> None:
  w, h = r.width(), r.height()
  color = p.brush().color()
  # top bump
  p.drawRoundedRect(
      QRectF(r.center().x() - w * 0.12, r.top() + h * 0.18, w * 0.24, h * 0.14),
      1.5,
      1.5,
  )
  # body
  p.drawRoundedRect(
      QRectF(r.left() + w * 0.16, r.top() + h * 0.30, w * 0.68, h * 0.50),
      2.5,
      2.5,
  )
  # lens ring (dark hole via destination-out after drawing filled ellipse ring)
  p.setBrush(color)
  outer = QRectF(r.center().x() - w * 0.14, r.center().y() - h * 0.06, w * 0.28, h * 0.28)
  p.drawEllipse(outer)
  # punch hole: redraw center with transparent using destination-out
  p.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationOut)
  p.setBrush(QColor(0, 0, 0, 255))
  inner = QRectF(r.center().x() - w * 0.08, r.center().y() + h * 0.00, w * 0.16, h * 0.16)
  # center the inner hole in the outer ellipse
  inner.moveCenter(outer.center())
  p.drawEllipse(inner)
  p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
  p.setBrush(color)


def _paint_download(p: QPainter, r: QRectF) -> None:
  w, h = r.width(), r.height()
  # shaft
  p.drawRoundedRect(
      QRectF(r.center().x() - w * 0.06, r.top() + h * 0.15, w * 0.12, h * 0.42),
      1.5,
      1.5,
  )
  # arrow head
  path = QPainterPath()
  path.moveTo(r.center().x(), r.top() + h * 0.72)
  path.lineTo(r.center().x() - w * 0.22, r.top() + h * 0.50)
  path.lineTo(r.center().x() + w * 0.22, r.top() + h * 0.50)
  path.closeSubpath()
  p.drawPath(path)
  # base
  p.drawRoundedRect(
      QRectF(r.left() + w * 0.22, r.top() + h * 0.78, w * 0.56, h * 0.08),
      1.5,
      1.5,
  )




def _paint_prev(p: QPainter, r: QRectF) -> None:
  w, h = r.width(), r.height()
  # bar + triangle left
  p.drawRoundedRect(QRectF(r.left() + w * 0.18, r.top() + h * 0.22, w * 0.12, h * 0.56), 1.2, 1.2)
  path = QPainterPath()
  path.moveTo(r.left() + w * 0.78, r.top() + h * 0.2)
  path.lineTo(r.left() + w * 0.35, r.center().y())
  path.lineTo(r.left() + w * 0.78, r.top() + h * 0.8)
  path.closeSubpath()
  p.drawPath(path)


def _paint_next(p: QPainter, r: QRectF) -> None:
  w, h = r.width(), r.height()
  path = QPainterPath()
  path.moveTo(r.left() + w * 0.22, r.top() + h * 0.2)
  path.lineTo(r.left() + w * 0.65, r.center().y())
  path.lineTo(r.left() + w * 0.22, r.top() + h * 0.8)
  path.closeSubpath()
  p.drawPath(path)
  p.drawRoundedRect(QRectF(r.left() + w * 0.70, r.top() + h * 0.22, w * 0.12, h * 0.56), 1.2, 1.2)


def _paint_repeat(p: QPainter, r: QRectF) -> None:
  w, h = r.width(), r.height()
  pen = QPen(p.brush().color(), max(1.6, w * 0.09))
  pen.setCapStyle(Qt.PenCapStyle.RoundCap)
  pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
  p.setPen(pen)
  p.setBrush(Qt.BrushStyle.NoBrush)
  p.drawArc(QRectF(r.left() + w * 0.18, r.top() + h * 0.18, w * 0.64, h * 0.64), 40 * 16, 280 * 16)
  # arrow head
  p.setBrush(pen.color())
  p.setPen(Qt.PenStyle.NoPen)
  path = QPainterPath()
  path.moveTo(r.left() + w * 0.62, r.top() + h * 0.18)
  path.lineTo(r.left() + w * 0.82, r.top() + h * 0.30)
  path.lineTo(r.left() + w * 0.58, r.top() + h * 0.38)
  path.closeSubpath()
  p.drawPath(path)


def _paint_repeat_one(p: QPainter, r: QRectF) -> None:
  color = p.brush().color()
  _paint_repeat(p, r)
  p.setPen(Qt.PenStyle.NoPen)
  p.setBrush(color)
  w, h = r.width(), r.height()
  p.drawRoundedRect(QRectF(r.center().x() - w * 0.04, r.top() + h * 0.34, w * 0.08, h * 0.32), 1, 1)


def _paint_shuffle(p: QPainter, r: QRectF) -> None:
  w, h = r.width(), r.height()
  pen = QPen(p.brush().color(), max(1.6, w * 0.08))
  pen.setCapStyle(Qt.PenCapStyle.RoundCap)
  p.setPen(pen)
  p.setBrush(Qt.BrushStyle.NoBrush)
  p.drawLine(QPointF(r.left() + w * 0.18, r.top() + h * 0.32), QPointF(r.left() + w * 0.45, r.top() + h * 0.32))
  p.drawLine(QPointF(r.left() + w * 0.55, r.top() + h * 0.68), QPointF(r.left() + w * 0.82, r.top() + h * 0.68))
  p.drawLine(QPointF(r.left() + w * 0.18, r.top() + h * 0.68), QPointF(r.left() + w * 0.38, r.top() + h * 0.68))
  p.drawLine(QPointF(r.left() + w * 0.38, r.top() + h * 0.68), QPointF(r.left() + w * 0.62, r.top() + h * 0.32))
  p.drawLine(QPointF(r.left() + w * 0.62, r.top() + h * 0.32), QPointF(r.left() + w * 0.82, r.top() + h * 0.32))

_PAINTERS = {
  "play": _paint_play,
  "pause": _paint_pause,
  "seek_back": _paint_seek_back,
  "seek_forward": _paint_seek_forward,
  "speed_down": _paint_speed_down,
  "speed_up": _paint_speed_up,
  "volume": _paint_volume,
  "volume_mute": _paint_volume_mute,
  "fullscreen": _paint_fullscreen,
  "fullscreen_exit": _paint_fullscreen_exit,
  "screenshot": _paint_screenshot,
  "download": _paint_download,
  "prev": _paint_prev,
  "next": _paint_next,
  "repeat": _paint_repeat,
  "repeat_one": _paint_repeat_one,
  "shuffle": _paint_shuffle,
}


def render_control_pixmap(name: str, color: str, size: int = 22, dpr: float = 1.0) -> QPixmap:
  """Rasterize a named control icon tinted to *color* (theme text / accent)."""
  painter_fn = _PAINTERS.get(name)
  px = max(12, int(round(size * dpr)))
  pm = QPixmap(px, px)
  pm.fill(Qt.GlobalColor.transparent)
  if painter_fn is None:
    return pm
  p = QPainter(pm)
  p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
  p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
  qc = _hex(color)
  p.setPen(Qt.PenStyle.NoPen)
  p.setBrush(qc)
  margin = px * 0.08
  painter_fn(p, QRectF(margin, margin, px - 2 * margin, px - 2 * margin))
  p.end()
  pm.setDevicePixelRatio(dpr)
  return pm


def control_icon(name: str, color: str, size: int = 22, dpr: float = 2.0) -> QIcon:
  return QIcon(render_control_pixmap(name, color, size=size, dpr=dpr))


def apply_icon(btn, name: str, color: str, size: int = 20) -> None:
  """Set a QPushButton icon and clear any leftover text label."""
  dpr = 2.0
  try:
    win = btn.window()
    if win is not None and win.windowHandle() is not None:
      dpr = float(win.windowHandle().devicePixelRatio())
  except Exception:
    pass
  btn.setIcon(control_icon(name, color, size=size, dpr=max(1.0, dpr)))
  btn.setIconSize(btn.iconSize() if btn.iconSize().width() > 0 else btn.size() * 0.55)
  from PyQt6.QtCore import QSize

  side = min(btn.width(), btn.height()) - 12
  side = max(16, side)
  btn.setIconSize(QSize(side, side))
  btn.setText("")
