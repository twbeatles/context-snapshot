from __future__ import annotations
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List
from PySide6 import QtCore, QtWidgets

from ctxsnap.i18n import tr
from ctxsnap.utils import git_title_suggestion
from ctxsnap.ui.styles import NoScrollComboBox


class SnapshotDialog(QtWidgets.QDialog):
    def __init__(
        self,
        parent: QtWidgets.QWidget,
        default_root: str,
        available_tags: List[str],
        templates: List[Dict[str, Any]],
        enforce_todos: bool = True,
    ):
        super().__init__(parent)
        self.setWindowTitle(tr("New Snapshot"))
        self.setModal(True)
        self.setMinimumWidth(500)
        self._templates = templates
        self._imported_payload = None
        self._import_apply_now = False
        self.enforce_todos = enforce_todos

        self.root_edit = QtWidgets.QLineEdit(default_root)
        self.title_edit = QtWidgets.QLineEdit()
        self.workspace_edit = QtWidgets.QLineEdit()
        self.workspace_edit.setPlaceholderText(tr("Workspace placeholder"))
        ws_btn = QtWidgets.QToolButton()
        ws_btn.setText(tr("Select Workspace"))
        ws_btn.clicked.connect(self.pick_workspace)
        ws_row = QtWidgets.QHBoxLayout()
        ws_row.addWidget(self.workspace_edit, 1)
        ws_row.addWidget(ws_btn)

        self.note_edit = QtWidgets.QTextEdit()
        self.note_edit.setPlaceholderText(tr("Note placeholder"))
        self.note_edit.setMaximumHeight(80)

        self.tags_list = QtWidgets.QListWidget()
        self.tags_list.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)
        self.tags_list.setMaximumHeight(80)
        for t in available_tags:
            it = QtWidgets.QListWidgetItem(t)
            it.setFlags(it.flags() | QtCore.Qt.ItemIsUserCheckable)
            it.setCheckState(QtCore.Qt.Unchecked)
            self.tags_list.addItem(it)

        self.custom_tag = QtWidgets.QLineEdit()
        self.custom_tag.setPlaceholderText(tr("Tags (optional)"))
        self.custom_tag.returnPressed.connect(self.add_custom_tag)

        self.todo1 = QtWidgets.QLineEdit()
        self.todo2 = QtWidgets.QLineEdit()
        self.todo3 = QtWidgets.QLineEdit()
        for t in (self.todo1, self.todo2, self.todo3):
            t.setPlaceholderText(tr("Required TODO"))
        self.title_edit.setPlaceholderText(tr("Title placeholder"))
        self.note_edit.setPlaceholderText(tr("Note placeholder"))

        template_row = QtWidgets.QHBoxLayout()
        self.template_combo = NoScrollComboBox()
        self.template_combo.addItem(tr("Select template"))
        for tmpl in templates:
            self.template_combo.addItem(str(tmpl.get("name", "")).strip() or tr("Untitled"))
        self.template_apply_btn = QtWidgets.QToolButton()
        self.template_apply_btn.setText(tr("Apply"))
        self.template_apply_btn.clicked.connect(self.apply_template)
        template_row.addWidget(self.template_combo, 1)
        template_row.addWidget(self.template_apply_btn)

        pick_btn = QtWidgets.QToolButton()
        pick_btn.setText(tr("Select folder"))
        pick_btn.clicked.connect(self.pick_folder)

        suggest_btn = QtWidgets.QToolButton()
        suggest_btn.setText(tr("Suggest Title"))
        suggest_btn.clicked.connect(self.suggest_title)

        root_row = QtWidgets.QHBoxLayout()
        root_row.addWidget(self.root_edit, 1)
        root_row.addWidget(pick_btn)

        title_row = QtWidgets.QHBoxLayout()
        title_row.addWidget(self.title_edit, 1)
        title_row.addWidget(suggest_btn)

        form = QtWidgets.QFormLayout()
        form.addRow(tr("Root"), root_row)
        form.addRow(tr("Title"), title_row)
        form.addRow(tr("Workspace"), ws_row)
        form.addRow(tr("Note"), self.note_edit)
        form.addRow(tr("Template"), template_row)

        tags_box = QtWidgets.QGroupBox(tr("Tags (optional)"))
        tags_layout = QtWidgets.QVBoxLayout(tags_box)
        tags_layout.addWidget(self.tags_list)
        tags_layout.addWidget(self.custom_tag)

        todo_box = QtWidgets.QGroupBox(tr("Next actions (3 required)"))
        todo_layout = QtWidgets.QVBoxLayout(todo_box)
        todo_layout.addWidget(self.todo1)
        todo_layout.addWidget(self.todo2)
        todo_layout.addWidget(self.todo3)

        self.err = QtWidgets.QLabel("")
        self.err.setStyleSheet("color: #ef4444; font-weight: 500;")
        self.err.setObjectName("ErrorLabel")

        btn_save = QtWidgets.QPushButton("✓ " + tr("Save Snapshot"))
        btn_save.setProperty("primary", True)
        btn_cancel = QtWidgets.QPushButton(tr("Cancel"))
        btn_save.clicked.connect(self.validate_and_accept)
        btn_cancel.clicked.connect(self.reject)

        btn_row = QtWidgets.QHBoxLayout()
        btn_row.setSpacing(10)
        btn_row.addStretch(1)
        btn_row.addWidget(btn_cancel)
        btn_row.addWidget(btn_save)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.addLayout(form)
        layout.addWidget(tags_box)
        layout.addWidget(todo_box)
        layout.addWidget(self.err)
        layout.addLayout(btn_row)

    def pick_folder(self):
        path = QtWidgets.QFileDialog.getExistingDirectory(self, tr("Select folder"), self.root_edit.text() or str(Path.home()))
        if path:
            self.root_edit.setText(path)

    def pick_workspace(self):
        start = self.root_edit.text().strip() or str(Path.home())
        f, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            tr("Select VSCode workspace"),
            start,
            "VSCode Workspace (*.code-workspace);;All Files (*)",
        )
        if f:
            self.workspace_edit.setText(f)

    def add_custom_tag(self):
        t = self.custom_tag.text().strip()
        if not t:
            return
        # prevent duplicates
        for i in range(self.tags_list.count()):
            if self.tags_list.item(i).text() == t:
                self.custom_tag.clear()
                return
        it = QtWidgets.QListWidgetItem(t)
        it.setFlags(it.flags() | QtCore.Qt.ItemIsUserCheckable)
        it.setCheckState(QtCore.Qt.Checked)
        self.tags_list.addItem(it)
        self.custom_tag.clear()

    def suggest_title(self):
        root = Path(self.root_edit.text().strip()).expanduser()
        sug = git_title_suggestion(root)
        if sug:
            self.title_edit.setText(sug)
        else:
            self.title_edit.setText(f"{root.name} - {datetime.now().strftime('%m/%d %H:%M')}")

    def imported_payload(self):
        return self._imported_payload

    def import_apply_now(self) -> bool:
        return bool(self._import_apply_now)

    def validate_and_accept(self):
        root = self.root_edit.text().strip()
        # root validation
        if not root or not Path(root).exists():
            self.err.setText(tr("Root invalid"))
            return
        
        # TODOS validation
        todos = [self.todo1.text().strip(), self.todo2.text().strip(), self.todo3.text().strip()]
        if self.enforce_todos:
            if any(not t for t in todos):
                self.err.setText(tr("Todos required"))
                return
        self.accept()

    def values(self) -> Dict[str, Any]:
        root = str(Path(self.root_edit.text().strip()).resolve())
        title = self.title_edit.text().strip()
        workspace = self.workspace_edit.text().strip()
        note = self.note_edit.toPlainText().strip()
        todos = [self.todo1.text().strip(), self.todo2.text().strip(), self.todo3.text().strip()]

        tags: List[str] = []
        for i in range(self.tags_list.count()):
            it = self.tags_list.item(i)
            if it.checkState() == QtCore.Qt.Checked:
                tags.append(it.text())
        if not title:
            # fallback suggestion logic if empty
            sug = git_title_suggestion(Path(root))
            title = sug or f"{Path(root).name} - {datetime.now().strftime('%m/%d %H:%M')}"
        return {"root": root, "title": title, "workspace": workspace, "note": note, "todos": todos, "tags": tags}

    def apply_template(self):
        idx = self.template_combo.currentIndex() - 1
        if idx < 0 or idx >= len(self._templates):
            return
        tmpl = self._templates[idx]
        note = str(tmpl.get("note", "") or "")
        todos = tmpl.get("todos", []) or []
        tags = tmpl.get("tags", []) or []
        if note:
            self.note_edit.setText(note)
        if len(todos) >= 1:
            self.todo1.setText(str(todos[0]))
        if len(todos) >= 2:
            self.todo2.setText(str(todos[1]))
        if len(todos) >= 3:
            self.todo3.setText(str(todos[2]))
        for i in range(self.tags_list.count()):
            it = self.tags_list.item(i)
            it.setCheckState(QtCore.Qt.Checked if it.text() in tags else QtCore.Qt.Unchecked)


class EditSnapshotDialog(SnapshotDialog):
    """Dialog for editing an existing snapshot."""
    
    def __init__(
        self,
        parent: QtWidgets.QWidget,
        snapshot: Dict[str, Any],
        available_tags: List[str],
        templates: List[Dict[str, Any]],
        enforce_todos: bool = True,
    ):
        super().__init__(
            parent,
            snapshot.get("root", str(Path.home())),
            available_tags,
            templates,
            enforce_todos=enforce_todos,
        )
        self.setWindowTitle(tr("Edit Snapshot"))
        self._snapshot_id = snapshot.get("id", "")
        
        # Populate fields with existing data
        self.title_edit.setText(snapshot.get("title", ""))
        self.workspace_edit.setText(snapshot.get("vscode_workspace", ""))
        self.note_edit.setText(snapshot.get("note", ""))
        
        todos = snapshot.get("todos", [])
        if len(todos) >= 1:
            self.todo1.setText(todos[0])
        if len(todos) >= 2:
            self.todo2.setText(todos[1])
        if len(todos) >= 3:
            self.todo3.setText(todos[2])
        
        # Check existing tags
        existing_tags = set(snapshot.get("tags", []))
        for i in range(self.tags_list.count()):
            it = self.tags_list.item(i)
            if it.text() in existing_tags:
                it.setCheckState(QtCore.Qt.Checked)
                existing_tags.discard(it.text())
        
        # Add any tags that weren't in the available list
        for tag in existing_tags:
            it = QtWidgets.QListWidgetItem(tag)
            it.setFlags(it.flags() | QtCore.Qt.ItemIsUserCheckable)
            it.setCheckState(QtCore.Qt.Checked)
            self.tags_list.addItem(it)
    
    def snapshot_id(self) -> str:
        return self._snapshot_id
