from __future__ import annotations

import json
import os
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

APP_NAME = "ctxsnap"


def app_dir() -> Path:
    """Returns %APPDATA%\\ctxsnap."""
    appdata = os.environ.get("APPDATA")
    if not appdata:
        appdata = str(Path.home() / "AppData" / "Roaming")
    return Path(appdata) / APP_NAME


def ensure_dirs() -> Dict[str, Path]:
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
                    "restore_preview_default": True,
                    "hotkey_enabled": True,
                    "hotkey": {"ctrl": True, "alt": True, "shift": False, "vk": "S"},
                    "restore": {"open_folder": True, "open_terminal": True},
                    "ui": {"start_in_tray": False},
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    return {"base": base, "snaps": snaps, "index": index_path, "settings": settings_path}


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data: Dict[str, Any]) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def now_iso() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


def gen_id() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


@dataclass
class Snapshot:
    id: str
    title: str
    created_at: str
    root: str
    note: str
    todos: List[str]  # exactly 3
    recent_files: List[str]
    processes: List[Dict[str, Any]]


def snapshot_path(snaps_dir: Path, sid: str) -> Path:
    return snaps_dir / f"{sid}.json"


def write_snapshot(snaps_dir: Path, snap: Snapshot) -> None:
    snapshot_path(snaps_dir, snap.id).write_text(
        json.dumps(asdict(snap), ensure_ascii=False, indent=2), encoding="utf-8"
    )


def read_snapshot(snaps_dir: Path, sid: str) -> Optional[Dict[str, Any]]:
    p = snapshot_path(snaps_dir, sid)
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))
