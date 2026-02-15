from __future__ import annotations

import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ctxsnap.constants import APP_NAME

LOGGER = logging.getLogger(APP_NAME)


def open_folder(path: Path) -> Tuple[bool, str]:
    """Open folder in Windows Explorer.
    
    Args:
        path: Path to folder
        
    Returns:
        Tuple of (success, error_message)
    """
    try:
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


def build_terminal_argv(path: Path, terminal_settings: Optional[Dict[str, Any]] = None) -> List[str]:
    """Build argv for opening a terminal at path.

    terminal_settings:
      - mode: auto|wt|cmd|pwsh|powershell|custom
      - custom_argv: list[str] (supports {path} placeholder)
    """
    s = terminal_settings or {}
    mode = str(s.get("mode") or "auto").strip().lower()
    custom_argv = s.get("custom_argv") if isinstance(s.get("custom_argv"), list) else []

    # Helper: {path} substitution only (no extra parsing).
    def subst(argv: List[str]) -> List[str]:
        out: List[str] = []
        for a in argv:
            out.append(str(a).replace("{path}", str(path)))
        return out

    if mode == "custom":
        argv = [str(x) for x in custom_argv if str(x).strip()]
        argv = subst(argv)
        if argv:
            return argv
        mode = "auto"

    if mode == "wt":
        wt = shutil.which("wt")
        if wt:
            return [wt, "-d", str(path)]
        mode = "auto"

    if mode == "cmd":
        return ["cmd.exe", "/K", f'cd /d "{path}"']

    if mode in ("pwsh", "powershell"):
        exe = shutil.which("pwsh") if mode == "pwsh" else None
        if not exe:
            exe = "powershell.exe"
        # Avoid quoting surprises by using -LiteralPath.
        p = str(path).replace("'", "''")
        return [exe, "-NoExit", "-Command", f"Set-Location -LiteralPath '{p}'"]

    # auto
    wt = shutil.which("wt")
    if wt:
        return [wt, "-d", str(path)]
    return ["cmd.exe", "/K", f'cd /d "{path}"']


def open_terminal_at(path: Path, terminal_settings: Optional[Dict[str, Any]] = None) -> Tuple[bool, str]:
    """Open terminal at specified path.
    
    Args:
        path: Path to open terminal at
        terminal_settings: Terminal preference/settings dict
        
    Returns:
        Tuple of (success, error_message)
    """
    try:
        if not path.exists():
            msg = f"Path does not exist: {path}"
            LOGGER.warning(msg)
            return False, msg

        argv = build_terminal_argv(path, terminal_settings)
        if not argv:
            msg = "No terminal command configured"
            LOGGER.warning(msg)
            return False, msg
        subprocess.Popen(argv, shell=False)
        return True, ""
    except Exception as e:
        msg = f"Failed to open terminal at {path}: {e}"
        LOGGER.exception(msg)
        return False, msg


def resolve_code_cmd() -> Optional[str]:
    code = shutil.which("code")
    if code:
        return code
    # Fallback for standard Windows install locations
    possible_paths = [
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Microsoft VS Code\bin\code.cmd"),
        os.path.expandvars(r"%PROGRAMFILES%\Microsoft VS Code\bin\code.cmd"),
        os.path.expandvars(r"%PROGRAMFILES(x86)%\Microsoft VS Code\bin\code.cmd"),
    ]
    for p in possible_paths:
        if Path(p).exists():
            return p
    return None


def open_vscode_at(target: Path) -> Tuple[bool, str]:
    """Open VSCode at specified path.
    
    Args:
        target: Path or workspace file to open
        
    Returns:
        Tuple of (success, error_message)
    """
    try:
        code = resolve_code_cmd()
        if not code:
            msg = "'code' command not found in PATH or standard locations"
            LOGGER.warning(msg)
            return False, msg

        code_path = Path(code)
        target_str = str(target)
        # If `code` resolves to a .cmd/.bat wrapper, execute it via cmd.exe with shell=False.
        if code_path.suffix.lower() in {".cmd", ".bat"}:
            subprocess.Popen(["cmd.exe", "/c", str(code_path), target_str], shell=False)
        else:
            subprocess.Popen([str(code_path), target_str], shell=False)
        return True, ""
    except Exception as e:
        msg = f"Failed to open VSCode at {target}: {e}"
        LOGGER.exception(msg)
        return False, msg


def open_vscode_files(files: List[Path]) -> Tuple[bool, str]:
    """Open (a few) specific files in the current VSCode window (best-effort)."""
    files = [Path(f) for f in (files or [])]
    files = [f for f in files if f.exists()]
    if not files:
        return False, "No existing files to open"
    try:
        code = resolve_code_cmd()
        if not code:
            msg = "'code' command not found in PATH or standard locations"
            LOGGER.warning(msg)
            return False, msg
        code_path = Path(code)

        argv = ["--reuse-window"]
        # Focus the first file.
        argv += ["-g", str(files[0])]
        argv += [str(f) for f in files[1:]]

        if code_path.suffix.lower() in {".cmd", ".bat"}:
            subprocess.Popen(["cmd.exe", "/c", str(code_path), *argv], shell=False)
        else:
            subprocess.Popen([str(code_path), *argv], shell=False)
        return True, ""
    except Exception as e:
        msg = f"Failed to open files in VSCode: {e}"
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
