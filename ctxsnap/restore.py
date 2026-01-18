from __future__ import annotations

import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, Tuple

APP_NAME = "ctxsnap"
LOGGER = logging.getLogger(APP_NAME)


def open_folder(path: Path) -> Tuple[bool, str]:
    """Open folder in Windows Explorer.
    
    Args:
        path: Path to folder
        
    Returns:
        Tuple of (success, error_message)
    """
    try:
        path = path.expanduser()
        if not path.exists():
            msg = f"Folder does not exist: {path}"
            LOGGER.warning(msg)
            return False, msg
        os.startfile(str(path))  # type: ignore
        return True, ""
    except Exception as e:
        msg = f"Failed to open folder {path}: {e}"
        LOGGER.exception(msg)
        return False, msg


def open_terminal_at(path: Path) -> Tuple[bool, str]:
    """Open terminal at specified path.
    
    Args:
        path: Path to open terminal at
        
    Returns:
        Tuple of (success, error_message)
    """
    try:
        path = path.expanduser()
        if not path.exists():
            msg = f"Path does not exist: {path}"
            LOGGER.warning(msg)
            return False, msg
        
        wt = shutil.which("wt")
        if wt:
            subprocess.Popen([wt, "-d", str(path)], shell=False)
            return True, ""
        
        # Fallback to cmd
        subprocess.Popen(["cmd.exe", "/K", f'cd /d "{path}"'], shell=False)
        return True, ""
    except Exception as e:
        msg = f"Failed to open terminal at {path}: {e}"
        LOGGER.exception(msg)
        return False, msg


def open_vscode_at(target: Path) -> Tuple[bool, str]:
    """Open VSCode at specified path.
    
    Args:
        target: Path or workspace file to open
        
    Returns:
        Tuple of (success, error_message)
    """
    try:
        target = target.expanduser()
        code = shutil.which("code")
        if not code:
            msg = "'code' command not found in PATH"
            LOGGER.warning(msg)
            return False, msg
        
        subprocess.Popen([code, str(target)], shell=False)
        return True, ""
    except Exception as e:
        msg = f"Failed to open VSCode at {target}: {e}"
        LOGGER.exception(msg)
        return False, msg


def resolve_vscode_target(snap: Dict[str, Any]) -> Path:
    """Resolve the target path for VSCode based on snapshot data.
    
    Args:
        snap: Snapshot dictionary
        
    Returns:
        Path to open in VSCode (workspace file or root folder)
    """
    ws = str(snap.get("vscode_workspace") or "").strip()
    root = str(snap.get("root") or "").strip()
    
    if ws:
        ws_path = Path(ws).expanduser()
        if ws_path.exists():
            return ws_path
    
    if root:
        root_path = Path(root).expanduser()
        if root_path.exists():
            return root_path
    
    return Path.home()
