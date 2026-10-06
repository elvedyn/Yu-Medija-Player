"""Lightweight themes — pure QSS, no animations, no extra processes."""

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


THEMES: dict[str, Theme] = {
  "cinema_dark": Theme(
      id="cinema_dark",
      label="Cinema Dark",
      bg="#0b0d10",
      panel="#12151a",
      panel2="#171b22",
      text="#e8eaed",
      muted="#9aa3ad",
      border="rgba(255,255,255,0.10)",
      accent="#e8a54b",
      accent_text="#1a1208",
      hover="#2a323e",
      input="#1c222b",
  ),
  "midnight_teal": Theme(
      id="midnight_teal",
      label="Midnight Teal",
      bg="#0a1214",
      panel="#101a1d",
      panel2="#152226",
      text="#e6eef0",
      muted="#8fa3a8",
      border="rgba(255,255,255,0.10)",
      accent="#3db8a8",
      accent_text="#041210",
      hover="#1e3035",
      input="#162428",
  ),
  "graphite": Theme(
      id="graphite",
      label="Graphite",
      bg="#121212",
      panel="#1a1a1a",
      panel2="#222222",
      text="#f0f0f0",
      muted="#a0a0a0",
      border="rgba(255,255,255,0.12)",
      accent="#c8c8c8",
      accent_text="#111111",
      hover="#2c2c2c",
      input="#242424",
  ),
  "paper_light": Theme(
      id="paper_light",
      label="Paper Light",
      bg="#f3f1ec",
      panel="#ffffff",
      panel2="#ffffff",
      text="#1c1b19",
      muted="#6b6760",
      border="rgba(0,0,0,0.12)",
      accent="#c47a2c",
      accent_text="#fff8f0",
      hover="#efeae2",
      input="#f7f5f1",
  ),
  "cloud_light": Theme(
      id="cloud_light",
      label="Cloud Light",
      bg="#eef2f6",
      panel="#ffffff",
      panel2="#ffffff",
      text="#15202b",
      muted="#5b6b7a",
      border="rgba(20,40,60,0.12)",
      accent="#2f6fed",
      accent_text="#ffffff",
      hover="#e8eef8",
      input="#f5f8fc",
  ),
}

DEFAULT_THEME = "cinema_dark"


def theme_choices() -> list[tuple[str, str]]:
  return [(t.id, t.label) for t in THEMES.values()]


def get_theme(theme_id: str) -> Theme:
  return THEMES.get(theme_id, THEMES[DEFAULT_THEME])


def app_stylesheet(theme_id: str = DEFAULT_THEME, subtitle_font_size: int = 18) -> str:
  t = get_theme(theme_id)
  accent_soft = t.accent
  return f"""
    QMainWindow, #stage {{
      background: {t.bg};
      color: {t.text};
    }}
    QMenuBar {{
      background: {t.panel};
      color: {t.text};
      border-bottom: 1px solid {t.border};
      padding: 2px 4px;
    }}
    QMenuBar::item {{
      background: transparent;
      padding: 6px 10px;
      border-radius: 4px;
    }}
    QMenuBar::item:selected {{
      background: {t.hover};
    }}
    QMenu {{
      background: {t.panel2};
      color: {t.text};
      border: 1px solid {t.border};
      padding: 6px;
    }}
    QMenu::item {{
      padding: 7px 28px 7px 12px;
      border-radius: 4px;
    }}
    QMenu::item:selected {{
      background: {t.hover};
      color: {t.accent};
    }}
    QMenu::separator {{
      height: 1px;
      background: {t.border};
      margin: 6px 8px;
    }}
    #statusLabel {{
      color: {t.accent};
      font-size: 12px;
      background: transparent;
      padding-left: 8px;
    }}
    #welcome {{
      background: {t.bg};
      color: {t.muted};
      font-size: 17px;
      font-weight: 600;
    }}
    #playlistPanel {{
      background: {t.panel};
      border-right: 1px solid {t.border};
      min-width: 200px;
    }}
    #playlistTitle {{
      color: {t.accent};
      font-size: 13px;
      font-weight: 700;
      background: transparent;
    }}
    #playlistPanel QComboBox {{
      background: {t.input};
      color: {t.text};
      border: 1px solid {t.border};
      border-radius: 6px;
      padding: 4px 8px;
    }}
    #playlistPanel QListWidget {{
      background: {t.input};
      color: {t.text};
      border: 1px solid {t.border};
      border-radius: 6px;
      outline: none;
    }}
    #playlistPanel QListWidget::item {{
      padding: 6px 8px;
      border-radius: 4px;
    }}
    #playlistPanel QListWidget::item:selected {{
      background: {t.hover};
      color: {t.accent};
    }}
    #playlistPanel #settingsHint {{
      color: {t.muted};
      font-size: 11px;
      background: transparent;
    }}
    #controls {{
      background: {t.panel};
      border-top: 1px solid {t.border};
      min-height: 88px;
    }}
    QPushButton {{
      background: {t.input};
      color: {t.text};
      border: 1px solid {t.border};
      border-radius: 8px;
      font-size: 12px;
      font-weight: 700;
      padding: 0 4px;
    }}
    #controls QPushButton {{
      padding: 0;
    }}
    QPushButton:hover {{
      background: {t.hover};
    }}
    QPushButton:pressed {{
      background: {t.hover};
    }}
    QPushButton:disabled {{
      color: {t.muted};
      background: {t.panel};
    }}
    #playBtn {{
      background: {t.accent};
      color: {t.accent_text};
      border: none;
      font-size: 12px;
    }}
    #playBtn:hover {{
      background: {accent_soft};
    }}
    #speedBtn {{
      font-size: 16px;
      font-weight: 700;
    }}
    #speedLabel {{
      font-size: 12px;
      font-family: "JetBrains Mono", "Cascadia Mono", "SF Mono", "Consolas", monospace;
      font-weight: 700;
    }}
    #speedLabel[active="true"] {{
      background: {t.hover};
      border-color: {t.accent};
      color: {t.accent};
    }}
    #ccBtn {{
      font-size: 11px;
      letter-spacing: 0.5px;
      font-weight: 800;
    }}
    #ccBtn[active="true"], #muteBtn:checked {{
      background: {t.hover};
      border-color: {t.accent};
      color: {t.accent};
    }}
    QSlider#seek {{
      min-height: 28px;
      max-height: 28px;
      background: transparent;
    }}
    QSlider#seek::groove:horizontal {{
      height: 10px;
      background: {t.border};
      border-radius: 5px;
      margin: 0 4px;
    }}
    QSlider#seek::sub-page:horizontal {{
      background: {t.accent};
      border-radius: 5px;
      margin: 0 4px;
    }}
    QSlider#seek::handle:horizontal {{
      background: {t.text};
      border: 2px solid {t.accent};
      width: 18px;
      height: 18px;
      margin: -6px -2px;
      border-radius: 11px;
    }}
    QSlider#seek::handle:horizontal:hover {{
      background: {t.accent};
    }}
    QSlider#volume::groove:horizontal {{
      height: 4px;
      background: {t.border};
      border-radius: 2px;
    }}
    QSlider#volume::sub-page:horizontal {{
      background: {t.accent};
      border-radius: 2px;
    }}
    QSlider#volume::handle:horizontal {{
      background: {t.text};
      width: 12px;
      height: 12px;
      margin: -4px 0;
      border-radius: 6px;
    }}
    #timeLabel {{
      color: {t.muted};
      font-size: 12px;
      font-family: "JetBrains Mono", "Cascadia Mono", "SF Mono", "Consolas", monospace;
      background: transparent;
    }}
    #subtitle {{
      color: {t.text};
      font-size: {subtitle_font_size}px;
      font-weight: 650;
      background: {t.bg};
      padding: 8px 16px;
      min-height: 28px;
    }}
    QGroupBox {{
      border: 1px solid {t.border};
      border-radius: 8px;
      margin-top: 12px;
      padding: 12px 10px 10px 10px;
      font-weight: 700;
      color: {t.text};
      background: {t.panel2};
    }}
    QGroupBox::title {{
      subcontrol-origin: margin;
      left: 10px;
      padding: 0 4px;
      color: {t.accent};
    }}
    QSpinBox, QComboBox, QLineEdit {{
      background: {t.input};
      color: {t.text};
      border: 1px solid {t.border};
      border-radius: 6px;
      padding: 4px 8px;
      min-height: 28px;
      selection-background-color: {t.hover};
      selection-color: {t.text};
    }}
    QComboBox QAbstractItemView {{
      background: {t.panel2};
      color: {t.text};
      selection-background-color: {t.hover};
      border: 1px solid {t.border};
    }}
    QCheckBox {{
      color: {t.text};
      spacing: 8px;
    }}
    QCheckBox::indicator {{
      width: 16px;
      height: 16px;
      border-radius: 4px;
      border: 1px solid {t.border};
      background: {t.input};
    }}
    QCheckBox::indicator:checked {{
      background: {t.accent};
      border-color: {t.accent};
    }}
  """


def dialog_stylesheet(theme_id: str = DEFAULT_THEME, subtitle_font_size: int = 18) -> str:
  """Stylesheet meant to be set directly on a QDialog (self + descendants)."""
  t = get_theme(theme_id)
  _ = subtitle_font_size  # kept for API symmetry with app_stylesheet
  return f"""
    QDialog {{
      background-color: {t.panel};
      color: {t.text};
    }}
    QScrollArea {{
      background-color: {t.panel};
      border: none;
    }}
    QScrollArea > QWidget > QWidget {{
      background-color: {t.panel};
    }}
    #settingsBody {{
      background-color: {t.panel};
      color: {t.text};
    }}
    QLabel {{
      color: {t.text};
      background: transparent;
    }}
    #settingsHint {{
      color: {t.muted};
      font-size: 12px;
      font-weight: 400;
      background: transparent;
    }}
    QGroupBox {{
      background-color: {t.panel2};
      border: 1px solid {t.border};
      border-radius: 8px;
      margin-top: 14px;
      padding: 14px 12px 12px 12px;
      font-weight: 700;
      color: {t.text};
    }}
    QGroupBox::title {{
      subcontrol-origin: margin;
      left: 10px;
      padding: 0 6px;
      color: {t.accent};
      background-color: {t.panel};
    }}
    QSpinBox, QComboBox, QLineEdit {{
      background-color: {t.input};
      color: {t.text};
      border: 1px solid {t.border};
      border-radius: 6px;
      padding: 4px 8px;
      min-height: 28px;
      selection-background-color: {t.hover};
      selection-color: {t.text};
    }}
    QComboBox QAbstractItemView {{
      background-color: {t.panel2};
      color: {t.text};
      selection-background-color: {t.hover};
      border: 1px solid {t.border};
    }}
    QCheckBox {{
      color: {t.text};
      spacing: 8px;
      background: transparent;
    }}
    QCheckBox::indicator {{
      width: 16px;
      height: 16px;
      border-radius: 4px;
      border: 1px solid {t.border};
      background-color: {t.input};
    }}
    QCheckBox::indicator:checked {{
      background-color: {t.accent};
      border-color: {t.accent};
    }}
    QPushButton {{
      background-color: {t.input};
      color: {t.text};
      border: 1px solid {t.border};
      border-radius: 8px;
      padding: 8px 16px;
      min-height: 28px;
      font-weight: 700;
    }}
    QPushButton:hover {{
      background-color: {t.hover};
    }}
    QDialogButtonBox QPushButton {{
      min-width: 88px;
    }}
    QListWidget {{
      background-color: {t.input};
      color: {t.text};
      border: 1px solid {t.border};
      border-radius: 6px;
      outline: none;
    }}
    QListWidget::item {{
      padding: 8px;
      border-radius: 4px;
    }}
    QListWidget::item:selected {{
      background-color: {t.hover};
      color: {t.accent};
    }}
  """


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
