from __future__ import annotations
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List
from PySide6 import QtCore, QtWidgets

from ctxsnap.constants import DEFAULT_TAGS, APP_NAME
from ctxsnap.i18n import tr
from ctxsnap.utils import log_exc
from ctxsnap.app_storage import (
    migrate_settings,
    export_backup_to_file,
    import_backup_from_file,
)
from ctxsnap.ui.styles import (
    NoScrollComboBox,
    NoScrollSpinBox,
    NoScrollDoubleSpinBox,
)


def _make_scrollable(widget: QtWidgets.QWidget) -> QtWidgets.QScrollArea:
    """Wrap a widget in a scroll area for overflow handling."""
    scroll = QtWidgets.QScrollArea()
    scroll.setWidget(widget)
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
    scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
    scroll.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
    return scroll


class SettingsDialog(QtWidgets.QDialog):
    """Settings UI:
    - Hotkey (Ctrl/Alt/Shift/Key, enable)
    - Restore options (folder/terminal/VSCode)
    - Recent files limit
    - Restore preview default toggle
    - Tags management
    """

    settingsImported = QtCore.Signal(dict)

    def __init__(self, parent: QtWidgets.QWidget, settings: Dict[str, Any], *, index_path: Path, snaps_dir: Path):
        super().__init__(parent)
        self.setWindowTitle(tr("Settings"))
        self.setModal(True)
        self.setMinimumSize(780, 600)

        self._settings = settings
        self._index_path = index_path
        self._snaps_dir = snaps_dir
        self._imported_payload = None
        self._import_apply_now = False

        header = QtWidgets.QLabel(tr("Settings"))
        header.setObjectName("TitleLabel")
        sub = QtWidgets.QLabel(tr("Settings Hint"))
        sub.setObjectName("HintLabel")

        tabs = QtWidgets.QTabWidget()

        # === Hotkey tab ===
        hk = settings.get("hotkey", {})
        self.hk_enabled = QtWidgets.QCheckBox(tr("Enable Hotkey"))
        self.hk_enabled.setChecked(bool(hk.get("enabled", True)))
        self.hk_ctrl = QtWidgets.QCheckBox("Ctrl")
        self.hk_alt = QtWidgets.QCheckBox("Alt")
        self.hk_shift = QtWidgets.QCheckBox("Shift")
        self.hk_ctrl.setChecked(bool(hk.get("ctrl", True)))
        self.hk_alt.setChecked(bool(hk.get("alt", True)))
        self.hk_shift.setChecked(bool(hk.get("shift", False)))
        self.hk_key = NoScrollComboBox()
        for c in [chr(i) for i in range(ord("A"), ord("Z") + 1)]:
            self.hk_key.addItem(c)
        vk = str(hk.get("vk", "S")).upper()
        idx = self.hk_key.findText(vk)
        if idx >= 0:
            self.hk_key.setCurrentIndex(idx)

        hk_row = QtWidgets.QHBoxLayout()
        hk_row.setSpacing(12)
        hk_row.addWidget(self.hk_ctrl)
        hk_row.addWidget(self.hk_alt)
        hk_row.addWidget(self.hk_shift)
        hk_row.addStretch(1)
        hk_row.addWidget(QtWidgets.QLabel("Key"))
        hk_row.addWidget(self.hk_key)

        hotkey_page = QtWidgets.QWidget()
        hk_box = QtWidgets.QGroupBox(tr("Global Hotkey"))
        hk_box_l = QtWidgets.QVBoxLayout(hk_box)
        hk_box_l.setSpacing(10)
        hk_box_l.addWidget(self.hk_enabled)
        hk_box_l.addLayout(hk_row)
        hk_hint = QtWidgets.QLabel(tr("Hotkey Hint"))
        hk_hint.setObjectName("HintLabel")
        hk_hint.setWordWrap(True)
        hk_layout = QtWidgets.QVBoxLayout(hotkey_page)
        hk_layout.setSpacing(12)
        hk_layout.setContentsMargins(16, 16, 16, 16)
        hk_layout.addWidget(hk_box)
        hk_layout.addWidget(hk_hint)
        hk_layout.addStretch(1)

        # === Restore tab ===
        restore = settings.get("restore", {})
        self.rs_folder = QtWidgets.QCheckBox(tr("Open folder on restore"))
        self.rs_terminal = QtWidgets.QCheckBox(tr("Open terminal on restore"))
        self.rs_vscode = QtWidgets.QCheckBox(tr("Open VSCode on restore"))
        self.rs_running_apps = QtWidgets.QCheckBox(tr("Restore apps on restore"))
        self.rs_recent_files = QtWidgets.QCheckBox(tr("Open recent files in VSCode"))
        self.rs_recent_files_limit = NoScrollSpinBox()
        self.rs_recent_files_limit.setRange(0, 20)
        self.rs_recent_files_limit.setSuffix(tr("suffix_files"))
        self.rs_checklist = QtWidgets.QCheckBox(tr("Show post-restore checklist"))
        self.rs_folder.setChecked(bool(restore.get("open_folder", True)))
        self.rs_terminal.setChecked(bool(restore.get("open_terminal", True)))
        self.rs_vscode.setChecked(bool(restore.get("open_vscode", True)))
        self.rs_running_apps.setChecked(bool(restore.get("open_running_apps", False)))
        self.rs_recent_files.setChecked(bool(restore.get("open_recent_files", False)))
        self.rs_recent_files_limit.setValue(int(restore.get("open_recent_files_limit", 5) or 0))
        self.rs_checklist.setChecked(bool(restore.get("show_post_restore_checklist", True)))

        self.preview_default = QtWidgets.QCheckBox(tr("Show restore preview by default"))
        self.preview_default.setChecked(bool(settings.get("restore_preview_default", True)))

        restore_page = QtWidgets.QWidget()
        restore_box = QtWidgets.QGroupBox(tr("Restore Defaults"))
        restore_l = QtWidgets.QVBoxLayout(restore_box)
        restore_l.setSpacing(8)
        restore_l.addWidget(self.rs_folder)
        restore_l.addWidget(self.rs_terminal)
        restore_l.addWidget(self.rs_vscode)
        rf_row = QtWidgets.QHBoxLayout()
        rf_row.setSpacing(8)
        rf_row.addWidget(self.rs_recent_files, 1)
        rf_row.addWidget(QtWidgets.QLabel(tr("Recent files to open")))
        rf_row.addWidget(self.rs_recent_files_limit)
        restore_l.addLayout(rf_row)
        restore_l.addWidget(self.rs_running_apps)
        restore_l.addWidget(self.rs_checklist)
        restore_l.addSpacing(12)
        restore_l.addWidget(self.preview_default)

        # Recent files in VSCode only makes sense when VSCode restore is enabled.
        def _sync_recent_files_enabled(vscode_on: bool) -> None:
            self.rs_recent_files.setEnabled(bool(vscode_on))
            self.rs_recent_files_limit.setEnabled(bool(vscode_on) and bool(self.rs_recent_files.isChecked()))
            if not vscode_on:
                self.rs_recent_files.setChecked(False)

        self.rs_vscode.toggled.connect(_sync_recent_files_enabled)
        self.rs_recent_files.toggled.connect(lambda on: self.rs_recent_files_limit.setEnabled(bool(self.rs_vscode.isChecked()) and bool(on)))
        _sync_recent_files_enabled(bool(self.rs_vscode.isChecked()))
        restore_hint = QtWidgets.QLabel(tr("Restore Preview Hint"))
        restore_hint.setObjectName("HintLabel")
        restore_hint.setWordWrap(True)
        restore_layout = QtWidgets.QVBoxLayout(restore_page)
        restore_layout.setSpacing(12)
        restore_layout.setContentsMargins(16, 16, 16, 16)
        restore_layout.addWidget(restore_box)
        restore_layout.addWidget(restore_hint)
        restore_layout.addStretch(1)

        # === General tab (SCROLLABLE) ===
        general_content = QtWidgets.QWidget()

        # Language selection
        lang_box = QtWidgets.QGroupBox(tr("Language (Requires Restart)"))
        lang_layout = QtWidgets.QHBoxLayout(lang_box)
        self.lang_combo = NoScrollComboBox()
        self.lang_combo.addItem(tr("System Default"), "auto")
        self.lang_combo.addItem("English", "en")
        self.lang_combo.addItem("한국어", "ko")
        lang_layout.addWidget(self.lang_combo)
        lang_layout.addStretch(1)

        # Recent files settings
        self.recent_spin = NoScrollSpinBox()
        self.recent_spin.setRange(0, 300)
        self.recent_spin.setValue(int(settings.get("recent_files_limit", 30)))
        self.recent_spin.setSuffix(tr("suffix_files"))
        self.scan_limit_spin = NoScrollSpinBox()
        self.scan_limit_spin.setRange(100, 200000)
        self.scan_limit_spin.setValue(int(settings.get("recent_files_scan_limit", 20000)))
        self.scan_limit_spin.setSuffix(tr("suffix_files"))
        self.scan_seconds_spin = NoScrollDoubleSpinBox()
        self.scan_seconds_spin.setRange(0.1, 10.0)
        self.scan_seconds_spin.setSingleStep(0.5)
        self.scan_seconds_spin.setValue(float(settings.get("recent_files_scan_seconds", 2.0)))
        self.scan_seconds_spin.setSuffix(tr("suffix_sec"))
        self.background_recent = QtWidgets.QCheckBox(tr("Recent Files Scan"))
        self.background_recent.setToolTip(tr("Recent Files Scan"))
        self.background_recent.setChecked(bool(settings.get("recent_files_background", False)))

        scan_box = QtWidgets.QGroupBox(tr("Recent Files Scan"))
        scan_layout = QtWidgets.QFormLayout(scan_box)
        scan_layout.setSpacing(8)
        scan_layout.addRow(tr("Files to collect") + ":", self.recent_spin)
        scan_layout.addRow(tr("Scan limit") + ":", self.scan_limit_spin)
        scan_layout.addRow(tr("Scan timeout") + ":", self.scan_seconds_spin)
        scan_layout.addRow("", self.background_recent)

        # Pagination
        self.page_size_spin = NoScrollSpinBox()
        self.page_size_spin.setRange(20, 2000)
        self.page_size_spin.setValue(int(settings.get("list_page_size", 200)))
        self.page_size_spin.setSuffix(tr("suffix_per_page"))

        # Auto snapshot
        self.auto_snapshot_minutes = NoScrollSpinBox()
        self.auto_snapshot_minutes.setRange(0, 1440)
        self.auto_snapshot_minutes.setSuffix(tr("suffix_min"))
        self.auto_snapshot_minutes.setValue(int(settings.get("auto_snapshot_minutes", 0)))
        self.auto_snapshot_on_git = QtWidgets.QCheckBox(tr("Trigger on Git commit"))
        self.auto_snapshot_on_git.setChecked(bool(settings.get("auto_snapshot_on_git_change", False)))

        auto_box = QtWidgets.QGroupBox(tr("Automation"))
        auto_layout = QtWidgets.QFormLayout(auto_box)
        auto_layout.setSpacing(8)
        auto_layout.addRow(tr("Snapshot list page size") + ":", self.page_size_spin)
        auto_layout.addRow(tr("Interval (minutes, 0=disabled)") + ":", self.auto_snapshot_minutes)
        auto_layout.addRow("", self.auto_snapshot_on_git)

        # Capture settings
        capture = settings.get("capture", {})
        self.capture_recent = QtWidgets.QCheckBox(tr("Capture recent files"))
        self.capture_processes = QtWidgets.QCheckBox(tr("Capture running processes"))
        self.capture_running_apps = QtWidgets.QCheckBox(tr("Running apps to restore"))
        self.capture_note = QtWidgets.QCheckBox(tr("Capture note"))
        self.capture_todos = QtWidgets.QCheckBox(tr("Capture TODOs"))
        self.capture_enforce_todos = QtWidgets.QCheckBox(tr("Enforce 3 TODOs"))

        self.capture_recent.setToolTip(tr("Recent Files Hint"))
        self.capture_processes.setToolTip(tr("Privacy Hint"))
        self.capture_running_apps.setToolTip(tr("Privacy Hint"))

        self.capture_recent.setChecked(bool(capture.get("recent_files", True)))
        self.capture_processes.setChecked(bool(capture.get("processes", True)))
        self.capture_running_apps.setChecked(bool(capture.get("running_apps", True)))
        self.capture_note.setChecked(bool(settings.get("capture_note", True)))
        self.capture_todos.setChecked(bool(settings.get("capture_todos", True)))
        self.capture_enforce_todos.setChecked(bool(settings.get("capture_enforce_todos", True)))

        capture_box = QtWidgets.QGroupBox(tr("Capture Options"))
        capture_layout = QtWidgets.QVBoxLayout(capture_box)
        capture_layout.setSpacing(6)
        capture_layout.addWidget(self.capture_recent)
        capture_layout.addWidget(self.capture_processes)
        capture_layout.addWidget(self.capture_running_apps)
        capture_layout.addWidget(self.capture_note)
        capture_layout.addWidget(self.capture_todos)
        capture_layout.addWidget(self.capture_enforce_todos)

        # Archive & Backup
        self.archive_after_days = NoScrollSpinBox()
        self.archive_after_days.setRange(0, 3650)
        self.archive_after_days.setValue(int(settings.get("archive_after_days", 0)))
        self.archive_after_days.setSuffix(tr("suffix_days"))
        self.archive_skip_pinned = QtWidgets.QCheckBox(tr("Skip pinned snapshots when auto-archiving"))
        self.archive_skip_pinned.setChecked(bool(settings.get("archive_skip_pinned", True)))
        self.auto_backup_hours = NoScrollSpinBox()
        self.auto_backup_hours.setRange(0, 168)
        self.auto_backup_hours.setValue(int(settings.get("auto_backup_hours", 0)))
        self.auto_backup_hours.setSuffix(tr("suffix_hours"))

        archive_box = QtWidgets.QGroupBox(tr("Archive & Backup"))
        archive_layout = QtWidgets.QFormLayout(archive_box)
        archive_layout.setSpacing(8)
        archive_layout.addRow(tr("Auto-archive after") + ":", self.archive_after_days)
        archive_layout.addRow("", self.archive_skip_pinned)
        archive_layout.addRow(tr("Auto backup interval") + ":", self.auto_backup_hours)

        # Filters section
        self.exclude_dirs = QtWidgets.QLineEdit()
        self.exclude_dirs.setPlaceholderText(tr("Exclude dirs (comma-separated)"))
        self.exclude_dirs.setText(", ".join(settings.get("recent_files_exclude", [])))
        self.exclude_dirs.setToolTip(tr("Exclude dirs (comma-separated)"))

        self.include_patterns = QtWidgets.QLineEdit()
        self.include_patterns.setPlaceholderText(tr("Include patterns for recent file scan"))
        self.include_patterns.setText(", ".join(settings.get("recent_files_include", [])))
        self.exclude_patterns = QtWidgets.QLineEdit()
        self.exclude_patterns.setPlaceholderText(tr("Exclude patterns for recent file scan"))
        self.exclude_patterns.setText(", ".join(settings.get("recent_files_exclude_patterns", [])))

        self.process_keywords = QtWidgets.QLineEdit()
        self.process_keywords.setPlaceholderText(tr("Process Keywords"))
        self.process_keywords.setText(", ".join(settings.get("process_keywords", [])))

        filter_box = QtWidgets.QGroupBox(tr("Filters"))
        filter_layout = QtWidgets.QFormLayout(filter_box)
        filter_layout.setSpacing(8)
        filter_layout.addRow(tr("Exclude dirs (comma-separated)") + ":", self.exclude_dirs)
        filter_layout.addRow(tr("Include patterns for recent file scan") + ":", self.include_patterns)
        filter_layout.addRow(tr("Exclude patterns for recent file scan") + ":", self.exclude_patterns)
        filter_layout.addRow(tr("Process Keywords") + ":", self.process_keywords)

        # Terminal settings
        term = settings.get("terminal", {}) if isinstance(settings.get("terminal"), dict) else {}
        self.terminal_mode = NoScrollComboBox()
        self.terminal_mode.addItem(tr("Auto"), "auto")
        self.terminal_mode.addItem("Windows Terminal (wt)", "wt")
        self.terminal_mode.addItem("cmd.exe", "cmd")
        self.terminal_mode.addItem("PowerShell (pwsh)", "pwsh")
        self.terminal_mode.addItem("Windows PowerShell", "powershell")
        self.terminal_mode.addItem(tr("Custom"), "custom")
        mode = str(term.get("mode") or "auto")
        midx = self.terminal_mode.findData(mode)
        self.terminal_mode.setCurrentIndex(midx if midx >= 0 else 0)

        self.terminal_custom_argv = QtWidgets.QPlainTextEdit()
        self.terminal_custom_argv.setPlaceholderText(tr("Terminal custom argv hint"))
        self.terminal_custom_argv.setMaximumHeight(90)
        argv0 = term.get("custom_argv") if isinstance(term.get("custom_argv"), list) else ["wt", "-d", "{path}"]
        self.terminal_custom_argv.setPlainText("\n".join([str(x) for x in argv0 if str(x).strip()]))
        self.terminal_custom_argv.setEnabled(self.terminal_mode.currentData() == "custom")
        self.terminal_mode.currentIndexChanged.connect(lambda: self.terminal_custom_argv.setEnabled(self.terminal_mode.currentData() == "custom"))

        term_box = QtWidgets.QGroupBox(tr("Terminal"))
        term_l = QtWidgets.QFormLayout(term_box)
        term_l.setSpacing(8)
        term_l.addRow(tr("Terminal mode") + ":", self.terminal_mode)
        term_l.addRow(tr("Custom argv") + ":", self.terminal_custom_argv)

        # Saved searches
        self.saved_searches_list = QtWidgets.QListWidget()
        self.saved_searches_list.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.saved_searches_list.setMaximumHeight(150)
        self.saved_search_name = QtWidgets.QLineEdit()
        self.saved_search_name.setPlaceholderText(tr("Saved search name"))
        self.saved_search_query = QtWidgets.QLineEdit()
        self.saved_search_query.setPlaceholderText(tr("Saved search query"))
        self.btn_saved_search_add = QtWidgets.QPushButton(tr("Add / Update"))
        self.btn_saved_search_add.setProperty("primary", True)
        self.btn_saved_search_remove = QtWidgets.QPushButton(tr("Delete"))
        self.btn_saved_search_remove.setProperty("danger", True)
        self.btn_saved_search_add.clicked.connect(self.add_or_update_saved_search)
        self.btn_saved_search_remove.clicked.connect(self.remove_saved_search)
        self.saved_searches_list.currentRowChanged.connect(self.load_saved_search_to_form)
        self._saved_searches_cache: List[Dict[str, str]] = []
        self._load_saved_searches(settings.get("saved_searches", []))

        ss_form = QtWidgets.QFormLayout()
        ss_form.setSpacing(8)
        ss_form.addRow(tr("Name"), self.saved_search_name)
        ss_form.addRow(tr("Query"), self.saved_search_query)

        ss_btns = QtWidgets.QHBoxLayout()
        ss_btns.setSpacing(8)
        ss_btns.addWidget(self.btn_saved_search_add)
        ss_btns.addWidget(self.btn_saved_search_remove)
        ss_btns.addStretch(1)

        ss_box = QtWidgets.QGroupBox(tr("Saved searches"))
        ss_l = QtWidgets.QVBoxLayout(ss_box)
        ss_l.setSpacing(10)
        ss_l.addWidget(self.saved_searches_list)
        ss_l.addLayout(ss_form)
        ss_l.addLayout(ss_btns)

        privacy_hint = QtWidgets.QLabel(tr("Privacy Hint"))
        privacy_hint.setObjectName("HintLabel")
        privacy_hint.setWordWrap(True)

        # General layout with all boxes
        general_layout = QtWidgets.QVBoxLayout(general_content)
        general_layout.setSpacing(12)
        general_layout.setContentsMargins(16, 16, 16, 16)
        general_layout.addWidget(lang_box)
        general_layout.addWidget(scan_box)
        general_layout.addWidget(capture_box)
        general_layout.addWidget(auto_box)
        general_layout.addWidget(archive_box)
        general_layout.addWidget(filter_box)
        general_layout.addWidget(term_box)
        general_layout.addWidget(ss_box)
        general_layout.addWidget(privacy_hint)
        general_layout.addStretch(1)

        # Wrap in scroll area
        general_page = _make_scrollable(general_content)

        # === Tags tab ===
        tags_content = QtWidgets.QWidget()
        self.tags_list = QtWidgets.QListWidget()
        self.tags_list.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        for t in (settings.get("tags") or DEFAULT_TAGS):
            self.tags_list.addItem(t)
        self.tag_input = QtWidgets.QLineEdit()
        self.tag_input.setPlaceholderText(tr("Add tag placeholder"))

        btn_add = QtWidgets.QPushButton(tr("Add"))
        btn_add.setProperty("primary", True)
        btn_remove = QtWidgets.QPushButton(tr("Delete"))
        btn_remove.setProperty("danger", True)
        btn_add.clicked.connect(self.add_tag)
        btn_remove.clicked.connect(self.remove_tag)

        tag_row = QtWidgets.QHBoxLayout()
        tag_row.setSpacing(8)
        tag_row.addWidget(self.tag_input, 1)
        tag_row.addWidget(btn_add)
        tag_row.addWidget(btn_remove)

        tags_box = QtWidgets.QGroupBox(tr("Tags"))
        tags_l = QtWidgets.QVBoxLayout(tags_box)
        tags_l.setSpacing(10)
        tags_l.addWidget(self.tags_list)
        tags_l.addLayout(tag_row)
        tags_hint = QtWidgets.QLabel(tr("Tags Hint"))
        tags_hint.setObjectName("HintLabel")
        tags_hint.setWordWrap(True)
        tags_layout = QtWidgets.QVBoxLayout(tags_content)
        tags_layout.setSpacing(12)
        tags_layout.setContentsMargins(16, 16, 16, 16)
        tags_layout.addWidget(tags_box)
        tags_layout.addWidget(tags_hint)
        tags_layout.addStretch(1)

        tags_page = _make_scrollable(tags_content)

        # === Templates tab ===
        templates_content = QtWidgets.QWidget()
        self.templates_list = QtWidgets.QListWidget()
        self.templates_list.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.templates_list.setMaximumHeight(150)
        self.template_name = QtWidgets.QLineEdit()
        self.template_name.setPlaceholderText(tr("Title placeholder"))
        self.template_note = QtWidgets.QTextEdit()
        self.template_note.setPlaceholderText(tr("Note placeholder"))
        self.template_note.setMaximumHeight(80)
        self.template_todo1 = QtWidgets.QLineEdit()
        self.template_todo2 = QtWidgets.QLineEdit()
        self.template_todo3 = QtWidgets.QLineEdit()
        for t in (self.template_todo1, self.template_todo2, self.template_todo3):
            t.setPlaceholderText(tr("Template TODO"))

        self.template_tags = QtWidgets.QLineEdit()
        self.template_tags.setPlaceholderText(tr("Tags (optional)"))
        self.btn_template_add = QtWidgets.QPushButton(tr("Add / Update"))
        self.btn_template_add.setProperty("primary", True)
        self.btn_template_remove = QtWidgets.QPushButton(tr("Delete"))
        self.btn_template_remove.setProperty("danger", True)
        self.btn_template_add.clicked.connect(self.add_or_update_template)
        self.btn_template_remove.clicked.connect(self.remove_template)
        self.templates_list.currentRowChanged.connect(self.load_template_to_form)

        template_form = QtWidgets.QFormLayout()
        template_form.setSpacing(8)
        template_form.addRow("Name", self.template_name)
        template_form.addRow("Note", self.template_note)
        template_form.addRow("TODO 1", self.template_todo1)
        template_form.addRow("TODO 2", self.template_todo2)
        template_form.addRow("TODO 3", self.template_todo3)
        template_form.addRow("Tags", self.template_tags)

        template_btns = QtWidgets.QHBoxLayout()
        template_btns.setSpacing(8)
        template_btns.addWidget(self.btn_template_add)
        template_btns.addWidget(self.btn_template_remove)
        template_btns.addStretch(1)

        templates_box = QtWidgets.QGroupBox(tr("Template"))
        templates_box_l = QtWidgets.QVBoxLayout(templates_box)
        templates_box_l.setSpacing(10)
        templates_box_l.addWidget(self.templates_list)
        templates_box_l.addLayout(template_form)
        templates_box_l.addLayout(template_btns)

        templates_layout = QtWidgets.QVBoxLayout(templates_content)
        templates_layout.setSpacing(12)
        templates_layout.setContentsMargins(16, 16, 16, 16)
        templates_layout.addWidget(templates_box)
        templates_layout.addStretch(1)

        self._templates_cache = []
        self._load_templates(settings.get("templates", []))

        templates_page = _make_scrollable(templates_content)

        # === Backup tab ===
        backup_content = QtWidgets.QWidget()
        b_title = QtWidgets.QLabel(tr("Backup / Restore"))
        b_title.setObjectName("TitleLabel")
        b_hint = QtWidgets.QLabel(tr("Backup Hint"))
        b_hint.setObjectName("HintLabel")
        b_hint.setWordWrap(True)

        # export options
        self.exp_settings = QtWidgets.QCheckBox(tr("Include settings"))
        self.exp_settings.setChecked(True)
        self.exp_settings.setEnabled(False)
        self.exp_index = QtWidgets.QCheckBox(tr("Include index"))
        self.exp_index.setChecked(True)
        self.exp_snaps = QtWidgets.QCheckBox(tr("Include snapshots"))
        self.exp_snaps.setChecked(True)

        exp_box = QtWidgets.QGroupBox(tr("Export options group"))
        exp_l = QtWidgets.QVBoxLayout(exp_box)
        exp_l.setSpacing(8)
        exp_l.addWidget(self.exp_settings)
        exp_l.addWidget(self.exp_index)
        exp_l.addWidget(self.exp_snaps)

        self.btn_export = QtWidgets.QPushButton(tr("Export Backup"))
        self.btn_export.setProperty("primary", True)
        self.btn_import = QtWidgets.QPushButton(tr("Import Backup"))
        self.btn_reset = QtWidgets.QPushButton(tr("Restore Defaults"))
        self.btn_reset.setProperty("danger", True)
        self.btn_export.clicked.connect(self.export_settings)
        self.btn_import.clicked.connect(self.import_settings)
        self.btn_reset.clicked.connect(self.reset_defaults)

        b_row = QtWidgets.QHBoxLayout()
        b_row.setSpacing(10)
        b_row.addWidget(self.btn_export)
        b_row.addWidget(self.btn_import)
        b_row.addStretch(1)
        b_row.addWidget(self.btn_reset)

        self.b_msg = QtWidgets.QLabel("")
        self.b_msg.setObjectName("HintLabel")
        self.b_msg.setWordWrap(True)

        b_layout = QtWidgets.QVBoxLayout(backup_content)
        b_layout.setSpacing(12)
        b_layout.setContentsMargins(16, 16, 16, 16)
        b_layout.addWidget(b_title)
        b_layout.addWidget(b_hint)
        b_layout.addSpacing(10)
        b_layout.addWidget(exp_box)
        b_layout.addSpacing(8)
        b_layout.addLayout(b_row)
        b_layout.addSpacing(10)
        b_layout.addWidget(self.b_msg)
        b_layout.addStretch(1)

        backup_page = _make_scrollable(backup_content)

        # Add tabs (clean text, no emoji)
        tabs.addTab(general_page, tr("General"))
        tabs.addTab(restore_page, tr("Restore"))
        tabs.addTab(hotkey_page, tr("Global Hotkey"))
        tabs.addTab(tags_page, tr("Tags"))
        tabs.addTab(templates_page, tr("Template"))
        tabs.addTab(backup_page, "Backup")

        # Bottom buttons
        self.err = QtWidgets.QLabel("")
        self.err.setStyleSheet("color: #ef4444; font-weight: 500;")
        self.err.setObjectName("ErrorLabel")
        btn_ok = QtWidgets.QPushButton(tr("Save"))
        btn_ok.setProperty("primary", True)
        btn_cancel = QtWidgets.QPushButton(tr("Cancel"))
        btn_ok.clicked.connect(self.validate_and_accept)
        btn_cancel.clicked.connect(self.reject)
        btn_row = QtWidgets.QHBoxLayout()
        btn_row.setSpacing(10)
        btn_row.addStretch(1)
        btn_row.addWidget(btn_cancel)
        btn_row.addWidget(btn_ok)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.addWidget(header)
        layout.addWidget(sub)
        layout.addSpacing(8)
        layout.addWidget(tabs, 1)
        layout.addWidget(self.err)
        layout.addLayout(btn_row)

    def export_settings(self):
        default_name = f"{APP_NAME}_backup_{datetime.now().strftime('%Y%m%d')}.json"
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Export backup", str(Path.home() / default_name), "JSON files (*.json)"
        )
        if not path:
            return
        try:
            # Always export migrated settings; include data optionally
            vals = migrate_settings(self.values() | {"onboarding_shown": True})
            export_backup_to_file(
                Path(path),
                settings=vals,
                snaps_dir=self._snaps_dir,
                index_path=self._index_path,
                include_snapshots=bool(self.exp_snaps.isChecked()),
                include_index=bool(self.exp_index.isChecked()),
            )
            self.b_msg.setText(f"{tr('Exported')}{path}")
        except Exception as e:
            log_exc("export backup", e)
            QtWidgets.QMessageBox.warning(self, "Export failed", str(e))

    def import_settings(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Import backup", str(Path.home()), "JSON files (*.json)"
        )
        if not path:
            return
        try:
            payload = import_backup_from_file(Path(path))
            self._imported_payload = payload
            new_settings = payload.get("settings", {})
            self.apply_settings_to_controls(new_settings)

            msg = QtWidgets.QMessageBox(self)
            msg.setWindowTitle(tr("Import Dialog Title"))
            msg.setText(tr("Import Params"))
            msg.setInformativeText(tr("Import Info"))
            btn_apply = msg.addButton(tr("Apply now"), QtWidgets.QMessageBox.AcceptRole)
            msg.addButton(tr("Keep in dialog"), QtWidgets.QMessageBox.RejectRole)
            msg.exec()
            self._import_apply_now = (msg.clickedButton() == btn_apply)

            if self._import_apply_now:
                self.settingsImported.emit(payload)
                self.b_msg.setText(f"{tr('Imported+Applied')}{path}")
            else:
                self.b_msg.setText(f"{tr('Imported into dialog')}{path}")
        except Exception as e:
            log_exc("import backup", e)
            QtWidgets.QMessageBox.warning(self, "Import failed", str(e))

    def reset_defaults(self):
        new_settings = migrate_settings({"tags": DEFAULT_TAGS})
        # Keep onboarding shown; reset is for behavior not education
        new_settings["onboarding_shown"] = True
        self.apply_settings_to_controls(new_settings)
        self.b_msg.setText(tr("Reset to defaults done"))

    def apply_settings_to_controls(self, settings: Dict[str, Any]) -> None:
        """Apply a settings dict to UI controls (does not save to disk here)."""
        settings = migrate_settings(settings)
        self._settings = settings
        self._imported_payload = None
        self._import_apply_now = False

        # Apply Language
        lang = settings.get("language", "auto")
        idx = self.lang_combo.findData(lang)
        if idx >= 0:
            self.lang_combo.setCurrentIndex(idx)
        else:
            self.lang_combo.setCurrentIndex(0)  # Default to auto if unknown

        hk = settings.get("hotkey", {})
        self.hk_enabled.setChecked(bool(hk.get("enabled", True)))
        self.hk_ctrl.setChecked(bool(hk.get("ctrl", True)))
        self.hk_alt.setChecked(bool(hk.get("alt", True)))
        self.hk_shift.setChecked(bool(hk.get("shift", False)))
        vk = str(hk.get("vk", "S")).upper()
        idx = self.hk_key.findText(vk)
        if idx >= 0:
            self.hk_key.setCurrentIndex(idx)

        restore = settings.get("restore", {})
        self.rs_folder.setChecked(bool(restore.get("open_folder", True)))
        self.rs_terminal.setChecked(bool(restore.get("open_terminal", True)))
        self.rs_vscode.setChecked(bool(restore.get("open_vscode", True)))
        self.rs_running_apps.setChecked(bool(restore.get("open_running_apps", False)))
        self.rs_recent_files.setChecked(bool(restore.get("open_recent_files", False)))
        self.rs_recent_files_limit.setValue(int(restore.get("open_recent_files_limit", 5) or 0))
        self.rs_checklist.setChecked(bool(restore.get("show_post_restore_checklist", True)))
        self.preview_default.setChecked(bool(settings.get("restore_preview_default", True)))

        term = settings.get("terminal", {}) if isinstance(settings.get("terminal"), dict) else {}
        mode = str(term.get("mode") or "auto")
        midx = self.terminal_mode.findData(mode)
        self.terminal_mode.setCurrentIndex(midx if midx >= 0 else 0)
        argv0 = term.get("custom_argv") if isinstance(term.get("custom_argv"), list) else ["wt", "-d", "{path}"]
        self.terminal_custom_argv.setPlainText("\n".join([str(x) for x in argv0 if str(x).strip()]))
        self.terminal_custom_argv.setEnabled(self.terminal_mode.currentData() == "custom")

        self._load_saved_searches(settings.get("saved_searches", []))

        self.recent_spin.setValue(int(settings.get("recent_files_limit", 30)))
        self.scan_limit_spin.setValue(int(settings.get("recent_files_scan_limit", 20000)))
        self.scan_seconds_spin.setValue(float(settings.get("recent_files_scan_seconds", 2.0)))
        self.background_recent.setChecked(bool(settings.get("recent_files_background", False)))
        self.page_size_spin.setValue(int(settings.get("list_page_size", 200)))
        self.auto_snapshot_minutes.setValue(int(settings.get("auto_snapshot_minutes", 0)))
        self.auto_snapshot_on_git.setChecked(bool(settings.get("auto_snapshot_on_git_change", False)))
        capture = settings.get("capture", {})
        self.capture_recent.setChecked(bool(capture.get("recent_files", True)))
        self.capture_processes.setChecked(bool(capture.get("processes", True)))
        self.capture_running_apps.setChecked(bool(capture.get("running_apps", True)))
        self.capture_note.setChecked(bool(settings.get("capture_note", True)))
        self.capture_todos.setChecked(bool(settings.get("capture_todos", True)))
        self.capture_enforce_todos.setChecked(bool(settings.get("capture_enforce_todos", True)))
        self.exclude_dirs.setText(", ".join(settings.get("recent_files_exclude", [])))
        self.include_patterns.setText(", ".join(settings.get("recent_files_include", [])))
        self.exclude_patterns.setText(", ".join(settings.get("recent_files_exclude_patterns", [])))
        self.process_keywords.setText(", ".join(settings.get("process_keywords", [])))
        self.archive_after_days.setValue(int(settings.get("archive_after_days", 0)))
        self.archive_skip_pinned.setChecked(bool(settings.get("archive_skip_pinned", True)))
        self.auto_backup_hours.setValue(int(settings.get("auto_backup_hours", 0)))

        self.tags_list.clear()
        for t in (settings.get("tags") or DEFAULT_TAGS):
            self.tags_list.addItem(t)
        self._load_templates(settings.get("templates", []))

    def add_tag(self):
        t = self.tag_input.text().strip()
        if not t:
            return
        for i in range(self.tags_list.count()):
            if self.tags_list.item(i).text() == t:
                self.tag_input.clear()
                return
        self.tags_list.addItem(t)
        self.tag_input.clear()

    def remove_tag(self):
        row = self.tags_list.currentRow()
        if row >= 0:
            self.tags_list.takeItem(row)

    def _load_templates(self, templates: List[Dict[str, Any]]) -> None:
        self._templates_cache = templates or []
        self.templates_list.clear()
        for tmpl in self._templates_cache:
            name = str(tmpl.get("name", "")).strip() or "Untitled"
            self.templates_list.addItem(name)
        self.template_name.clear()
        self.template_note.clear()
        self.template_todo1.clear()
        self.template_todo2.clear()
        self.template_todo3.clear()
        self.template_tags.clear()

    def _load_saved_searches(self, saved: Any) -> None:
        self._saved_searches_cache = []
        if isinstance(saved, list):
            for it in saved:
                if not isinstance(it, dict):
                    continue
                name = str(it.get("name") or "").strip()
                query = str(it.get("query") or "").strip()
                if not query:
                    continue
                self._saved_searches_cache.append({"name": name or "Untitled", "query": query})
        self.saved_searches_list.clear()
        for it in self._saved_searches_cache:
            self.saved_searches_list.addItem(str(it.get("name") or "Untitled"))
        self.saved_search_name.clear()
        self.saved_search_query.clear()

    def load_saved_search_to_form(self, row: int) -> None:
        if row < 0 or row >= len(self._saved_searches_cache):
            return
        it = self._saved_searches_cache[row]
        self.saved_search_name.setText(str(it.get("name") or ""))
        self.saved_search_query.setText(str(it.get("query") or ""))

    def add_or_update_saved_search(self) -> None:
        name = self.saved_search_name.text().strip() or "Untitled"
        query = self.saved_search_query.text().strip()
        if not query:
            self.err.setText(tr("Saved search query required"))
            return
        self.err.setText("")
        row = self.saved_searches_list.currentRow()
        it = {"name": name, "query": query}
        if row >= 0 and row < len(self._saved_searches_cache):
            self._saved_searches_cache[row] = it
            self.saved_searches_list.item(row).setText(name)
        else:
            self._saved_searches_cache.append(it)
            self.saved_searches_list.addItem(name)
            self.saved_searches_list.setCurrentRow(len(self._saved_searches_cache) - 1)

    def remove_saved_search(self) -> None:
        row = self.saved_searches_list.currentRow()
        if row < 0 or row >= len(self._saved_searches_cache):
            return
        self._saved_searches_cache.pop(row)
        self.saved_searches_list.takeItem(row)
        self.saved_search_name.clear()
        self.saved_search_query.clear()

    def load_template_to_form(self, row: int) -> None:
        if row < 0 or row >= len(self._templates_cache):
            return
        tmpl = self._templates_cache[row]
        self.template_name.setText(str(tmpl.get("name", "")))
        self.template_note.setText(str(tmpl.get("note", "")))
        todos = tmpl.get("todos", []) or []
        self.template_todo1.setText(str(todos[0]) if len(todos) > 0 else "")
        self.template_todo2.setText(str(todos[1]) if len(todos) > 1 else "")
        self.template_todo3.setText(str(todos[2]) if len(todos) > 2 else "")
        self.template_tags.setText(", ".join(tmpl.get("tags", []) or []))

    def add_or_update_template(self) -> None:
        name = self.template_name.text().strip() or "Untitled"
        tmpl = {
            "name": name,
            "note": self.template_note.toPlainText().strip(),
            "todos": [
                self.template_todo1.text().strip(),
                self.template_todo2.text().strip(),
                self.template_todo3.text().strip(),
            ],
            "tags": [t.strip() for t in self.template_tags.text().split(",") if t.strip()],
        }
        row = self.templates_list.currentRow()
        if row >= 0 and row < len(self._templates_cache):
            self._templates_cache[row] = tmpl
            self.templates_list.item(row).setText(name)
        else:
            self._templates_cache.append(tmpl)
            self.templates_list.addItem(name)
            self.templates_list.setCurrentRow(len(self._templates_cache) - 1)

    def remove_template(self) -> None:
        row = self.templates_list.currentRow()
        if row < 0 or row >= len(self._templates_cache):
            return
        self._templates_cache.pop(row)
        self.templates_list.takeItem(row)

    def imported_payload(self):
        return self._imported_payload

    def import_apply_now(self) -> bool:
        return bool(self._import_apply_now)

    def validate_and_accept(self):
        # Ensure at least one modifier is chosen when enabled
        if self.hk_enabled.isChecked():
            if not (self.hk_ctrl.isChecked() or self.hk_alt.isChecked() or self.hk_shift.isChecked()):
                self.err.setText(tr("Hotkey selection err"))
                return
        self.accept()

    def values(self) -> Dict[str, Any]:
        tags: List[str] = []
        for i in range(self.tags_list.count()):
            t = self.tags_list.item(i).text().strip()
            if t:
                tags.append(t)
        return {
            "language": self.lang_combo.currentData(),
            "recent_files_limit": int(self.recent_spin.value()),
            "restore_preview_default": bool(self.preview_default.isChecked()),
            "tags": tags or DEFAULT_TAGS,
            "hotkey": {
                "enabled": bool(self.hk_enabled.isChecked()),
                "ctrl": bool(self.hk_ctrl.isChecked()),
                "alt": bool(self.hk_alt.isChecked()),
                "shift": bool(self.hk_shift.isChecked()),
                "vk": str(self.hk_key.currentText()),
            },
            "capture": {
                "recent_files": bool(self.capture_recent.isChecked()),
                "processes": bool(self.capture_processes.isChecked()),
                "running_apps": bool(self.capture_running_apps.isChecked()),
            },
            "capture_note": bool(self.capture_note.isChecked()),
            "capture_todos": bool(self.capture_todos.isChecked()),
            "capture_enforce_todos": bool(self.capture_enforce_todos.isChecked()),
            "recent_files_scan_limit": int(self.scan_limit_spin.value()),
            "recent_files_scan_seconds": float(self.scan_seconds_spin.value()),
            "recent_files_background": bool(self.background_recent.isChecked()),
            "list_page_size": int(self.page_size_spin.value()),
            "recent_files_include": [
                part.strip() for part in self.include_patterns.text().split(",") if part.strip()
            ],
            "recent_files_exclude_patterns": [
                part.strip() for part in self.exclude_patterns.text().split(",") if part.strip()
            ],
            "process_keywords": [
                part.strip() for part in self.process_keywords.text().split(",") if part.strip()
            ],
            "archive_after_days": int(self.archive_after_days.value()),
            "archive_skip_pinned": bool(self.archive_skip_pinned.isChecked()),
            "auto_backup_hours": int(self.auto_backup_hours.value()),
            "templates": self._templates_cache,
            "auto_snapshot_minutes": int(self.auto_snapshot_minutes.value()),
            "auto_snapshot_on_git_change": bool(self.auto_snapshot_on_git.isChecked()),
            "recent_files_exclude": [
                part.strip() for part in self.exclude_dirs.text().split(",") if part.strip()
            ],
            "restore": {
                "open_folder": bool(self.rs_folder.isChecked()),
                "open_terminal": bool(self.rs_terminal.isChecked()),
                "open_vscode": bool(self.rs_vscode.isChecked()),
                "open_running_apps": bool(self.rs_running_apps.isChecked()),
                "open_recent_files": bool(self.rs_recent_files.isChecked()),
                "open_recent_files_limit": int(self.rs_recent_files_limit.value()),
                "show_post_restore_checklist": bool(self.rs_checklist.isChecked()),
            },
            "terminal": {
                "mode": self.terminal_mode.currentData(),
                "custom_argv": [line.strip() for line in self.terminal_custom_argv.toPlainText().splitlines() if line.strip()],
            },
            "saved_searches": self._saved_searches_cache,
        }
