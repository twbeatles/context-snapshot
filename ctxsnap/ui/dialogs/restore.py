from __future__ import annotations
from pathlib import Path
from typing import Any, Dict, List, Optional
from PySide6 import QtCore, QtWidgets
from ctxsnap.i18n import tr
from ctxsnap.utils import git_dirty, git_state


class RestorePreviewDialog(QtWidgets.QDialog):
    """Preview dialog shown before restoring a snapshot."""

    def __init__(self, parent: QtWidgets.QWidget, snapshot: Dict[str, Any], restore_opts: Dict[str, Any]) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("Restore preview"))
        self.setModal(True)
        self.setMinimumSize(600, 440)

        title = QtWidgets.QLabel(tr("Restore preview"))
        title.setObjectName("TitleLabel")

        # Snapshot info rendered as structured HTML
        snap_title = snapshot.get("title", "")
        snap_root = snapshot.get("root", "")
        snap_created = snapshot.get("created_at", "")
        snap_note = snapshot.get("note", "") or ""
        todos = snapshot.get("todos", [])
        todo_html = "".join(f"<div style='padding:2px 0;'>{i+1}. {str(t or '').strip() or '(empty)'}</div>" for i, t in enumerate(todos[:3]))

        # Git context (best-effort): show saved vs current and warn on mismatch.
        saved_branch = str(snapshot.get("git_branch") or "").strip()
        saved_sha = str(snapshot.get("git_sha") or "").strip()
        saved_dirty = bool(snapshot.get("git_dirty", False))
        cur_branch = ""
        cur_sha = ""
        cur_dirty = None
        try:
            root_path = Path(str(snap_root or "")).expanduser()
            st = git_state(root_path)
            if st:
                cur_branch, cur_sha = st
                cur_dirty = git_dirty(root_path)
        except Exception:
            cur_branch, cur_sha, cur_dirty = "", "", None

        def _sha_short(s: str) -> str:
            s = (s or "").strip()
            return s[:8] if len(s) >= 8 else s

        git_rows = ""
        git_warn = ""
        if saved_branch or saved_sha or cur_branch or cur_sha:
            saved_str = ""
            if saved_branch or saved_sha:
                saved_str = f"{saved_branch or '?'}@{_sha_short(saved_sha) or '?'}" + (" (dirty)" if saved_dirty else "")
            else:
                saved_str = "(none)"
            cur_str = ""
            if cur_branch or cur_sha:
                cur_str = f"{cur_branch or '?'}@{_sha_short(cur_sha) or '?'}"
                if cur_dirty is True:
                    cur_str += " (dirty)"
            else:
                cur_str = "(not a git repo)"

            mismatch = False
            if saved_branch and cur_branch and saved_branch != cur_branch:
                mismatch = True
            if saved_sha and cur_sha and saved_sha != cur_sha:
                mismatch = True
            if cur_dirty is not None and bool(saved_dirty) != bool(cur_dirty):
                mismatch = True
            if mismatch:
                git_warn = f"<div style='margin-top:6px;color:#fbbf24;font-size:12px;'><b>{tr('Git mismatch warn')}</b></div>"

            git_rows = f"""
            <div style="background:#18181f;border:1px solid #262636;border-radius:8px;padding:10px 12px;margin-bottom:8px;">
                <div style="font-size:11px;color:#8888a0;font-weight:600;text-transform:uppercase;margin-bottom:4px;">{tr('Git')}</div>
                <div style="font-size:13px;">{tr('Saved')}: {saved_str}</div>
                <div style="font-size:13px;">{tr('Current')}: {cur_str}</div>
                {git_warn}
            </div>
            """

        info_html = f"""
        <div style="font-family:'Segoe UI','Malgun Gothic',sans-serif;color:#e8e8f0;line-height:1.6;">
            <div style="font-size:15px;font-weight:600;margin-bottom:8px;">{snap_title}</div>
            <div style="color:#8888a0;font-size:12px;margin-bottom:12px;">{snap_root}  ·  {snap_created}</div>
            {git_rows}
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
        self.opt_recent_files = QtWidgets.QCheckBox(tr("Open recent files in VSCode"))

        self.opt_folder.setChecked(bool(restore_opts.get("open_folder", True)))
        self.opt_terminal.setChecked(bool(restore_opts.get("open_terminal", True)))
        self.opt_vscode.setChecked(bool(restore_opts.get("open_vscode", True)))
        self.opt_running_apps.setChecked(bool(restore_opts.get("open_running_apps", False)))
        self.opt_recent_files.setChecked(bool(restore_opts.get("open_recent_files", False)))
        self.opt_recent_files.setEnabled(bool(self.opt_vscode.isChecked()))
        self.opt_vscode.toggled.connect(lambda on: self.opt_recent_files.setEnabled(bool(on)))

        opts_box = QtWidgets.QGroupBox(tr("Restore Options"))
        opts_layout = QtWidgets.QVBoxLayout(opts_box)
        opts_layout.setSpacing(6)
        opts_layout.addWidget(self.opt_folder)
        opts_layout.addWidget(self.opt_terminal)
        opts_layout.addWidget(self.opt_vscode)
        opts_layout.addWidget(self.opt_recent_files)
        opts_layout.addWidget(self.opt_running_apps)

        # Running apps picker (only if restoring apps)
        self.apps_box = QtWidgets.QGroupBox(tr("Running apps to restore"))
        apps_l = QtWidgets.QVBoxLayout(self.apps_box)
        apps_l.setSpacing(6)
        self.apps_list = QtWidgets.QListWidget()
        self.apps_list.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)

        apps = snapshot.get("running_apps", []) if isinstance(snapshot.get("running_apps"), list) else []
        for app in apps:
            if not isinstance(app, dict):
                continue
            name = str(app.get("name") or app.get("exe") or "app").strip()
            title_txt = str(app.get("title") or "").strip()
            label = name if not title_txt else f"{name}  ·  {title_txt}"
            it = QtWidgets.QListWidgetItem(label)
            it.setFlags(it.flags() | QtCore.Qt.ItemIsUserCheckable)
            it.setCheckState(QtCore.Qt.Checked)
            it.setData(QtCore.Qt.UserRole, app)
            self.apps_list.addItem(it)

        btn_row_apps = QtWidgets.QHBoxLayout()
        btn_sel_all = QtWidgets.QPushButton(tr("Select all"))
        btn_sel_none = QtWidgets.QPushButton(tr("Select none"))
        btn_row_apps.addWidget(btn_sel_all)
        btn_row_apps.addWidget(btn_sel_none)
        btn_row_apps.addStretch(1)

        def _set_all(state: QtCore.Qt.CheckState) -> None:
            for i in range(self.apps_list.count()):
                it = self.apps_list.item(i)
                it.setCheckState(state)

        btn_sel_all.clicked.connect(lambda: _set_all(QtCore.Qt.Checked))
        btn_sel_none.clicked.connect(lambda: _set_all(QtCore.Qt.Unchecked))

        apps_l.addWidget(self.apps_list, 1)
        apps_l.addLayout(btn_row_apps)
        self._has_apps = bool(apps)
        self.apps_box.setVisible(bool(apps))
        self.apps_list.setEnabled(bool(self.opt_running_apps.isChecked()))
        self.apps_box.setEnabled(bool(self.opt_running_apps.isChecked()))
        self.opt_running_apps.toggled.connect(lambda on: self.apps_box.setEnabled(bool(on)))
        self.opt_running_apps.toggled.connect(lambda on: self.apps_list.setEnabled(bool(on)))

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
        if bool(apps):
            layout.addWidget(self.apps_box)
        layout.addLayout(btn_row)

    def restore_options(self) -> Dict[str, bool]:
        return {
            "open_folder": bool(self.opt_folder.isChecked()),
            "open_terminal": bool(self.opt_terminal.isChecked()),
            "open_vscode": bool(self.opt_vscode.isChecked()),
            "open_running_apps": bool(self.opt_running_apps.isChecked()),
            "open_recent_files": bool(self.opt_recent_files.isChecked()),
        }

    def choices(self) -> Dict[str, Any]:
        ch: Dict[str, Any] = dict(self.restore_options())
        selected_apps: List[Dict[str, Any]] = []
        if ch.get("open_running_apps") and bool(getattr(self, "_has_apps", False)):
            for i in range(self.apps_list.count()):
                it = self.apps_list.item(i)
                if it.checkState() == QtCore.Qt.Checked:
                    app = it.data(QtCore.Qt.UserRole)
                    if isinstance(app, dict):
                        selected_apps.append(app)
        ch["running_apps"] = selected_apps
        return ch


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
