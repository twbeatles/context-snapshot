from __future__ import annotations

import json
import logging
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ctxsnap.constants import APP_NAME, DEFAULT_PROCESS_KEYWORDS, DEFAULT_TAGS

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
                    "capture_note": True,
                    "capture_todos": True,
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


def load_json(p: Path, default: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Load JSON file with error handling.
    
    Args:
        p: Path to JSON file
        default: Default value if file doesn't exist or is corrupted
    
    Returns:
        Parsed JSON data or default value
    """
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
        # Try to backup corrupted file
        try:
            # Avoid collisions when the file keeps failing to parse.
            stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
            corrupted_path = p.with_name(f"{p.name}.corrupted.{stamp}.json")
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
    """Save JSON file atomically using temp file + rename pattern.
    
    This prevents data corruption if the app crashes during write.
    
    Args:
        p: Path to save JSON file
        data: Data to save
    
    Returns:
        True if save was successful, False otherwise
    """
    try:
        content = json.dumps(data, ensure_ascii=False, indent=2)
        # Write to temp file first, then rename (atomic on most filesystems)
        p.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(
            suffix=".tmp",
            prefix=p.stem + "_",
            dir=str(p.parent)
        )
        try:
            # Use a file object to guarantee full writes (os.write can be partial).
            with os.fdopen(fd, "wb") as f:
                f.write(content.encode("utf-8"))
                f.flush()
                try:
                    os.fsync(f.fileno())
                except OSError:
                    # Some filesystems / environments may not support fsync.
                    pass
            # os.replace is atomic on both Windows and Unix
            os.replace(tmp_path, str(p))
            return True
        except Exception as e:
            LOGGER.exception("Failed to write temp file %s: %s", tmp_path, e)
            # Clean up temp file
            try:
                Path(tmp_path).unlink(missing_ok=True)
            except Exception:
                pass
            return False
    except Exception as e:
        LOGGER.exception("Failed to save JSON to %s: %s", p, e)
        return False


def append_restore_history(entry: Dict[str, Any]) -> None:
    """Append a restore entry to history with atomic write.
    
    Args:
        entry: Restore history entry to append
    """
    path = app_dir() / "restore_history.json"
    history = load_json(path, default={"restores": []})
    history.setdefault("restores", [])
    history["restores"].insert(0, entry)
    history["restores"] = history["restores"][:200]
    if not save_json(path, history):
        LOGGER.warning("Failed to save restore history")


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
    settings.setdefault(
        "last_snapshot_form",
        {
            "root": settings.get("default_root", str(Path.home())),
            "vscode_workspace": "",
            "note": "",
            "todos": ["", "", ""],
            "tags": [],
        },
    )
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


def export_backup_to_file(
    path: Path,
    *,
    settings: Dict[str, Any],
    snaps_dir: Path,
    index_path: Path,
    include_snapshots: bool,
    include_index: bool,
) -> None:
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
        except Exception as exc:
            LOGGER.exception("read index for export: %s", exc)
            data["index"] = {"snapshots": []}
    if include_snapshots:
        snaps: List[Dict[str, Any]] = []
        for f in sorted(snaps_dir.glob("*.json")):
            try:
                snaps.append(json.loads(f.read_text(encoding="utf-8")))
            except Exception as exc:
                LOGGER.exception("read snapshot %s: %s", f.name, exc)
                continue
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


def migrate_snapshot(snap: Dict[str, Any]) -> Dict[str, Any]:
    """Backfill missing keys for older snapshots."""
    snap.setdefault("vscode_workspace", "")
    snap.setdefault("tags", [])
    snap.setdefault("pinned", False)
    snap.setdefault("archived", False)
    snap.setdefault("running_apps", [])
    return snap


def now_iso() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


def gen_id() -> str:
    import random
    return datetime.now().strftime("%Y%m%d-%H%M%S") + f"-{random.randint(100, 999)}"


def save_snapshot_file(path: Path, snap: Dict[str, Any]) -> bool:
    """Save snapshot file atomically.
    
    Args:
        path: Path to snapshot file
        snap: Snapshot data to save
    
    Returns:
        True if save was successful, False otherwise
    """
    return save_json(path, snap)
