"""Modern themes — pure QSS, no animations, no extra processes.

Palette tokens are injected into QSS templates through @token@ placeholders so the
stylesheets stay readable (no doubled braces) and every widget shares one visual
language: soft raised surfaces, 10-12px radii, a single accent hue and muted text.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Theme:
  id: str
  label: str
  bg: str
  panel: str
  panel2: str
  text: str
  muted: str
  border: str
  accent: str
  accent_text: str
  hover: str
  input: str
  # Optional refinements (fall back to sensible derivations when empty)
  accent_soft: str = ""
  track: str = ""


THEMES: dict[str, Theme] = {
  "cinema_dark": Theme(
      id="cinema_dark",
      label="Cinema Dark",
      bg="#0a0b0e",
      panel="#111318",
      panel2="#171a21",
      text="#f1f3f6",
      muted="#98a1ae",
      border="rgba(255,255,255,0.085)",
      accent="#f0a63c",
      accent_text="#1b1205",
      hover="#232833",
      input="#1a1e26",
      accent_soft="rgba(240,166,60,0.16)",
      track="rgba(255,255,255,0.14)",
  ),
  "midnight_teal": Theme(
      id="midnight_teal",
      label="Midnight Teal",
      bg="#070f11",
      panel="#0e171a",
      panel2="#142025",
      text="#eaf3f4",
      muted="#8fa5ab",
      border="rgba(255,255,255,0.085)",
      accent="#43c3ae",
      accent_text="#031311",
      hover="#1c2c31",
      input="#132127",
      accent_soft="rgba(67,195,174,0.16)",
      track="rgba(255,255,255,0.14)",
  ),
  "graphite": Theme(
      id="graphite",
      label="Graphite",
      bg="#0e0e10",
      panel="#161619",
      panel2="#1d1d21",
      text="#f4f4f6",
      muted="#a0a1a8",
      border="rgba(255,255,255,0.09)",
      accent="#8ab4ff",
      accent_text="#080d16",
      hover="#26262c",
      input="#1b1b20",
      accent_soft="rgba(138,180,255,0.16)",
      track="rgba(255,255,255,0.14)",
  ),
  "paper_light": Theme(
      id="paper_light",
      label="Paper Light",
      bg="#f4f2ed",
      panel="#ffffff",
      panel2="#fbfaf7",
      text="#1b1a18",
      muted="#6d6860",
      border="rgba(0,0,0,0.10)",
      accent="#c2703a",
      accent_text="#fff9f4",
      hover="#efeae1",
      input="#f6f4ef",
      accent_soft="rgba(194,112,58,0.14)",
      track="rgba(0,0,0,0.14)",
  ),
  "cloud_light": Theme(
      id="cloud_light",
      label="Cloud Light",
      bg="#eef2f7",
      panel="#ffffff",
      panel2="#f7f9fc",
      text="#131a22",
      muted="#5d6c7b",
      border="rgba(15,35,55,0.10)",
      accent="#2f6fed",
      accent_text="#ffffff",
      hover="#e7eef9",
      input="#f4f7fb",
      accent_soft="rgba(47,111,237,0.14)",
      track="rgba(15,35,55,0.14)",
  ),
}

DEFAULT_THEME = "cinema_dark"

UI_FONT = '"Inter", "Noto Sans", "Segoe UI", "SF Pro Text", "Helvetica Neue", sans-serif'
MONO_FONT = '"JetBrains Mono", "Cascadia Mono", "SF Mono", "Consolas", monospace'


def theme_choices() -> list[tuple[str, str]]:
  return [(t.id, t.label) for t in THEMES.values()]


def get_theme(theme_id: str) -> Theme:
  return THEMES.get(theme_id, THEMES[DEFAULT_THEME])


def _shade(color: str, factor: float) -> str:
  """Lighten (factor > 0) or darken (factor < 0) a #rrggbb color."""
  raw = (color or "").strip().lstrip("#")
  if len(raw) != 6:
    return color
  try:
    r, g, b = int(raw[0:2], 16), int(raw[2:4], 16), int(raw[4:6], 16)
  except ValueError:
    return color
  if factor >= 0:
    r = int(r + (255 - r) * factor)
    g = int(g + (255 - g) * factor)
    b = int(b + (255 - b) * factor)
  else:
    f = 1.0 + factor
    r, g, b = int(r * f), int(g * f), int(b * f)
  clamp = lambda v: max(0, min(255, v))  # noqa: E731
  return "#{:02x}{:02x}{:02x}".format(clamp(r), clamp(g), clamp(b))


def _tokens(t: Theme, subtitle_font_size: int = 18) -> dict[str, str]:
  accent_soft = t.accent_soft or "rgba(127,127,127,0.16)"
  track = t.track or t.border
  return {
      "bg": t.bg,
      "panel": t.panel,
      "panel2": t.panel2,
      "text": t.text,
      "muted": t.muted,
      "border": t.border,
      "accent": t.accent,
      "accent_text": t.accent_text,
      "accent_soft": accent_soft,
      "accent_hover": _shade(t.accent, 0.14),
      "accent_press": _shade(t.accent, -0.12),
      "hover": t.hover,
      "input": t.input,
      "track": track,
      "ui_font": UI_FONT,
      "mono_font": MONO_FONT,
      "sub_size": str(int(subtitle_font_size)),
      "error_text": "#ff9d9d",
      "error_bg": "rgba(255,90,90,0.12)",
      "error_border": "rgba(255,90,90,0.28)",
  }


def _fill(template: str, values: dict[str, str]) -> str:
  out = template
  for key, value in values.items():
    out = out.replace("@" + key + "@", value)
  return out


_APP_QSS = """
* {
  font-family: @ui_font@;
  outline: none;
}
QMainWindow, #stage, #welcome {
  background: @bg@;
  color: @text@;
}

/* ---------- menu bar & popups ---------- */
QMenuBar {
  background: @panel@;
  color: @text@;
  border-bottom: 1px solid @border@;
  padding: 3px 6px;
  font-size: 12px;
}
QMenuBar::item {
  background: transparent;
  padding: 5px 11px;
  margin: 0 1px;
  border-radius: 6px;
}
QMenuBar::item:selected {
  background: @hover@;
  color: @text@;
}
QMenuBar::item:pressed {
  background: @accent_soft@;
  color: @accent@;
}
QMenu {
  background: @panel2@;
  color: @text@;
  border: 1px solid @border@;
  border-radius: 10px;
  padding: 6px;
  font-size: 12px;
}
QMenu::item {
  padding: 7px 30px 7px 14px;
  border-radius: 6px;
  background: transparent;
}
QMenu::item:selected {
  background: @accent_soft@;
  color: @accent@;
}
QMenu::item:disabled {
  color: @muted@;
}
QMenu::separator {
  height: 1px;
  background: @border@;
  margin: 6px 10px;
}
QToolTip {
  background: @panel2@;
  color: @text@;
  border: 1px solid @border@;
  border-radius: 6px;
  padding: 6px 9px;
  font-size: 11px;
}

/* ---------- welcome / hero ---------- */
#heroTitle {
  color: @text@;
  font-size: 26px;
  font-weight: 700;
  letter-spacing: -0.3px;
}
#heroSub {
  color: @muted@;
  font-size: 13px;
}
#heroPrimary {
  background: @accent@;
  color: @accent_text@;
  border: none;
  border-radius: 12px;
  padding: 0 26px;
  min-height: 46px;
  font-size: 14px;
  font-weight: 700;
}
#heroPrimary:hover {
  background: @accent_hover@;
}
#heroPrimary:pressed {
  background: @accent_press@;
}
#heroSecondary {
  background: @input@;
  color: @text@;
  border: 1px solid @border@;
  border-radius: 10px;
  padding: 0 16px;
  min-height: 38px;
  font-size: 12px;
  font-weight: 600;
}
#heroSecondary:hover {
  background: @hover@;
  border-color: @accent@;
  color: @accent@;
}
#heroSecondary:pressed {
  background: @accent_soft@;
}
#heroSection {
  color: @muted@;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 1.4px;
}
#recentItem {
  background: transparent;
  color: @text@;
  border: 1px solid transparent;
  border-radius: 8px;
  padding: 7px 12px;
  text-align: left;
  font-size: 12px;
  font-weight: 500;
}
#recentItem:hover {
  background: @input@;
  border-color: @border@;
}
#recentItem:pressed {
  background: @accent_soft@;
}
#heroHint {
  color: @muted@;
  font-size: 11px;
}
#heroError {
  color: @error_text@;
  background: @error_bg@;
  border: 1px solid @error_border@;
  border-radius: 9px;
  padding: 9px 12px;
  font-size: 12px;
  font-weight: 600;
}
#heroVersion {
  color: @muted@;
  font-size: 10px;
}
#statusLabel {
  color: @accent@;
  background: @accent_soft@;
  border-radius: 9px;
  padding: 3px 10px;
  font-size: 11px;
  font-weight: 600;
}
#welcome {
  color: @muted@;
}
#playlistPanel {
  background: @panel@;
  border-right: 1px solid @border@;
  min-width: 200px;
}
#playlistTitle {
  color: @text@;
  font-size: 13px;
  font-weight: 700;
  background: transparent;
}
#playlistPanel QComboBox {
  background: @input@;
  color: @text@;
  border: 1px solid @border@;
  border-radius: 8px;
  padding: 4px 8px;
}
#playlistPanel QListWidget {
  background: @input@;
  color: @text@;
  border: 1px solid @border@;
  border-radius: 10px;
  outline: none;
}
#playlistPanel QListWidget::item {
  padding: 7px 9px;
  border-radius: 6px;
  margin: 1px 4px;
}
#playlistPanel QListWidget::item:selected {
  background: @accent_soft@;
  color: @accent@;
}
#playlistPanel #settingsHint {
  color: @muted@;
  font-size: 11px;
  background: transparent;
}

/* ---------- control bar ---------- */
#controls {
  background: @panel@;
  border-top: 1px solid @border@;
}
#nowTitle {
  color: @text@;
  font-size: 13px;
  font-weight: 600;
  background: transparent;
}
#nowMeta {
  color: @muted@;
  font-size: 11px;
  background: transparent;
}
#timeLabel {
  color: @muted@;
  font-size: 11px;
  font-family: @mono_font@;
  background: transparent;
}
#speedLabel {
  background: @input@;
  color: @text@;
  border: 1px solid @border@;
  border-radius: 9px;
  font-family: @mono_font@;
  font-size: 12px;
  font-weight: 700;
}
#speedLabel:hover {
  background: @hover@;
  border-color: @accent@;
  color: @accent@;
}
#speedLabel[active="true"] {
  background: @accent_soft@;
  border-color: @accent@;
  color: @accent@;
}
#speedLabel::menu-indicator {
  image: none;
  width: 0;
  height: 0;
}
QPushButton {
  background: transparent;
  color: @text@;
  border: 1px solid transparent;
  border-radius: 10px;
  font-size: 12px;
  font-weight: 600;
  padding: 0 8px;
}
QPushButton:hover {
  background: @hover@;
}
QPushButton:pressed {
  background: @accent_soft@;
}
QPushButton:disabled {
  color: @muted@;
  background: transparent;
}
QPushButton:checked {
  background: @accent_soft@;
  border-color: @accent@;
  color: @accent@;
}
#playBtn {
  background: @accent@;
  border: none;
  border-radius: 22px;
  padding: 0;
}
#playBtn:hover {
  background: @accent_hover@;
}
#playBtn:pressed {
  background: @accent_press@;
}
#muteBtn:checked {
  color: @accent@;
}
#ccBtn {
  font-size: 11px;
  letter-spacing: 0.6px;
  font-weight: 800;
}

/* ---------- sliders ---------- */
/* Seek/volume bars are custom-painted in app/widgets.py (round thumb, thin
   track).  Qt's Fusion style ignores border-radius on slider sub-controls. */
QSlider {
  background: transparent;
}

/* ---------- subtitles ---------- */
#subtitle {
  color: @text@;
  font-size: @sub_size@px;
  font-weight: 650;
  background: @bg@;
  padding: 8px 16px;
  min-height: 28px;
}

/* ---------- scrollbars ---------- */
QScrollBar:vertical {
  background: transparent;
  width: 10px;
  margin: 2px;
}
QScrollBar::handle:vertical {
  background: @track@;
  border-radius: 4px;
  min-height: 28px;
}
QScrollBar::handle:vertical:hover {
  background: @muted@;
}
QScrollBar:horizontal {
  background: transparent;
  height: 10px;
  margin: 2px;
}
QScrollBar::handle:horizontal {
  background: @track@;
  border-radius: 4px;
  min-width: 28px;
}
QScrollBar::handle:horizontal:hover {
  background: @muted@;
}
QScrollBar::add-line, QScrollBar::sub-line {
  width: 0;
  height: 0;
}
QScrollBar::add-page, QScrollBar::sub-page {
  background: transparent;
}

/* ---------- forms ---------- */
QGroupBox {
  border: 1px solid @border@;
  border-radius: 10px;
  margin-top: 14px;
  padding: 14px 12px 12px 12px;
  font-weight: 700;
  color: @text@;
  background: @panel2@;
}
QGroupBox::title {
  subcontrol-origin: margin;
  left: 10px;
  padding: 0 6px;
  color: @muted@;
}
QSpinBox, QComboBox, QLineEdit {
  background: @input@;
  color: @text@;
  border: 1px solid @border@;
  border-radius: 8px;
  padding: 4px 9px;
  min-height: 30px;
  selection-background-color: @hover@;
  selection-color: @text@;
}
QLineEdit:focus, QSpinBox:focus, QComboBox:focus {
  border-color: @accent@;
}
QComboBox QAbstractItemView {
  background: @panel2@;
  color: @text@;
  selection-background-color: @accent_soft@;
  selection-color: @accent@;
  border: 1px solid @border@;
  border-radius: 8px;
}
QCheckBox {
  color: @text@;
  spacing: 8px;
  background: transparent;
}
QCheckBox::indicator {
  width: 16px;
  height: 16px;
  border-radius: 5px;
  border: 1px solid @border@;
  background: @input@;
}
QCheckBox::indicator:hover {
  border-color: @accent@;
}
QCheckBox::indicator:checked {
  background: @accent@;
  border-color: @accent@;
}
"""


_DIALOG_QSS = """
QDialog {
  background-color: @panel@;
  color: @text@;
}
QScrollArea {
  background-color: @panel@;
  border: none;
}
QScrollArea > QWidget > QWidget {
  background-color: @panel@;
}
#settingsBody {
  background-color: @panel@;
  color: @text@;
}
QLabel {
  color: @text@;
  background: transparent;
}
#settingsHint {
  color: @muted@;
  font-size: 12px;
  font-weight: 400;
  background: transparent;
}
QGroupBox {
  background-color: @panel2@;
  border: 1px solid @border@;
  border-radius: 10px;
  margin-top: 16px;
  padding: 16px 14px 12px 14px;
  font-weight: 700;
  color: @text@;
}
QGroupBox::title {
  subcontrol-origin: margin;
  left: 10px;
  padding: 0 6px;
  color: @muted@;
  background-color: @panel@;
}
QSpinBox, QComboBox, QLineEdit {
  background-color: @input@;
  color: @text@;
  border: 1px solid @border@;
  border-radius: 8px;
  padding: 4px 9px;
  min-height: 30px;
  selection-background-color: @hover@;
  selection-color: @text@;
}
QLineEdit:focus, QSpinBox:focus, QComboBox:focus {
  border-color: @accent@;
}
QComboBox QAbstractItemView {
  background-color: @panel2@;
  color: @text@;
  selection-background-color: @accent_soft@;
  selection-color: @accent@;
  border: 1px solid @border@;
}
QCheckBox {
  color: @text@;
  spacing: 8px;
  background: transparent;
}
QCheckBox::indicator {
  width: 16px;
  height: 16px;
  border-radius: 5px;
  border: 1px solid @border@;
  background-color: @input@;
}
QCheckBox::indicator:hover {
  border-color: @accent@;
}
QCheckBox::indicator:checked {
  background-color: @accent@;
  border-color: @accent@;
}
QPushButton {
  background-color: @input@;
  color: @text@;
  border: 1px solid @border@;
  border-radius: 9px;
  padding: 8px 16px;
  min-height: 30px;
  font-weight: 600;
}
QPushButton:hover {
  background-color: @hover@;
  border-color: @accent@;
}
QPushButton:default {
  background-color: @accent@;
  color: @accent_text@;
  border-color: @accent@;
}
QPushButton:default:hover {
  background-color: @accent_hover@;
}
QDialogButtonBox QPushButton {
  min-width: 92px;
}
QListWidget {
  background-color: @input@;
  color: @text@;
  border: 1px solid @border@;
  border-radius: 10px;
  outline: none;
}
QListWidget::item {
  padding: 8px;
  border-radius: 6px;
}
QListWidget::item:selected {
  background-color: @accent_soft@;
  color: @accent@;
}
QScrollBar:vertical {
  background: transparent;
  width: 10px;
  margin: 2px;
}
QScrollBar::handle:vertical {
  background: @track@;
  border-radius: 4px;
  min-height: 28px;
}
QScrollBar::add-line, QScrollBar::sub-line {
  height: 0;
}
"""


def app_stylesheet(theme_id: str = DEFAULT_THEME, subtitle_font_size: int = 18) -> str:
  t = get_theme(theme_id)
  return _fill(_APP_QSS, _tokens(t, subtitle_font_size))


def dialog_stylesheet(theme_id: str = DEFAULT_THEME, subtitle_font_size: int = 18) -> str:
  """Stylesheet meant to be set directly on a QDialog (self + descendants)."""
  t = get_theme(theme_id)
  return _fill(_DIALOG_QSS, _tokens(t, subtitle_font_size))


def apply_dialog_theme(widget, theme_id: str, subtitle_font_size: int = 18) -> None:
  """Force dialog colors via palette + QSS (Fusion often ignores QSS bg alone)."""
  from PyQt6.QtCore import Qt
  from PyQt6.QtGui import QColor, QPalette

  t = get_theme(theme_id)
  widget.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

  pal = QPalette(widget.palette())
  bg = QColor(t.panel)
  text = QColor(t.text)
  base = QColor(t.input)
  muted = QColor(t.muted)
  accent = QColor(t.accent)
  hover = QColor(t.hover)
  for role, color in (
      (QPalette.ColorRole.Window, bg),
      (QPalette.ColorRole.Base, base),
      (QPalette.ColorRole.AlternateBase, QColor(t.panel2)),
      (QPalette.ColorRole.Button, base),
      (QPalette.ColorRole.WindowText, text),
      (QPalette.ColorRole.Text, text),
      (QPalette.ColorRole.ButtonText, text),
      (QPalette.ColorRole.PlaceholderText, muted),
      (QPalette.ColorRole.BrightText, accent),
      (QPalette.ColorRole.Highlight, hover),
      (QPalette.ColorRole.HighlightedText, accent),
      (QPalette.ColorRole.ToolTipBase, QColor(t.panel2)),
      (QPalette.ColorRole.ToolTipText, text),
  ):
    pal.setColor(role, color)
  widget.setPalette(pal)
  widget.setStyleSheet(dialog_stylesheet(theme_id, subtitle_font_size))
  widget.style().unpolish(widget)
  widget.style().polish(widget)
  widget.update()
