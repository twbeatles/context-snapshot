from __future__ import annotations

import json
import logging
from logging.handlers import RotatingFileHandler
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from PySide6 import QtCore, QtGui, QtWidgets

from ctxsnap.utils import (
    build_search_blob,
    list_processes_filtered,
    list_running_apps,
    recent_files_under,
    restore_running_apps,
    snapshot_mtime,
)

APP_NAME = "ctxsnap"

# Predefined tags (user can edit via Settings)
DEFAULT_TAGS = ["업무", "개인", "부동산", "정산"]


# -------- Logging --------
LOGGER = logging.getLogger(APP_NAME)


def setup_logging() -> Path:
    """Configure rotating file logs under %APPDATA%\ctxsnap\logs."""
    log_dir = app_dir() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "ctxsnap.log"

    LOGGER.setLevel(logging.INFO)
    if not LOGGER.handlers:
        handler = RotatingFileHandler(str(log_file), maxBytes=1_000_000, backupCount=5, encoding="utf-8")
        fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
        handler.setFormatter(fmt)
        LOGGER.addHandler(handler)

    return log_file


def log_exc(context: str, e: Exception) -> None:
    try:
        LOGGER.exception("%s: %s", context, e)
    except Exception:
        pass



def app_dir() -> Path:
    """Return %APPDATA%\\ctxsnap."""
    appdata = os.environ.get("APPDATA")
    if not appdata:
        appdata = str(Path.home() / "AppData" / "Roaming")
    return Path(appdata) / APP_NAME


def ensure_storage() -> Tuple[Path, Path, Path]:
    base = app_dir()
    snaps = base / "snapshots"
    base.mkdir(parents=True, exist_ok=True)
    snaps.mkdir(parents=True, exist_ok=True)
    index_path = base / "index.json"
    settings_path = base / "settings.json"
    if not index_path.exists():
        index_path.write_text(json.dumps({"snapshots": []}, ensure_ascii=False, indent=2), encoding="utf-8")
    if not settings_path.exists():
        settings_path.write_text(
            json.dumps(
                {
                    "default_root": str(Path.home()),
                    "recent_files_limit": 30,
                    "restore_preview_default": True,
                    "tags": DEFAULT_TAGS,
                    "hotkey": {"enabled": True, "ctrl": True, "alt": True, "shift": False, "vk": "S"},
                    "capture": {"recent_files": True, "processes": True, "running_apps": True},
                    "recent_files_exclude": [".git", "node_modules", "venv", "dist", "build"],
                    "recent_files_scan_limit": 20000,
                    "recent_files_scan_seconds": 2.0,
                    "auto_snapshot_minutes": 0,
                    "auto_snapshot_on_git_change": False,
                    "restore": {
                        "open_folder": True,
                        "open_terminal": True,
                        "open_vscode": True,
                        "open_running_apps": True,
                        "show_post_restore_checklist": True,
                    },
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
    return snaps, index_path, settings_path


def load_json(p: Path) -> Dict[str, Any]:
    return json.loads(p.read_text(encoding="utf-8"))


def save_json(p: Path, data: Dict[str, Any]) -> None:
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def append_restore_history(entry: Dict[str, Any]) -> None:
    path = app_dir() / "restore_history.json"
    history = {"restores": []}
    if path.exists():
        try:
            history = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            history = {"restores": []}
    history.setdefault("restores", [])
    history["restores"].insert(0, entry)
    history["restores"] = history["restores"][:200]
    path.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")


def migrate_settings(settings: Dict[str, Any]) -> Dict[str, Any]:
    """Backfill missing keys for older settings.json."""
    settings.setdefault("default_root", str(Path.home()))
    settings.setdefault("recent_files_limit", 30)
    settings.setdefault("restore_preview_default", True)
    settings.setdefault("tags", DEFAULT_TAGS)
    settings.setdefault("hotkey", {"enabled": True, "ctrl": True, "alt": True, "shift": False, "vk": "S"})
    settings.setdefault("capture", {"recent_files": True, "processes": True, "running_apps": True})
    settings.setdefault("recent_files_exclude", [".git", "node_modules", "venv", "dist", "build"])
    settings.setdefault("recent_files_scan_limit", 20000)
    settings.setdefault("recent_files_scan_seconds", 2.0)
    settings.setdefault("auto_snapshot_minutes", 0)
    settings.setdefault("auto_snapshot_on_git_change", False)
    settings.setdefault(
        "restore",
        {
            "open_folder": True,
            "open_terminal": True,
            "open_vscode": True,
            "open_running_apps": True,
            "show_post_restore_checklist": True,
        },
    )
    # UX
    settings.setdefault("onboarding_shown", False)
    return settings


def export_settings_to_file(path: Path, settings: Dict[str, Any]) -> None:
    payload = {
        "app": APP_NAME,
        "version": 1,
        "exported_at": now_iso(),
        "settings": settings,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def import_settings_from_file(path: Path) -> Dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    # Accept either raw settings.json shape or exported payload.
    if isinstance(data, dict) and "settings" in data and isinstance(data["settings"], dict):
        data = data["settings"]
    if not isinstance(data, dict):
        raise ValueError("Invalid settings format")
    return migrate_settings(data)


# -------- Backup package (settings + optional snapshots/index) --------

def export_backup_to_file(path: Path, *, settings: Dict[str, Any], snaps_dir: Path, index_path: Path, include_snapshots: bool, include_index: bool) -> None:
    """Export a single JSON file that can contain settings and optionally snapshots/index."""
    payload: Dict[str, Any] = {
        "app": APP_NAME,
        "version": 2,
        "exported_at": now_iso(),
        "settings": migrate_settings(settings),
    }
    data: Dict[str, Any] = {}
    if include_index:
        try:
            data["index"] = load_json(index_path)
        except Exception as e:
            log_exc("read index for export", e)
            data["index"] = {"snapshots": []}
    if include_snapshots:
        snaps: List[Dict[str, Any]] = []
        for f in sorted(snaps_dir.glob("*.json")):
            try:
                snaps.append(json.loads(f.read_text(encoding="utf-8")))
            except Exception as e:
                log_exc(f"read snapshot {f.name}", e)
        data["snapshots"] = snaps
    if data:
        payload["data"] = data
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def import_backup_from_file(path: Path) -> Dict[str, Any]:
    """Import either settings-only export, or full backup with data."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("Invalid backup format")

    # Accept old settings-only exports
    if "settings" in raw and isinstance(raw["settings"], dict):
        settings = migrate_settings(raw["settings"])
        data = raw.get("data") if isinstance(raw.get("data"), dict) else None
        return {"settings": settings, "data": data}

    # Accept raw settings.json
    settings = migrate_settings(raw)
    return {"settings": settings, "data": None}


@dataclass
class Snapshot:
    id: str
    title: str
    created_at: str
    root: str
    vscode_workspace: str  # optional .code-workspace path
    note: str
    todos: List[str]
    tags: List[str]
    pinned: bool
    recent_files: List[str]
    processes: List[Dict[str, Any]]
    running_apps: List[Dict[str, Any]]


def migrate_snapshot(snap: Dict[str, Any]) -> Dict[str, Any]:
    """Backfill missing keys for older snapshots."""
    snap.setdefault("vscode_workspace", "")
    snap.setdefault("tags", [])
    snap.setdefault("pinned", False)
    snap.setdefault("running_apps", [])
    return snap


def now_iso() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


def gen_id() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def open_folder(path: Path) -> None:
    os.startfile(str(path))  # type: ignore


def open_terminal_at(path: Path) -> None:
    wt = shutil.which("wt")
    if wt:
        subprocess.Popen([wt, "-d", str(path)], shell=False)
        return
    subprocess.Popen(["cmd.exe", "/K", f"cd /d {path}"], shell=False)


def open_vscode_at(target: Path) -> bool:
    code = shutil.which("code")
    if not code:
        return False
    subprocess.Popen([code, str(target)], shell=False)
    return True


def git_title_suggestion(root: Path) -> Optional[str]:
    git = shutil.which("git")
    if not git:
        return None
    if not (root / ".git").exists():
        return None
    try:
        branch = subprocess.check_output([git, "-C", str(root), "rev-parse", "--abbrev-ref", "HEAD"], text=True).strip()
        subj = subprocess.check_output([git, "-C", str(root), "log", "-1", "--pretty=%s"], text=True).strip()
        return f"{root.name} [{branch}] - {subj}"
    except Exception:
        return None


def git_state(root: Path) -> Optional[Tuple[str, str]]:
    git = shutil.which("git")
    if not git:
        return None
    if not (root / ".git").exists():
        return None
    try:
        branch = subprocess.check_output([git, "-C", str(root), "rev-parse", "--abbrev-ref", "HEAD"], text=True).strip()
        sha = subprocess.check_output([git, "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
        return branch, sha
    except Exception:
        return None


# -------- Global hotkey (RegisterHotKey) --------
user32 = ctypes.windll.user32
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
WM_HOTKEY = 0x0312
VK_MAP = {chr(i): i for i in range(0x41, 0x5B)}


class HotkeyFilter(QtCore.QAbstractNativeEventFilter):
    hotkeyPressed = QtCore.Signal()

    def __init__(self, hotkey_id: int):
        super().__init__()
        self.hotkey_id = hotkey_id

    def nativeEventFilter(self, eventType, message):
        if eventType != "windows_generic_MSG":
            return False, 0
        msg = ctypes.wintypes.MSG.from_address(int(message))
        if msg.message == WM_HOTKEY and msg.wParam == self.hotkey_id:
            self.hotkeyPressed.emit()
            return True, 0
        return False, 0


def register_hotkey(hotkey_id: int, ctrl: bool, alt: bool, shift: bool, vk_letter: str) -> bool:
    mods = 0
    if ctrl:
        mods |= MOD_CONTROL
    if alt:
        mods |= MOD_ALT
    if shift:
        mods |= MOD_SHIFT
    vk = VK_MAP.get(vk_letter.upper(), VK_MAP["S"])
    return bool(user32.RegisterHotKey(None, hotkey_id, mods, vk))


def unregister_hotkey(hotkey_id: int) -> None:
    try:
        user32.UnregisterHotKey(None, hotkey_id)
    except Exception:
        pass


# -------- UI styling --------

def set_pretty_style(app: QtWidgets.QApplication) -> None:
    app.setStyle("Fusion")
    palette = QtGui.QPalette()
    palette.setColor(QtGui.QPalette.Window, QtGui.QColor(18, 18, 20))
    palette.setColor(QtGui.QPalette.WindowText, QtGui.QColor(235, 235, 235))
    palette.setColor(QtGui.QPalette.Base, QtGui.QColor(24, 24, 26))
    palette.setColor(QtGui.QPalette.AlternateBase, QtGui.QColor(30, 30, 34))
    palette.setColor(QtGui.QPalette.Text, QtGui.QColor(235, 235, 235))
    palette.setColor(QtGui.QPalette.Button, QtGui.QColor(34, 34, 38))
    palette.setColor(QtGui.QPalette.ButtonText, QtGui.QColor(235, 235, 235))
    palette.setColor(QtGui.QPalette.Highlight, QtGui.QColor(90, 120, 255))
    palette.setColor(QtGui.QPalette.HighlightedText, QtGui.QColor(255, 255, 255))
    app.setPalette(palette)
    app.setFont(QtGui.QFont("Segoe UI", 10))


APP_QSS = """
QMainWindow { background: #121214; }
QLineEdit, QTextEdit, QListWidget {
    background: #18181a;
    border: 1px solid #2a2a2f;
    border-radius: 10px;
    padding: 8px;
}
QListWidget::item { padding: 10px; border-radius: 10px; }
QListWidget::item:selected { background: rgba(90,120,255,0.25); }
QPushButton {
    background: #222226;
    border: 1px solid #2a2a2f;
    border-radius: 12px;
    padding: 10px 12px;
}
QPushButton:hover { border-color: rgba(90,120,255,0.7); }
QPushButton:pressed { background: #1c1c20; }
QToolButton {
    background: #222226;
    border: 1px solid #2a2a2f;
    border-radius: 12px;
    padding: 8px 10px;
}
QCheckBox { spacing: 8px; }
QGroupBox {
    border: 1px solid #2a2a2f;
    border-radius: 14px;
    margin-top: 12px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 6px;
}
QLabel#TitleLabel { font-size: 16px; font-weight: 700; }
QLabel#HintLabel { color: #b8b8c0; }
"""


class SnapshotDialog(QtWidgets.QDialog):
    def __init__(self, parent: QtWidgets.QWidget, default_root: str, available_tags: List[str]):
        super().__init__(parent)
        self.setWindowTitle("New Snapshot")
        self.setModal(True)
        self.setMinimumWidth(580)

        self.root_edit = QtWidgets.QLineEdit(default_root)
        self.title_edit = QtWidgets.QLineEdit("")
        self.note_edit = QtWidgets.QTextEdit("")

        # Optional VSCode workspace (.code-workspace)
        self.workspace_edit = QtWidgets.QLineEdit("")
        self.workspace_edit.setPlaceholderText("선택: .code-workspace 파일 (VSCode 복원 시 사용)")
        ws_btn = QtWidgets.QToolButton()
        ws_btn.setText("워크스페이스 선택")
        ws_btn.clicked.connect(self.pick_workspace)

        ws_row = QtWidgets.QHBoxLayout()
        ws_row.addWidget(self.workspace_edit, 1)
        ws_row.addWidget(ws_btn)

        # Tags
        self.tags_list = QtWidgets.QListWidget()
        self.tags_list.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)
        for t in available_tags:
            it = QtWidgets.QListWidgetItem(t)
            it.setFlags(it.flags() | QtCore.Qt.ItemIsUserCheckable)
            it.setCheckState(QtCore.Qt.Unchecked)
            self.tags_list.addItem(it)
        self.custom_tag = QtWidgets.QLineEdit("")
        self.custom_tag.setPlaceholderText("추가 태그 (엔터로 추가)")
        self.custom_tag.returnPressed.connect(self.add_custom_tag)
        self.todo1 = QtWidgets.QLineEdit("")
        self.todo2 = QtWidgets.QLineEdit("")
        self.todo3 = QtWidgets.QLineEdit("")
        for t in (self.todo1, self.todo2, self.todo3):
            t.setPlaceholderText("필수 TODO")
        self.title_edit.setPlaceholderText("제목 (비워도 자동 생성)")
        self.note_edit.setPlaceholderText("메모 (선택)")

        pick_btn = QtWidgets.QToolButton()
        pick_btn.setText("폴더 선택")
        pick_btn.clicked.connect(self.pick_folder)

        suggest_btn = QtWidgets.QToolButton()
        suggest_btn.setText("제목 추천")
        suggest_btn.clicked.connect(self.suggest_title)

        root_row = QtWidgets.QHBoxLayout()
        root_row.addWidget(self.root_edit, 1)
        root_row.addWidget(pick_btn)

        title_row = QtWidgets.QHBoxLayout()
        title_row.addWidget(self.title_edit, 1)
        title_row.addWidget(suggest_btn)

        form = QtWidgets.QFormLayout()
        form.addRow("Root", root_row)
        form.addRow("Title", title_row)
        form.addRow("Workspace", ws_row)
        form.addRow("Note", self.note_edit)

        tags_box = QtWidgets.QGroupBox("Tags (optional)")
        tags_layout = QtWidgets.QVBoxLayout(tags_box)
        tags_layout.addWidget(self.tags_list)
        tags_layout.addWidget(self.custom_tag)

        todo_box = QtWidgets.QGroupBox("Next actions (3 required)")
        todo_layout = QtWidgets.QVBoxLayout(todo_box)
        todo_layout.addWidget(self.todo1)
        todo_layout.addWidget(self.todo2)
        todo_layout.addWidget(self.todo3)

        self.err = QtWidgets.QLabel("")
        self.err.setStyleSheet("color: #ff6b6b;")

        btn_save = QtWidgets.QPushButton("Save Snapshot")
        btn_cancel = QtWidgets.QPushButton("Cancel")
        btn_save.clicked.connect(self.validate_and_accept)
        btn_cancel.clicked.connect(self.reject)

        btn_row = QtWidgets.QHBoxLayout()
        btn_row.addStretch(1)
        btn_row.addWidget(btn_cancel)
        btn_row.addWidget(btn_save)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(tags_box)
        layout.addWidget(todo_box)
        layout.addWidget(self.err)
        layout.addLayout(btn_row)

    def pick_folder(self):
        path = QtWidgets.QFileDialog.getExistingDirectory(self, "Select folder", self.root_edit.text() or str(Path.home()))
        if path:
            self.root_edit.setText(path)

    def pick_workspace(self):
        start = self.root_edit.text().strip() or str(Path.home())
        f, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Select VSCode workspace",
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
        todos = [self.todo1.text().strip(), self.todo2.text().strip(), self.todo3.text().strip()]
        if not root or not Path(root).exists():
            self.err.setText("Root 폴더가 유효하지 않습니다.")
            return
        if any(not t for t in todos):
            self.err.setText("TODO 3개를 모두 입력해야 저장됩니다.")
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
            sug = git_title_suggestion(Path(root))
            title = sug or f"{Path(root).name} - {datetime.now().strftime('%m/%d %H:%M')}"
        return {"root": root, "title": title, "workspace": workspace, "note": note, "todos": todos, "tags": tags}


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
        self.setWindowTitle("Restore preview")
        self.setModal(True)
        self.setMinimumWidth(660)

        title = QtWidgets.QLabel(snap.get("title", "Snapshot"))
        title.setObjectName("TitleLabel")

        hint = QtWidgets.QLabel("아래 항목이 실행됩니다. 확인 후 Restore를 누르세요.")
        hint.setObjectName("HintLabel")

        self.cb_folder = QtWidgets.QCheckBox("Open folder")
        self.cb_terminal = QtWidgets.QCheckBox("Open terminal (cd root)")
        self.cb_vscode = QtWidgets.QCheckBox("Open VSCode at root")
        self.cb_running_apps = QtWidgets.QCheckBox("Open running apps (taskbar)")
        self.cb_folder.setChecked(open_folder)
        self.cb_terminal.setChecked(open_terminal)
        self.cb_vscode.setChecked(open_vscode)
        self.cb_running_apps.setChecked(open_running_apps)

        root = snap.get("root", "")
        note = snap.get("note", "")
        todos = snap.get("todos", [])
        recent = snap.get("recent_files", [])
        running_apps = snap.get("running_apps", [])
        self.apps_list = QtWidgets.QListWidget()
        self.apps_list.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)
        for app in running_apps:
            label = f"{app.get('name','')}  {app.get('exe','')}"
            item = QtWidgets.QListWidgetItem(label)
            item.setFlags(item.flags() | QtCore.Qt.ItemIsUserCheckable)
            item.setCheckState(QtCore.Qt.Checked if open_running_apps else QtCore.Qt.Unchecked)
            item.setData(QtCore.Qt.UserRole, app)
            self.apps_list.addItem(item)

        info = QtWidgets.QTextEdit()
        info.setReadOnly(True)
        info.setText(
            f"Root:\n  {root}\n\n"
            f"Note:\n  {note or '(none)'}\n\n"
            f"TODOs:\n  - {todos[0] if len(todos)>0 else ''}\n  - {todos[1] if len(todos)>1 else ''}\n  - {todos[2] if len(todos)>2 else ''}\n\n"
            f"Recent files (top {min(len(recent), 10)} shown):\n" +
            "".join([f"  - {p}\n" for p in recent[:10]]) +
            f"\nRunning apps (top {min(len(running_apps), 8)} shown):\n" +
            "".join([f"  - {p.get('name','')}   {p.get('exe','')}\n" for p in running_apps[:8]])
        )

        btn_restore = QtWidgets.QPushButton("Restore")
        btn_cancel = QtWidgets.QPushButton("Cancel")
        btn_restore.clicked.connect(self.accept)
        btn_cancel.clicked.connect(self.reject)

        btn_row = QtWidgets.QHBoxLayout()
        btn_row.addStretch(1)
        btn_row.addWidget(btn_cancel)
        btn_row.addWidget(btn_restore)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(title)
        layout.addWidget(hint)
        layout.addSpacing(6)
        layout.addWidget(self.cb_folder)
        layout.addWidget(self.cb_terminal)
        layout.addWidget(self.cb_vscode)
        layout.addWidget(self.cb_running_apps)
        if running_apps:
            layout.addWidget(QtWidgets.QLabel("Running apps to restore"))
            layout.addWidget(self.apps_list, 1)
        layout.addSpacing(6)
        layout.addWidget(info, 1)
        layout.addLayout(btn_row)

    def choices(self) -> Dict[str, bool]:
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


class SettingsDialog(QtWidgets.QDialog):
    """Settings UI:
    - Hotkey (Ctrl/Alt/Shift/Key, enable)
    - Restore options (folder/terminal/VSCode)
    - Recent files limit
    - Restore preview default toggle
    - Tags management
    """

    def __init__(self, parent: QtWidgets.QWidget, settings: Dict[str, Any], *, index_path: Path, snaps_dir: Path):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setModal(True)
        self.setMinimumSize(720, 540)

        self._settings = settings
        self._index_path = index_path
        self._snaps_dir = snaps_dir
        self._imported_payload = None
        self._import_apply_now = False

        header = QtWidgets.QLabel("Settings")
        header.setObjectName("TitleLabel")
        sub = QtWidgets.QLabel("단축키, 복원 동작, 태그를 한 곳에서 관리합니다. 내보내기/가져오기도 지원합니다.")
        sub.setObjectName("HintLabel")

        tabs = QtWidgets.QTabWidget()

        # --- Hotkey tab ---
        hk = settings.get("hotkey", {})
        self.hk_enabled = QtWidgets.QCheckBox("Enable global hotkey")
        self.hk_enabled.setChecked(bool(hk.get("enabled", True)))
        self.hk_ctrl = QtWidgets.QCheckBox("Ctrl")
        self.hk_alt = QtWidgets.QCheckBox("Alt")
        self.hk_shift = QtWidgets.QCheckBox("Shift")
        self.hk_ctrl.setChecked(bool(hk.get("ctrl", True)))
        self.hk_alt.setChecked(bool(hk.get("alt", True)))
        self.hk_shift.setChecked(bool(hk.get("shift", False)))
        self.hk_key = QtWidgets.QComboBox()
        for c in [chr(i) for i in range(ord("A"), ord("Z") + 1)]:
            self.hk_key.addItem(c)
        vk = str(hk.get("vk", "S")).upper()
        idx = self.hk_key.findText(vk)
        if idx >= 0:
            self.hk_key.setCurrentIndex(idx)

        hk_row = QtWidgets.QHBoxLayout()
        hk_row.addWidget(self.hk_ctrl)
        hk_row.addWidget(self.hk_alt)
        hk_row.addWidget(self.hk_shift)
        hk_row.addStretch(1)
        hk_row.addWidget(QtWidgets.QLabel("Key"))
        hk_row.addWidget(self.hk_key)

        hotkey_page = QtWidgets.QWidget()
        hk_box = QtWidgets.QGroupBox("Global hotkey")
        hk_box_l = QtWidgets.QVBoxLayout(hk_box)
        hk_box_l.addWidget(self.hk_enabled)
        hk_box_l.addLayout(hk_row)
        hk_hint = QtWidgets.QLabel(
            "추천: <b>Ctrl+Alt+S</b> (Quick Snapshot) — 언제든지 작업 상태를 저장할 수 있어요."
        )
        hk_hint.setObjectName("HintLabel")
        hk_layout = QtWidgets.QVBoxLayout(hotkey_page)
        hk_layout.addWidget(hk_box)
        hk_layout.addWidget(hk_hint)
        hk_layout.addStretch(1)

        # --- Restore tab ---
        restore = settings.get("restore", {})
        self.rs_folder = QtWidgets.QCheckBox("Open folder")
        self.rs_terminal = QtWidgets.QCheckBox("Open terminal")
        self.rs_vscode = QtWidgets.QCheckBox("Open VSCode")
        self.rs_running_apps = QtWidgets.QCheckBox("Open running apps (taskbar)")
        self.rs_checklist = QtWidgets.QCheckBox("Show post-restore checklist")
        self.rs_folder.setChecked(bool(restore.get("open_folder", True)))
        self.rs_terminal.setChecked(bool(restore.get("open_terminal", True)))
        self.rs_vscode.setChecked(bool(restore.get("open_vscode", True)))
        self.rs_running_apps.setChecked(bool(restore.get("open_running_apps", True)))
        self.rs_checklist.setChecked(bool(restore.get("show_post_restore_checklist", True)))

        self.preview_default = QtWidgets.QCheckBox("Show restore preview by default")
        self.preview_default.setChecked(bool(settings.get("restore_preview_default", True)))

        restore_page = QtWidgets.QWidget()
        restore_box = QtWidgets.QGroupBox("Restore defaults")
        restore_l = QtWidgets.QVBoxLayout(restore_box)
        restore_l.addWidget(self.rs_folder)
        restore_l.addWidget(self.rs_terminal)
        restore_l.addWidget(self.rs_vscode)
        restore_l.addWidget(self.rs_running_apps)
        restore_l.addWidget(self.rs_checklist)
        restore_l.addSpacing(8)
        restore_l.addWidget(self.preview_default)
        restore_hint = QtWidgets.QLabel(
            "복원은 <b>미리보기</b>에서 체크 후 실행됩니다. 필요 없으면 미리보기 기본값을 끌 수 있어요."
        )
        restore_hint.setObjectName("HintLabel")
        restore_layout = QtWidgets.QVBoxLayout(restore_page)
        restore_layout.addWidget(restore_box)
        restore_layout.addWidget(restore_hint)
        restore_layout.addStretch(1)

        # --- General tab ---
        general_page = QtWidgets.QWidget()
        self.recent_spin = QtWidgets.QSpinBox()
        self.recent_spin.setRange(0, 300)
        self.recent_spin.setValue(int(settings.get("recent_files_limit", 30)))
        self.recent_spin.setSuffix(" files")
        self.scan_limit_spin = QtWidgets.QSpinBox()
        self.scan_limit_spin.setRange(100, 200000)
        self.scan_limit_spin.setValue(int(settings.get("recent_files_scan_limit", 20000)))
        self.scan_limit_spin.setSuffix(" files")
        self.scan_seconds_spin = QtWidgets.QDoubleSpinBox()
        self.scan_seconds_spin.setRange(0.1, 10.0)
        self.scan_seconds_spin.setSingleStep(0.5)
        self.scan_seconds_spin.setValue(float(settings.get("recent_files_scan_seconds", 2.0)))
        self.scan_seconds_spin.setSuffix(" sec")
        self.auto_snapshot_minutes = QtWidgets.QSpinBox()
        self.auto_snapshot_minutes.setRange(0, 1440)
        self.auto_snapshot_minutes.setSuffix(" min")
        self.auto_snapshot_minutes.setValue(int(settings.get("auto_snapshot_minutes", 0)))
        self.auto_snapshot_on_git = QtWidgets.QCheckBox("Auto snapshot on git change")
        self.auto_snapshot_on_git.setChecked(bool(settings.get("auto_snapshot_on_git_change", False)))
        capture = settings.get("capture", {})
        self.capture_recent = QtWidgets.QCheckBox("Capture recent files")
        self.capture_processes = QtWidgets.QCheckBox("Capture running processes")
        self.capture_running_apps = QtWidgets.QCheckBox("Capture running apps (taskbar)")
        self.capture_recent.setToolTip("최근 변경 파일 경로를 스냅샷에 저장합니다.")
        self.capture_processes.setToolTip("필터된 프로세스 목록을 스냅샷에 저장합니다.")
        self.capture_running_apps.setToolTip("작업표시줄에 보이는 앱(최상위 창)을 스냅샷에 저장합니다.")
        self.capture_recent.setChecked(bool(capture.get("recent_files", True)))
        self.capture_processes.setChecked(bool(capture.get("processes", True)))
        self.capture_running_apps.setChecked(bool(capture.get("running_apps", True)))
        self.exclude_dirs = QtWidgets.QLineEdit()
        self.exclude_dirs.setPlaceholderText("Excluded folders (comma-separated)")
        self.exclude_dirs.setText(", ".join(settings.get("recent_files_exclude", [])))
        self.exclude_dirs.setToolTip("예: .git, node_modules, venv, **/dist/** 같은 패턴을 쉼표로 구분해 입력")
        rf_row = QtWidgets.QHBoxLayout()
        rf_row.addWidget(QtWidgets.QLabel("Recent files to capture"))
        rf_row.addStretch(1)
        rf_row.addWidget(self.recent_spin)
        scan_row = QtWidgets.QHBoxLayout()
        scan_row.addWidget(QtWidgets.QLabel("Scan limits"))
        scan_row.addStretch(1)
        scan_row.addWidget(self.scan_limit_spin)
        scan_row.addWidget(self.scan_seconds_spin)
        auto_row = QtWidgets.QHBoxLayout()
        auto_row.addWidget(QtWidgets.QLabel("Auto snapshot interval"))
        auto_row.addStretch(1)
        auto_row.addWidget(self.auto_snapshot_minutes)
        capture_row = QtWidgets.QVBoxLayout()
        capture_row.addWidget(self.capture_recent)
        capture_row.addWidget(self.capture_processes)
        capture_row.addWidget(self.capture_running_apps)
        general_hint = QtWidgets.QLabel(
            "최근 파일 목록은 ‘어디까지 했지?’를 빠르게 떠올리게 해줍니다. 너무 크면 속도가 느려질 수 있어요."
        )
        general_hint.setObjectName("HintLabel")
        general_layout = QtWidgets.QVBoxLayout(general_page)
        general_layout.addLayout(rf_row)
        general_layout.addLayout(capture_row)
        general_layout.addLayout(scan_row)
        general_layout.addLayout(auto_row)
        general_layout.addWidget(self.auto_snapshot_on_git)
        general_layout.addWidget(QtWidgets.QLabel("Exclude folders for recent file scan"))
        general_layout.addWidget(self.exclude_dirs)
        privacy_hint = QtWidgets.QLabel(
            "스냅샷에는 파일 경로, 프로세스, 실행 앱 정보가 저장될 수 있습니다. 필요한 항목만 캡처하세요."
        )
        privacy_hint.setObjectName("HintLabel")
        general_layout.addWidget(general_hint)
        general_layout.addWidget(privacy_hint)
        general_layout.addStretch(1)

        # --- Tags tab ---
        tags_page = QtWidgets.QWidget()
        self.tags_list = QtWidgets.QListWidget()
        self.tags_list.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        for t in (settings.get("tags") or DEFAULT_TAGS):
            self.tags_list.addItem(t)
        self.tag_input = QtWidgets.QLineEdit()
        self.tag_input.setPlaceholderText("새 태그 입력 후 Add")
        btn_add = QtWidgets.QPushButton("Add")
        btn_remove = QtWidgets.QPushButton("Remove")
        btn_add.clicked.connect(self.add_tag)
        btn_remove.clicked.connect(self.remove_tag)

        tag_row = QtWidgets.QHBoxLayout()
        tag_row.addWidget(self.tag_input, 1)
        tag_row.addWidget(btn_add)
        tag_row.addWidget(btn_remove)

        tags_box = QtWidgets.QGroupBox("Tags")
        tags_l = QtWidgets.QVBoxLayout(tags_box)
        tags_l.addWidget(self.tags_list)
        tags_l.addLayout(tag_row)
        tags_hint = QtWidgets.QLabel(
            "태그는 ‘업무/개인/부동산/정산’처럼 컨텍스트를 나누는 핵심 기능입니다."
        )
        tags_hint.setObjectName("HintLabel")
        tags_layout = QtWidgets.QVBoxLayout(tags_page)
        tags_layout.addWidget(tags_box)
        tags_layout.addWidget(tags_hint)
        tags_layout.addStretch(1)        # --- Backup tab (export/import) ---
        backup_page = QtWidgets.QWidget()
        b_title = QtWidgets.QLabel("Backup / Restore")
        b_title.setObjectName("TitleLabel")
        b_hint = QtWidgets.QLabel("설정/태그/단축키는 물론, 원하면 스냅샷(핀/태그 포함)까지 한 파일로 백업할 수 있어요.\n가져오기는 '바로 적용' 또는 '대화상자에만 반영'을 선택할 수 있습니다.")
        b_hint.setObjectName("HintLabel")

        # export options
        self.exp_settings = QtWidgets.QCheckBox("Include settings")
        self.exp_settings.setChecked(True)
        self.exp_settings.setEnabled(False)
        self.exp_index = QtWidgets.QCheckBox("Include index (list/pin/tag metadata)")
        self.exp_index.setChecked(True)
        self.exp_snaps = QtWidgets.QCheckBox("Include snapshots (full JSON)")
        self.exp_snaps.setChecked(True)

        exp_box = QtWidgets.QGroupBox("Export options")
        exp_l = QtWidgets.QVBoxLayout(exp_box)
        exp_l.addWidget(self.exp_settings)
        exp_l.addWidget(self.exp_index)
        exp_l.addWidget(self.exp_snaps)

        self.btn_export = QtWidgets.QPushButton("Export backup...")
        self.btn_import = QtWidgets.QPushButton("Import backup...")
        self.btn_reset = QtWidgets.QPushButton("Reset to defaults")
        self.btn_export.clicked.connect(self.export_settings)
        self.btn_import.clicked.connect(self.import_settings)
        self.btn_reset.clicked.connect(self.reset_defaults)

        b_row = QtWidgets.QHBoxLayout()
        b_row.addWidget(self.btn_export)
        b_row.addWidget(self.btn_import)
        b_row.addStretch(1)
        b_row.addWidget(self.btn_reset)

        self.b_msg = QtWidgets.QLabel("")
        self.b_msg.setObjectName("HintLabel")

        b_layout = QtWidgets.QVBoxLayout(backup_page)
        b_layout.addWidget(b_title)
        b_layout.addWidget(b_hint)
        b_layout.addSpacing(10)
        b_layout.addWidget(exp_box)
        b_layout.addSpacing(6)
        b_layout.addLayout(b_row)
        b_layout.addSpacing(8)
        b_layout.addWidget(self.b_msg)
        b_layout.addStretch(1)

        tabs.addTab(general_page, "General")
        tabs.addTab(restore_page, "Restore")
        tabs.addTab(hotkey_page, "Hotkey")
        tabs.addTab(tags_page, "Tags")
        tabs.addTab(backup_page, "Backup")

        # Buttons
        self.err = QtWidgets.QLabel("")
        self.err.setStyleSheet("color: #ff6b6b;")
        btn_ok = QtWidgets.QPushButton("Save")
        btn_cancel = QtWidgets.QPushButton("Cancel")
        btn_ok.clicked.connect(self.validate_and_accept)
        btn_cancel.clicked.connect(self.reject)
        btn_row = QtWidgets.QHBoxLayout()
        btn_row.addStretch(1)
        btn_row.addWidget(btn_cancel)
        btn_row.addWidget(btn_ok)

        layout = QtWidgets.QVBoxLayout(self)
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
            self.b_msg.setText(f"Exported: {path}")
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
            msg.setWindowTitle("Import")
            msg.setText("백업을 불러왔습니다. 지금 바로 적용할까요?")
            msg.setInformativeText("Apply now: 저장 후 즉시 UI/단축키/태그에 반영합니다.\nKeep: 설정 창에서 검토 후 Save로 적용합니다.")
            btn_apply = msg.addButton("Apply now", QtWidgets.QMessageBox.AcceptRole)
            btn_keep = msg.addButton("Keep in dialog", QtWidgets.QMessageBox.RejectRole)
            msg.exec()
            self._import_apply_now = (msg.clickedButton() == btn_apply)

            if self._import_apply_now:
                parent = self.parent()
                if hasattr(parent, "apply_imported_backup"):
                    parent.apply_imported_backup(payload)  # type: ignore[attr-defined]
                self.b_msg.setText(f"Imported+Applied: {path}")
            else:
                self.b_msg.setText(f"Imported into dialog: {path}")
        except Exception as e:
            log_exc("import backup", e)
            QtWidgets.QMessageBox.warning(self, "Import failed", str(e))

    def reset_defaults(self):
        new_settings = migrate_settings({"tags": DEFAULT_TAGS})
        # Keep onboarding shown; reset is for behavior not education
        new_settings["onboarding_shown"] = True
        self.apply_settings_to_controls(new_settings)
        self.b_msg.setText("Reset to defaults.")

    def apply_settings_to_controls(self, settings: Dict[str, Any]) -> None:
        """Apply a settings dict to UI controls (does not save to disk here)."""
        settings = migrate_settings(settings)
        self._settings = settings
        self._index_path = index_path
        self._snaps_dir = snaps_dir
        self._imported_payload = None
        self._import_apply_now = False

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
        self.rs_running_apps.setChecked(bool(restore.get("open_running_apps", True)))
        self.rs_checklist.setChecked(bool(restore.get("show_post_restore_checklist", True)))
        self.preview_default.setChecked(bool(settings.get("restore_preview_default", True)))

        self.recent_spin.setValue(int(settings.get("recent_files_limit", 30)))
        self.scan_limit_spin.setValue(int(settings.get("recent_files_scan_limit", 20000)))
        self.scan_seconds_spin.setValue(float(settings.get("recent_files_scan_seconds", 2.0)))
        self.auto_snapshot_minutes.setValue(int(settings.get("auto_snapshot_minutes", 0)))
        self.auto_snapshot_on_git.setChecked(bool(settings.get("auto_snapshot_on_git_change", False)))
        capture = settings.get("capture", {})
        self.capture_recent.setChecked(bool(capture.get("recent_files", True)))
        self.capture_processes.setChecked(bool(capture.get("processes", True)))
        self.capture_running_apps.setChecked(bool(capture.get("running_apps", True)))
        self.exclude_dirs.setText(", ".join(settings.get("recent_files_exclude", [])))

        self.tags_list.clear()
        for t in (settings.get("tags") or DEFAULT_TAGS):
            self.tags_list.addItem(t)

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

    def imported_payload(self):
        return self._imported_payload

    def import_apply_now(self) -> bool:
        return bool(self._import_apply_now)

    def validate_and_accept(self):
        # Ensure at least one modifier is chosen when enabled
        if self.hk_enabled.isChecked():
            if not (self.hk_ctrl.isChecked() or self.hk_alt.isChecked() or self.hk_shift.isChecked()):
                self.err.setText("Hotkey를 켜려면 Ctrl/Alt/Shift 중 최소 1개를 선택하세요.")
                return
        self.accept()

    def values(self) -> Dict[str, Any]:
        tags: List[str] = []
        for i in range(self.tags_list.count()):
            t = self.tags_list.item(i).text().strip()
            if t:
                tags.append(t)
        return {
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
            "recent_files_scan_limit": int(self.scan_limit_spin.value()),
            "recent_files_scan_seconds": float(self.scan_seconds_spin.value()),
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
                "show_post_restore_checklist": bool(self.rs_checklist.isChecked()),
            },
        }


class OnboardingDialog(QtWidgets.QDialog):
    """Friendly first-run onboarding.

    A lightweight, in-app guide so users can learn the core workflow
    without opening external docs.
    """

    def __init__(self, parent: QtWidgets.QWidget):
        super().__init__(parent)
        self.setWindowTitle("Welcome to CtxSnap")
        self.setModal(True)
        self.setMinimumSize(720, 520)

        header = QtWidgets.QLabel("Welcome to CtxSnap")
        header.setObjectName("TitleLabel")
        sub = QtWidgets.QLabel("작업 컨텍스트를 ‘저장하고’, 다시 ‘복원’하는 가장 빠른 방법")
        sub.setObjectName("HintLabel")

        self.stack = QtWidgets.QStackedWidget()
        self.pages: List[QtWidgets.QWidget] = []
        self._build_pages()

        self.btn_back = QtWidgets.QPushButton("Back")
        self.btn_next = QtWidgets.QPushButton("Next")
        self.btn_finish = QtWidgets.QPushButton("Finish")
        self.btn_back.clicked.connect(self._back)
        self.btn_next.clicked.connect(self._next)
        self.btn_finish.clicked.connect(self.accept)

        btn_row = QtWidgets.QHBoxLayout()
        btn_row.addWidget(self.btn_back)
        btn_row.addStretch(1)
        btn_row.addWidget(self.btn_next)
        btn_row.addWidget(self.btn_finish)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(header)
        layout.addWidget(sub)
        layout.addSpacing(10)
        layout.addWidget(self.stack, 1)
        layout.addLayout(btn_row)

        self._sync_buttons()

    def _mk_page(self, title: str, body_html: str) -> QtWidgets.QWidget:
        w = QtWidgets.QWidget()
        t = QtWidgets.QLabel(title)
        t.setObjectName("TitleLabel")
        b = QtWidgets.QTextBrowser()
        b.setOpenExternalLinks(False)
        b.setHtml(body_html)
        b.setStyleSheet("QTextBrowser { background: #18181a; border: 1px solid #2a2a2f; border-radius: 12px; padding: 10px; }")
        lay = QtWidgets.QVBoxLayout(w)
        lay.addWidget(t)
        lay.addWidget(b, 1)
        return w

    def _build_pages(self) -> None:
        p1 = self._mk_page(
            "1) 저장 (Snapshot)",
            """
            <p><b>Snapshot</b>은 ‘지금 작업 상태’를 저장합니다.</p>
            <ul>
              <li><b>New Snapshot</b>: 제목/메모/태그/TODO를 작성하고 저장</li>
              <li><b>Quick Snapshot</b>: 빠르게 저장 (기본 단축키: <b>Ctrl+Alt+S</b>)</li>
            </ul>
            <p>저장 시 <b>TODO 3개</b>를 필수로 입력하면, 복원했을 때 “뭘 해야 하지?”가 사라져요.</p>
            """,
        )
        p2 = self._mk_page(
            "2) 복원 (Restore)",
            """
            <p><b>Restore</b>는 저장된 컨텍스트를 다시 열어줍니다.</p>
            <ul>
              <li>기본 옵션: 폴더 / 터미널 / VSCode</li>
              <li>복원은 기본적으로 <b>미리보기(Preview)</b>에서 체크 후 실행됩니다.</li>
            </ul>
            <p>VSCode는 <code>code</code> 명령이 PATH에 있어야 자동으로 열 수 있어요.</p>
            """,
        )
        p3 = self._mk_page(
            "3) 태그 & 핀 (Tags & Pin)",
            """
            <p>스냅샷을 <b>업무/개인/부동산/정산</b>처럼 태그로 분류해두면 검색이 훨씬 빨라집니다.</p>
            <ul>
              <li><b>Tag filter</b>로 원하는 컨텍스트만 보기</li>
              <li><b>Pin</b>으로 중요한 스냅샷을 항상 위로 고정</li>
            </ul>
            """,
        )
        p4 = self._mk_page(
            "4) 설정 & 백업", 
            """
            <p><b>Settings</b>에서 아래를 조정할 수 있어요.</p>
            <ul>
              <li>전역 단축키 변경 (Ctrl/Alt/Shift/Key)</li>
              <li>복원 기본 옵션 (폴더/터미널/VSCode)</li>
              <li>최근 파일 개수</li>
              <li>Preview 기본값</li>
              <li><b>설정 내보내기/가져오기</b> (PC 교체/재설치 대비)</li>
            </ul>
            <p>트레이(작업표시줄)에서도 Quick Snapshot / Restore Last가 가능합니다.</p>
            """,
        )
        for p in [p1, p2, p3, p4]:
            self.pages.append(p)
            self.stack.addWidget(p)

    def _sync_buttons(self) -> None:
        i = self.stack.currentIndex()
        self.btn_back.setEnabled(i > 0)
        last = (i == self.stack.count() - 1)
        self.btn_next.setEnabled(not last)
        self.btn_finish.setEnabled(last)

    def _next(self) -> None:
        i = self.stack.currentIndex()
        if i < self.stack.count() - 1:
            self.stack.setCurrentIndex(i + 1)
        self._sync_buttons()

    def _back(self) -> None:
        i = self.stack.currentIndex()
        if i > 0:
            self.stack.setCurrentIndex(i - 1)
        self._sync_buttons()


class MainWindow(QtWidgets.QMainWindow):
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

        m_file = mb.addMenu("File")
        a_new = QtGui.QAction("New Snapshot…", self)
        a_new.triggered.connect(self.new_snapshot)
        a_quick = QtGui.QAction(f"Quick Snapshot ({self.hotkey_label()})", self)
        a_quick.triggered.connect(self.quick_snapshot)
        a_restore = QtGui.QAction("Restore", self)
        a_restore.triggered.connect(self.restore_selected)
        a_restore_last = QtGui.QAction("Restore Last", self)
        a_restore_last.triggered.connect(self.restore_last)
        a_open_folder = QtGui.QAction("Open App Folder", self)
        a_open_folder.triggered.connect(self.open_app_folder)
        a_quit = QtGui.QAction("Quit", self)
        a_quit.triggered.connect(QtWidgets.QApplication.quit)
        for a in [a_new, a_quick, None, a_restore, a_restore_last, None, a_open_folder, None, a_quit]:
            if a is None:
                m_file.addSeparator()
            else:
                m_file.addAction(a)

        m_tools = mb.addMenu("Tools")
        a_settings = QtGui.QAction("Settings…", self)
        a_settings.triggered.connect(self.open_settings)
        a_export_snap = QtGui.QAction("Export Selected Snapshot…", self)
        a_export_snap.triggered.connect(self.export_selected_snapshot)
        a_report = QtGui.QAction("Export Weekly Report…", self)
        a_report.triggered.connect(self.export_weekly_report)
        a_history = QtGui.QAction("Open Restore History", self)
        a_history.triggered.connect(self.open_restore_history)
        m_tools.addAction(a_settings)
        m_tools.addSeparator()
        m_tools.addAction(a_export_snap)
        m_tools.addAction(a_report)
        m_tools.addSeparator()
        m_tools.addAction(a_history)

        m_help = mb.addMenu("Help")
        a_onb = QtGui.QAction("Onboarding…", self)
        a_onb.triggered.connect(self.show_onboarding)
        a_about = QtGui.QAction("About", self)
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
            "About CtxSnap",
            "CtxSnap\n\n작업 컨텍스트 스냅샷 도구 (Windows)\n- Snapshot 저장/복원\n- 태그/핀 필터\n- 전역 단축키\n- 설정 내보내기/가져오기\n",
        )

    def open_app_folder(self) -> None:
        open_folder(app_dir())

    def __init__(self):
        super().__init__()
        self.setWindowTitle("CtxSnap — Work Context Snapshot (Windows)")
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
            if "vscode_workspace" not in it:
                it["vscode_workspace"] = ""
                changed = True
        if changed:
            save_json(self.index_path, self.index)

        central = QtWidgets.QWidget()
        self.setCentralWidget(central)

        self.search = QtWidgets.QLineEdit()
        self.search.setPlaceholderText("Search snapshots (title/root)...")
        self.search.textChanged.connect(self.refresh_list)

        self.selected_tags: set[str] = set()
        self.tag_filter_btn = QtWidgets.QToolButton()
        self.tag_filter_btn.setText("Tags")
        self.tag_filter_btn.setPopupMode(QtWidgets.QToolButton.InstantPopup)
        self._build_tag_menu()

        self.days_filter = QtWidgets.QComboBox()
        self.days_filter.addItems(["All time", "Last 1 day", "Last 3 days", "Last 7 days", "Last 30 days"])
        self.days_filter.currentIndexChanged.connect(self.refresh_list)

        self.sort_combo = QtWidgets.QComboBox()
        self.sort_combo.addItems(["Newest", "Oldest", "Pinned first", "Title"])
        self.sort_combo.currentIndexChanged.connect(self.refresh_list)

        self.pinned_only = QtWidgets.QCheckBox("Pinned only")
        self.pinned_only.stateChanged.connect(self.refresh_list)

        self.listw = QtWidgets.QListWidget()
        self.listw.currentRowChanged.connect(self.on_select)

        self.detail_title = QtWidgets.QLabel("No snapshot selected")
        self.detail_title.setObjectName("TitleLabel")
        self.detail_meta = QtWidgets.QLabel("")
        self.detail_meta.setObjectName("HintLabel")

        self.detail = QtWidgets.QTextEdit()
        self.detail.setReadOnly(True)

        btn_new = QtWidgets.QPushButton("New Snapshot")
        self.btn_quick = QtWidgets.QPushButton(f"Quick Snapshot ({self.hotkey_label()})")
        btn_settings = QtWidgets.QPushButton("Settings")
        btn_restore = QtWidgets.QPushButton("Restore")
        btn_pin = QtWidgets.QPushButton("Pin / Unpin")
        btn_restore_last = QtWidgets.QPushButton("Restore Last")
        btn_open_root = QtWidgets.QPushButton("Open Root Folder")
        btn_open_vscode = QtWidgets.QPushButton("Open in VSCode")
        btn_delete = QtWidgets.QPushButton("Delete")

        btn_new.clicked.connect(self.new_snapshot)
        self.btn_quick.clicked.connect(self.quick_snapshot)
        btn_settings.clicked.connect(self.open_settings)
        btn_restore.clicked.connect(self.restore_selected)
        btn_restore_last.clicked.connect(self.restore_last)
        btn_open_root.clicked.connect(self.open_selected_root)
        btn_open_vscode.clicked.connect(self.open_selected_vscode)
        btn_delete.clicked.connect(self.delete_selected)
        btn_pin.clicked.connect(self.toggle_pin)

        left = QtWidgets.QVBoxLayout()
        search_row = QtWidgets.QHBoxLayout()
        search_row.addWidget(self.search, 1)
        search_row.addWidget(self.tag_filter_btn)
        search_row.addWidget(self.days_filter)
        search_row.addWidget(self.sort_combo)
        search_row.addWidget(self.pinned_only)
        left.addLayout(search_row)
        left.addWidget(self.listw, 1)
        left_btns = QtWidgets.QHBoxLayout()
        left_btns.addWidget(btn_new)
        left_btns.addWidget(self.btn_quick)
        left_btns.addWidget(btn_settings)
        left.addLayout(left_btns)

        right = QtWidgets.QVBoxLayout()
        right.addWidget(self.detail_title)
        right.addWidget(self.detail_meta)
        right.addWidget(self.detail, 1)

        right_btns1 = QtWidgets.QHBoxLayout()
        right_btns1.addWidget(btn_open_root)
        right_btns1.addWidget(btn_open_vscode)
        right_btns1.addStretch(1)
        right.addLayout(right_btns1)

        right_btns2 = QtWidgets.QHBoxLayout()
        right_btns2.addStretch(1)
        right_btns2.addWidget(btn_pin)
        right_btns2.addWidget(btn_delete)
        right_btns2.addWidget(btn_restore_last)
        right_btns2.addWidget(btn_restore)
        right.addLayout(right_btns2)

        root_layout = QtWidgets.QHBoxLayout(central)
        left_wrap = QtWidgets.QWidget()
        left_wrap.setLayout(left)
        right_wrap = QtWidgets.QWidget()
        right_wrap.setLayout(right)
        root_layout.addWidget(left_wrap, 0)
        root_layout.addWidget(right_wrap, 1)

        self.refresh_list()
        if self.listw.count() > 0:
            self.listw.setCurrentRow(0)

        self.statusBar().showMessage(f"Storage: {app_dir()}")

        self.auto_timer = QtCore.QTimer(self)
        self.auto_timer.timeout.connect(self._auto_snapshot_prompt)
        self.git_timer = QtCore.QTimer(self)
        self.git_timer.setInterval(60_000)
        self.git_timer.timeout.connect(self._check_git_change)
        self._last_git_state = None
        self._update_auto_snapshot_timer()
        self.git_timer.start()

        # external hook (set by main) to re-apply hotkey settings
        self.on_settings_applied = None

    def _auto_snapshot_prompt(self) -> None:
        if int(self.settings.get("auto_snapshot_minutes", 0)) <= 0:
            return
        self.quick_snapshot()

    def _update_auto_snapshot_timer(self) -> None:
        minutes = int(self.settings.get("auto_snapshot_minutes", 0))
        if minutes <= 0:
            self.auto_timer.stop()
            return
        self.auto_timer.setInterval(minutes * 60_000)
        if not self.auto_timer.isActive():
            self.auto_timer.start()

    def _check_git_change(self) -> None:
        if not bool(self.settings.get("auto_snapshot_on_git_change", False)):
            return
        root = Path(self.settings.get("default_root", str(Path.home())))
        state = git_state(root)
        if not state:
            return
        if self._last_git_state and self._last_git_state != state:
            self.quick_snapshot()
        self._last_git_state = state

    def _build_tag_menu(self) -> None:
        menu = QtWidgets.QMenu(self)
        clear_action = QtGui.QAction("All tags", self)
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

    def _toggle_tag_filter(self) -> None:
        action = self.sender()
        if isinstance(action, QtGui.QAction):
            tag = action.text()
            if action.isChecked():
                self.selected_tags.add(tag)
            else:
                self.selected_tags.discard(tag)
        self.refresh_list()

    def _clear_tag_filter(self) -> None:
        self.selected_tags.clear()
        self._build_tag_menu()
        self.refresh_list()

    # ----- index helpers -----
    def refresh_list(self) -> None:
        query = self.search.text().strip().lower()
        pinned_only = bool(self.pinned_only.isChecked()) if hasattr(self, "pinned_only") else False

        self.listw.clear()
        items = list(self.index.get("snapshots", []))
        index_changed = False

        sort_mode = self.sort_combo.currentText() if hasattr(self, "sort_combo") else "Newest"
        if sort_mode == "Pinned first":
            items.sort(key=lambda x: (not bool(x.get("pinned", False)), x.get("created_at", "")), reverse=False)
        elif sort_mode == "Oldest":
            items.sort(key=lambda x: x.get("created_at", ""))
        elif sort_mode == "Title":
            items.sort(key=lambda x: (x.get("title", "").lower(), x.get("created_at", "")))
        else:
            items.sort(key=lambda x: x.get("created_at", ""), reverse=True)

        days_filter = self.days_filter.currentText() if hasattr(self, "days_filter") else "All time"
        now = datetime.now()
        day_cutoff = None
        if days_filter.startswith("Last"):
            try:
                days = int(days_filter.split()[1])
                day_cutoff = now - timedelta(days=days)
            except Exception:
                day_cutoff = None

        for it in items:
            tags = it.get("tags", []) or []
            if self.selected_tags and not self.selected_tags.intersection(tags):
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
                try:
                    created_at = datetime.strptime(it.get("created_at", ""), "%Y-%m-%dT%H:%M:%S")
                    if created_at < day_cutoff:
                        continue
                except Exception:
                    pass

            title = it.get("title", "")
            root = it.get("root", "")
            created = it.get("created_at", "")
            pin = "📌 " if bool(it.get("pinned", False)) else ""
            tag_badge = f"[{', '.join(tags)}] " if tags else ""
            item = QtWidgets.QListWidgetItem(f"{pin}{tag_badge}{title}\n{root}   •   {created}")
            item.setData(QtCore.Qt.UserRole, it.get("id"))
            self.listw.addItem(item)
        if index_changed:
            save_json(self.index_path, self.index)

    def selected_id(self) -> Optional[str]:
        it = self.listw.currentItem()
        if not it:
            return None
        return it.data(QtCore.Qt.UserRole)

    def snap_path(self, sid: str) -> Path:
        return self.snaps_dir / f"{sid}.json"

    def load_snapshot(self, sid: str) -> Optional[Dict[str, Any]]:
        p = self.snap_path(sid)
        if not p.exists():
            return None
        return migrate_snapshot(json.loads(p.read_text(encoding="utf-8")))

    def save_snapshot(self, snap: Snapshot) -> None:
        snap_path = self.snap_path(snap.id)
        snap_path.write_text(json.dumps(asdict(snap), ensure_ascii=False, indent=2), encoding="utf-8")
        snap_mtime = snapshot_mtime(snap_path)
        self.index["snapshots"].insert(0, {
            "id": snap.id,
            "title": snap.title,
            "created_at": snap.created_at,
            "root": snap.root,
            "vscode_workspace": snap.vscode_workspace,
            "tags": snap.tags,
            "pinned": snap.pinned,
            "search_blob": build_search_blob(asdict(snap)),
            "search_blob_mtime": snap_mtime,
        })
        save_json(self.index_path, self.index)
        self.settings["default_root"] = snap.root
        save_json(self.settings_path, self.settings)

    # ----- selection rendering -----
    def on_select(self, row: int) -> None:
        if row < 0:
            self.detail_title.setText("No snapshot selected")
            self.detail_meta.setText("")
            self.detail.setText("")
            return
        sid = self.selected_id()
        if not sid:
            return
        snap = self.load_snapshot(sid)
        if not snap:
            self.detail_title.setText("Snapshot file missing")
            self.detail_meta.setText("")
            self.detail.setText("")
            return

        self.detail_title.setText(snap.get("title", sid))
        tags = snap.get("tags", [])
        pinned = "📌" if bool(snap.get("pinned", False)) else ""
        ws = snap.get("vscode_workspace", "")
        ws_line = f"  •  workspace: {ws}" if ws else ""
        tag_line = f"  •  tags: {', '.join(tags)}" if tags else ""
        self.detail_meta.setText(f"{pinned}{snap.get('created_at','')}  •  {snap.get('root','')}{ws_line}{tag_line}")

        todos = snap.get("todos", [])
        recent = snap.get("recent_files", [])
        proc = snap.get("processes", [])
        running_apps = snap.get("running_apps", [])
        text = (
            f"NOTE:\n{snap.get('note','') or '(none)'}\n\n"
            f"TODOs:\n"
            f"  1) {todos[0] if len(todos)>0 else ''}\n"
            f"  2) {todos[1] if len(todos)>1 else ''}\n"
            f"  3) {todos[2] if len(todos)>2 else ''}\n\n"
            f"Recent files (top 12):\n" +
            "".join([f"  - {p}\n" for p in recent[:12]]) +
            f"\nProcesses (filtered, {len(proc)}):\n" +
            "".join([f"  - {p.get('name','')}   {p.get('exe','')}\n" for p in proc[:20]]) +
            f"\nRunning apps (taskbar, {len(running_apps)}):\n" +
            "".join([f"  - {p.get('name','')}   {p.get('exe','')}\n" for p in running_apps[:20]])
        )
        self.detail.setText(text)

    # ----- actions -----
    def new_snapshot(self) -> None:
        dlg = SnapshotDialog(self, self.settings.get("default_root", str(Path.home())), self.settings.get("tags", DEFAULT_TAGS))
        if dlg.exec() != QtWidgets.QDialog.Accepted:
            return
        v = dlg.values()
        self._create_snapshot(v["root"], v["title"], v["workspace"], v["note"], v["todos"], v["tags"])

    def quick_snapshot(self) -> None:
        dlg = SnapshotDialog(self, self.settings.get("default_root", str(Path.home())), self.settings.get("tags", DEFAULT_TAGS))
        dlg.setWindowTitle(f"Quick Snapshot ({self.hotkey_label()})")
        if dlg.exec() != QtWidgets.QDialog.Accepted:
            return
        v = dlg.values()
        self._create_snapshot(v["root"], v["title"], v["workspace"], v["note"], v["todos"], v["tags"])

    def _create_snapshot(self, root: str, title: str, workspace: str, note: str, todos: List[str], tags: List[str]) -> None:
        root_path = Path(root).resolve()
        ws = workspace.strip()
        if not ws:
            # if exactly one workspace file exists under root, use it
            wss = list(root_path.glob("*.code-workspace"))
            if len(wss) == 1:
                ws = str(wss[0].resolve())
        sid = gen_id()
        capture = self.settings.get("capture", {})
        capture_recent = bool(capture.get("recent_files", True))
        capture_processes = bool(capture.get("processes", True))
        capture_running_apps = bool(capture.get("running_apps", True))
        snap = Snapshot(
            id=sid,
            title=title,
            created_at=now_iso(),
            root=str(root_path),
            vscode_workspace=ws,
            note=note,
            todos=todos[:3],
            tags=tags,
            pinned=False,
            recent_files=recent_files_under(
                root_path,
                limit=int(self.settings.get("recent_files_limit", 30)),
                exclude_dirs=self.settings.get("recent_files_exclude", []),
                scan_limit=int(self.settings.get("recent_files_scan_limit", 20000)),
                scan_seconds=float(self.settings.get("recent_files_scan_seconds", 2.0)),
            ) if capture_recent else [],
            processes=list_processes_filtered() if capture_processes else [],
            running_apps=list_running_apps() if capture_running_apps else [],
        )
        self.save_snapshot(snap)
        self.refresh_list()
        self.listw.setCurrentRow(0)
        self.statusBar().showMessage(f"Saved snapshot: {sid}", 3500)

    def _update_snapshot_meta(self, sid: str, *, pinned: Optional[bool] = None, tags: Optional[List[str]] = None) -> None:
        """Update snapshot file + index with given metadata."""
        snap = self.load_snapshot(sid)
        if not snap:
            return
        if pinned is not None:
            snap["pinned"] = bool(pinned)
        if tags is not None:
            snap["tags"] = tags
        # write snapshot file
        self.snap_path(sid).write_text(json.dumps(snap, ensure_ascii=False, indent=2), encoding="utf-8")

        # update index
        for it in self.index.get("snapshots", []):
            if it.get("id") == sid:
                if pinned is not None:
                    it["pinned"] = bool(pinned)
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
        self.refresh_list()
        self.statusBar().showMessage("Pinned." if new_state else "Unpinned.", 2000)

    def apply_settings(self, vals: Dict[str, Any], *, save: bool = True) -> None:
        """Apply settings immediately (UI + hotkey)."""
        vals = migrate_settings(vals)
        vals.setdefault("default_root", self.settings.get("default_root", str(Path.home())))
        self.settings = vals
        if save:
            try:
                save_json(self.settings_path, self.settings)
            except Exception as e:
                log_exc("save settings", e)

        # Refresh tag filter
        self._build_tag_menu()
        self.refresh_list()

        # Update labels
        if hasattr(self, "btn_quick"):
            self.btn_quick.setText(f"Quick Snapshot ({self.hotkey_label()})")
        self._build_menus()

        if callable(self.on_settings_applied):
            self.on_settings_applied()
        self._update_auto_snapshot_timer()

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
            btn_replace = msg.addButton("Replace all", QtWidgets.QMessageBox.DestructiveRole)
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
                    "pinned": bool(snap.get("pinned", False)),
                    "tags": snap.get("tags", []),
                }

            for snap in imported_snaps:
                sid = snap.get("id")
                if not sid:
                    continue
                if strategy == "merge" and sid in existing_ids:
                    continue
                try:
                    self.snap_path(sid).write_text(json.dumps(migrate_snapshot(snap), ensure_ascii=False, indent=2), encoding="utf-8")
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

            self.refresh_list()

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

        self.statusBar().showMessage("Settings applied.", 2500)

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
        target = Path(snap.get("vscode_workspace") or snap["root"])
        ok = open_vscode_at(target)
        if not ok:
            QtWidgets.QMessageBox.information(self, "VSCode", "'code' 명령을 찾을 수 없습니다. VSCode에서 Command Palette -> 'Shell Command: Install code command in PATH'를 실행해보세요.")

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
        Path(path).write_text(json.dumps(snap, ensure_ascii=False, indent=2), encoding="utf-8")
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
            try:
                created_at = datetime.strptime(it.get("created_at", ""), "%Y-%m-%dT%H:%M:%S")
            except Exception:
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

    def open_restore_history(self) -> None:
        history_path = app_dir() / "restore_history.json"
        if history_path.exists():
            open_folder(history_path.parent)
        else:
            QtWidgets.QMessageBox.information(self, "Restore history", "No restore history yet.")

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
            QtWidgets.QMessageBox.warning(self, "Error", "Snapshot file missing.")
            return

        restore_cfg = self.settings.get("restore", {})
        open_folder_default = bool(restore_cfg.get("open_folder", True))
        open_terminal_default = bool(restore_cfg.get("open_terminal", True))
        open_vscode_default = bool(restore_cfg.get("open_vscode", True))
        open_running_apps_default = bool(restore_cfg.get("open_running_apps", True))
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
        if ch.get("open_folder"):
            open_folder(root)
        if ch.get("open_terminal"):
            open_terminal_at(root)
        if ch.get("open_vscode"):
            target = Path(snap.get("vscode_workspace") or snap["root"])
            open_vscode_at(target)
        if ch.get("open_running_apps"):
            apps = ch.get("running_apps") or snap.get("running_apps", [])
            restore_running_apps(apps, parent=self)

        append_restore_history({
            "snapshot_id": sid,
            "created_at": now_iso(),
            "open_folder": bool(ch.get("open_folder")),
            "open_terminal": bool(ch.get("open_terminal")),
            "open_vscode": bool(ch.get("open_vscode")),
            "open_running_apps": bool(ch.get("open_running_apps")),
        })

        if show_checklist:
            todos = snap.get("todos", [])
            if any(todos):
                QtWidgets.QMessageBox.information(
                    self,
                    "Checklist",
                    "복원 후 체크리스트:\n" + "\n".join([f"- {t}" for t in todos if t]),
                )
        self.statusBar().showMessage("Restore triggered.", 2500)

    def delete_selected(self) -> None:
        sid = self.selected_id()
        if not sid:
            return
        r = QtWidgets.QMessageBox.question(
            self,
            "Delete snapshot?",
            "정말 삭제할까요? (파일도 함께 삭제됩니다)",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
        )
        if r != QtWidgets.QMessageBox.Yes:
            return
        p = self.snap_path(sid)
        if p.exists():
            try:
                p.unlink()
            except Exception:
                pass
        self.index["snapshots"] = [x for x in self.index.get("snapshots", []) if x.get("id") != sid]
        save_json(self.index_path, self.index)
        self.refresh_list()
        if self.listw.count() > 0:
            self.listw.setCurrentRow(0)
        else:
            self.on_select(-1)
        self.statusBar().showMessage("Deleted.", 2000)


def build_tray(app: QtWidgets.QApplication, win: MainWindow) -> QtWidgets.QSystemTrayIcon:
    tray = QtWidgets.QSystemTrayIcon(win)
    icon = app.windowIcon()
    tray.setIcon(icon)
    tray.setToolTip("CtxSnap")

    menu = QtWidgets.QMenu()

    act_quick = menu.addAction(f"Quick Snapshot ({win.hotkey_label()})")
    act_restore_last = menu.addAction("Restore Last")
    menu.addSeparator()
    act_settings = menu.addAction("Settings")
    act_onboarding = menu.addAction("Onboarding")
    act_open_folder = menu.addAction("Open App Folder")
    menu.addSeparator()
    act_show = menu.addAction("Show/Hide")
    act_quit = menu.addAction("Quit")

    act_quick.triggered.connect(win.quick_snapshot)
    act_restore_last.triggered.connect(win.restore_last)
    act_settings.triggered.connect(win.open_settings)
    act_onboarding.triggered.connect(win.show_onboarding)
    act_open_folder.triggered.connect(lambda: open_folder(app_dir()))

    def toggle_show():
        if win.isVisible():
            win.hide()
        else:
            win.show()
            win.raise_()
            win.activateWindow()

    act_show.triggered.connect(toggle_show)
    act_quit.triggered.connect(app.quit)

    tray.setContextMenu(menu)
    # keep references for live updates
    tray.act_quick = act_quick  # type: ignore[attr-defined]
    tray.activated.connect(lambda reason: toggle_show() if reason == QtWidgets.QSystemTrayIcon.Trigger else None)
    tray.show()
    return tray


def main() -> None:
    app = QtWidgets.QApplication(sys.argv)
    set_pretty_style(app)
    app.setStyleSheet(APP_QSS)

    # Logging
    log_file = setup_logging()
    LOGGER.info("Starting CtxSnap (log: %s)", log_file)

    # App icon (.ico) if present
    icon_path = Path(__file__).parent / "assets" / "icon.ico"
    if icon_path.exists():
        app.setWindowIcon(QtGui.QIcon(str(icon_path)))
    else:
        app.setWindowIcon(app.style().standardIcon(QtWidgets.QStyle.SP_ComputerIcon))

    _, _, settings_path = ensure_storage()
    settings = migrate_settings(load_json(settings_path))
    save_json(settings_path, settings)

    win = MainWindow()
    win.show()

    # First-run onboarding (in-app guide)
    if not bool(win.settings.get("onboarding_shown", False)):
        dlg = OnboardingDialog(win)
        dlg.exec()
        win.settings["onboarding_shown"] = True
        save_json(win.settings_path, win.settings)

        # Keep menu/hotkey label consistent after onboarding
        win._build_menus()
        if hasattr(win, "btn_quick"):
            win.btn_quick.setText(f"Quick Snapshot ({win.hotkey_label()})")

    tray = build_tray(app, win)

    # Global hotkey (re-applied when settings change)
    hotkey_id = 0xC7A5
    hotkey_filter = HotkeyFilter(hotkey_id)

    QtCore.QCoreApplication.instance().installNativeEventFilter(hotkey_filter)
    hotkey_filter.hotkeyPressed.connect(win.quick_snapshot)

    def apply_hotkey_from_settings():
        unregister_hotkey(hotkey_id)
        hk = migrate_settings(win.settings).get("hotkey", {})
        if not hk.get("enabled", True):
            win.statusBar().showMessage("Hotkey disabled.", 2500)
            return
        ok = register_hotkey(
            hotkey_id,
            bool(hk.get("ctrl", True)),
            bool(hk.get("alt", True)),
            bool(hk.get("shift", False)),
            str(hk.get("vk", "S")),
        )
        if ok:
            mods = "+".join([m for m, on in [("Ctrl", hk.get("ctrl", True)), ("Alt", hk.get("alt", True)), ("Shift", hk.get("shift", False))] if on])
            win.statusBar().showMessage(f"Hotkey enabled: {mods}+{hk.get('vk','S')}", 3500)
        else:
            win.statusBar().showMessage("Hotkey registration failed (maybe already in use).", 6000)

            # Conflict handling: offer alternatives
            try:
                dlg = QtWidgets.QMessageBox(win)
                dlg.setWindowTitle("Hotkey conflict")
                dlg.setText("전역 단축키를 등록하지 못했습니다 (다른 앱에서 이미 사용 중일 수 있어요).")
                dlg.setInformativeText("대체 단축키를 자동으로 시도하거나, 단축키를 끌 수 있습니다.")
                btn_try = dlg.addButton("Try alternatives", QtWidgets.QMessageBox.AcceptRole)
                btn_disable = dlg.addButton("Disable hotkey", QtWidgets.QMessageBox.DestructiveRole)
                dlg.addButton("Keep as is", QtWidgets.QMessageBox.RejectRole)
                dlg.exec()
                if dlg.clickedButton() == btn_try:
                    candidates = [
                        {"ctrl": True, "alt": True, "shift": False, "vk": "S"},
                        {"ctrl": True, "alt": True, "shift": False, "vk": "D"},
                        {"ctrl": True, "alt": True, "shift": False, "vk": "Q"},
                        {"ctrl": True, "alt": False, "shift": True, "vk": "S"},
                    ]
                    for cand in candidates:
                        unregister_hotkey(hotkey_id)
                        if register_hotkey(hotkey_id, cand["ctrl"], cand["alt"], cand["shift"], cand["vk"]):
                            win.settings.setdefault("hotkey", {})
                            win.settings["hotkey"].update({"enabled": True, **cand})
                            save_json(win.settings_path, win.settings)
                            win.statusBar().showMessage(f"Hotkey updated to {win.hotkey_label()}", 4500)
                            break
                elif dlg.clickedButton() == btn_disable:
                    win.settings.setdefault("hotkey", {})
                    win.settings["hotkey"].update({"enabled": False})
                    save_json(win.settings_path, win.settings)
                    unregister_hotkey(hotkey_id)
                    win.statusBar().showMessage("Hotkey disabled.", 3500)
            except Exception as e:
                log_exc("hotkey conflict dialog", e)

        # Update UI labels that depend on hotkey
        win._build_menus()
        if hasattr(win, "btn_quick"):
            win.btn_quick.setText(f"Quick Snapshot ({win.hotkey_label()})")
        if hasattr(tray, "act_quick"):
            tray.act_quick.setText(f"Quick Snapshot ({win.hotkey_label()})")  # type: ignore[attr-defined]

    win.on_settings_applied = apply_hotkey_from_settings
    apply_hotkey_from_settings()

    def cleanup():
        tray.hide()
        unregister_hotkey(hotkey_id)

    app.aboutToQuit.connect(cleanup)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
