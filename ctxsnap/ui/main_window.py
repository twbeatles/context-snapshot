from __future__ import annotations

import copy
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set

from PySide6 import QtCore, QtGui, QtWidgets

from ctxsnap.app_storage import (
    Snapshot,
    app_dir,
    ensure_storage,
    export_backup_to_file,
    load_json,
    migrate_settings,
    now_iso,
    save_json,
    save_snapshot_file,
)
from ctxsnap.constants import APP_NAME, DEFAULT_TAGS
from ctxsnap.core.logging import get_logger
from ctxsnap.core.security import SecurityService
from ctxsnap.core.sync import SyncEngine
from ctxsnap.i18n import tr
from ctxsnap.restore import (
    open_folder,
    open_vscode_at,
    resolve_vscode_target,
)
from ctxsnap.ui.dialogs.history import CompareDialog, RestoreHistoryDialog
from ctxsnap.ui.dialogs.onboarding import OnboardingDialog
from ctxsnap.ui.dialogs.settings import SettingsDialog
from ctxsnap.ui.main_window_sections import (
    MainWindowAutomationSection,
    MainWindowListViewSection,
    MainWindowRestoreActionsSection,
    MainWindowSettingsBackupSection,
    MainWindowSnapshotCrudSection,
)
from ctxsnap.ui.models import SnapshotListModel, SnapshotItemDelegate
from ctxsnap.services import BackupService, RestoreService, SearchService, SnapshotService
from ctxsnap.ui.styles import NoScrollComboBox
from ctxsnap.utils import (
    git_state_details,
    log_exc,
    safe_parse_datetime,
)

LOGGER = get_logger()


class MainWindow(
    MainWindowSettingsBackupSection,
    MainWindowRestoreActionsSection,
    MainWindowAutomationSection,
    MainWindowListViewSection,
    MainWindowSnapshotCrudSection,
    QtWidgets.QMainWindow,
):
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

    def _refresh_saved_query_combo(self) -> None:
        if not hasattr(self, "saved_query_combo"):
            return
        queries = self.settings.get("search", {}).get("saved_queries", [])
        combo = self.saved_query_combo
        current_text = self.search.text() if hasattr(self, "search") else ""
        with QtCore.QSignalBlocker(combo):
            combo.clear()
            combo.addItem(tr("Saved Queries"), "")
            for query in queries:
                label = str(query).strip()
                if label:
                    combo.addItem(label, label)
            match_index = combo.findData(current_text)
            combo.setCurrentIndex(match_index if match_index >= 0 else 0)

    def _apply_saved_query_choice(self, row: int) -> None:
        if row <= 0:
            return
        query = str(self.saved_query_combo.itemData(row) or "").strip()
        if query:
            self.search.setText(query)
            self.search.setFocus()

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
        a_sync = QtGui.QAction(tr("Sync Now"), self)
        a_sync.triggered.connect(self._run_scheduled_sync)
        a_sync.setEnabled(bool(self.settings.get("dev_flags", {}).get("sync_enabled", False)))
        a_export_snap = QtGui.QAction(tr("Export Selected Snapshot"), self)
        a_export_snap.triggered.connect(self.export_selected_snapshot)
        a_report = QtGui.QAction(tr("Export Weekly Report"), self)
        a_report.triggered.connect(self.export_weekly_report)
        a_compare = QtGui.QAction(tr("Compare Snapshots") + "…", self)
        a_compare.triggered.connect(self.open_compare_dialog)
        a_history = QtGui.QAction(tr("Open Restore History"), self)
        a_history.triggered.connect(self.open_restore_history)
        a_conflicts = QtGui.QAction(tr("Open Sync Conflicts"), self)
        a_conflicts.triggered.connect(self.open_sync_conflicts)
        m_tools.addAction(a_settings)
        m_tools.addAction(a_sync)
        m_tools.addSeparator()
        m_tools.addAction(a_export_snap)
        m_tools.addAction(a_report)
        m_tools.addAction(a_compare)
        m_tools.addSeparator()
        m_tools.addAction(a_history)
        m_tools.addAction(a_conflicts)

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

    def request_quit(self) -> None:
        self._quit_requested = True
        self.close()
        QtWidgets.QApplication.quit()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("CtxSnap")
        self.setMinimumSize(1020, 640)

        # Initialize Services
        self.snapshot_service = SnapshotService()
        self.search_service = SearchService()
        self.backup_service = BackupService()
        self.restore_service = RestoreService()
        self.security_service = SecurityService()
        self.sync_engine: Optional[SyncEngine] = None

        # Storage & Settings
        self.snaps_dir, self.index_path, self.settings_path = ensure_storage()
        raw_index = load_json(self.index_path)
        self.index = self.snapshot_service.migrate_index(raw_index)
        self.settings = migrate_settings(load_json(self.settings_path))
        self.settings["restore_profiles"] = self.restore_service.normalize_profiles(
            self.settings.get("restore_profiles", [])
        )
        if not save_json(self.settings_path, self.settings):
            LOGGER.warning("Failed to persist migrated settings at startup.")

        # Menus
        self._build_menus()

        # Migrate index entries
        changed = self.index != raw_index
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
            if "source" not in it:
                it["source"] = ""
                changed = True
            if "trigger" not in it:
                it["trigger"] = ""
                changed = True
            if "auto_fingerprint" not in it:
                it["auto_fingerprint"] = ""
                changed = True
            if not isinstance(it.get("git_state"), dict):
                it["git_state"] = {}
                changed = True
            if "rev" not in it:
                it["rev"] = 1
                changed = True
            if "updated_at" not in it:
                it["updated_at"] = it.get("created_at", now_iso())
                changed = True
            if "search_blob" not in it:
                it["search_blob"] = ""
                changed = True
            if "search_blob_mtime" not in it:
                it["search_blob_mtime"] = 0.0
                changed = True
        
        if "schema_version" not in self.index:
            changed = True
        if "search_meta" not in self.index:
            changed = True
        if "tombstones" not in self.index:
            changed = True
        if "rev" not in self.index:
            changed = True
        if "updated_at" not in self.index:
            changed = True
            
        if changed:
            self.index = self.snapshot_service.touch_index(self.index)
            if not save_json(self.index_path, self.index):
                LOGGER.warning("Failed to persist migrated index at startup.")

        self._apply_archive_policy()

        # UI Components
        central = QtWidgets.QWidget()
        self.setCentralWidget(central)

        self.search = QtWidgets.QLineEdit()
        self.search.setPlaceholderText(tr("Search placeholder"))
        self.search.textChanged.connect(self._reset_pagination_and_refresh)
        self.search.textChanged.connect(lambda _text: self._refresh_saved_query_combo())
        self.saved_query_combo = NoScrollComboBox()
        self.saved_query_combo.currentIndexChanged.connect(self._apply_saved_query_choice)
        self._refresh_saved_query_combo()
        self.search_btn_clear = QtWidgets.QToolButton()
        self.search_btn_clear.setText(tr("Clear"))
        self.search_btn_clear.clicked.connect(self._clear_search)

        self.selected_tags: Set[str] = set()
        self.tag_filter_btn = QtWidgets.QToolButton()
        self.tag_filter_btn.setText(tr("Tags"))
        self.tag_filter_btn.setPopupMode(
            QtWidgets.QToolButton.ToolButtonPopupMode.InstantPopup
        )
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

        # List Stack (for Empty State)
        self.list_stack = QtWidgets.QStackedWidget()
        
        self.listw = QtWidgets.QListView()
        self.listw.setUniformItemSizes(False)
        self.listw.setSelectionMode(
            QtWidgets.QAbstractItemView.SelectionMode.SingleSelection
        )
        self.listw.setWordWrap(True)
        self.listw.setTextElideMode(QtCore.Qt.TextElideMode.ElideRight)
        
        self.item_delegate = SnapshotItemDelegate(self.listw)
        self.listw.setItemDelegate(self.item_delegate)
        
        self.list_model = SnapshotListModel(self)
        self.listw.setModel(self.list_model)
        self.listw.selectionModel().currentChanged.connect(self.on_select)
        
        self.list_stack.addWidget(self.listw)
        
        self.empty_state = QtWidgets.QWidget()
        empty_layout = QtWidgets.QVBoxLayout(self.empty_state)
        empty_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        empty_icon = QtWidgets.QLabel("📭")
        empty_icon.setStyleSheet("font-size: 48px; color: #606078;")
        empty_icon.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        empty_text = QtWidgets.QLabel(tr("No snapshots found.\nPress 'New Snapshot' to create one."))
        empty_text.setStyleSheet("font-size: 14px; color: #9090a8;")
        empty_text.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(empty_icon)
        empty_layout.addWidget(empty_text)
        
        self.list_stack.addWidget(self.empty_state)

        # Detail View
        self.detail_title = QtWidgets.QLabel(tr("No snapshot selected"))
        self.detail_title.setObjectName("TitleLabel")
        self.detail_meta = QtWidgets.QLabel("")
        self.detail_meta.setObjectName("HintLabel")

        self.detail = QtWidgets.QTextEdit()
        self.detail.setReadOnly(True)
        self.detail.setPlaceholderText(tr("Select a snapshot to see details."))

        # Buttons
        btn_new = QtWidgets.QPushButton(tr("New Snapshot"))
        btn_new.setProperty("primary", True)
        self.btn_quick = QtWidgets.QPushButton(f"{tr('Quick Snapshot')} ({self.hotkey_label()})")
        btn_settings = QtWidgets.QPushButton("⚙ " + tr("Settings"))
        
        btn_restore = QtWidgets.QPushButton("▶ " + tr("Restore"))
        btn_restore.setProperty("primary", True)
        btn_restore_last = QtWidgets.QPushButton(tr("Restore Last"))
        
        btn_edit = QtWidgets.QPushButton("✏ " + tr("Edit"))
        btn_pin = QtWidgets.QPushButton("📌 " + tr("Pin / Unpin"))
        btn_archive = QtWidgets.QPushButton("🗄 " + tr("Archive / Unarchive"))
        btn_compare = QtWidgets.QPushButton(tr("Compare"))
        
        btn_open_root = QtWidgets.QPushButton("📁 " + tr("Open Root Folder"))
        btn_open_vscode = QtWidgets.QPushButton("💻 " + tr("Open in VSCode"))
        
        btn_delete = QtWidgets.QPushButton("🗑 " + tr("Delete"))
        btn_delete.setProperty("danger", True)

        # Connections
        btn_new.clicked.connect(self.new_snapshot)
        self.btn_quick.clicked.connect(self.quick_snapshot)
        btn_settings.clicked.connect(self.open_settings)
        btn_restore.clicked.connect(self.restore_selected)
        btn_restore_last.clicked.connect(self.restore_last)
        btn_open_root.clicked.connect(self.open_selected_root)
        btn_open_vscode.clicked.connect(self.open_selected_vscode)
        btn_delete.clicked.connect(self.delete_selected)
        btn_edit.clicked.connect(self.edit_selected)
        btn_pin.clicked.connect(self.toggle_pin)
        btn_archive.clicked.connect(self.toggle_archive)
        btn_compare.clicked.connect(self.open_compare_dialog)
        
        self._setup_shortcuts()

        # Layout
        left = QtWidgets.QVBoxLayout()
        left.setContentsMargins(12, 12, 6, 12)
        left.setSpacing(10)
        
        search_row = QtWidgets.QHBoxLayout()
        search_row.setSpacing(8)
        search_row.addWidget(self.search, 1)
        search_row.addWidget(self.saved_query_combo)
        search_row.addWidget(self.search_btn_clear)
        search_row.addWidget(self.tag_filter_btn)
        
        filter_row = QtWidgets.QHBoxLayout()
        filter_row.setSpacing(8)
        filter_row.addWidget(self.days_filter)
        filter_row.addWidget(self.sort_combo)
        filter_row.addWidget(self.pinned_only)
        filter_row.addWidget(self.show_archived)
        filter_row.addStretch(1)
        
        left.addLayout(search_row)
        left.addLayout(filter_row)
        left.addWidget(self.list_stack, 1)
        
        self.result_label = QtWidgets.QLabel("")
        self.result_label.setObjectName("HintLabel")
        left.addWidget(self.result_label)
        
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
        
        left_btns = QtWidgets.QHBoxLayout()
        left_btns.setSpacing(8)
        left_btns.addWidget(btn_new)
        left_btns.addWidget(self.btn_quick)
        left_btns.addWidget(btn_settings)
        left.addLayout(left_btns)

        right = QtWidgets.QVBoxLayout()
        right.setContentsMargins(6, 12, 12, 12)
        right.setSpacing(8)
        right.addWidget(self.detail_title)
        right.addWidget(self.detail_meta)
        right.addWidget(self.detail, 1)

        right_btns1 = QtWidgets.QHBoxLayout()
        right_btns1.setSpacing(8)
        right_btns1.addWidget(btn_open_root)
        right_btns1.addWidget(btn_open_vscode)
        right_btns1.addStretch(1)
        right.addLayout(right_btns1)

        right_btns2 = QtWidgets.QHBoxLayout()
        right_btns2.setSpacing(8)
        right_btns2.addWidget(btn_pin)
        right_btns2.addWidget(btn_archive)
        right_btns2.addWidget(btn_compare)
        right_btns2.addStretch(1)
        right_btns2.addWidget(btn_edit)
        right_btns2.addWidget(btn_delete)
        right_btns2.addWidget(btn_restore_last)
        right_btns2.addWidget(btn_restore)
        right.addLayout(right_btns2)

        root_layout = QtWidgets.QHBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        left_wrap = QtWidgets.QWidget()
        left_wrap.setLayout(left)
        right_wrap = QtWidgets.QWidget()
        right_wrap.setLayout(right)
        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        splitter.addWidget(left_wrap)
        splitter.addWidget(right_wrap)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([380, 640])
        root_layout.addWidget(splitter, 1)

        # Initial Refresh
        self._current_page = 1
        self._total_pages = 1
        self.refresh_list(reset_page=True)
        if self.list_model.rowCount() > 0:
            self.listw.setCurrentIndex(self.list_model.index(0, 0))

        self.statusBar().showMessage(f"Storage: {app_dir()}")

        # Timers & Workers
        self.auto_timer = QtCore.QTimer(self)
        self.auto_timer.timeout.connect(self._auto_snapshot_prompt)
        self.backup_timer = QtCore.QTimer(self)
        self.backup_timer.timeout.connect(self._run_scheduled_backup)
        self.sync_timer = QtCore.QTimer(self)
        self.sync_timer.timeout.connect(self._run_scheduled_sync)
        self.git_timer = QtCore.QTimer(self)
        self.git_timer.setInterval(60_000)
        self.git_timer.timeout.connect(self._check_git_change)
        self._last_git_state = None
        
        self._init_sync_engine()
        self._update_auto_snapshot_timer()
        self._update_backup_timer()
        self._update_sync_timer()
        self.git_timer.start()
        self._recent_workers: Dict[str, QtCore.QThread] = {}

        self.on_settings_applied: Optional[Callable[[], None]] = None
        self._is_closing = False
        self._quit_requested = False

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        """Minimize to tray by default; only quit on explicit request."""
        if not self._quit_requested:
            self.hide()
            event.ignore()
            return

        self._is_closing = True
        
        # Stop all timers
        self.auto_timer.stop()
        self.backup_timer.stop()
        self.sync_timer.stop()
        self.git_timer.stop()
        
        # Stop all background workers
        for sid, thread in list(self._recent_workers.items()):
            try:
                thread.quit()
                if not thread.wait(2000):
                    LOGGER.warning("Worker thread %s did not stop in time", sid)
                    thread.terminate()
                    thread.wait(1000)
            except Exception as e:
                LOGGER.exception("Error stopping worker thread %s: %s", sid, e)
        self._recent_workers.clear()
        
        event.accept()

    def _setup_shortcuts(self) -> None:
        """Set up in-app keyboard shortcuts."""
        QtGui.QShortcut(QtGui.QKeySequence("Ctrl+N"), self).activated.connect(self.new_snapshot)
        QtGui.QShortcut(QtGui.QKeySequence("Ctrl+E"), self).activated.connect(self.edit_selected)
        QtGui.QShortcut(QtGui.QKeySequence("Delete"), self).activated.connect(self.delete_selected)
        QtGui.QShortcut(QtGui.QKeySequence("Ctrl+R"), self).activated.connect(self.restore_selected)
        QtGui.QShortcut(QtGui.QKeySequence("Return"), self).activated.connect(self.restore_selected)
        QtGui.QShortcut(QtGui.QKeySequence("Ctrl+F"), self).activated.connect(lambda: self.search.setFocus())
        QtGui.QShortcut(QtGui.QKeySequence("Ctrl+,"), self).activated.connect(self.open_settings)
        QtGui.QShortcut(QtGui.QKeySequence("Ctrl+P"), self).activated.connect(self.toggle_pin)
        QtGui.QShortcut(QtGui.QKeySequence("Escape"), self).activated.connect(self._clear_search)

    def open_settings(self) -> None:
        MainWindowSettingsBackupSection.open_settings(self)

    def open_selected_root(self) -> None:
        MainWindowRestoreActionsSection.open_selected_root(self)

    def open_selected_vscode(self) -> None:
        MainWindowRestoreActionsSection.open_selected_vscode(self)

    def export_selected_snapshot(self) -> None:
        MainWindowRestoreActionsSection.export_selected_snapshot(self)

    def export_weekly_report(self) -> None:
        MainWindowRestoreActionsSection.export_weekly_report(self)

    def open_compare_dialog(self) -> None:
        MainWindowRestoreActionsSection.open_compare_dialog(self)

    def open_restore_history(self) -> None:
        MainWindowRestoreActionsSection.open_restore_history(self)
