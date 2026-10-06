"""Settings dialog."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.settings import AppSettings
from app.styles import app_stylesheet, apply_dialog_theme, theme_choices


class SettingsDialog(QDialog):
  def __init__(self, settings: AppSettings, parent=None):
    super().__init__(parent)
    self.settings = settings
    self._theme_before = settings.theme_id
    self._sub_size_before = settings.subtitle_font_size
    self._aspect_before = settings.aspect_mode
    self.setWindowTitle("Settings")
    self.setModal(True)
    self.setMinimumSize(560, 620)
    self.resize(580, 640)
    self._build()
    self._load()
    self._apply_dialog_theme(settings.theme_id, settings.subtitle_font_size)

  def _apply_dialog_theme(self, theme_id: str, sub_size: int | None = None):
    size = self.sub_size.value() if hasattr(self, "sub_size") else (sub_size or 18)
    apply_dialog_theme(self, theme_id, size)
    if hasattr(self, "_scroll"):
      self._scroll.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
    if hasattr(self, "_body"):
      self._body.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
      self._body.setAutoFillBackground(True)

  def _form(self, parent: QWidget) -> QFormLayout:
    form = QFormLayout(parent)
    form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
    form.setFormAlignment(Qt.AlignmentFlag.AlignTop)
    form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
    form.setHorizontalSpacing(16)
    form.setVerticalSpacing(10)
    form.setContentsMargins(12, 16, 12, 12)
    return form

  def _hint(self, text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("settingsHint")
    label.setWordWrap(True)
    return label

  def _build(self):
    outer = QVBoxLayout(self)
    outer.setContentsMargins(14, 14, 14, 14)
    outer.setSpacing(12)

    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QScrollArea.Shape.NoFrame)
    scroll.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
    self._scroll = scroll
    body = QWidget()
    body.setObjectName("settingsBody")
    body.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
    body.setAutoFillBackground(True)
    self._body = body
    root = QVBoxLayout(body)
    root.setSpacing(14)
    root.setContentsMargins(0, 0, 8, 0)

    appearance = QGroupBox("Appearance")
    aform = self._form(appearance)
    self.theme = QComboBox()
    self.theme.setMinimumHeight(32)
    for theme_id, label in theme_choices():
      self.theme.addItem(label, theme_id)
    aform.addRow("Theme", self.theme)
    aform.addRow(self._hint("Applies instantly — Cancel restores the previous theme."))

    self.aspect = QComboBox()
    self.aspect.setMinimumHeight(32)
    from app.aspect import aspect_choices
    for mode_id, label in aspect_choices():
      self.aspect.addItem(label, mode_id)
    aform.addRow("Aspect ratio", self.aspect)
    aform.addRow(self._hint("Fit / Fill / Stretch, or force 16:9, 4:3, 21:9, 1:1."))
    root.addWidget(appearance)

    playback = QGroupBox("Playback")
    form = self._form(playback)
    self.volume = QSpinBox()
    self.volume.setRange(0, 100)
    self.volume.setSuffix("%")
    self.volume.setMinimumHeight(32)
    form.addRow("Default volume", self.volume)
    self.remember_volume = QCheckBox("Remember volume between sessions")
    form.addRow(self.remember_volume)
    self.seek_step = QSpinBox()
    self.seek_step.setRange(1, 60)
    self.seek_step.setSuffix(" s")
    self.seek_step.setMinimumHeight(32)
    form.addRow("Skip step (← / →)", self.seek_step)
    self.autoplay_next = QCheckBox("Auto-play next file / channel when finished")
    form.addRow(self.autoplay_next)
    self.resume_playback = QCheckBox("Resume local files where you left off")
    form.addRow(self.resume_playback)
    form.addRow(self._hint("Skips live streams, clips under ~2 minutes, and near-end positions."))
    self.hwdec = QCheckBox("Hardware video decoding (local files)")
    form.addRow(self.hwdec)
    form.addRow(self._hint("Uses mpv hwdec=auto-safe for local files. Keep off if IPTV is unstable."))
    root.addWidget(playback)

    subs = QGroupBox("Subtitles")
    sform = self._form(subs)
    self.auto_srt = QCheckBox("Auto-load matching .srt next to video")
    sform.addRow(self.auto_srt)
    self.sub_size = QSpinBox()
    self.sub_size.setRange(12, 48)
    self.sub_size.setSuffix(" px")
    self.sub_size.setMinimumHeight(32)
    sform.addRow("Subtitle size", self.sub_size)
    self.os_key = QLineEdit()
    self.os_key.setEchoMode(QLineEdit.EchoMode.Password)
    self.os_key.setPlaceholderText("Paste free API key…")
    self.os_key.setMinimumHeight(32)
    sform.addRow("OpenSubtitles API key", self.os_key)
    sform.addRow(
        self._hint(
            "Free key: https://www.opensubtitles.com/en/consumers — used to search by video name."
        )
    )
    self.os_langs = QComboBox()
    self.os_langs.setMinimumHeight(32)
    for code, label in [
        ("en", "English"),
        ("bs", "Bosanski"),
        ("hr", "Hrvatski"),
        ("sr", "Srpski"),
        ("en,bs,hr,sr", "EN + BS + HR + SR"),
        ("de", "Deutsch"),
        ("fr", "Français"),
        ("es", "Español"),
    ]:
      self.os_langs.addItem(label, code)
    sform.addRow("Search languages", self.os_langs)
    self.btn_os_search = QPushButton("Search OpenSubtitles…")
    self.btn_os_search.setMinimumHeight(36)
    self.btn_os_search.clicked.connect(self._open_subtitle_search)
    sform.addRow(self.btn_os_search)
    sform.addRow(
        self._hint("Also: File → Search OpenSubtitles…  or  CC menu  or  Ctrl+Shift+S")
    )
    root.addWidget(subs)

    shots = QGroupBox("Screenshots")
    shform = self._form(shots)
    self.shot_fmt = QComboBox()
    self.shot_fmt.addItems(["png", "jpg"])
    self.shot_fmt.setMinimumHeight(32)
    shform.addRow("Format", self.shot_fmt)
    self.shot_ask = QCheckBox("Ask where to save screenshots")
    shform.addRow(self.shot_ask)
    root.addWidget(shots)

    downloads = QGroupBox("Downloads")
    dform = self._form(downloads)
    self.ask_dl = QCheckBox("Ask where to save YouTube downloads")
    dform.addRow(self.ask_dl)
    root.addWidget(downloads)

    ui = QGroupBox("Performance & interface")
    uiform = self._form(ui)
    self.hide_fs = QCheckBox("Auto-hide controls in fullscreen")
    uiform.addRow(self.hide_fs)
    uiform.addRow(self._hint("Hide seek bar and buttons after a short idle time in fullscreen."))
    self.low_power = QCheckBox("Low power mode (recommended)")
    uiform.addRow(self.low_power)
    uiform.addRow(self._hint("Skips status-text timers. Auto-hide fullscreen still works."))
    self.check_updates = QCheckBox("Check for updates on startup (once per day)")
    uiform.addRow(self.check_updates)
    root.addWidget(ui)

    root.addStretch(1)
    scroll.setWidget(body)
    outer.addWidget(scroll, 1)

    buttons = QDialogButtonBox(
        QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
    )
    buttons.accepted.connect(self.accept)
    buttons.rejected.connect(self.reject)
    row = QHBoxLayout()
    row.addStretch(1)
    row.addWidget(buttons)
    outer.addLayout(row)

    self.theme.currentIndexChanged.connect(self._preview_theme)
    self.sub_size.valueChanged.connect(self._preview_theme)
    self.aspect.currentIndexChanged.connect(self._preview_aspect)

  def _preview_theme(self, *_args):
    theme_id = self.theme.currentData()
    if not theme_id:
      return
    size = self.sub_size.value()
    self._apply_dialog_theme(theme_id, size)
    parent = self.parent()
    if parent is not None and hasattr(parent, "setStyleSheet"):
      parent.setStyleSheet(app_stylesheet(theme_id, size))

  def _preview_aspect(self, *_args):
    parent = self.parent()
    if parent is not None and hasattr(parent, "_apply_aspect_mode"):
      mid = self.aspect.currentData()
      if mid:
        parent._apply_aspect_mode(mid)

  def _open_subtitle_search(self):
    # Save key/langs from fields so search uses what the user just typed
    self.settings.opensubtitles_api_key = self.os_key.text()
    lang = self.os_langs.currentData()
    if lang:
      self.settings.opensubtitles_languages = lang
    self.settings.sync()
    parent = self.parent()
    if parent is not None and hasattr(parent, "search_opensubtitles"):
      parent.search_opensubtitles()

  def _load(self):
    s = self.settings
    self.theme.blockSignals(True)
    idx = self.theme.findData(s.theme_id)
    self.theme.setCurrentIndex(idx if idx >= 0 else 0)
    self.theme.blockSignals(False)
    aidx = self.aspect.findData(s.aspect_mode)
    self.aspect.setCurrentIndex(aidx if aidx >= 0 else 0)
    self.volume.setValue(s.volume)
    self.remember_volume.setChecked(s.remember_volume)
    self.seek_step.setValue(s.seek_step_sec)
    self.autoplay_next.setChecked(s.autoplay_next)
    self.resume_playback.setChecked(s.resume_playback)
    self.hwdec.setChecked(s.hardware_decoding)
    self.auto_srt.setChecked(s.auto_load_srt)
    self.sub_size.blockSignals(True)
    self.sub_size.setValue(s.subtitle_font_size)
    self.sub_size.blockSignals(False)
    self.os_key.setText(s.opensubtitles_api_key)
    lidx = self.os_langs.findData(s.opensubtitles_languages)
    self.os_langs.setCurrentIndex(lidx if lidx >= 0 else 0)
    self.shot_fmt.setCurrentText(s.screenshot_format)
    self.shot_ask.setChecked(s.screenshot_ask_path)
    self.ask_dl.setChecked(s.ask_download_path)
    self.hide_fs.setChecked(s.hide_controls_fullscreen)
    self.low_power.setChecked(s.low_power)
    self.check_updates.setChecked(s.check_updates_startup)

  def apply(self) -> None:
    s = self.settings
    s.theme_id = self.theme.currentData()
    s.aspect_mode = self.aspect.currentData()
    s.volume = self.volume.value()
    s.remember_volume = self.remember_volume.isChecked()
    s.seek_step_sec = self.seek_step.value()
    s.autoplay_next = self.autoplay_next.isChecked()
    s.resume_playback = self.resume_playback.isChecked()
    s.hardware_decoding = self.hwdec.isChecked()
    s.auto_load_srt = self.auto_srt.isChecked()
    s.subtitle_font_size = self.sub_size.value()
    s.opensubtitles_api_key = self.os_key.text()
    s.opensubtitles_languages = self.os_langs.currentData()
    s.screenshot_format = self.shot_fmt.currentText()
    s.screenshot_ask_path = self.shot_ask.isChecked()
    s.ask_download_path = self.ask_dl.isChecked()
    s.hide_controls_fullscreen = self.hide_fs.isChecked()
    s.low_power = self.low_power.isChecked()
    s.check_updates_startup = self.check_updates.isChecked()
    s.sync()

  def reject(self):
    parent = self.parent()
    if parent is not None and hasattr(parent, "setStyleSheet"):
      parent.setStyleSheet(
          app_stylesheet(self._theme_before, self._sub_size_before)
      )
    if parent is not None and hasattr(parent, "_apply_aspect_mode"):
      parent._apply_aspect_mode(self._aspect_before)
    super().reject()
