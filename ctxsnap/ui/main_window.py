from __future__ import annotations

import json
import os
from dataclasses import asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from PySide6 import QtCore, QtGui, QtWidgets

from ctxsnap.app_storage import (
    Snapshot,
    append_restore_history,
    app_dir,
    ensure_storage,
    export_backup_to_file,
    gen_id,
    load_json,
    migrate_settings,
    migrate_snapshot,
    now_iso,
    save_json,
    save_snapshot_file,
)
from ctxsnap.constants import APP_NAME, DEFAULT_TAGS
from ctxsnap.core.logging import get_logger
from ctxsnap.core.worker import RecentFilesWorker
from ctxsnap.i18n import tr
from ctxsnap.restore import (
    open_folder,
    open_terminal_at,
    open_vscode_at,
    resolve_vscode_target,
)
from ctxsnap.ui.dialogs.history import CompareDialog, RestoreHistoryDialog
from ctxsnap.ui.dialogs.onboarding import OnboardingDialog
from ctxsnap.ui.dialogs.restore import ChecklistDialog, RestorePreviewDialog
from ctxsnap.ui.dialogs.settings import SettingsDialog
from ctxsnap.ui.dialogs.snapshot import EditSnapshotDialog, SnapshotDialog
from ctxsnap.ui.models import SnapshotListModel
from ctxsnap.ui.styles import NoScrollComboBox
from ctxsnap.utils import (
    build_search_blob,
    git_state,
    git_title_suggestion,
    list_processes_filtered,
    list_running_apps,
    log_exc,
    recent_files_under,
    restore_running_apps,
    safe_parse_datetime,
    snapshot_mtime,
)

LOGGER = get_logger()


class MainWindow(QtWidgets.QMainWindow):
    def _set_last_snapshot_form_in_memory(
        self,
        *,
        root: str,
        workspace: str,
        note: str,
        todos: List[str],
        tags: List[str],
    ) -> None:
        # Keep this small and stable; used by silent Quick/Auto snapshots.
        t = (todos or [])[:3]
        while len(t) < 3:
            t.append("")
        self.settings["last_snapshot_form"] = {
            "root": str(root or self.settings.get("default_root", str(Path.home()))),
            "vscode_workspace": str(workspace or ""),
            "note": str(note or ""),
            "todos": [str(x or "") for x in t],
            "tags": [str(x).strip() for x in (tags or []) if str(x).strip()],
        }

    def _dedupe_title(self, root_path: Path, title: str) -> str:
        existing = {
            (str(Path(it.get("root", "")).resolve()), str(it.get("title", "")))
            for it in (self.index.get("snapshots", []) or [])
            if not bool(it.get("archived", False))
        }
        base = title.strip() or f"{root_path.name} - {datetime.now().strftime('%m/%d %H:%M')}"
        cand = base
        if (str(root_path.resolve()), cand) not in existing:
            return cand
        # Keep appending time until unique.
        stamp = datetime.now().strftime("%H:%M:%S")
        cand = f"{base} ({stamp})"
        if (str(root_path.resolve()), cand) not in existing:
            return cand
        for i in range(2, 50):
            cand2 = f"{base} ({stamp}) #{i}"
            if (str(root_path.resolve()), cand2) not in existing:
                return cand2
        return f"{base} ({datetime.now().strftime('%H%M%S')})"

    def _silent_snapshot(self, *, allow_dialog_fallback: bool, reason: str) -> bool:
        """Create a snapshot without showing SnapshotDialog.

        If required inputs are missing and allow_dialog_fallback is True, falls back to SnapshotDialog once.
        Returns True if a snapshot was created.
        """
        form = self.settings.get("last_snapshot_form", {}) if isinstance(self.settings.get("last_snapshot_form", {}), dict) else {}
        root = str(form.get("root") or self.settings.get("default_root", str(Path.home()))).strip()
        workspace = str(form.get("vscode_workspace") or "").strip()
        note = str(form.get("note") or "")
        todos_raw = form.get("todos") if isinstance(form.get("todos"), list) else []
        todos = [str(x or "").strip() for x in (todos_raw or [])][:3]
        while len(todos) < 3:
            todos.append("")
        tags_raw = form.get("tags") if isinstance(form.get("tags"), list) else []
        tags = [str(x).strip() for x in (tags_raw or []) if str(x).strip()]

        root_path = Path(root).expanduser()
        if not root or not root_path.exists():
            if allow_dialog_fallback:
                self.statusBar().showMessage(tr("Root invalid"), 3500)
                self._run_snapshot_dialog_prefill(
                    quick=True,
                    prefill={
                        "root": root,
                        "vscode_workspace": workspace,
                        "note": note,
                        "todos": todos,
                        "tags": tags,
                    },
                )
            else:
                self.statusBar().showMessage(f"Auto snapshot skipped ({reason}): invalid root.", 3500)
            return False

        capture_todos = bool(self.settings.get("capture_todos", True))
        enforce = bool(self.settings.get("capture_enforce_todos", True)) and capture_todos
        if enforce and any(not t for t in todos):
            if allow_dialog_fallback:
                self.statusBar().showMessage(tr("Todos required"), 3500)
                self._run_snapshot_dialog_prefill(
                    quick=True,
                    prefill={
                        "root": root,
                        "vscode_workspace": workspace,
                        "note": note,
                        "todos": todos,
                        "tags": tags,
                    },
                )
            else:
                self.statusBar().showMessage(f"Auto snapshot skipped ({reason}): TODOs required.", 3500)
            return False

        # Validate workspace if set; otherwise let _create_snapshot auto-pick a single workspace under root.
        if workspace:
            ws_path = Path(workspace).expanduser()
            if not ws_path.exists():
                workspace = ""

        root_resolved = str(root_path.resolve())
        title = git_title_suggestion(Path(root_resolved)) or f"{Path(root_resolved).name} - {datetime.now().strftime('%m/%d %H:%M')}"
        title = self._dedupe_title(Path(root_resolved), title)

        self._create_snapshot(
            root_resolved,
            title,
            workspace,
            note,
            todos,
            tags,
            interactive=False,
        )
        return True

    def _run_snapshot_dialog(self, *, quick: bool) -> bool:
        return self._run_snapshot_dialog_prefill(quick=quick, prefill=None)

    def _run_snapshot_dialog_prefill(self, *, quick: bool, prefill: Optional[Dict[str, Any]]) -> bool:
        dlg = SnapshotDialog(
            self,
            self.settings.get("default_root", str(Path.home())),
            self.settings.get("tags", DEFAULT_TAGS),
            self.settings.get("templates", []),
            enforce_todos=bool(self.settings.get("capture_enforce_todos", True)),
            prefill=prefill,
        )
        if quick:
            dlg.setWindowTitle(f"{tr('Quick Snapshot')} ({self.hotkey_label()})")
        if dlg.exec() != QtWidgets.QDialog.Accepted:
            return False
        v = dlg.values()
        self._create_snapshot(v["root"], v["title"], v["workspace"], v["note"], v["todos"], v["tags"], interactive=True)
        return True

    def hotkey_label(self) -> str:
        hk = self.settings.get("hotkey", {})
        parts = []
        if hk.get("ctrl"):
            parts.append("Ctrl")
        if hk.get("alt"):
            parts.append("Alt")
        if hk.get("shift"):
            parts.append("Shift")
        parts.append(str(hk.get("vk", "S")).upper())
        return "+".join(parts)

    def _build_menus(self) -> None:
        """Menu bar for a more discoverable UX."""
        mb = self.menuBar()
        mb.clear()

        m_file = mb.addMenu(tr("File"))
        a_new = QtGui.QAction(tr("New Snapshot") + "…", self)
        a_new.triggered.connect(self.new_snapshot)
        a_quick = QtGui.QAction(f"{tr('Quick Snapshot')} ({self.hotkey_label()})", self)
        a_quick.triggered.connect(self.quick_snapshot)
        a_restore = QtGui.QAction(tr("Restore"), self)
        a_restore.triggered.connect(self.restore_selected)
        a_restore_last = QtGui.QAction(tr("Restore Last"), self)
        a_restore_last.triggered.connect(self.restore_last)
        a_open_folder = QtGui.QAction(tr("Open App Folder"), self)
        a_open_folder.triggered.connect(self.open_app_folder)
        a_quit = QtGui.QAction(tr("Quit"), self)
        a_quit.triggered.connect(self.request_quit)
        for a in [a_new, a_quick, None, a_restore, a_restore_last, None, a_open_folder, None, a_quit]:
            if a is None:
                m_file.addSeparator()
            else:
                m_file.addAction(a)

        m_tools = mb.addMenu(tr("Tools"))
        a_settings = QtGui.QAction(tr("Settings") + "…", self)
        a_settings.triggered.connect(self.open_settings)
        a_export_snap = QtGui.QAction(tr("Export Selected Snapshot"), self)
        a_export_snap.triggered.connect(self.export_selected_snapshot)
        a_report = QtGui.QAction(tr("Export Weekly Report"), self)
        a_report.triggered.connect(self.export_weekly_report)
        a_compare = QtGui.QAction(tr("Compare Snapshots") + "…", self)
        a_compare.triggered.connect(self.open_compare_dialog)
        a_history = QtGui.QAction(tr("Open Restore History"), self)
        a_history.triggered.connect(self.open_restore_history)
        m_tools.addAction(a_settings)
        m_tools.addSeparator()
        m_tools.addAction(a_export_snap)
        m_tools.addAction(a_report)
        m_tools.addAction(a_compare)
        m_tools.addSeparator()
        m_tools.addAction(a_history)

        m_help = mb.addMenu(tr("Help"))
        a_onb = QtGui.QAction(tr("Onboarding") + "…", self)
        a_onb.triggered.connect(self.show_onboarding)
        a_about = QtGui.QAction(tr("About"), self)
        a_about.triggered.connect(self.show_about)
        m_help.addAction(a_onb)
        m_help.addSeparator()
        m_help.addAction(a_about)

    def show_onboarding(self) -> None:
        dlg = OnboardingDialog(self)
        dlg.exec()

    def show_about(self) -> None:
        QtWidgets.QMessageBox.information(
            self,
            tr("About CtxSnap"),
            tr("About content"),
        )

    def open_app_folder(self) -> None:
        open_folder(app_dir())

    def __init__(self):
        super().__init__()
        self.setWindowTitle("CtxSnap")
        self.setMinimumSize(1020, 640)

        self.snaps_dir, self.index_path, self.settings_path = ensure_storage()
        self.index = load_json(self.index_path)
        self.settings = migrate_settings(load_json(self.settings_path))
        save_json(self.settings_path, self.settings)

        # Menus early (uses settings)
        self._build_menus()

        # migrate index entries
        changed = False
        for it in self.index.get("snapshots", []):
            if "tags" not in it:
                it["tags"] = []
                changed = True
            if "pinned" not in it:
                it["pinned"] = False
                changed = True
            if "archived" not in it:
                it["archived"] = False
                changed = True
            if "vscode_workspace" not in it:
                it["vscode_workspace"] = ""
                changed = True
        if changed:
            save_json(self.index_path, self.index)

        self._apply_archive_policy()

        central = QtWidgets.QWidget()
        self.setCentralWidget(central)

        self.search = QtWidgets.QLineEdit()
        self.search.setPlaceholderText(tr("Search placeholder"))
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._reset_pagination_and_refresh)

        self.selected_tags: Set[str] = set()
        self.tag_filter_btn = QtWidgets.QToolButton()
        self.tag_filter_btn.setText(tr("Tags"))
        self.tag_filter_btn.setPopupMode(QtWidgets.QToolButton.InstantPopup)
        self._build_tag_menu()

        self.days_filter = NoScrollComboBox()
        self.days_filter.addItem(tr("All time"), "all")
        self.days_filter.addItem(tr("Last 1 day"), "1")
        self.days_filter.addItem(tr("Last 3 days"), "3")
        self.days_filter.addItem(tr("Last 7 days"), "7")
        self.days_filter.addItem(tr("Last 30 days"), "30")
        
        self.days_filter.currentIndexChanged.connect(self._reset_pagination_and_refresh)

        self.sort_combo = NoScrollComboBox()
        self.sort_combo.addItem(tr("Newest"), "newest")
        self.sort_combo.addItem(tr("Oldest"), "oldest")
        self.sort_combo.addItem(tr("Pinned first"), "pinned")
        self.sort_combo.addItem(tr("Title"), "title")
        
        self.sort_combo.currentIndexChanged.connect(self._reset_pagination_and_refresh)

        self.pinned_only = QtWidgets.QCheckBox(tr("Pinned only"))
        self.pinned_only.stateChanged.connect(self._reset_pagination_and_refresh)

        self.show_archived = QtWidgets.QCheckBox(tr("Show archived"))
        self.show_archived.stateChanged.connect(self._reset_pagination_and_refresh)

        self.listw = QtWidgets.QListView()
        self.listw.setUniformItemSizes(False)
        self.listw.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.listw.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.listw.setWordWrap(True)
        self.listw.setTextElideMode(QtCore.Qt.ElideRight)
        self.list_model = SnapshotListModel(self)
        self.listw.setModel(self.list_model)
        self.listw.selectionModel().currentChanged.connect(self.on_select)
        self.listw.doubleClicked.connect(lambda _idx: self.restore_selected())
        self.listw.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.listw.customContextMenuRequested.connect(self._show_list_context_menu)

        self.detail_title = QtWidgets.QLabel(tr("No snapshot selected"))
        self.detail_title.setObjectName("TitleLabel")
        self.detail_meta = QtWidgets.QLabel("")
        self.detail_meta.setObjectName("HintLabel")

        # Detail panel: structured tabs (more scannable than a single long text blob)
        self.detail_tabs = QtWidgets.QTabWidget()

        self.tab_overview = QtWidgets.QTextEdit()
        self.tab_overview.setReadOnly(True)
        self.tab_overview.setLineWrapMode(QtWidgets.QTextEdit.NoWrap)
        self.tab_overview.setPlaceholderText(tr("Select a snapshot to see details."))
        self.detail_tabs.addTab(self.tab_overview, tr("Overview"))

        self.tab_recent_files = QtWidgets.QListWidget()
        self.tab_recent_files.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.tab_recent_files.setToolTip(tr("Recent files tab hint"))
        self.detail_tabs.addTab(self.tab_recent_files, tr("Recent files"))

        self.tab_processes = QtWidgets.QListWidget()
        self.tab_processes.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.detail_tabs.addTab(self.tab_processes, tr("Processes"))

        self.tab_running_apps = QtWidgets.QListWidget()
        self.tab_running_apps.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.detail_tabs.addTab(self.tab_running_apps, tr("Running apps"))

        # Recent files UX: double-click to open; right-click for copy/open folder.
        self.tab_recent_files.itemDoubleClicked.connect(lambda it: self._open_recent_file(str(it.data(QtCore.Qt.UserRole) or it.text())))
        self.tab_recent_files.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.tab_recent_files.customContextMenuRequested.connect(self._show_recent_files_context_menu)

        # Primary action buttons
        btn_new = QtWidgets.QPushButton(tr("New Snapshot"))
        btn_new.setProperty("primary", True)
        self.btn_quick = QtWidgets.QPushButton(f"{tr('Quick Snapshot')} ({self.hotkey_label()})")
        btn_settings = QtWidgets.QPushButton("⚙ " + tr("Settings"))
        
        # Restore action buttons
        btn_restore = QtWidgets.QPushButton("▶ " + tr("Restore"))
        btn_restore.setProperty("primary", True)
        btn_restore_last = QtWidgets.QPushButton(tr("Restore Last"))

        # Overflow actions (reduces button density; context menu also available)
        btn_more = QtWidgets.QToolButton()
        btn_more.setText("⋯ " + tr("More"))
        btn_more.setPopupMode(QtWidgets.QToolButton.InstantPopup)
        self.more_menu = QtWidgets.QMenu(self)
        self.more_menu.aboutToShow.connect(self._populate_more_menu)
        btn_more.setMenu(self.more_menu)
        
        # Quick actions
        btn_open_root = QtWidgets.QPushButton("📁 " + tr("Open Root Folder"))
        btn_open_vscode = QtWidgets.QPushButton("💻 " + tr("Open in VSCode"))

        btn_new.clicked.connect(self.new_snapshot)
        self.btn_quick.clicked.connect(self.quick_snapshot)
        btn_settings.clicked.connect(self.open_settings)
        btn_restore.clicked.connect(self.restore_selected)
        btn_restore_last.clicked.connect(self.restore_last)
        btn_open_root.clicked.connect(self.open_selected_root)
        btn_open_vscode.clicked.connect(self.open_selected_vscode)
        
        # In-app keyboard shortcuts
        self._setup_shortcuts()

        # Keep references for enabling/disabling based on selection.
        self.btn_restore = btn_restore
        self.btn_restore_last = btn_restore_last
        self.btn_open_root = btn_open_root
        self.btn_open_vscode = btn_open_vscode
        self.btn_more = btn_more
        self._sync_action_enabled(False)

        # Left panel - Snapshot list
        left = QtWidgets.QVBoxLayout()
        left.setContentsMargins(12, 12, 6, 12)
        left.setSpacing(10)
        
        # Search row with improved spacing
        search_row = QtWidgets.QHBoxLayout()
        search_row.setSpacing(8)
        search_row.addWidget(self.search, 1)
        search_row.addWidget(self.tag_filter_btn)
        
        # Filter row (separate for cleaner layout)
        filter_row = QtWidgets.QHBoxLayout()
        filter_row.setSpacing(8)
        filter_row.addWidget(self.days_filter)
        filter_row.addWidget(self.sort_combo)
        filter_row.addWidget(self.pinned_only)
        filter_row.addWidget(self.show_archived)
        filter_row.addStretch(1)
        
        left.addLayout(search_row)
        left.addLayout(filter_row)
        left.addWidget(self.listw, 1)
        
        self.result_label = QtWidgets.QLabel("")
        self.result_label.setObjectName("HintLabel")
        left.addWidget(self.result_label)
        
        # Pagination row
        page_row = QtWidgets.QHBoxLayout()
        page_row.setSpacing(6)
        self.page_prev_btn = QtWidgets.QToolButton()
        self.page_prev_btn.setText("← " + tr("Prev"))
        self.page_prev_btn.clicked.connect(self._prev_page)
        self.page_next_btn = QtWidgets.QToolButton()
        self.page_next_btn.setText(tr("Next") + " →")
        self.page_next_btn.clicked.connect(self._next_page)
        self.page_label = QtWidgets.QLabel("")
        self.page_label.setObjectName("HintLabel")
        page_row.addWidget(self.page_prev_btn)
        page_row.addWidget(self.page_next_btn)
        page_row.addStretch(1)
        page_row.addWidget(self.page_label)
        left.addLayout(page_row)
        
        # Left button row
        left_btns = QtWidgets.QHBoxLayout()
        left_btns.setSpacing(8)
        left_btns.addWidget(btn_new)
        left_btns.addWidget(self.btn_quick)
        left_btns.addWidget(btn_settings)
        left.addLayout(left_btns)

        # Right panel - Detail view
        right = QtWidgets.QVBoxLayout()
        right.setContentsMargins(6, 12, 12, 12)
        right.setSpacing(8)
        right.addWidget(self.detail_title)
        right.addWidget(self.detail_meta)
        right.addWidget(self.detail_tabs, 1)

        # Quick action buttons
        right_btns1 = QtWidgets.QHBoxLayout()
        right_btns1.setSpacing(8)
        right_btns1.addWidget(btn_open_root)
        right_btns1.addWidget(btn_open_vscode)
        right_btns1.addStretch(1)
        right.addLayout(right_btns1)

        # Management buttons
        right_btns2 = QtWidgets.QHBoxLayout()
        right_btns2.setSpacing(8)
        right_btns2.addWidget(btn_more)
        right_btns2.addStretch(1)
        right_btns2.addWidget(btn_restore_last)
        right_btns2.addWidget(btn_restore)
        right.addLayout(right_btns2)

        root_layout = QtWidgets.QHBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        left_wrap = QtWidgets.QWidget()
        left_wrap.setLayout(left)
        right_wrap = QtWidgets.QWidget()
        right_wrap.setLayout(right)
        splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        splitter.addWidget(left_wrap)
        splitter.addWidget(right_wrap)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([380, 640])
        root_layout.addWidget(splitter, 1)

        self._current_page = 1
        self._total_pages = 1
        self.refresh_list(reset_page=True)
        if self.list_model.rowCount() > 0:
            self.listw.setCurrentIndex(self.list_model.index(0, 0))

        self.statusBar().showMessage(f"Storage: {app_dir()}")

        self.auto_timer = QtCore.QTimer(self)
        self.auto_timer.timeout.connect(self._auto_snapshot_prompt)
        self.backup_timer = QtCore.QTimer(self)
        self.backup_timer.timeout.connect(self._run_scheduled_backup)
        self.git_timer = QtCore.QTimer(self)
        self.git_timer.setInterval(60_000)
        self.git_timer.timeout.connect(self._check_git_change)
        self._last_git_state = None
        self._update_auto_snapshot_timer()
        self._update_backup_timer()
        self.git_timer.start()
        self._recent_workers: Dict[str, QtCore.QThread] = {}

        # external hook (set by main) to re-apply hotkey settings
        self.on_settings_applied = None
        
        # When False: X closes to tray (hide). Quit must be explicit.
        self._quit_requested = False
        self._tray_hint_shown_session = False

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        # Default UX: close to tray (hide). Quit must be explicit.
        if not bool(getattr(self, "_quit_requested", False)) and not QtCore.QCoreApplication.closingDown():
            self.hide()
            # One-time, non-blocking hint (per session) to avoid confusion.
            try:
                tray = getattr(self, "_tray", None)
                if tray is not None and not bool(getattr(self, "_tray_hint_shown_session", False)):
                    tray.showMessage(
                        tr("Still running in tray title"),
                        tr("Still running in tray msg"),
                        QtWidgets.QSystemTrayIcon.Information,
                        3500,
                    )
                    self._tray_hint_shown_session = True
            except Exception:
                pass
            event.ignore()
            return

        # Explicit quit: stop timers and background workers.
        try:
            self.auto_timer.stop()
            self.backup_timer.stop()
            self.git_timer.stop()
        except Exception:
            pass

        for sid, thread in list(self._recent_workers.items()):
            try:
                thread.quit()
                if not thread.wait(2000):  # Wait up to 2 seconds
                    LOGGER.warning("Worker thread %s did not stop in time", sid)
                    thread.terminate()
                    thread.wait(1000)
            except Exception as e:
                LOGGER.exception("Error stopping worker thread %s: %s", sid, e)
        self._recent_workers.clear()
        event.accept()

    def request_quit(self) -> None:
        """Request a clean, explicit quit (used by tray/menu Quit)."""
        self._quit_requested = True
        try:
            self.close()
        finally:
            QtWidgets.QApplication.quit()

    def _setup_shortcuts(self) -> None:
        """Set up in-app keyboard shortcuts."""
        # Ctrl+N: New Snapshot
        QtGui.QShortcut(
            QtGui.QKeySequence("Ctrl+N"), self
        ).activated.connect(self.new_snapshot)
        
        # List-scoped shortcuts (avoid destructive actions while typing in search/note fields).
        QtGui.QShortcut(QtGui.QKeySequence("Ctrl+E"), self.listw).activated.connect(self.edit_selected)
        QtGui.QShortcut(QtGui.QKeySequence("Delete"), self.listw).activated.connect(self.delete_selected)
        QtGui.QShortcut(QtGui.QKeySequence("Ctrl+R"), self.listw).activated.connect(self.restore_selected)
        QtGui.QShortcut(QtGui.QKeySequence("Return"), self.listw).activated.connect(self.restore_selected)
        QtGui.QShortcut(QtGui.QKeySequence("Enter"), self.listw).activated.connect(self.restore_selected)
        
        # Ctrl+F: Focus search bar
        QtGui.QShortcut(
            QtGui.QKeySequence("Ctrl+F"), self
        ).activated.connect(lambda: self.search.setFocus())
        
        # Ctrl+,: Open settings
        QtGui.QShortcut(
            QtGui.QKeySequence("Ctrl+,"), self
        ).activated.connect(self.open_settings)
        
        # Ctrl+P: Toggle pin
        QtGui.QShortcut(QtGui.QKeySequence("Ctrl+P"), self.listw).activated.connect(self.toggle_pin)
        
        # Escape: Clear search
        QtGui.QShortcut(
            QtGui.QKeySequence("Escape"), self
        ).activated.connect(self._clear_search)

    def _copy_text(self, label: str, text: str) -> None:
        try:
            QtWidgets.QApplication.clipboard().setText(text or "")
            self.statusBar().showMessage(f"{label} {tr('Copied')}", 2500)
        except Exception:
            pass

    def _show_list_context_menu(self, pos: QtCore.QPoint) -> None:
        idx = self.listw.indexAt(pos)
        if idx.isValid():
            self.listw.setCurrentIndex(idx)
        sid = self.selected_id()
        if not sid:
            return
        snap = self.load_snapshot(sid) or {}

        menu = QtWidgets.QMenu(self)
        a_restore = menu.addAction(tr("Restore"))
        a_restore.triggered.connect(self.restore_selected)
        menu.addSeparator()

        a_edit = menu.addAction(tr("Edit"))
        a_edit.triggered.connect(self.edit_selected)

        a_pin = menu.addAction(tr("Pin / Unpin"))
        a_pin.triggered.connect(self.toggle_pin)

        a_arch = menu.addAction(tr("Archive / Unarchive"))
        a_arch.triggered.connect(self.toggle_archive)

        menu.addSeparator()
        a_open_root = menu.addAction(tr("Open Root Folder"))
        a_open_root.triggered.connect(self.open_selected_root)
        a_open_vscode = menu.addAction(tr("Open in VSCode"))
        a_open_vscode.triggered.connect(self.open_selected_vscode)

        menu.addSeparator()
        a_copy_title = menu.addAction(tr("Copy title"))
        a_copy_title.triggered.connect(lambda: self._copy_text(tr("Title") + ":", str(snap.get("title") or "")))
        a_copy_root = menu.addAction(tr("Copy root path"))
        a_copy_root.triggered.connect(lambda: self._copy_text(tr("Root") + ":", str(snap.get("root") or "")))
        a_copy_todos = menu.addAction(tr("Copy TODOs"))
        todos = [str(t).strip() for t in (snap.get("todos", []) or []) if str(t).strip()]
        a_copy_todos.triggered.connect(lambda: self._copy_text(tr("TODOs") + ":", "\n".join(todos)))

        menu.addSeparator()
        a_delete = menu.addAction(tr("Delete"))
        a_delete.triggered.connect(self.delete_selected)

        menu.exec(self.listw.viewport().mapToGlobal(pos))

    def _populate_more_menu(self) -> None:
        menu = getattr(self, "more_menu", None)
        if menu is None:
            return
        menu.clear()

        sid = self.selected_id()
        snap = self.load_snapshot(sid) if sid else None
        has_sel = bool(snap)
        snaps_any = (self.index.get("snapshots", []) or []) if isinstance(getattr(self, "index", None), dict) else []
        has_any = bool(snaps_any)

        a_edit = menu.addAction(tr("Edit"))
        a_edit.setEnabled(has_sel)
        a_edit.triggered.connect(self.edit_selected)

        a_pin = menu.addAction(tr("Pin / Unpin"))
        a_pin.setEnabled(has_sel)
        a_pin.triggered.connect(self.toggle_pin)

        a_arch = menu.addAction(tr("Archive / Unarchive"))
        a_arch.setEnabled(has_sel)
        a_arch.triggered.connect(self.toggle_archive)

        menu.addSeparator()

        a_export = menu.addAction(tr("Export Selected Snapshot"))
        a_export.setEnabled(has_sel)
        a_export.triggered.connect(self.export_selected_snapshot)

        a_report = menu.addAction(tr("Export Weekly Report"))
        a_report.setEnabled(has_any)
        a_report.triggered.connect(self.export_weekly_report)

        a_compare = menu.addAction(tr("Compare Snapshots"))
        a_compare.setEnabled(len(snaps_any) >= 2)
        a_compare.triggered.connect(self.open_compare_dialog)

        a_history = menu.addAction(tr("Open Restore History"))
        a_history.setEnabled(True)
        a_history.triggered.connect(self.open_restore_history)

        menu.addSeparator()

        a_settings = menu.addAction(tr("Settings"))
        a_settings.triggered.connect(self.open_settings)

        menu.addSeparator()

        a_delete = menu.addAction(tr("Delete"))
        a_delete.setEnabled(has_sel)
        a_delete.triggered.connect(self.delete_selected)

    def _open_recent_file(self, p: str) -> None:
        p = str(p or "").strip()
        if not p:
            return
        try:
            path = Path(p).expanduser()
            if not path.exists():
                QtWidgets.QMessageBox.information(self, tr("Information"), tr("File not found") + f":\n{p}")
                return
            os.startfile(str(path))  # type: ignore[attr-defined]
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, tr("Error"), f"{tr('Open file failed')}: {e}")

    def _show_recent_files_context_menu(self, pos: QtCore.QPoint) -> None:
        it = self.tab_recent_files.itemAt(pos)
        if it is None:
            return
        p = str(it.data(QtCore.Qt.UserRole) or it.text() or "").strip()
        if not p:
            return
        path = Path(p).expanduser()

        menu = QtWidgets.QMenu(self)
        a_open = menu.addAction(tr("Open file"))
        a_open.triggered.connect(lambda: self._open_recent_file(p))
        a_open_folder = menu.addAction(tr("Open containing folder"))
        a_open_folder.triggered.connect(lambda: open_folder(path.parent if path.parent else Path.home()))
        menu.addSeparator()
        a_copy = menu.addAction(tr("Copy path"))
        a_copy.triggered.connect(lambda: self._copy_text(tr("Path") + ":", p))
        menu.exec(self.tab_recent_files.viewport().mapToGlobal(pos))

    def _sync_action_enabled(self, has_selection: bool) -> None:
        # Restore Last is meaningful as long as there is at least one snapshot.
        snaps_any = (self.index.get("snapshots", []) or []) if isinstance(getattr(self, "index", None), dict) else []
        has_any = bool(snaps_any)
        w_last = getattr(self, "btn_restore_last", None)
        if w_last is not None:
            w_last.setEnabled(has_any)
        for name in (
            "btn_restore",
            "btn_open_root",
            "btn_open_vscode",
        ):
            w = getattr(self, name, None)
            if w is not None:
                w.setEnabled(bool(has_selection))
        w_more = getattr(self, "btn_more", None)
        if w_more is not None:
            w_more.setEnabled(True)

    def _auto_snapshot_prompt(self) -> None:
        if int(self.settings.get("auto_snapshot_minutes", 0)) <= 0:
            return
        # Auto-snapshot must be silent (no modal dialog).
        self._silent_snapshot(allow_dialog_fallback=False, reason="auto")

    def _update_auto_snapshot_timer(self) -> None:
        minutes = int(self.settings.get("auto_snapshot_minutes", 0))
        if minutes <= 0:
            self.auto_timer.stop()
            return
        self.auto_timer.setInterval(minutes * 60_000)
        if not self.auto_timer.isActive():
            self.auto_timer.start()

    def _update_backup_timer(self) -> None:
        hours = int(self.settings.get("auto_backup_hours", 0))
        if hours <= 0:
            self.backup_timer.stop()
            return
        self.backup_timer.setInterval(hours * 60_000 * 60)
        if not self.backup_timer.isActive():
            self.backup_timer.start()

    def _run_scheduled_backup(self) -> None:
        hours = int(self.settings.get("auto_backup_hours", 0))
        if hours <= 0:
            return
        last = self.settings.get("auto_backup_last", "")
        if last:
            try:
                last_dt = safe_parse_datetime(last)
                if last_dt and datetime.now() - last_dt < timedelta(hours=hours):
                    return
            except Exception:
                pass
        bkp = self._auto_backup_current()
        self.settings["auto_backup_last"] = now_iso()
        save_json(self.settings_path, self.settings)
        self.statusBar().showMessage(f"Auto backup created: {bkp.name}", 3500)

        # Cleanup old backups (keep last 5)
        try:
            backups_dir = app_dir() / "backups"
            if backups_dir.exists():
                backups = sorted(backups_dir.glob(f"{APP_NAME}_autobackup_*.json"), key=lambda p: p.stat().st_mtime)
                while len(backups) > 5:
                    old = backups.pop(0)
                    try:
                        old.unlink()
                    except Exception:
                        pass
        except Exception as e:
            LOGGER.debug("Backup cleanup failed: %s", e)

    def _apply_archive_policy(self) -> None:
        days = int(self.settings.get("archive_after_days", 0))
        if days <= 0:
            return
        skip_pinned = bool(self.settings.get("archive_skip_pinned", True))
        cutoff = datetime.now() - timedelta(days=days)
        updated = False
        for it in self.index.get("snapshots", []):
            if skip_pinned and bool(it.get("pinned", False)):
                continue
            if bool(it.get("archived", False)):
                continue
            created_at = safe_parse_datetime(it.get("created_at", ""))
            if not created_at:
                continue
            if created_at >= cutoff:
                continue
            it["archived"] = True
            sid = it.get("id")
            if sid:
                snap = self.load_snapshot(sid)
                if snap:
                    snap["archived"] = True
                    save_snapshot_file(self.snap_path(sid), snap)
            updated = True
        if updated:
            save_json(self.index_path, self.index)

    def _check_git_change(self) -> None:
        if not bool(self.settings.get("auto_snapshot_on_git_change", False)):
            return
        root = Path(self.settings.get("default_root", str(Path.home())))
        state = git_state(root)
        if not state:
            return
        if self._last_git_state and self._last_git_state != state:
            # Git-triggered snapshot must be silent (no modal dialog).
            self._silent_snapshot(allow_dialog_fallback=False, reason="git")
        self._last_git_state = state

    def _start_recent_files_scan(self, sid: str, root: Path) -> None:
        if sid in self._recent_workers:
            return
        worker = RecentFilesWorker(
            sid,
            root,
            limit=int(self.settings.get("recent_files_limit", 30)),
            exclude_dirs=self.settings.get("recent_files_exclude", []),
            include_patterns=self.settings.get("recent_files_include", []),
            exclude_patterns=self.settings.get("recent_files_exclude_patterns", []),
            scan_limit=int(self.settings.get("recent_files_scan_limit", 20000)),
            scan_seconds=float(self.settings.get("recent_files_scan_seconds", 2.0)),
        )
        thread = QtCore.QThread(self)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(self._on_recent_files_ready)
        worker.failed.connect(self._on_recent_files_failed)
        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        worker.failed.connect(worker.deleteLater)
        thread.finished.connect(lambda: self._recent_workers.pop(sid, None))
        thread.finished.connect(thread.deleteLater)
        thread.worker = worker
        self._recent_workers[sid] = thread
        thread.start()

    def _on_recent_files_ready(self, sid: str, files: List[str]) -> None:
        snap = self.load_snapshot(sid)
        if not snap:
            return
        snap["recent_files"] = files
        snap_path = self.snap_path(sid)
        save_snapshot_file(snap_path, snap)
        snap_mtime = snapshot_mtime(snap_path)
        for it in self.index.get("snapshots", []):
            if it.get("id") == sid:
                it["search_blob"] = build_search_blob(snap)
                it["search_blob_mtime"] = snap_mtime
                break
        save_json(self.index_path, self.index)
        self.refresh_list(reset_page=False)
        self.statusBar().showMessage(tr("Recent files updated in background."), 2500)

    def _on_recent_files_failed(self, sid: str, error: str) -> None:
        log_exc(f"recent files background scan ({sid})", Exception(error))

    def _build_tag_menu(self) -> None:
        menu = QtWidgets.QMenu(self)
        clear_action = QtGui.QAction(tr("All tags"), self)
        clear_action.triggered.connect(self._clear_tag_filter)
        menu.addAction(clear_action)
        menu.addSeparator()
        tags = self.settings.get("tags", DEFAULT_TAGS)
        self.selected_tags.intersection_update(tags)
        for tag in tags:
            action = QtGui.QAction(tag, self)
            action.setCheckable(True)
            action.setChecked(tag in self.selected_tags)
            action.triggered.connect(self._toggle_tag_filter)
            menu.addAction(action)
        self.tag_filter_btn.setMenu(menu)
        if self.selected_tags:
            self.tag_filter_btn.setText(f"{tr('Tags')} ({len(self.selected_tags)})")
        else:
            self.tag_filter_btn.setText(tr("Tags"))

    def _toggle_tag_filter(self) -> None:
        action = self.sender()
        if isinstance(action, QtGui.QAction):
            tag = action.text()
            if action.isChecked():
                self.selected_tags.add(tag)
            else:
                self.selected_tags.discard(tag)
        self._build_tag_menu()
        self._reset_pagination_and_refresh()

    def _clear_tag_filter(self) -> None:
        self.selected_tags.clear()
        self._build_tag_menu()
        self._reset_pagination_and_refresh()

    # ----- index helpers -----
    def _clear_search(self) -> None:
        self.search.clear()

    def _reset_pagination_and_refresh(self) -> None:
        self._current_page = 1
        self.refresh_list(reset_page=False)

    def _update_pagination_controls(self) -> None:
        self.page_prev_btn.setEnabled(self._current_page > 1)
        self.page_next_btn.setEnabled(self._current_page < self._total_pages)
        self.page_label.setText(f"Page {self._current_page} / {self._total_pages}")

    def _prev_page(self) -> None:
        if self._current_page > 1:
            self._current_page -= 1
            self.refresh_list(reset_page=False)

    def _next_page(self) -> None:
        if self._current_page < self._total_pages:
            self._current_page += 1
            self.refresh_list(reset_page=False)

    def refresh_list(self, *, reset_page: bool = False) -> None:
        query = self.search.text().strip().lower()
        pinned_only = bool(self.pinned_only.isChecked()) if hasattr(self, "pinned_only") else False
        show_archived = bool(self.show_archived.isChecked()) if hasattr(self, "show_archived") else False

        items = list(self.index.get("snapshots", []))
        index_changed = False
        view_items: List[Dict[str, Any]] = []

        sort_mode = self.sort_combo.currentData() if hasattr(self, "sort_combo") else "newest"
        
        if sort_mode == "pinned":
            items.sort(key=lambda x: (not bool(x.get("pinned", False)), x.get("created_at", "")), reverse=False)
        elif sort_mode == "oldest":
            items.sort(key=lambda x: x.get("created_at", ""))
        elif sort_mode == "title":
            items.sort(key=lambda x: (x.get("title", "").lower(), x.get("created_at", "")))
        else: # newest or default
            items.sort(key=lambda x: x.get("created_at", ""), reverse=True)

        days_filter = self.days_filter.currentData() if hasattr(self, "days_filter") else "all"
        now = datetime.now()
        day_cutoff = None
        # Logic based on "1", "3", "7", "30", "all"
        if days_filter and days_filter != "all":
            try:
                days = int(days_filter)
                day_cutoff = now - timedelta(days=days)
            except Exception:
                day_cutoff = None

        for it in items:
            tags = it.get("tags", []) or []
            if self.selected_tags and not self.selected_tags.intersection(tags):
                continue
            if bool(it.get("archived", False)) and not show_archived:
                continue
            base_hay = f"{it.get('title','')} {it.get('root','')} {' '.join(tags)}".lower()
            if query and query not in base_hay:
                search_blob = (it.get("search_blob") or "").lower()
                snap_mtime = 0.0
                if it.get("id"):
                    snap_mtime = snapshot_mtime(self.snap_path(it["id"]))
                if it.get("search_blob_mtime", 0.0) < snap_mtime:
                    search_blob = ""
                if not search_blob and it.get("id"):
                    snap = self.load_snapshot(it.get("id"))
                    if snap:
                        search_blob = build_search_blob(snap)
                        it["search_blob"] = search_blob
                        it["search_blob_mtime"] = snap_mtime or snapshot_mtime(self.snap_path(it["id"]))
                        index_changed = True
                if not search_blob or query not in search_blob:
                    continue

            if pinned_only and not bool(it.get("pinned", False)):
                continue

            if day_cutoff:
                created_at = safe_parse_datetime(it.get("created_at", ""))
                if created_at and created_at < day_cutoff:
                    continue

            view_items.append(it)
        if index_changed:
            save_json(self.index_path, self.index)
        page_size = max(1, int(self.settings.get("list_page_size", 200)))
        total = len(view_items)
        self._total_pages = max(1, (total + page_size - 1) // page_size)
        if reset_page:
            self._current_page = 1
        if self._current_page > self._total_pages:
            self._current_page = self._total_pages
        start = (self._current_page - 1) * page_size
        end = start + page_size
        self.list_model.set_items(view_items[start:end])
        if hasattr(self, "result_label"):
            total_all = len(self.index.get("snapshots", []))
            showing = len(view_items[start:end])
            self.result_label.setText(
                f"{tr('Storage:')} {showing} / {len(view_items)} (Total {total_all})"
            )
        self._update_pagination_controls()
        if self.list_model.rowCount() == 0:
            # Keep detail panel in sync when filtering yields zero results.
            self.on_select(QtCore.QModelIndex(), QtCore.QModelIndex())

    def selected_id(self) -> Optional[str]:
        idx = self.listw.currentIndex()
        if not idx.isValid():
            return None
        sid = self.list_model.id_for_index(idx)
        if not sid:
            return None
        return sid

    def snap_path(self, sid: str) -> Path:
        return self.snaps_dir / f"{sid}.json"

    def load_snapshot(self, sid: str) -> Optional[Dict[str, Any]]:
        p = self.snap_path(sid)
        if not p.exists():
            return None
        try:
            return migrate_snapshot(json.loads(p.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, Exception) as e:
            log_exc(f"load snapshot {sid}", e)
            return None

    def save_snapshot(self, snap: Snapshot) -> None:
        snap_path = self.snap_path(snap.id)
        save_snapshot_file(snap_path, asdict(snap))
        snap_mtime = snapshot_mtime(snap_path)
        self.index["snapshots"].insert(0, {
            "id": snap.id,
            "title": snap.title,
            "created_at": snap.created_at,
            "root": snap.root,
            "vscode_workspace": snap.vscode_workspace,
            "tags": snap.tags,
            "pinned": snap.pinned,
            "archived": snap.archived,
            "search_blob": build_search_blob(asdict(snap)),
            "search_blob_mtime": snap_mtime,
        })
        save_json(self.index_path, self.index)
        self.settings["default_root"] = snap.root
        save_json(self.settings_path, self.settings)

    # ----- selection rendering -----
    def on_select(self, current: QtCore.QModelIndex, previous: QtCore.QModelIndex) -> None:
        if not current.isValid():
            self.detail_title.setText(tr("No snapshot selected"))
            self.detail_meta.setText("")
            self.tab_overview.clear()
            self.tab_recent_files.clear()
            self.tab_processes.clear()
            self.tab_running_apps.clear()
            self._sync_action_enabled(False)
            return
        sid = self.selected_id()
        if not sid:
            return
        snap = self.load_snapshot(sid)
        if not snap:
            self.detail_title.setText(tr("Snapshot file missing"))
            self.detail_meta.setText("")
            self.tab_overview.clear()
            self.tab_recent_files.clear()
            self.tab_processes.clear()
            self.tab_running_apps.clear()
            self._sync_action_enabled(False)
            return

        self._sync_action_enabled(True)
        self.detail_title.setText(snap.get("title", sid))
        tags = snap.get("tags", [])
        pinned = "📌" if bool(snap.get("pinned", False)) else ""
        archived = "🗄️ " if bool(snap.get("archived", False)) else ""
        ws = snap.get("vscode_workspace", "")
        ws_line = f"  •  workspace: {ws}" if ws else ""
        tag_line = f"  •  tags: {', '.join(tags)}" if tags else ""
        self.detail_meta.setText(
            f"{archived}{pinned}{snap.get('created_at','')}  •  {snap.get('root','')}{ws_line}{tag_line}"
        )

        todos = snap.get("todos", [])
        recent = snap.get("recent_files", [])
        proc = snap.get("processes", [])
        running_apps = snap.get("running_apps", [])
        
        text = (
            f"{tr('Note')}:\n{snap.get('note','') or '(none)'}\n\n"
            f"{tr('TODOs')}:\n"
            f"  1) {todos[0] if len(todos)>0 else ''}\n"
            f"  2) {todos[1] if len(todos)>1 else ''}\n"
            f"  3) {todos[2] if len(todos)>2 else ''}\n"
        )
        self.tab_overview.setText(text)

        self.tab_recent_files.clear()
        for p in (recent or []):
            p_str = str(p or "").strip()
            if not p_str:
                continue
            it = QtWidgets.QListWidgetItem(p_str)
            it.setToolTip(p_str)
            it.setData(QtCore.Qt.UserRole, p_str)
            self.tab_recent_files.addItem(it)

        self.tab_processes.clear()
        for p in (proc or []):
            name = str(p.get("name", "") or "")
            exe = str(p.get("exe", "") or "")
            label = f"{name}  -  {exe}".strip()
            if not label:
                continue
            it = QtWidgets.QListWidgetItem(label)
            it.setToolTip(label)
            self.tab_processes.addItem(it)

        self.tab_running_apps.clear()
        for a in (running_apps or []):
            name = str(a.get("name", "") or "")
            title = str(a.get("title", "") or "")
            exe = str(a.get("exe", "") or "")
            label = f"{name}  |  {title}  |  {exe}".strip()
            if not label:
                continue
            it = QtWidgets.QListWidgetItem(label)
            it.setToolTip(label)
            self.tab_running_apps.addItem(it)

    # ----- actions -----
    def edit_selected(self) -> None:
        """Open edit dialog for the selected snapshot."""
        sid = self.selected_id()
        if not sid:
            self.statusBar().showMessage(tr("No snapshot selected"), 2000)
            return
        snap = self.load_snapshot(sid)
        if not snap:
            QtWidgets.QMessageBox.warning(self, tr("Error"), tr("Snapshot file missing"))
            return
        
        dlg = EditSnapshotDialog(
            self,
            snap,
            self.settings.get("tags", DEFAULT_TAGS),
            self.settings.get("templates", []),
            enforce_todos=bool(self.settings.get("capture_enforce_todos", True)),
        )
        if dlg.exec() != QtWidgets.QDialog.Accepted:
            return
        
        v = dlg.values()
        self._update_snapshot(
            sid,
            title=v["title"],
            root=v["root"],
            workspace=v["workspace"],
            note=v["note"],
            todos=v["todos"],
            tags=v["tags"],
        )
        self.statusBar().showMessage(tr("Snapshot Updated"), 2500)
    
    def _update_snapshot(
        self,
        sid: str,
        *,
        title: str,
        root: str,
        workspace: str,
        note: str,
        todos: List[str],
        tags: List[str],
    ) -> None:
        """Update an existing snapshot with new data."""
        snap = self.load_snapshot(sid)
        if not snap:
            return
        
        # Update snapshot fields
        snap["title"] = title
        snap["root"] = root
        snap["vscode_workspace"] = workspace
        snap["note"] = note
        snap["todos"] = todos[:3]
        snap["tags"] = tags
        
        # Write updated snapshot file
        snap_path = self.snap_path(sid)
        save_snapshot_file(snap_path, snap)
        snap_mtime = snapshot_mtime(snap_path)
        
        # Update index entry
        for it in self.index.get("snapshots", []):
            if it.get("id") == sid:
                it["title"] = title
                it["root"] = root
                it["vscode_workspace"] = workspace
                it["tags"] = tags
                it["search_blob"] = build_search_blob(snap)
                it["search_blob_mtime"] = snap_mtime
                break
        save_json(self.index_path, self.index)
        
        # Update default_root setting
        self.settings["default_root"] = root
        self._set_last_snapshot_form_in_memory(
            root=root,
            workspace=workspace,
            note=note,
            todos=todos,
            tags=tags,
        )
        save_json(self.settings_path, self.settings)
        
        # Refresh UI
        self.refresh_list(reset_page=False)
        self.on_select(self.listw.currentIndex(), QtCore.QModelIndex())

    def new_snapshot(self) -> None:
        self._run_snapshot_dialog(quick=False)

    def quick_snapshot(self) -> None:
        # Always show dialog for Quick Snapshot (hotkey/tray), prefilled from last form.
        form = self.settings.get("last_snapshot_form", {}) if isinstance(self.settings.get("last_snapshot_form", {}), dict) else {}
        prefill = {
            "root": str(form.get("root") or self.settings.get("default_root", str(Path.home()))),
            "vscode_workspace": str(form.get("vscode_workspace") or ""),
            "note": str(form.get("note") or ""),
            "todos": form.get("todos") if isinstance(form.get("todos"), list) else ["", "", ""],
            "tags": form.get("tags") if isinstance(form.get("tags"), list) else [],
        }
        # If the main window is hidden (close-to-tray), ensure the dialog is visible.
        dlg_parent = self if self.isVisible() else None
        dlg = SnapshotDialog(
            dlg_parent,
            self.settings.get("default_root", str(Path.home())),
            self.settings.get("tags", DEFAULT_TAGS),
            self.settings.get("templates", []),
            enforce_todos=bool(self.settings.get("capture_enforce_todos", True)),
            prefill=prefill,
        )
        dlg.setWindowTitle(f"{tr('Quick Snapshot')} ({self.hotkey_label()})")
        if not self.isVisible():
            dlg.setWindowFlag(QtCore.Qt.WindowStaysOnTopHint, True)
        if dlg.exec() != QtWidgets.QDialog.Accepted:
            return
        v = dlg.values()
        self._create_snapshot(v["root"], v["title"], v["workspace"], v["note"], v["todos"], v["tags"], interactive=True)

    def _create_snapshot(
        self,
        root: str,
        title: str,
        workspace: str,
        note: str,
        todos: List[str],
        tags: List[str],
        *,
        interactive: bool = True,
    ) -> None:
        root_path = Path(root).resolve()

        # Check for duplication (same root and title in active snapshots)
        for it in self.index.get("snapshots", []):
            if not bool(it.get("archived", False)):
                if it.get("title") == title and Path(it.get("root", "")).resolve() == root_path:
                    if interactive:
                        r = QtWidgets.QMessageBox.warning(
                            self,
                            tr("Duplicate Snapshot"),
                            tr("Duplicate snapshot warn"),
                            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
                        )
                        if r != QtWidgets.QMessageBox.Yes:
                            return
                    break
        ws = workspace.strip()
        if not ws:
            # if exactly one workspace file exists under root, use it
            wss = list(root_path.glob("*.code-workspace"))
            if len(wss) == 1:
                ws = str(wss[0].resolve())
        # Persist the last-used snapshot form (for silent Quick/Auto snapshots).
        self._set_last_snapshot_form_in_memory(
            root=str(root_path),
            workspace=ws,
            note=note,
            todos=todos,
            tags=tags,
        )
        sid = gen_id()
        capture = self.settings.get("capture", {})
        capture_recent = bool(capture.get("recent_files", True))
        capture_processes = bool(capture.get("processes", True))
        capture_running_apps = bool(capture.get("running_apps", True))
        capture_note = bool(self.settings.get("capture_note", True))
        capture_todos = bool(self.settings.get("capture_todos", True))
        background_recent = bool(self.settings.get("recent_files_background", False))
        recent_files: List[str] = []
        if capture_recent and not background_recent:
            recent_files = recent_files_under(
                root_path,
                limit=int(self.settings.get("recent_files_limit", 30)),
                exclude_dirs=self.settings.get("recent_files_exclude", []),
                include_patterns=self.settings.get("recent_files_include", []),
                exclude_patterns=self.settings.get("recent_files_exclude_patterns", []),
                scan_limit=int(self.settings.get("recent_files_scan_limit", 20000)),
                scan_seconds=float(self.settings.get("recent_files_scan_seconds", 2.0)),
            )
        snapshot_note = note if capture_note else ""
        snapshot_todos = todos[:3] if capture_todos else ["", "", ""]
        process_keywords = self.settings.get("process_keywords", [])
        snap = Snapshot(
            id=sid,
            title=title,
            created_at=now_iso(),
            root=str(root_path),
            vscode_workspace=ws,
            note=snapshot_note,
            todos=snapshot_todos,
            tags=tags,
            pinned=False,
            archived=False,
            recent_files=recent_files,
            processes=list_processes_filtered(process_keywords) if capture_processes else [],
            running_apps=list_running_apps() if capture_running_apps else [],
        )
        self.save_snapshot(snap)
        if capture_recent and background_recent:
            self._start_recent_files_scan(sid, root_path)
        self._reset_pagination_and_refresh()
        if self.list_model.rowCount() > 0:
            self.listw.setCurrentIndex(self.list_model.index(0, 0))
        self.statusBar().showMessage(f"{tr('Snapshot saved')}: {sid}", 3500)

    def _update_snapshot_meta(
        self,
        sid: str,
        *,
        pinned: Optional[bool] = None,
        archived: Optional[bool] = None,
        tags: Optional[List[str]] = None,
    ) -> None:
        """Update snapshot file + index with given metadata."""
        snap = self.load_snapshot(sid)
        if not snap:
            return
        if pinned is not None:
            snap["pinned"] = bool(pinned)
        if archived is not None:
            snap["archived"] = bool(archived)
        if tags is not None:
            snap["tags"] = tags
        # write snapshot file
        save_snapshot_file(self.snap_path(sid), snap)

        # update index
        for it in self.index.get("snapshots", []):
            if it.get("id") == sid:
                if pinned is not None:
                    it["pinned"] = bool(pinned)
                if archived is not None:
                    it["archived"] = bool(archived)
                if tags is not None:
                    it["tags"] = tags
                break
        save_json(self.index_path, self.index)

    def toggle_pin(self) -> None:
        sid = self.selected_id()
        if not sid:
            return
        snap = self.load_snapshot(sid)
        if not snap:
            return
        new_state = not bool(snap.get("pinned", False))
        self._update_snapshot_meta(sid, pinned=new_state)
        self.refresh_list(reset_page=False)
        self.statusBar().showMessage(tr("Pinned.") if new_state else tr("Unpinned."), 2000)

    def toggle_archive(self) -> None:
        sid = self.selected_id()
        if not sid:
            return
        snap = self.load_snapshot(sid)
        if not snap:
            return
        new_state = not bool(snap.get("archived", False))
        self._update_snapshot_meta(sid, archived=new_state)
        self._reset_pagination_and_refresh()
        self.statusBar().showMessage(tr("Archived.") if new_state else tr("Unarchived."), 2000)

    def apply_settings(self, vals: Dict[str, Any], *, save: bool = True) -> None:
        """Apply settings immediately (UI + hotkey)."""
        vals = migrate_settings(vals)
        vals.setdefault("default_root", self.settings.get("default_root", str(Path.home())))
        # Preserve last snapshot form when Settings dialog doesn't include it.
        vals.setdefault("last_snapshot_form", self.settings.get("last_snapshot_form", {}))
        self.settings = vals
        if save:
            try:
                save_json(self.settings_path, self.settings)
            except Exception as e:
                log_exc("save settings", e)

        # Refresh tag filter
        self._build_tag_menu()
        self._reset_pagination_and_refresh()

        # Update labels
        if hasattr(self, "btn_quick"):
            self.btn_quick.setText(f"{tr('Quick Snapshot')} ({self.hotkey_label()})")
        self._build_menus()

        if callable(self.on_settings_applied):
            self.on_settings_applied()
        self._update_auto_snapshot_timer()
        self._update_backup_timer()
        self._apply_archive_policy()

    def _auto_backup_current(self) -> Path:
        backups = app_dir() / "backups"
        backups.mkdir(parents=True, exist_ok=True)
        bkp = backups / f"{APP_NAME}_autobackup_{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
        try:
            export_backup_to_file(bkp, settings=self.settings, snaps_dir=self.snaps_dir, index_path=self.index_path, include_snapshots=True, include_index=True)
        except Exception as e:
            log_exc("auto backup", e)
        return bkp

    def apply_imported_backup(self, payload: Dict[str, Any]) -> None:
        """Apply imported backup: optionally merge/overwrite snapshots/index, then apply settings."""
        # Apply data first (may be destructive)
        data = payload.get("data")
        if data:
            bkp = self._auto_backup_current()
            self.statusBar().showMessage(f"Safety backup created: {bkp.name}", 3500)

            # Strategy prompt
            msg = QtWidgets.QMessageBox(self)
            msg.setWindowTitle("Import snapshots")
            msg.setText("백업에 스냅샷이 포함되어 있습니다. 적용 방식을 선택하세요.")
            msg.setInformativeText("Merge: 기존은 유지하고 새 항목만 추가\nOverwrite: 같은 ID는 덮어쓰기\nReplace all: 현재 스냅샷을 모두 삭제 후 백업으로 교체")
            btn_merge = msg.addButton("Merge", QtWidgets.QMessageBox.AcceptRole)
            btn_overwrite = msg.addButton("Overwrite", QtWidgets.QMessageBox.DestructiveRole)
            msg.addButton("Replace all", QtWidgets.QMessageBox.DestructiveRole)
            btn_cancel = msg.addButton("Cancel", QtWidgets.QMessageBox.RejectRole)
            msg.exec()
            clicked = msg.clickedButton()
            if clicked == btn_cancel:
                return
            strategy = "merge" if clicked == btn_merge else ("overwrite" if clicked == btn_overwrite else "replace")

            imported_snaps = data.get("snapshots") or []
            imported_index = data.get("index") if isinstance(data.get("index"), dict) else None

            if strategy == "replace":
                try:
                    for f in self.snaps_dir.glob("*.json"):
                        f.unlink(missing_ok=True)
                except Exception as e:
                    log_exc("wipe snapshots", e)
                self.index = {"snapshots": []}

            existing_ids = {it.get("id") for it in self.index.get("snapshots", []) if it.get("id")}

            def index_entry_from_snap(snap: Dict[str, Any]) -> Dict[str, Any]:
                return {
                    "id": snap.get("id"),
                    "title": snap.get("title", ""),
                    "created_at": snap.get("created_at", ""),
                    "root": snap.get("root", ""),
                    "vscode_workspace": snap.get("vscode_workspace", ""),
                    "pinned": bool(snap.get("pinned", False)),
                    "archived": bool(snap.get("archived", False)),
                    "tags": snap.get("tags", []),
                }

            for snap in imported_snaps:
                sid = snap.get("id")
                if not sid:
                    continue
                if strategy == "merge" and sid in existing_ids:
                    continue
                try:
                    snap_to_write = migrate_snapshot(snap)
                    snap_to_write["origin"] = "imported"
                    snap_to_write["imported_at"] = now_iso()
                    save_snapshot_file(self.snap_path(sid), snap_to_write)
                except Exception as e:
                    log_exc("write imported snapshot", e)
                    continue
                if sid not in existing_ids:
                    self.index.setdefault("snapshots", []).append(index_entry_from_snap(snap))
                    existing_ids.add(sid)
                elif strategy == "overwrite":
                    # update index entry meta
                    for it in self.index.get("snapshots", []):
                        if it.get("id") == sid:
                            it.update(index_entry_from_snap(snap))
                            break

            # If imported index exists and overwrite/replace: prefer it
            if imported_index and strategy in ("overwrite", "replace"):
                self.index = imported_index

            # Dedup index by id
            seen = set()
            dedup = []
            for it in self.index.get("snapshots", []):
                sid = it.get("id")
                if not sid or sid in seen:
                    continue
                seen.add(sid)
                dedup.append(it)
            self.index["snapshots"] = dedup

            try:
                save_json(self.index_path, self.index)
            except Exception as e:
                log_exc("save index after import", e)

            self._reset_pagination_and_refresh()

        # Apply settings (always)
        self.apply_settings(payload.get("settings", {}), save=True)

    def open_settings(self) -> None:
        dlg = SettingsDialog(self, self.settings, index_path=self.index_path, snaps_dir=self.snaps_dir)
        if dlg.exec() != QtWidgets.QDialog.Accepted:
            return

        vals = dlg.values()
        payload = dlg.imported_payload()

        # If user imported but did not apply, apply now on Save
        if payload and not dlg.import_apply_now():
            self.apply_imported_backup(payload)
        else:
            self.apply_settings(vals, save=True)

        self.statusBar().showMessage(tr("Settings applied."), 2500)

    def open_selected_root(self) -> None:
        sid = self.selected_id()
        if not sid:
            return
        snap = self.load_snapshot(sid)
        if not snap:
            return
        open_folder(Path(snap["root"]))

    def open_selected_vscode(self) -> None:
        sid = self.selected_id()
        if not sid:
            return
        snap = self.load_snapshot(sid)
        if not snap:
            return
        target = resolve_vscode_target(snap)
        success, msg = open_vscode_at(target)
        if not success:
            QtWidgets.QMessageBox.information(self, tr("VSCode not found title"), msg or tr("VSCode command missing"))

    def export_selected_snapshot(self) -> None:
        sid = self.selected_id()
        if not sid:
            return
        snap = self.load_snapshot(sid)
        if not snap:
            return
        default_name = f"snapshot_{sid}.json"
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Export snapshot", str(Path.home() / default_name), "JSON files (*.json)"
        )
        if not path:
            return
        save_snapshot_file(Path(path), snap)
        self.statusBar().showMessage("Snapshot exported.", 2500)

    def export_weekly_report(self) -> None:
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Export weekly report", str(Path.home() / "ctxsnap_weekly_report.md"), "Markdown files (*.md)"
        )
        if not path:
            return
        cutoff = datetime.now() - timedelta(days=7)
        lines = ["# Weekly Snapshot Report", f"Generated: {now_iso()}", ""]
        for it in self.index.get("snapshots", []):
            created_at = safe_parse_datetime(it.get("created_at", ""))
            if not created_at:
                continue
            if created_at < cutoff:
                continue
            snap = self.load_snapshot(it.get("id", "")) or {}
            lines.append(f"## {snap.get('title','(no title)')}")
            lines.append(f"- Created: {snap.get('created_at','')}")
            lines.append(f"- Root: {snap.get('root','')}")
            tags = snap.get("tags", [])
            if tags:
                lines.append(f"- Tags: {', '.join(tags)}")
            todos = [t for t in snap.get("todos", []) if t]
            if todos:
                lines.append("### TODOs")
                lines.extend([f"- {t}" for t in todos])
            note = snap.get("note", "")
            if note:
                lines.append("### Note")
                lines.append(note)
            lines.append("")
        Path(path).write_text("\n".join(lines), encoding="utf-8")
        self.statusBar().showMessage("Weekly report exported.", 2500)

    def open_compare_dialog(self) -> None:
        snapshots = [s for s in self.index.get("snapshots", []) if s.get("id")]
        if len(snapshots) < 2:
            QtWidgets.QMessageBox.information(self, tr("Compare"), tr("Need at least two snapshots to compare"))
            return
        dlg = CompareDialog(self, snapshots, loader=self.load_snapshot)
        dlg.exec()

    def open_restore_history(self) -> None:
        history_path = app_dir() / "restore_history.json"
        if not history_path.exists():
            QtWidgets.QMessageBox.information(self, tr("Restore History"), tr("No restore history yet"))
            return
        try:
            history = json.loads(history_path.read_text(encoding="utf-8"))
        except Exception:
            history = {"restores": []}
        dlg = RestoreHistoryDialog(self, history)
        dlg.exec()

    def restore_last(self) -> None:
        items = self.index.get("snapshots", [])
        if not items:
            return
        sid = items[0].get("id")
        if not sid:
            return
        self._restore_by_id(sid)

    def restore_selected(self) -> None:
        sid = self.selected_id()
        if not sid:
            return
        self._restore_by_id(sid)

    def _restore_by_id(self, sid: str) -> None:
        snap = self.load_snapshot(sid)
        if not snap:
            QtWidgets.QMessageBox.warning(self, tr("Error"), tr("Snapshot file missing"))
            return

        restore_cfg = self.settings.get("restore", {})
        open_folder_default = bool(restore_cfg.get("open_folder", True))
        open_terminal_default = bool(restore_cfg.get("open_terminal", True))
        open_vscode_default = bool(restore_cfg.get("open_vscode", True))
        open_running_apps_default = bool(restore_cfg.get("open_running_apps", False))
        show_checklist = bool(restore_cfg.get("show_post_restore_checklist", True))
        preview_default = bool(self.settings.get("restore_preview_default", True))

        if preview_default:
            dlg = RestorePreviewDialog(
                self,
                snap,
                open_folder_default,
                open_terminal_default,
                open_vscode_default,
                open_running_apps_default,
            )
            if dlg.exec() != QtWidgets.QDialog.Accepted:
                return
            ch = dlg.choices()
        else:
            ch = {
                "open_folder": open_folder_default,
                "open_terminal": open_terminal_default,
                "open_vscode": open_vscode_default,
                "open_running_apps": open_running_apps_default,
            }

        root = Path(snap["root"]).expanduser()
        # root_exists = root.exists() # unused
        root_missing = False
        errors: List[str] = []
        
        if ch.get("open_folder"):
            success, error = open_folder(root)
            if not success:
                root_missing = True
                errors.append(f"{tr('Restore open folder failed')} {error}")
        
        if ch.get("open_terminal"):
            success, error = open_terminal_at(root)
            if not success:
                root_missing = True
                errors.append(f"{tr('Restore open terminal failed')} {error}")
        
        vscode_opened = False
        if ch.get("open_vscode"):
            target = resolve_vscode_target(snap)
            success, error = open_vscode_at(target)
            vscode_opened = success
            if not success:
                errors.append(f"{tr('Restore open vscode failed')} {error}")
        
        requested_apps = []
        running_app_failures: List[str] = []
        apps_restore_skipped = False
        apps_restore_skip_reason = ""
        if ch.get("open_running_apps"):
            # Respect the user's explicit selection (empty list means "none").
            requested_apps = ch.get("running_apps", [])
            if snap.get("origin") == "imported" and requested_apps:
                msg = QtWidgets.QMessageBox(self)
                msg.setIcon(QtWidgets.QMessageBox.Warning)
                msg.setWindowTitle(tr("Imported snapshot warning title"))
                msg.setText(tr("Imported snapshot warning msg"))
                btn_proceed = msg.addButton(tr("Proceed"), QtWidgets.QMessageBox.AcceptRole)
                msg.addButton(tr("Cancel"), QtWidgets.QMessageBox.RejectRole)
                msg.exec()
                if msg.clickedButton() != btn_proceed:
                    apps_restore_skipped = True
                    apps_restore_skip_reason = "imported_snapshot_cancel"
                    requested_apps = []
                    running_app_failures = []
                    self.statusBar().showMessage(tr("Skipped app restore for imported snapshot"), 4500)
                else:
                    running_app_failures = restore_running_apps(requested_apps, parent=self)
            else:
                running_app_failures = restore_running_apps(requested_apps, parent=self)

        append_restore_history({
            "snapshot_id": sid,
            "created_at": now_iso(),
            "open_folder": bool(ch.get("open_folder")),
            "open_terminal": bool(ch.get("open_terminal")),
            "open_vscode": bool(ch.get("open_vscode")),
            "open_running_apps": bool(ch.get("open_running_apps")),
            "running_apps_requested": len(requested_apps),
            "running_apps_failed": running_app_failures,
            "root_missing": root_missing,
            "vscode_opened": vscode_opened,
            "running_apps_skipped": apps_restore_skipped,
            "running_apps_skip_reason": apps_restore_skip_reason,
        })

        # Show errors if any
        if errors:
            QtWidgets.QMessageBox.warning(
                self, 
                tr("Restore"), 
                tr("Restore failed for some items:") + "\n" + "\n".join(errors)
            )
        
        if show_checklist:
            todos = snap.get("todos", [])
            if any(todos):
                dlg = ChecklistDialog(self, [t for t in todos if t])
                dlg.exec()
        self.statusBar().showMessage("Restore triggered.", 2500)

    def delete_selected(self) -> None:
        sid = self.selected_id()
        if not sid:
            return
        r = QtWidgets.QMessageBox.question(
            self,
            tr("Delete snapshot?"),
            tr("Delete confirm msg"),
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
        )
        if r != QtWidgets.QMessageBox.Yes:
            return
        p = self.snap_path(sid)
        if p.exists():
            try:
                p.unlink()
            except Exception as e:
                log_exc("delete snapshot file", e)
                QtWidgets.QMessageBox.warning(
                    self,
                    tr("Error"),
                    tr("Failed to delete snapshot file") + f": {e}"
                )
                return
        self.index["snapshots"] = [x for x in self.index.get("snapshots", []) if x.get("id") != sid]
        save_json(self.index_path, self.index)
        self._reset_pagination_and_refresh()
        if self.list_model.rowCount() > 0:
            self.listw.setCurrentIndex(self.list_model.index(0, 0))
        else:
            self.on_select(QtCore.QModelIndex(), QtCore.QModelIndex())
        self.statusBar().showMessage(tr("Deleted"), 2000)

