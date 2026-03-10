from __future__ import annotations
from typing import Any, Dict, List, Optional, cast
from PySide6 import QtCore, QtGui, QtWidgets


class SnapshotItemDelegate(QtWidgets.QStyledItemDelegate):
    """HTML을 지원하는 QListView 커스텀 카드 델리게이트"""
    def paint(
        self,
        painter: QtGui.QPainter,
        option: QtWidgets.QStyleOptionViewItem,
        index: QtCore.QModelIndex | QtCore.QPersistentModelIndex,
    ) -> None:
        options = QtWidgets.QStyleOptionViewItem(option)
        self.initStyleOption(options, index)
        options_any = cast(Any, options)

        # 기본 배경 및 선택 효과 그리기 (CSS 스타일 유지)
        style = (
            options_any.widget.style()
            if options_any.widget
            else QtWidgets.QApplication.style()
        )
        options_any.text = ""  # 기본 텍스트 렌더링 방지
        style.drawControl(
            QtWidgets.QStyle.ControlElement.CE_ItemViewItem,
            options,
            painter,
            options_any.widget,
        )

        painter.save()
        
        # HTML 텍스트 문서 생성
        doc = QtGui.QTextDocument()
        doc.setDefaultFont(options_any.font)
        doc.setHtml(str(index.data(QtCore.Qt.ItemDataRole.DisplayRole) or ""))
        doc.setTextWidth(float(options_any.rect.width()))
        
        # 렌더링 위치 설정
        painter.translate(options_any.rect.left(), options_any.rect.top())
        clip = QtCore.QRectF(
            0.0,
            0.0,
            float(options_any.rect.width()),
            float(options_any.rect.height()),
        )
        doc.drawContents(painter, clip)
        
        painter.restore()

    def sizeHint(
        self,
        option: QtWidgets.QStyleOptionViewItem,
        index: QtCore.QModelIndex | QtCore.QPersistentModelIndex,
    ) -> QtCore.QSize:
        options = QtWidgets.QStyleOptionViewItem(option)
        self.initStyleOption(options, index)
        options_any = cast(Any, options)
        
        doc = QtGui.QTextDocument()
        doc.setDefaultFont(options_any.font)
        doc.setHtml(str(index.data(QtCore.Qt.ItemDataRole.DisplayRole) or ""))
        rect_width = int(options_any.rect.width())
        doc.setTextWidth(float(rect_width if rect_width > 0 else 300))
        
        return QtCore.QSize(int(doc.idealWidth()), int(doc.size().height()))


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

    def rowCount(
        self,
        parent: QtCore.QModelIndex | QtCore.QPersistentModelIndex = QtCore.QModelIndex(),
    ) -> int:
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

    def data(
        self,
        index: QtCore.QModelIndex | QtCore.QPersistentModelIndex,
        role: int = int(QtCore.Qt.ItemDataRole.DisplayRole),
    ) -> Any:
        if not index.isValid():
            return None
        row = index.row()
        if row < 0 or row >= len(self._items):
            return None
        
        item = self._items[row]
        sid = str(item.get("id") or "")
        if role == int(QtCore.Qt.ItemDataRole.DisplayRole):
            cached = self._display_cache.get(sid)
            if cached is not None:
                return cached
            title = item.get("title", "")
            root = item.get("root", "")
            created = item.get("created_at", "")
            tags = item.get("tags", []) or []
            pin = "📌&nbsp;" if bool(item.get("pinned", False)) else ""
            archived = "🗄️&nbsp;" if bool(item.get("archived", False)) else ""
            
            # 태그 배지 HTML 디자인
            tag_html = ""
            for tag in tags:
                tag_html += f'<span style="background-color: #2a2a40; color: #a78bfa; padding: 2px 6px; border-radius: 4px; font-size: 11px;">{tag}</span>&nbsp;'
            
            # 메인 타이틀
            title_html = f'<span style="font-size: 14px; font-weight: bold; color: #f0f0f5;">{title}</span>'
            
            # 하위 정보
            sub_html = f'<span style="font-size: 12px; color: #9090a8;">{root} &bull; {created}</span>'
            
            html = f"{pin}{archived}{tag_html}<br>{title_html}<br>{sub_html}"
            
            self._display_cache[sid] = html
            return html
            
        if role == int(QtCore.Qt.ItemDataRole.UserRole):
            return sid
        
        if role == int(QtCore.Qt.ItemDataRole.UserRole) + 1:
            return item
            
        return None
