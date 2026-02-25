from __future__ import annotations
import difflib
from typing import Any, Callable, Dict, List, Optional
from PySide6 import QtCore, QtWidgets
from ctxsnap.i18n import tr
from ctxsnap.ui.styles import NoScrollComboBox


class RestoreHistoryDialog(QtWidgets.QDialog):
    def __init__(self, parent: QtWidgets.QWidget, history: Dict[str, Any]) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("Restore History"))
        self.setModal(True)
        self.setMinimumSize(680, 480)

        title = QtWidgets.QLabel("📋 " + tr("Restore History"))
        title.setObjectName("TitleLabel")

        self.listw = QtWidgets.QListWidget()
        self.listw.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.detail = QtWidgets.QTextEdit()
        self.detail.setReadOnly(True)
        self.detail.setPlaceholderText(tr("Select a restore entry to view details."))

        self._items = history.get("restores", []) if isinstance(history.get("restores"), list) else []
        for entry in self._items:
            label = f"🕐 {entry.get('created_at','')}  •  {entry.get('snapshot_id','')}"
            self.listw.addItem(label)

        self.listw.currentRowChanged.connect(self._on_select)

        btn_close = QtWidgets.QPushButton(tr("Close"))
        btn_close.clicked.connect(self.accept)
        btn_row = QtWidgets.QHBoxLayout()
        btn_row.setSpacing(10)
        btn_row.addStretch(1)
        btn_row.addWidget(btn_close)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.addWidget(title)
        layout.addWidget(self.listw, 1)
        layout.addWidget(self.detail, 2)
        layout.addLayout(btn_row)

    def _on_select(self, row: int) -> None:
        if row < 0 or row >= len(self._items):
            self.detail.clear()
            return
        entry = self._items[row]
        failed_raw = entry.get("running_apps_failed")
        failed_count = entry.get("running_apps_failed_count")
        if failed_count is None:
            if isinstance(failed_raw, list):
                failed_count = len(failed_raw)
            elif isinstance(failed_raw, (int, float)):
                failed_count = int(failed_raw)
            else:
                failed_count = 0
        lines = [
            f"📝 Snapshot ID: {entry.get('snapshot_id','')}",
            f"🕐 Created: {entry.get('created_at','')}",
            "",
            "📂 Actions:",
            f"   • Open folder: {'✓' if entry.get('open_folder') else '✗'}",
            f"   • Open terminal: {'✓' if entry.get('open_terminal') else '✗'}",
            f"   • Open VSCode: {'✓' if entry.get('open_vscode') else '✗'}",
            f"   • Restore apps: {'✓' if entry.get('open_running_apps') else '✗'}",
            "",
            "📊 Results:",
            f"   • Apps requested: {entry.get('running_apps_requested', 0)}",
            f"   • Apps failed: {failed_count}",
            f"   • Root missing: {'Yes' if entry.get('root_missing') else 'No'}",
            f"   • VSCode opened: {'Yes' if entry.get('vscode_opened') else 'No'}",
        ]
        self.detail.setText("\n".join(str(l) for l in lines))


class CompareDialog(QtWidgets.QDialog):
    def __init__(self, parent: QtWidgets.QWidget, snapshots: List[Dict[str, Any]], loader: Callable[[str], Optional[Dict[str, Any]]]) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("Compare Snapshots"))
        self.setModal(True)
        self.setMinimumSize(780, 560)
        self._snaps = snapshots
        self._loader = loader

        title = QtWidgets.QLabel("🔍 " + tr("Compare two snapshots"))
        title.setObjectName("TitleLabel")

        # Combo boxes with labels
        label_a = QtWidgets.QLabel("A:")
        label_a.setObjectName("SubtitleLabel")
        label_b = QtWidgets.QLabel("B:")
        label_b.setObjectName("SubtitleLabel")
        
        self.left_combo = NoScrollComboBox()
        self.right_combo = NoScrollComboBox()
        for snap in snapshots:
            label = f"{snap.get('title','')}  •  {snap.get('created_at','')}"
            self.left_combo.addItem(label)
            self.right_combo.addItem(label)

        if snapshots:
            self.left_combo.setCurrentIndex(0)
            self.right_combo.setCurrentIndex(min(1, len(snapshots) - 1))

        row = QtWidgets.QHBoxLayout()
        row.setSpacing(12)
        row.addWidget(label_a)
        row.addWidget(self.left_combo, 1)
        row.addSpacing(16)
        row.addWidget(label_b)
        row.addWidget(self.right_combo, 1)

        self.diff_view = QtWidgets.QTextEdit()
        self.diff_view.setReadOnly(True)
        self.diff_view.setPlaceholderText(tr("Click Compare to see differences"))

        btn_compare = QtWidgets.QPushButton("⚡ " + tr("Compare"))
        btn_compare.setProperty("primary", True)
        btn_compare.clicked.connect(self._run_compare)
        btn_close = QtWidgets.QPushButton(tr("Close"))
        btn_close.clicked.connect(self.accept)
        
        btn_row = QtWidgets.QHBoxLayout()
        btn_row.setSpacing(10)
        btn_row.addStretch(1)
        btn_row.addWidget(btn_compare)
        btn_row.addWidget(btn_close)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.addWidget(title)
        layout.addLayout(row)
        layout.addWidget(self.diff_view, 1)
        layout.addLayout(btn_row)

    def _serialize(self, snap: Dict[str, Any]) -> List[str]:
        lines = [
            f"Title: {snap.get('title','')}",
            f"Created: {snap.get('created_at','')}",
            f"Root: {snap.get('root','')}",
            f"Note: {snap.get('note','')}",
            "",
            "TODOs:",
        ]
        lines.extend([f"  • {t}" for t in snap.get("todos", [])])
        lines.append("")
        lines.append("Tags: " + ", ".join(snap.get("tags", []) or []))
        lines.append("")
        lines.append("Recent files:")
        lines.extend([f"  • {p}" for p in snap.get("recent_files", [])[:10]])
        if len(snap.get("recent_files", [])) > 10:
            lines.append(f"  ... and {len(snap.get('recent_files', [])) - 10} more")
        lines.append("")
        lines.append("Processes:")
        lines.extend([f"  • {p.get('name','')} → {p.get('exe','')}" for p in snap.get("processes", [])[:10]])
        lines.append("")
        lines.append("Running apps:")
        lines.extend([f"  • {p.get('name','')} → {p.get('exe','')}" for p in snap.get("running_apps", [])[:10]])
        return lines

    def _run_compare(self) -> None:
        if not self._snaps:
            self.diff_view.setText(tr("Need at least two snapshots to compare"))
            return
        left_meta = self._snaps[self.left_combo.currentIndex()]
        right_meta = self._snaps[self.right_combo.currentIndex()]
        left = self._loader(left_meta.get("id")) or left_meta
        right = self._loader(right_meta.get("id")) or right_meta
        left_lines = self._serialize(left)
        right_lines = self._serialize(right)
        diff = difflib.unified_diff(
            left_lines,
            right_lines,
            fromfile="Snapshot A",
            tofile="Snapshot B",
            lineterm="",
        )
        diff_text = "\n".join(diff)
        if not diff_text.strip():
            diff_text = "✓ No differences found between the two snapshots."
        self.diff_view.setText(diff_text)
