from __future__ import annotations
from typing import Any, Dict, List, Optional
from PySide6 import QtCore, QtGui, QtWidgets


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
            pin = "[PIN] " if bool(item.get("pinned", False)) else ""
            archived = "[ARC] " if bool(item.get("archived", False)) else ""
            tag_str = " · ".join(tags) if tags else ""
            # Line 1: pin + title
            # Line 2: root path (truncated) | date | tags
            line1 = f"{pin}{archived}{title}"
            parts = []
            if root:
                parts.append(root)
            if created:
                # Show just date portion
                parts.append(created[:16] if len(created) > 16 else created)
            if tag_str:
                parts.append(tag_str)
            line2 = "  ·  ".join(parts)
            text = f"{line1}\n{line2}"
            self._display_cache[sid] = text
            return text
        if role == QtCore.Qt.UserRole:
            return sid
        return None


class SnapshotDelegate(QtWidgets.QStyledItemDelegate):
    """Custom delegate for rendering snapshot list items with structured layout."""

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self._title_font = QtGui.QFont("Segoe UI", 12, QtGui.QFont.DemiBold)
        self._meta_font = QtGui.QFont("Segoe UI", 10)
        self._tag_font = QtGui.QFont("Segoe UI", 9, QtGui.QFont.Medium)

    def sizeHint(self, option: QtWidgets.QStyleOptionViewItem, index: QtCore.QModelIndex) -> QtCore.QSize:
        return QtCore.QSize(option.rect.width(), 64)

    def paint(self, painter: QtGui.QPainter, option: QtWidgets.QStyleOptionViewItem, index: QtCore.QModelIndex) -> None:
        painter.save()
        painter.setRenderHint(QtGui.QPainter.Antialiasing)

        model = index.model()
        if not model or index.row() < 0 or index.row() >= model.rowCount():
            painter.restore()
            return

        item = model._items[index.row()]
        rect = option.rect.adjusted(2, 2, -2, -2)
        is_selected = bool(option.state & QtWidgets.QStyle.State_Selected)
        is_hovered = bool(option.state & QtWidgets.QStyle.State_MouseOver)
        is_pinned = bool(item.get("pinned", False))
        is_archived = bool(item.get("archived", False))

        # Background
        bg_color = QtGui.QColor("#18181f")
        border_color = QtGui.QColor("#1e1e2a")
        if is_selected:
            bg_color = QtGui.QColor(108, 99, 255, 30)
            border_color = QtGui.QColor(108, 99, 255, 100)
        elif is_hovered:
            bg_color = QtGui.QColor("#1e1e2a")
            border_color = QtGui.QColor(108, 99, 255, 50)

        # Draw card background
        path = QtGui.QPainterPath()
        path.addRoundedRect(QtCore.QRectF(rect), 8, 8)
        painter.fillPath(path, bg_color)
        painter.setPen(QtGui.QPen(border_color, 1))
        painter.drawPath(path)

        # Pin accent bar
        if is_pinned:
            pin_rect = QtCore.QRectF(rect.left(), rect.top() + 4, 3, rect.height() - 8)
            pin_path = QtGui.QPainterPath()
            pin_path.addRoundedRect(pin_rect, 1.5, 1.5)
            painter.fillPath(pin_path, QtGui.QColor("#fbbf24"))

        # Text content area
        text_left = rect.left() + 14 + (4 if is_pinned else 0)
        text_right = rect.right() - 12

        # Title
        title = str(item.get("title", ""))
        if is_archived:
            title = f"[Archived] {title}"
        title_color = QtGui.QColor("#e8e8f0") if not is_archived else QtGui.QColor("#6b7280")
        painter.setFont(self._title_font)
        painter.setPen(title_color)
        title_rect = QtCore.QRectF(text_left, rect.top() + 8, text_right - text_left, 22)
        painter.drawText(title_rect, QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter | QtCore.Qt.TextSingleLine, title)

        # Meta line: root · date
        root = str(item.get("root", ""))
        created = str(item.get("created_at", ""))
        date_str = created[:16] if len(created) > 16 else created
        meta_parts = []
        if root:
            # Truncate long paths
            if len(root) > 50:
                root = "..." + root[-47:]
            meta_parts.append(root)
        if date_str:
            meta_parts.append(date_str)
        meta_text = "  ·  ".join(meta_parts)

        meta_color = QtGui.QColor("#8888a0") if not is_archived else QtGui.QColor("#555568")
        painter.setFont(self._meta_font)
        painter.setPen(meta_color)
        meta_rect = QtCore.QRectF(text_left, rect.top() + 30, text_right - text_left, 18)
        painter.drawText(meta_rect, QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter | QtCore.Qt.TextSingleLine, meta_text)

        # Tags (right-aligned chips on top line)
        tags = item.get("tags", []) or []
        if tags:
            painter.setFont(self._tag_font)
            fm = QtGui.QFontMetrics(self._tag_font)
            tag_x = text_right
            for tag in reversed(tags[:3]):
                tag_text = f" {tag} "
                tw = fm.horizontalAdvance(tag_text) + 8
                tag_x -= tw + 4
                if tag_x < text_left + 100:
                    break
                tag_rect = QtCore.QRectF(tag_x, rect.top() + 10, tw, 18)
                tag_bg = QtGui.QPainterPath()
                tag_bg.addRoundedRect(tag_rect, 4, 4)
                painter.fillPath(tag_bg, QtGui.QColor(108, 99, 255, 25))
                painter.setPen(QtGui.QColor("#8178ff"))
                painter.drawText(tag_rect, QtCore.Qt.AlignCenter, tag)

        painter.restore()
