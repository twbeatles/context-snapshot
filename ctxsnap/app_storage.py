from __future__ import annotations

import json
import logging
import os
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ctxsnap.constants import APP_NAME, DEFAULT_PROCESS_KEYWORDS, DEFAULT_TAGS
from ctxsnap.core.security import SecurityService

LOGGER = logging.getLogger(APP_NAME)


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
    archived: bool
    recent_files: List[str]
    processes: List[Dict[str, Any]]
    running_apps: List[Dict[str, Any]]
    source: str = ""
    trigger: str = ""
    git_state: Dict[str, Any] = field(default_factory=dict)
    auto_fingerprint: str = ""
    schema_version: int = 2
    rev: int = 1
    updated_at: str = ""
    sensitive: Dict[str, Any] = field(default_factory=dict)


def app_dir() -> Path:
    """Return %APPDATA%\\ctxsnap."""
    appdata = os.environ.get("APPDATA")
    if not appdata:
        appdata = str(Path.home() / "AppData" / "Roaming")
    return Path(appdata) / APP_NAME


def now_iso() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


def _default_index() -> Dict[str, Any]:
    return {
        "schema_version": 2,
        "rev": 1,
        "updated_at": now_iso(),
        "search_meta": {"engine": "blob", "version": 1},
        "snapshots": [],
    }


def _default_settings() -> Dict[str, Any]:
    return {
        "schema_version": 2,
        "default_root": str(Path.home()),
        "recent_files_limit": 30,
        "restore_preview_default": True,
        "tags": DEFAULT_TAGS,
        "hotkey": {"enabled": True, "ctrl": True, "alt": True, "shift": False, "vk": "S"},
        "capture": {"recent_files": True, "processes": True, "running_apps": True},
        "capture_note": True,
        "capture_todos": True,
        "capture_enforce_todos": True,
        "recent_files_exclude": [".git", "node_modules", "venv", "dist", "build"],
        "recent_files_scan_limit": 20000,
        "recent_files_scan_seconds": 2.0,
        "recent_files_background": False,
        "recent_files_include": [],
        "recent_files_exclude_patterns": [],
        "list_page_size": 200,
        "process_keywords": DEFAULT_PROCESS_KEYWORDS,
        "templates": [],
        "archive_after_days": 0,
        "archive_skip_pinned": True,
        "auto_backup_hours": 0,
        "auto_backup_last": "",
        "auto_snapshot_minutes": 0,
        "auto_snapshot_on_git_change": False,
        "language": "auto",
        "dev_flags": {
            "sync_enabled": False,
            "security_enabled": False,
            "advanced_search_enabled": False,
            "restore_profiles_enabled": False,
        },
        "sync": {
            "provider": "local",
            "local_root": str(app_dir() / "sync_local"),
            "auto_interval_min": 0,
            "last_cursor": "",
        },
        "security": {
            "dpapi_enabled": False,
            "encrypt_note": True,
            "encrypt_todos": True,
            "encrypt_processes": True,
            "encrypt_running_apps": True,
        },
        "search": {
            "enable_field_query": True,
            "saved_queries": [],
        },
        "restore_profiles": [],
        "restore": {
            "open_folder": True,
            "open_terminal": True,
            "open_vscode": True,
            "open_running_apps": False,
            "show_post_restore_checklist": True,
        },
        "onboarding_shown": False,
    }


def ensure_storage() -> Tuple[Path, Path, Path]:
    base = app_dir()
    snaps = base / "snapshots"
    base.mkdir(parents=True, exist_ok=True)
    snaps.mkdir(parents=True, exist_ok=True)

    index_path = base / "index.json"
    settings_path = base / "settings.json"
    conflicts_path = base / "sync_conflicts.json"
    sync_state_path = base / "sync_state.json"

    if not index_path.exists():
        index_path.write_text(json.dumps(_default_index(), ensure_ascii=False, indent=2), encoding="utf-8")
    if not settings_path.exists():
        settings_path.write_text(json.dumps(_default_settings(), ensure_ascii=False, indent=2), encoding="utf-8")
    if not conflicts_path.exists():
        conflicts_path.write_text(json.dumps({"conflicts": []}, ensure_ascii=False, indent=2), encoding="utf-8")
    if not sync_state_path.exists():
        sync_state_path.write_text(
            json.dumps(
                {
                    "provider": "",
                    "last_cursor": "",
                    "synced_at": "",
                    "snapshot_count": 0,
                    "conflict_count": 0,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
    return snaps, index_path, settings_path


def load_json(p: Path, default: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Load JSON file with error handling."""
    if default is None:
        default = {}
    try:
        if not p.exists():
            LOGGER.warning("JSON file not found: %s, using default", p)
            return default.copy()
        content = p.read_text(encoding="utf-8")
        data = json.loads(content)
        if not isinstance(data, dict):
            LOGGER.warning("JSON file %s is not a dict, using default", p)
            return default.copy()
        return data
    except json.JSONDecodeError as e:
        LOGGER.exception("JSON decode error in %s: %s", p, e)
        try:
            corrupted_path = p.with_suffix(".corrupted.json")
            if p.exists():
                p.rename(corrupted_path)
                LOGGER.info("Corrupted file backed up to %s", corrupted_path)
        except Exception:
            pass
        return default.copy()
    except Exception as e:
        LOGGER.exception("Failed to load JSON from %s: %s", p, e)
        return default.copy()


def save_json(p: Path, data: Dict[str, Any]) -> bool:
    """Save JSON file atomically using temp file + rename pattern."""
    try:
        content = json.dumps(data, ensure_ascii=False, indent=2)
        p.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(suffix=".tmp", prefix=p.stem + "_", dir=str(p.parent))
        fd_closed = False
        try:
            os.write(fd, content.encode("utf-8"))
            os.close(fd)
            fd_closed = True
            os.replace(tmp_path, str(p))
            return True
        except Exception as e:
            if not fd_closed:
                try:
                    os.close(fd)
                except OSError:
                    pass
            LOGGER.exception("Failed to write temp file %s: %s", tmp_path, e)
            try:
                Path(tmp_path).unlink(missing_ok=True)
            except Exception:
                pass
            return False
    except Exception as e:
        LOGGER.exception("Failed to save JSON to %s: %s", p, e)
        return False


def append_restore_history(entry: Dict[str, Any]) -> None:
    """Append a restore entry to history with atomic write."""
    path = app_dir() / "restore_history.json"
    history = load_json(path, default={"restores": []})
    history.setdefault("restores", [])
    history["restores"].insert(0, entry)
    history["restores"] = history["restores"][:200]
    if not save_json(path, history):
        LOGGER.warning("Failed to save restore history")


def _migrate_dev_flags(settings: Dict[str, Any]) -> None:
    flags = settings.setdefault("dev_flags", {})
    if not isinstance(flags, dict):
        flags = {}
        settings["dev_flags"] = flags
    flags.setdefault("sync_enabled", False)
    flags.setdefault("security_enabled", False)
    flags.setdefault("advanced_search_enabled", False)
    flags.setdefault("restore_profiles_enabled", False)


def _migrate_sync(settings: Dict[str, Any]) -> None:
    sync = settings.setdefault("sync", {})
    if not isinstance(sync, dict):
        sync = {}
        settings["sync"] = sync
    sync.setdefault("provider", "local")
    sync.setdefault("local_root", str(app_dir() / "sync_local"))
    sync.setdefault("auto_interval_min", 0)
    sync.setdefault("last_cursor", "")


def _migrate_security(settings: Dict[str, Any]) -> None:
    sec = settings.setdefault("security", {})
    if not isinstance(sec, dict):
        sec = {}
        settings["security"] = sec
    sec.setdefault("dpapi_enabled", False)
    sec.setdefault("encrypt_note", True)
    sec.setdefault("encrypt_todos", True)
    sec.setdefault("encrypt_processes", True)
    sec.setdefault("encrypt_running_apps", True)


def _migrate_search(settings: Dict[str, Any]) -> None:
    search = settings.setdefault("search", {})
    if not isinstance(search, dict):
        search = {}
        settings["search"] = search
    search.setdefault("enable_field_query", True)
    saved = search.setdefault("saved_queries", [])
    if not isinstance(saved, list):
        search["saved_queries"] = []


def migrate_settings(settings: Dict[str, Any]) -> Dict[str, Any]:
    """Backfill missing keys for older settings.json."""
    settings.setdefault("schema_version", 2)
    settings["schema_version"] = max(2, int(settings.get("schema_version", 1) or 1))
    settings.setdefault("default_root", str(Path.home()))
    settings.setdefault("recent_files_limit", 30)
    settings.setdefault("restore_preview_default", True)
    settings.setdefault("tags", DEFAULT_TAGS)

    hotkey = settings.setdefault("hotkey", {"enabled": True, "ctrl": True, "alt": True, "shift": False, "vk": "S"})
    if not isinstance(hotkey, dict):
        hotkey = {}
        settings["hotkey"] = hotkey
    hotkey.setdefault("enabled", True)
    hotkey.setdefault("ctrl", True)
    hotkey.setdefault("alt", True)
    hotkey.setdefault("shift", False)
    hotkey.setdefault("vk", "S")

    capture = settings.setdefault("capture", {"recent_files": True, "processes": True, "running_apps": True})
    if not isinstance(capture, dict):
        capture = {}
        settings["capture"] = capture
    capture.setdefault("recent_files", True)
    capture.setdefault("processes", True)
    capture.setdefault("running_apps", True)

    settings.setdefault("recent_files_exclude", [".git", "node_modules", "venv", "dist", "build"])
    settings.setdefault("recent_files_scan_limit", 20000)
    settings.setdefault("recent_files_scan_seconds", 2.0)
    settings.setdefault("recent_files_background", False)
    settings.setdefault("recent_files_include", [])
    settings.setdefault("recent_files_exclude_patterns", [])
    settings.setdefault("list_page_size", 200)
    settings.setdefault("process_keywords", DEFAULT_PROCESS_KEYWORDS)
    settings.setdefault("templates", [])
    settings.setdefault("archive_after_days", 0)
    settings.setdefault("archive_skip_pinned", True)
    settings.setdefault("auto_backup_hours", 0)
    settings.setdefault("auto_backup_last", "")
    settings.setdefault("capture_note", True)
    settings.setdefault("capture_todos", True)
    settings.setdefault("capture_enforce_todos", True)
    settings.setdefault("auto_snapshot_minutes", 0)
    settings.setdefault("auto_snapshot_on_git_change", False)
    settings.setdefault("language", "auto")

    restore = settings.setdefault(
        "restore",
        {
            "open_folder": True,
            "open_terminal": True,
            "open_vscode": True,
            "open_running_apps": False,
            "show_post_restore_checklist": True,
        },
    )
    if not isinstance(restore, dict):
        restore = {}
        settings["restore"] = restore
    restore.setdefault("open_folder", True)
    restore.setdefault("open_terminal", True)
    restore.setdefault("open_vscode", True)
    restore.setdefault("open_running_apps", False)
    restore.setdefault("show_post_restore_checklist", True)

    profiles = settings.setdefault("restore_profiles", [])
    if not isinstance(profiles, list):
        settings["restore_profiles"] = []

    _migrate_dev_flags(settings)
    _migrate_sync(settings)
    _migrate_security(settings)
    _migrate_search(settings)

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
    if isinstance(data, dict) and "settings" in data and isinstance(data["settings"], dict):
        data = data["settings"]
    if not isinstance(data, dict):
        raise ValueError("Invalid settings format")
    return migrate_settings(data)


# -------- Backup package (settings + optional snapshots/index) --------


def export_backup_to_file(
    path: Path,
    *,
    settings: Dict[str, Any],
    snaps_dir: Path,
    index_path: Path,
    include_snapshots: bool,
    include_index: bool,
    encrypt_backup: bool = False,
) -> None:
    """Export a single JSON file that can contain settings and optionally snapshots/index."""
    payload: Dict[str, Any] = {
        "app": APP_NAME,
        "version": 3,
        "exported_at": now_iso(),
        "settings": migrate_settings(settings),
    }
    data: Dict[str, Any] = {}
    if include_index:
        try:
            data["index"] = load_json(index_path, default=_default_index())
        except Exception as exc:
            LOGGER.exception("read index for export: %s", exc)
            data["index"] = _default_index()
    if include_snapshots:
        snaps: List[Dict[str, Any]] = []
        for f in sorted(snaps_dir.glob("*.json")):
            try:
                snaps.append(migrate_snapshot(json.loads(f.read_text(encoding="utf-8"))))
            except Exception as exc:
                LOGGER.exception("read snapshot %s: %s", f.name, exc)
                continue
        data["snapshots"] = snaps
    if data:
        payload["data"] = data

    if encrypt_backup:
        security = SecurityService()
        wrapped = security.encrypt_backup_payload(payload)
        path.write_text(json.dumps(wrapped, ensure_ascii=False, indent=2), encoding="utf-8")
        return

    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def import_backup_from_file(path: Path) -> Dict[str, Any]:
    """Import either settings-only export, full backup, or encrypted backup."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("Invalid backup format")

    if bool(raw.get("encrypted_backup", False)):
        security = SecurityService()
        raw = security.decrypt_backup_payload(raw)

    if "settings" in raw and isinstance(raw["settings"], dict):
        settings = migrate_settings(raw["settings"])
        data = raw.get("data") if isinstance(raw.get("data"), dict) else None
        return {
            "settings": settings,
            "data": data,
            "encrypted_backup": bool(raw.get("encrypted_backup", False)),
        }

    settings = migrate_settings(raw)
    return {"settings": settings, "data": None, "encrypted_backup": False}


def migrate_snapshot(snap: Dict[str, Any]) -> Dict[str, Any]:
    """Backfill missing keys for older snapshots."""
    snap.setdefault("schema_version", 2)
    snap["schema_version"] = max(2, int(snap.get("schema_version", 1) or 1))
    snap.setdefault("vscode_workspace", "")
    snap.setdefault("tags", [])
    snap.setdefault("pinned", False)
    snap.setdefault("archived", False)
    snap.setdefault("running_apps", [])
    snap.setdefault("source", "")
    snap.setdefault("trigger", "")
    snap.setdefault("auto_fingerprint", "")
    snap.setdefault("rev", 1)
    snap["rev"] = max(1, int(snap.get("rev", 1) or 1))
    snap.setdefault("updated_at", str(snap.get("created_at") or now_iso()))
    if not isinstance(snap.get("git_state"), dict):
        snap["git_state"] = {}
    else:
        snap.setdefault("git_state", {})
    git_state = snap.get("git_state", {})
    git_state.setdefault("branch", "")
    git_state.setdefault("sha", "")
    git_state.setdefault("dirty", False)
    git_state.setdefault("changed", 0)
    git_state.setdefault("staged", 0)
    git_state.setdefault("untracked", 0)
    if not isinstance(snap.get("sensitive"), dict):
        snap["sensitive"] = {}
    return snap


def gen_id() -> str:
    import random

    return datetime.now().strftime("%Y%m%d-%H%M%S") + f"-{random.randint(100, 999)}"


def save_snapshot_file(path: Path, snap: Dict[str, Any]) -> bool:
    """Save snapshot file atomically."""
    return save_json(path, snap)
