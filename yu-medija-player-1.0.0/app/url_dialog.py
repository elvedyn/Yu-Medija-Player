"""Open URL dialog."""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
)

from app.styles import apply_dialog_theme


class UrlDialog(QDialog):
  def __init__(self, theme_id: str = "cinema_dark", initial: str = "", parent=None):
    super().__init__(parent)
    self.setWindowTitle("Open YT URL")
    self.setMinimumWidth(520)
    apply_dialog_theme(self, theme_id)

    root = QVBoxLayout(self)
    root.setSpacing(10)
    hint = QLabel("Paste a YouTube / video URL, or an M3U playlist URL.")
    hint.setObjectName("settingsHint")
    hint.setWordWrap(True)
    root.addWidget(hint)

    self.url_edit = QLineEdit(initial)
    self.url_edit.setPlaceholderText("https://…")
    self.url_edit.setMinimumHeight(36)
    self.url_edit.selectAll()
    root.addWidget(self.url_edit)

    buttons = QDialogButtonBox(
        QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
    )
    buttons.accepted.connect(self.accept)
    buttons.rejected.connect(self.reject)
    row = QHBoxLayout()
    row.addStretch(1)
    row.addWidget(buttons)
    root.addLayout(row)

    self.url_edit.returnPressed.connect(self.accept)
    self.url_edit.setFocus()

  def url(self) -> str:
    return self.url_edit.text().strip()
