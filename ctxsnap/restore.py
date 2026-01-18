from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict


def open_folder(path: Path) -> None:
    os.startfile(str(path))  # type: ignore


def open_terminal_at(path: Path) -> None:
    wt = shutil.which("wt")
    if wt:
        subprocess.Popen([wt, "-d", str(path)], shell=False)
        return
    subprocess.Popen(["cmd.exe", "/K", f'cd /d "{path}"'], shell=False)


def open_vscode_at(target: Path) -> bool:
    code = shutil.which("code")
    if not code:
        return False
    subprocess.Popen([code, str(target)], shell=False)
    return True


def resolve_vscode_target(snap: Dict[str, Any]) -> Path:
    ws = str(snap.get("vscode_workspace") or "").strip()
    root = str(snap.get("root") or "").strip()
    if ws:
        ws_path = Path(ws).expanduser()
        if ws_path.exists():
            return ws_path
    if root:
        return Path(root).expanduser()
    return Path.home()
