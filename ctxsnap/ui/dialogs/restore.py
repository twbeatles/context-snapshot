from __future__ import annotations
from typing import Any, Dict, List, Optional
from PySide6 import QtCore, QtWidgets
from ctxsnap.i18n import tr


class RestorePreviewDialog(QtWidgets.QDialog):
    """Preview dialog shown before restoring a snapshot."""

    def __init__(self, parent: QtWidgets.QWidget, snapshot: Dict[str, Any], restore_opts: Dict[str, Any]) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("Restore Preview"))
        self.setModal(True)
        self.setMinimumSize(600, 440)

        title = QtWidgets.QLabel(tr("Restore Preview"))
        title.setObjectName("TitleLabel")

        # Snapshot info rendered as structured HTML
        snap_title = snapshot.get("title", "")
        snap_root = snapshot.get("root", "")
        snap_created = snapshot.get("created_at", "")
        snap_note = snapshot.get("note", "") or ""
        todos = snapshot.get("todos", [])
        todo_html = "".join(f"<div style='padding:2px 0;'>{i+1}. {str(t or '').strip() or '(empty)'}</div>" for i, t in enumerate(todos[:3]))

        info_html = f"""
        <div style="font-family:'Segoe UI','Malgun Gothic',sans-serif;color:#e8e8f0;line-height:1.6;">
            <div style="font-size:15px;font-weight:600;margin-bottom:8px;">{snap_title}</div>
            <div style="color:#8888a0;font-size:12px;margin-bottom:12px;">{snap_root}  ·  {snap_created}</div>
            <div style="background:#18181f;border:1px solid #262636;border-radius:8px;padding:10px 12px;margin-bottom:8px;">
                <div style="font-size:11px;color:#8888a0;font-weight:600;text-transform:uppercase;margin-bottom:4px;">{tr('Note')}</div>
                <div style="font-size:13px;">{snap_note.replace(chr(10), '<br>') if snap_note else '<span style="color:#555568;">(none)</span>'}</div>
            </div>
            <div style="background:#18181f;border:1px solid #262636;border-radius:8px;padding:10px 12px;">
                <div style="font-size:11px;color:#8888a0;font-weight:600;text-transform:uppercase;margin-bottom:4px;">{tr('TODOs')}</div>
                {todo_html}
            </div>
        </div>
        """

        info_view = QtWidgets.QTextBrowser()
        info_view.setHtml(info_html)
        info_view.setReadOnly(True)
        info_view.setOpenExternalLinks(False)

        # Restore options
        self.opt_folder = QtWidgets.QCheckBox(tr("Open folder on restore"))
        self.opt_terminal = QtWidgets.QCheckBox(tr("Open terminal on restore"))
        self.opt_vscode = QtWidgets.QCheckBox(tr("Open VSCode on restore"))
        self.opt_running_apps = QtWidgets.QCheckBox(tr("Restore apps on restore"))

        self.opt_folder.setChecked(bool(restore_opts.get("open_folder", True)))
        self.opt_terminal.setChecked(bool(restore_opts.get("open_terminal", True)))
        self.opt_vscode.setChecked(bool(restore_opts.get("open_vscode", True)))
        self.opt_running_apps.setChecked(bool(restore_opts.get("open_running_apps", False)))

        opts_box = QtWidgets.QGroupBox(tr("Restore Options"))
        opts_layout = QtWidgets.QVBoxLayout(opts_box)
        opts_layout.setSpacing(6)
        opts_layout.addWidget(self.opt_folder)
        opts_layout.addWidget(self.opt_terminal)
        opts_layout.addWidget(self.opt_vscode)
        opts_layout.addWidget(self.opt_running_apps)

        btn_restore = QtWidgets.QPushButton(tr("Restore"))
        btn_restore.setProperty("primary", True)
        btn_cancel = QtWidgets.QPushButton(tr("Cancel"))
        btn_restore.clicked.connect(self.accept)
        btn_cancel.clicked.connect(self.reject)
        btn_row = QtWidgets.QHBoxLayout()
        btn_row.setSpacing(10)
        btn_row.addStretch(1)
        btn_row.addWidget(btn_cancel)
        btn_row.addWidget(btn_restore)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.addWidget(title)
        layout.addWidget(info_view, 1)
        layout.addWidget(opts_box)
        layout.addLayout(btn_row)

    def restore_options(self) -> Dict[str, bool]:
        return {
            "open_folder": bool(self.opt_folder.isChecked()),
            "open_terminal": bool(self.opt_terminal.isChecked()),
            "open_vscode": bool(self.opt_vscode.isChecked()),
            "open_running_apps": bool(self.opt_running_apps.isChecked()),
        }


class ChecklistDialog(QtWidgets.QDialog):
    """Post-restore checklist dialog."""

    def __init__(self, parent: QtWidgets.QWidget, items: List[str]) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("Post-Restore Checklist"))
        self.setModal(True)
        self.setMinimumSize(460, 360)

        title = QtWidgets.QLabel(tr("Post-Restore Checklist"))
        title.setObjectName("TitleLabel")
        hint = QtWidgets.QLabel(tr("Check off completed items"))
        hint.setObjectName("HintLabel")

        self.checks: List[QtWidgets.QCheckBox] = []
        checklist_widget = QtWidgets.QWidget()
        check_layout = QtWidgets.QVBoxLayout(checklist_widget)
        check_layout.setSpacing(8)
        check_layout.setContentsMargins(8, 8, 8, 8)
        for item in items:
            cb = QtWidgets.QCheckBox(item)
            check_layout.addWidget(cb)
            self.checks.append(cb)
        check_layout.addStretch(1)

        scroll = QtWidgets.QScrollArea()
        scroll.setWidget(checklist_widget)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.NoFrame)

        btn_done = QtWidgets.QPushButton(tr("Done"))
        btn_done.setProperty("primary", True)
        btn_done.clicked.connect(self.accept)
        btn_row = QtWidgets.QHBoxLayout()
        btn_row.addStretch(1)
        btn_row.addWidget(btn_done)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.addWidget(title)
        layout.addWidget(hint)
        layout.addWidget(scroll, 1)
        layout.addLayout(btn_row)
