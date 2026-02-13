from __future__ import annotations
from typing import Any, Dict, List, Optional
from PySide6 import QtCore


class SnapshotListModel(QtCore.QAbstractListModel):
    def __init__(self, parent: Optional[QtCore.QObject] = None) -> None:
        super().__init__(parent)
        self._items: List[Dict[str, Any]] = []
        self._display_cache: Dict[str, str] = {}

    def set_items(self, items: List[Dict[str, Any]]) -> None:
        self.beginResetModel()
        self._items = items
        self._display_cache.clear()
        self.endResetModel()

    def rowCount(self, parent: QtCore.QModelIndex = QtCore.QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self._items)

    def id_for_index(self, index: QtCore.QModelIndex) -> Optional[str]:
        if not index.isValid():
            return None
        row = index.row()
        if row < 0 or row >= len(self._items):
            return None
        return str(self._items[row].get("id") or "")

    def data(self, index: QtCore.QModelIndex, role: int = QtCore.Qt.DisplayRole) -> Any:
        if not index.isValid():
            return None
        row = index.row()
        if row < 0 or row >= len(self._items):
            return None
        
        item = self._items[row]
        sid = str(item.get("id") or "")
        if role == QtCore.Qt.DisplayRole:
            cached = self._display_cache.get(sid)
            if cached is not None:
                return cached
            title = item.get("title", "")
            root = item.get("root", "")
            created = item.get("created_at", "")
            tags = item.get("tags", []) or []
            pin = "📌 " if bool(item.get("pinned", False)) else ""
            archived = "🗄️ " if bool(item.get("archived", False)) else ""
            tag_badge = f"[{', '.join(tags)}] " if tags else ""
            text = f"{pin}{archived}{tag_badge}{title}\n{root}   •   {created}"
            self._display_cache[sid] = text
            return text
        if role == QtCore.Qt.UserRole:
            return sid
        return None
