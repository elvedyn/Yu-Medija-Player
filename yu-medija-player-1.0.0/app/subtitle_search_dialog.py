"""Search & download subtitles from OpenSubtitles.com."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from app.opensubtitles import (
    SubtitleHit,
    download_subtitle,
    query_from_video_path,
    search_subtitles,
)
from app.styles import apply_dialog_theme


class _SearchWorker(QThread):
  finished_ok = pyqtSignal(list)
  failed = pyqtSignal(str)

  def __init__(self, api_key: str, query: str, languages: str):
    super().__init__()
    self.api_key = api_key
    self.query = query
    self.languages = languages

  def run(self):
    try:
      hits = search_subtitles(self.api_key, self.query, self.languages)
      self.finished_ok.emit(hits)
    except Exception as exc:  # noqa: BLE001 — show any API/network error
      self.failed.emit(str(exc))


class _DownloadWorker(QThread):
  finished_ok = pyqtSignal(str)
  failed = pyqtSignal(str)

  def __init__(self, api_key: str, file_id: int, dest: str):
    super().__init__()
    self.api_key = api_key
    self.file_id = file_id
    self.dest = dest

  def run(self):
    try:
      path = download_subtitle(self.api_key, self.file_id, self.dest)
      self.finished_ok.emit(path)
    except Exception as exc:  # noqa: BLE001
      self.failed.emit(str(exc))


class SubtitleSearchDialog(QDialog):
  def __init__(
      self,
      api_key: str,
      video_path: str | None,
      languages: str = "en",
      theme_id: str = "cinema_dark",
      parent=None,
  ):
    super().__init__(parent)
    self.api_key = api_key
    self.video_path = video_path
    self.downloaded_path: str | None = None
    self._hits: list[SubtitleHit] = []
    self._worker: QThread | None = None

    self.setWindowTitle("Search OpenSubtitles")
    self.setMinimumSize(640, 480)
    self.resize(700, 520)
    apply_dialog_theme(self, theme_id)

    root = QVBoxLayout(self)
    root.setSpacing(10)

    hint = QLabel(
        "Uses opensubtitles.com API. Free API key required in Settings → Subtitles."
    )
    hint.setObjectName("settingsHint")
    hint.setWordWrap(True)
    root.addWidget(hint)

    row = QHBoxLayout()
    self.query = QLineEdit(query_from_video_path(video_path))
    self.query.setPlaceholderText("Movie or episode name…")
    self.query.returnPressed.connect(self.start_search)
    row.addWidget(self.query, 1)

    self.lang = QComboBox()
    for code, label in [
        ("en", "English"),
        ("bs", "Bosanski"),
        ("hr", "Hrvatski"),
        ("sr", "Srpski"),
        ("en,bs,hr,sr", "EN+BS+HR+SR"),
        ("de", "Deutsch"),
        ("fr", "Français"),
        ("es", "Español"),
        ("it", "Italiano"),
        ("pt", "Português"),
        ("ru", "Русский"),
        ("tr", "Türkçe"),
    ]:
      self.lang.addItem(label, code)
    idx = self.lang.findData(languages)
    self.lang.setCurrentIndex(idx if idx >= 0 else 0)
    row.addWidget(self.lang)

    self.btn_search = QPushButton("Search")
    self.btn_search.clicked.connect(self.start_search)
    row.addWidget(self.btn_search)
    root.addLayout(row)

    self.status = QLabel("")
    self.status.setObjectName("settingsHint")
    root.addWidget(self.status)

    self.results = QListWidget()
    self.results.itemDoubleClicked.connect(lambda _i: self.download_selected())
    root.addWidget(self.results, 1)

    buttons = QDialogButtonBox()
    self.btn_download = buttons.addButton(
        "Download & use", QDialogButtonBox.ButtonRole.AcceptRole
    )
    buttons.addButton(QDialogButtonBox.StandardButton.Cancel)
    self.btn_download.clicked.connect(self.download_selected)
    buttons.rejected.connect(self.reject)
    root.addWidget(buttons)

    if self.query.text().strip():
      QTimer.singleShot(100, self.start_search)

  def start_search(self):
    if self._worker and self._worker.isRunning():
      return
    q = self.query.text().strip()
    if not q:
      QMessageBox.information(self, "Search", "Enter a title to search.")
      return
    self.results.clear()
    self._hits = []
    self.status.setText("Searching…")
    self.btn_search.setEnabled(False)
    self.btn_download.setEnabled(False)
    self._worker = _SearchWorker(self.api_key, q, self.lang.currentData())
    self._worker.finished_ok.connect(self._on_search_ok)
    self._worker.failed.connect(self._on_search_fail)
    self._worker.finished.connect(lambda: self.btn_search.setEnabled(True))
    self._worker.start()

  def _on_search_ok(self, hits: list):
    self._hits = hits
    self.results.clear()
    if not hits:
      self.status.setText("No results.")
      return
    self.status.setText(f"{len(hits)} result(s)")
    for hit in hits:
      hi = " [HI]" if hit.hearing_impaired else ""
      label = f"[{hit.language}] {hit.movie_name or hit.title}{hi}  ·  ↓{hit.download_count}"
      if hit.release and hit.release != hit.title:
        label += f"\n    {hit.release}"
      item = QListWidgetItem(label)
      item.setData(Qt.ItemDataRole.UserRole, hit.file_id)
      self.results.addItem(item)
    self.results.setCurrentRow(0)
    self.btn_download.setEnabled(True)

  def _on_search_fail(self, message: str):
    self.status.setText("Search failed")
    QMessageBox.warning(self, "OpenSubtitles", message)

  def download_selected(self):
    item = self.results.currentItem()
    if item is None:
      return
    file_id = item.data(Qt.ItemDataRole.UserRole)
    if not file_id:
      return
    if self._worker and self._worker.isRunning():
      return

    if self.video_path:
      stem = Path(self.video_path).stem
      folder = Path(self.video_path).parent
      lang = self.lang.currentData().split(",")[0]
      dest = str(folder / f"{stem}.{lang}.srt")
    else:
      dest = str(Path.home() / "Downloads" / f"yu-medija-player_{file_id}.srt")

    self.status.setText("Downloading…")
    self.btn_download.setEnabled(False)
    self._worker = _DownloadWorker(self.api_key, int(file_id), dest)
    self._worker.finished_ok.connect(self._on_download_ok)
    self._worker.failed.connect(self._on_download_fail)
    self._worker.start()

  def _on_download_ok(self, path: str):
    self.downloaded_path = path
    self.status.setText(f"Saved: {Path(path).name}")
    self.accept()

  def _on_download_fail(self, message: str):
    self.btn_download.setEnabled(True)
    self.status.setText("Download failed")
    QMessageBox.warning(self, "OpenSubtitles", message)
