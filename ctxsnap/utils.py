from __future__ import annotations

import ctypes
import fnmatch
import logging
import subprocess
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import psutil
from PySide6 import QtWidgets

APP_NAME = "ctxsnap"
LOGGER = logging.getLogger(APP_NAME)

DEFAULT_PROC_KEYWORDS = [
    "code", "pycharm", "idea", "chrome", "msedge", "firefox", "wt", "terminal",
    "powershell", "cmd", "python", "node", "docker", "postman", "slack", "notion"
]


def recent_files_under(
    root: Path,
    limit: int = 30,
    *,
    exclude_dirs: Optional[List[str]] = None,
    scan_limit: int = 20000,
    scan_seconds: float = 2.0,
) -> List[str]:
    if not root.exists():
        return []
    exclude = {d.lower() for d in (exclude_dirs or [])}
    files: List[Tuple[float, Path]] = []
    start = time.monotonic()
    scanned = 0
    truncated_reason: Optional[str] = None
    for p in root.rglob("*"):
        try:
            if p.is_dir():
                continue
            if any(part.lower() in exclude for part in p.parts):
                continue
            if exclude and any(fnmatch.fnmatch(p.as_posix().lower(), f"*{pattern.lower()}*") for pattern in exclude):
                continue
            if any(part.startswith(".") for part in p.parts):
                continue
            st = p.stat()
            files.append((st.st_mtime, p))
            scanned += 1
            if scanned >= scan_limit:
                truncated_reason = "scan_limit"
                break
            if time.monotonic() - start >= scan_seconds:
                truncated_reason = "scan_seconds"
                break
        except (PermissionError, FileNotFoundError):
            continue
    if truncated_reason:
        LOGGER.info(
            "Recent file scan truncated (%s): root=%s scanned=%s limit=%s seconds=%.2f",
            truncated_reason,
            root,
            scanned,
            scan_limit,
            scan_seconds,
        )
    files.sort(key=lambda x: x[0], reverse=True)
    return [str(p.resolve()) for _, p in files[:limit]]


def list_processes_filtered(keywords: Optional[List[str]] = None) -> List[Dict[str, str]]:
    kws = keywords or DEFAULT_PROC_KEYWORDS
    out: List[Dict[str, str]] = []
    for proc in psutil.process_iter(attrs=["pid", "name", "exe", "cmdline"]):
        try:
            name = (proc.info.get("name") or "").lower()
            exe = (proc.info.get("exe") or "").lower()
            hay = f"{name} {exe}"
            if any(k in hay for k in kws):
                out.append({
                    "pid": proc.info.get("pid"),
                    "name": proc.info.get("name"),
                    "exe": proc.info.get("exe") or "",
                    "cmdline": (proc.info.get("cmdline") or [])[:6],
                })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    seen = set()
    uniq = []
    for p in out:
        key = (p.get("name") or "", p.get("exe") or "")
        if key in seen:
            continue
        seen.add(key)
        uniq.append(p)
    return uniq


def list_running_apps() -> List[Dict[str, object]]:
    user32 = ctypes.windll.user32
    get_window_text_length = user32.GetWindowTextLengthW
    get_window_text = user32.GetWindowTextW
    is_window_visible = user32.IsWindowVisible
    get_window_thread_process_id = user32.GetWindowThreadProcessId

    results: List[Dict[str, object]] = []
    seen: set[Tuple[str, str]] = set()

    @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    def enum_proc(hwnd: int, lparam: int) -> bool:
        if not is_window_visible(hwnd):
            return True
        length = get_window_text_length(hwnd)
        if length <= 0:
            return True
        buf = ctypes.create_unicode_buffer(length + 1)
        get_window_text(hwnd, buf, length + 1)
        title = buf.value.strip()
        if not title:
            return True

        pid = ctypes.c_uint()
        get_window_thread_process_id(hwnd, ctypes.byref(pid))
        try:
            proc = psutil.Process(pid.value)
            exe = proc.exe()
            name = proc.name()
            cmdline = proc.cmdline()
        except (psutil.NoSuchProcess, psutil.AccessDenied, FileNotFoundError):
            return True

        key = ((exe or name).lower(), title.lower())
        if key in seen:
            return True
        seen.add(key)
        results.append(
            {
                "pid": pid.value,
                "name": name,
                "exe": exe,
                "title": title,
                "cmdline": cmdline[:10] if cmdline else [],
            }
        )
        return True

    user32.EnumWindows(enum_proc, 0)
    return results


def restore_running_apps(apps: List[Dict[str, object]], parent: Optional[QtWidgets.QWidget] = None) -> List[str]:
    if not apps:
        return []
    running: set[str] = set()
    failures: List[str] = []
    for proc in psutil.process_iter(attrs=["exe"]):
        try:
            exe = (proc.info.get("exe") or "").lower()
            if exe:
                running.add(exe)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    for app in apps:
        exe = str(app.get("exe") or "").strip()
        cmdline = app.get("cmdline") or []
        exe_lower = exe.lower() if exe else ""
        if exe_lower and exe_lower in running:
            continue
        try:
            launch_cmd = []
            if cmdline:
                launch_cmd = cmdline
            elif exe:
                launch_cmd = [exe]
            if launch_cmd:
                if launch_cmd[0] and not Path(launch_cmd[0]).exists() and exe:
                    launch_cmd = [exe]
                if not Path(launch_cmd[0]).exists():
                    failures.append(f"{app.get('name') or app.get('exe') or 'unknown'} (path missing)")
                    continue
                subprocess.Popen(launch_cmd, shell=False)
            else:
                failures.append(f"{app.get('name') or app.get('exe') or 'unknown'} (no command)")
        except Exception:
            LOGGER.exception("restore running app")
            failures.append(f"{app.get('name') or app.get('exe') or 'unknown'} (error)")
    if failures:
        QtWidgets.QMessageBox.information(
            parent,
            "Restore apps",
            "일부 앱을 다시 실행하지 못했습니다:\n" + "\n".join(sorted(set(failures))),
        )
    return failures


def build_search_blob(snap: Dict[str, object]) -> str:
    parts: List[str] = []
    parts.append(str(snap.get("note", "") or ""))
    parts.extend([str(p) for p in snap.get("todos", [])])
    parts.extend([str(p) for p in snap.get("recent_files", [])])
    parts.extend([str(p.get("name", "")) for p in snap.get("running_apps", [])])
    return " ".join(p for p in parts if p).lower()


def snapshot_mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except (FileNotFoundError, PermissionError):
        return 0.0
