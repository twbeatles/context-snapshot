from __future__ import annotations
from typing import Any, Dict, List
from PySide6 import QtCore, QtWidgets
from ctxsnap.i18n import tr


class RestorePreviewDialog(QtWidgets.QDialog):
    def __init__(
        self,
        parent: QtWidgets.QWidget,
        snap: Dict[str, Any],
        open_folder: bool,
        open_terminal: bool,
        open_vscode: bool,
        open_running_apps: bool,
    ):
        super().__init__(parent)
        self.setWindowTitle(tr("Restore preview"))
        self.setModal(True)
        self.setMinimumWidth(700)
        self.setMinimumHeight(500)

        # Title section
        title = QtWidgets.QLabel("🔄 " + snap.get("title", "Snapshot"))
        title.setObjectName("TitleLabel")

        hint = QtWidgets.QLabel(tr("Restore hint"))
        hint.setObjectName("HintLabel")

        # Restore options groupbox
        options_group = QtWidgets.QGroupBox(tr("Restore Options"))
        options_layout = QtWidgets.QVBoxLayout(options_group)
        options_layout.setSpacing(8)
        
        self.cb_folder = QtWidgets.QCheckBox("📁 " + tr("Open folder"))
        self.cb_terminal = QtWidgets.QCheckBox("💻 " + tr("Open terminal"))
        self.cb_vscode = QtWidgets.QCheckBox("🔷 " + tr("Open VSCode"))
        self.cb_running_apps = QtWidgets.QCheckBox("📱 " + tr("Open running apps"))
        self.cb_folder.setChecked(open_folder)
        self.cb_terminal.setChecked(open_terminal)
        self.cb_vscode.setChecked(open_vscode)
        self.cb_running_apps.setChecked(open_running_apps)
        
        options_layout.addWidget(self.cb_folder)
        options_layout.addWidget(self.cb_terminal)
        options_layout.addWidget(self.cb_vscode)
        options_layout.addWidget(self.cb_running_apps)

        root = snap.get("root", "")
        note = snap.get("note", "")
        todos = snap.get("todos", [])
        recent = snap.get("recent_files", [])
        running_apps = snap.get("running_apps", [])
        
        # Apps list (if any)
        self.apps_list = QtWidgets.QListWidget()
        self.apps_list.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)
        self.apps_list.setMaximumHeight(120)
        for app in running_apps:
            label = f"  {app.get('name','')}  •  {app.get('exe','')}"
            item = QtWidgets.QListWidgetItem(label)
            item.setFlags(item.flags() | QtCore.Qt.ItemIsUserCheckable)
            item.setCheckState(QtCore.Qt.Checked if open_running_apps else QtCore.Qt.Unchecked)
            item.setData(QtCore.Qt.UserRole, app)
            self.apps_list.addItem(item)

        # Snapshot info display
        info = QtWidgets.QTextEdit()
        info.setReadOnly(True)
        info.setPlaceholderText(tr("Snapshot details"))
        
        todo_text = "\n".join([f"  {i+1}. {t}" for i, t in enumerate(todos[:3]) if t])
        recent_text = "\n".join([f"  • {p}" for p in recent[:8]])
        apps_text = "\n".join([f"  • {p.get('name','')}  →  {p.get('exe','')}" for p in running_apps[:6]])
        
        info.setText(
            f"📂 Root:\n  {root}\n\n"
            f"📝 Note:\n  {note or '(none)'}\n\n"
            f"📋 TODOs:\n{todo_text or '  (none)'}\n\n"
            f"📁 Recent files ({len(recent)} total, showing top 8):\n{recent_text or '  (none)'}\n\n"
            f"📱 Running apps ({len(running_apps)} total, showing top 6):\n{apps_text or '  (none)'}"
        )

        # Buttons
        btn_restore = QtWidgets.QPushButton("▶ " + tr("Restore"))
        btn_restore.setProperty("primary", True)
        btn_cancel = QtWidgets.QPushButton(tr("Cancel"))
        btn_restore.clicked.connect(self.accept)
        btn_cancel.clicked.connect(self.reject)

        btn_row = QtWidgets.QHBoxLayout()
        btn_row.setSpacing(10)
        btn_row.addStretch(1)
        btn_row.addWidget(btn_cancel)
        btn_row.addWidget(btn_restore)

        # Main layout
        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.addWidget(title)
        layout.addWidget(hint)
        layout.addSpacing(8)
        layout.addWidget(options_group)
        
        if running_apps:
            apps_label = QtWidgets.QLabel("📱 " + tr("Running apps to restore"))
            apps_label.setObjectName("SubtitleLabel")
            layout.addWidget(apps_label)
            layout.addWidget(self.apps_list)
            
        layout.addSpacing(8)
        layout.addWidget(info, 1)
        layout.addLayout(btn_row)

    def choices(self) -> Dict[str, Any]:
        selected_apps = []
        for i in range(self.apps_list.count()):
            it = self.apps_list.item(i)
            if it.checkState() == QtCore.Qt.Checked:
                selected_apps.append(it.data(QtCore.Qt.UserRole))
        return {
            "open_folder": self.cb_folder.isChecked(),
            "open_terminal": self.cb_terminal.isChecked(),
            "open_vscode": self.cb_vscode.isChecked(),
            "open_running_apps": self.cb_running_apps.isChecked(),
            "running_apps": selected_apps,
        }


class ChecklistDialog(QtWidgets.QDialog):
    def __init__(self, parent: QtWidgets.QWidget, todos: List[str]) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("Checklist"))
        self.setModal(True)
        self.setMinimumWidth(480)
        self.setMinimumHeight(320)

        title = QtWidgets.QLabel("✅ " + tr("Post-restore checklist"))
        title.setObjectName("TitleLabel")
        
        hint = QtWidgets.QLabel(tr("Checklist hint"))
        hint.setObjectName("HintLabel")

        self.listw = QtWidgets.QListWidget()
        self.listw.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)
        for i, t in enumerate(todos):
            if t:  # Skip empty todos
                it = QtWidgets.QListWidgetItem(f"  {i+1}. {t}")
                it.setFlags(it.flags() | QtCore.Qt.ItemIsUserCheckable)
                it.setCheckState(QtCore.Qt.Unchecked)
                self.listw.addItem(it)

        btn_ok = QtWidgets.QPushButton("✓ " + tr("Done"))
        btn_ok.setProperty("primary", True)
        btn_ok.clicked.connect(self.accept)
        
        btn_row = QtWidgets.QHBoxLayout()
        btn_row.setSpacing(10)
        btn_row.addStretch(1)
        btn_row.addWidget(btn_ok)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.addWidget(title)
        layout.addWidget(hint)
        layout.addWidget(self.listw, 1)
        layout.addLayout(btn_row)
