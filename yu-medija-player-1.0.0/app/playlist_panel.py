"""Side playlist panel: category filter + channel list."""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.m3u import PlaylistEntry, group_entries


class PlaylistPanel(QWidget):
  channel_chosen = pyqtSignal(str, str)  # url, title

  def __init__(self, parent=None):
    super().__init__(parent)
    self.setObjectName("playlistPanel")
    self.setMinimumWidth(220)
    self.setMaximumWidth(340)
    self._entries: list[PlaylistEntry] = []
    self._by_group: dict[str, list[PlaylistEntry]] = {}

    root = QVBoxLayout(self)
    root.setContentsMargins(10, 10, 10, 10)
    root.setSpacing(8)

    head = QLabel("Playlist")
    head.setObjectName("playlistTitle")
    root.addWidget(head)

    self.category = QComboBox()
    self.category.setMinimumHeight(32)
    self.category.currentIndexChanged.connect(self._fill_list)
    root.addWidget(self.category)

    self.list = QListWidget()
    self.list.itemActivated.connect(self._on_activated)
    self.list.itemDoubleClicked.connect(self._on_activated)
    root.addWidget(self.list, 1)

    tip = QLabel("Double-click or Enter to play")
    tip.setObjectName("settingsHint")
    tip.setWordWrap(True)
    root.addWidget(tip)

  def set_entries(self, entries: list[PlaylistEntry]) -> None:
    self._entries = list(entries)
    self._by_group = dict(group_entries(entries))
    self.category.blockSignals(True)
    self.category.clear()
    self.category.addItem("All", "__all__")
    for name in self._by_group:
      self.category.addItem(name, name)
    self.category.blockSignals(False)
    self._fill_list()

  def select_category(self, name: str) -> None:
    idx = self.category.findData(name)
    if idx < 0 and name:
      idx = self.category.findText(name)
    if idx >= 0:
      self.category.setCurrentIndex(idx)

  def clear_playlist(self) -> None:
    self._entries = []
    self._by_group = {}
    self.category.clear()
    self.list.clear()

  def _fill_list(self, *_args) -> None:
    self.list.clear()
    key = self.category.currentData()
    if key == "__all__" or key is None:
      items = self._entries
    else:
      items = self._by_group.get(str(key), [])
    for entry in items:
      item = QListWidgetItem(entry.title)
      item.setData(Qt.ItemDataRole.UserRole, entry.url)
      item.setToolTip(entry.url)
      self.list.addItem(item)

  def _on_activated(self, item: QListWidgetItem) -> None:
    if item is None:
      return
    url = item.data(Qt.ItemDataRole.UserRole)
    if url:
      self.channel_chosen.emit(str(url), item.text())
