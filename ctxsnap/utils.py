from __future__ import annotations

import ctypes
import fnmatch
import logging
import os
import subprocess
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import psutil
from PySide6 import QtWidgets

from ctxsnap.constants import APP_NAME, DEFAULT_PROCESS_KEYWORDS
from ctxsnap.i18n import tr

LOGGER = logging.getLogger(APP_NAME)


def resource_path(relative_path: str) -> Path:
    """Get absolute path to resource, works for dev and for PyInstaller"""
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / relative_path
    return Path(__file__).parent.parent / relative_path


def safe_parse_datetime(s: str) -> Optional[datetime]:
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%dT%H:%M:%S")
    except ValueError:
        return None


def recent_files_under(
    root: Path,
    limit: int = 30,
    *,
    exclude_dirs: Optional[List[str]] = None,
    include_patterns: Optional[List[str]] = None,
    exclude_patterns: Optional[List[str]] = None,
    scan_limit: int = 20000,
    scan_seconds: float = 2.0,
) -> List[str]:
    if not root.exists():
        return []

    exclude_dirs_set = {d.lower() for d in (exclude_dirs or [])}
    include_globs = [p.lower() for p in (include_patterns or []) if p.strip()]
    exclude_globs = [p.lower() for p in (exclude_patterns or []) if p.strip()]

    files: List[Tuple[float, Path]] = []
    start_time = time.monotonic()
    scanned_count = 0
    truncated_reason: Optional[str] = None

    # Stack-based recursive scan (iterative) to avoid recursion depth limits
    # Stack items: (Path object)
    stack = [root]

    while stack:
        if truncated_reason:
            break
            
        current_dir = stack.pop()
        
        try:
            # os.scandir is faster than Path.iterdir or rglob as it yields DirEntry objects with cached stat
            with os.scandir(current_dir) as entries:
                for entry in entries:
                    if truncated_reason:
                        break

                    # Check limits
                    if scanned_count >= scan_limit:
                        truncated_reason = "scan_limit"
                        break
                    if time.monotonic() - start_time >= scan_seconds:
                        truncated_reason = "scan_seconds"
                        break

                    entry_name_lower = entry.name.lower()

                    # 1. Directory handling (Pruning)
                    if entry.is_dir(follow_symlinks=False):
                        # Skip hidden dirs if implicit rule (checking "." prefix)
                        if entry.name.startswith("."):
                            continue
                        # Skip excluded dirs
                        if entry_name_lower in exclude_dirs_set:
                            continue
                        # Skip if dir matches exclude patterns (broad check)
                        # (Optimized: Checking directory name against globs might be aggressive, 
                        # but standard usage usually implies excluding folder names)
                        if exclude_globs and any(fnmatch.fnmatch(entry_name_lower, pat) for pat in exclude_globs):
                            continue
                        
                        stack.append(Path(entry.path))
                        continue
                    
                    # 2. File handling
                    if not entry.is_file(follow_symlinks=False):
                        continue

                    # Skip hidden files
                    if entry.name.startswith("."):
                        continue
                    
                    scanned_count += 1
                    
                    # File-level Excludes
                    if exclude_globs and any(fnmatch.fnmatch(entry_name_lower, pat) for pat in exclude_globs):
                        continue
                        
                    # File-level Includes (if specified, must match at least one)
                    if include_globs and not any(fnmatch.fnmatch(entry_name_lower, pat) for pat in include_globs):
                        continue

                    try:
                        # entry.stat() is cached on Windows for os.scandir
                        mtime = entry.stat().st_mtime
                        files.append((mtime, Path(entry.path)))
                    except OSError:
                        pass
                        
        except (PermissionError, OSError):
            continue

    if truncated_reason:
        LOGGER.info(
            "Recent file scan truncated (%s): root=%s scanned=%s limit=%s seconds=%.2f",
            truncated_reason,
            root,
            scanned_count,
            scan_limit,
            scan_seconds,
        )

    files.sort(key=lambda x: x[0], reverse=True)
    return [str(p.resolve()) for _, p in files[:limit]]


def list_processes_filtered(keywords: Optional[List[str]] = None) -> List[Dict[str, str]]:
    kws = keywords or DEFAULT_PROCESS_KEYWORDS
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
                cand0 = str(launch_cmd[0] or "").strip()
                if cand0 and not Path(cand0).exists():
                    # Allow restoring apps whose cmdline uses a command name on PATH.
                    resolved = shutil.which(cand0)
                    if resolved:
                        launch_cmd = [resolved, *launch_cmd[1:]]
                    elif exe and Path(exe).exists():
                        launch_cmd = [exe]
                    else:
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
            tr("Restore"),
            tr("Failed to restore some apps") + ":\n" + "\n".join(sorted(set(failures))),
        )
    return failures


def build_search_blob(snap: Dict[str, object]) -> str:
    parts: List[str] = []
    parts.append(str(snap.get("note", "") or ""))
    parts.extend([str(p) for p in snap.get("todos", [])])
    parts.extend([str(p) for p in snap.get("recent_files", [])])
    parts.extend([str(p.get("name", "")) for p in snap.get("processes", [])])
    parts.extend([str(p.get("exe", "")) for p in snap.get("processes", [])])
    parts.extend([str(p.get("name", "")) for p in snap.get("running_apps", [])])
    return " ".join(p for p in parts if p).lower()



def snapshot_mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except (FileNotFoundError, PermissionError):
        return 0.0


def parse_search_query(q: str) -> Tuple[Dict[str, Any], List[str]]:
    """Parse a simple search query language.

    Supported filters (case-insensitive):
      - tag:<text>
      - root:<text>
      - title:<text>
      - todo:<text>
      - note:<text>
      - archived:true|false
      - pinned:true|false

    Returns:
      (filters, terms)
        filters: dict with optional keys above
        terms: remaining tokens to be applied as AND full-text terms
    """

    def _parse_bool(s: str) -> Optional[bool]:
        v = (s or "").strip().lower()
        if v in ("1", "true", "yes", "y", "on"):
            return True
        if v in ("0", "false", "no", "n", "off"):
            return False
        return None

    filters: Dict[str, Any] = {}
    terms: List[str] = []
    if not q:
        return filters, terms

    supported = {"tag", "root", "title", "todo", "note", "archived", "pinned"}
    for tok in [t for t in q.strip().split() if t.strip()]:
        if ":" in tok:
            k, v = tok.split(":", 1)
            key = k.strip().lower()
            val = v.strip()
            if key in supported and val:
                if key in ("archived", "pinned"):
                    b = _parse_bool(val)
                    if b is None:
                        terms.append(tok.lower())
                    else:
                        filters[key] = b
                else:
                    filters.setdefault(key, []).append(val.lower())
                continue
        terms.append(tok.lower())
    return filters, terms


def git_title_suggestion(root: Path) -> Optional[str]:
    git = shutil.which("git")
    if not git:
        return None
    if not (root / ".git").exists():
        return None
    try:
        branch = subprocess.check_output(
            [git, "-C", str(root), "rev-parse", "--abbrev-ref", "HEAD"],
            text=True,
            timeout=3,
        ).strip()
        subj = subprocess.check_output(
            [git, "-C", str(root), "log", "-1", "--pretty=%s"],
            text=True,
            timeout=3,
        ).strip()
        return f"{root.name} [{branch}] - {subj}"
    except Exception as e:
        LOGGER.debug("Git title suggestion failed: %s", e)
        return None


def git_state(root: Path) -> Optional[Tuple[str, str]]:
    git = shutil.which("git")
    if not git:
        return None
    if not (root / ".git").exists():
        return None
    try:
        branch = subprocess.check_output([git, "-C", str(root), "rev-parse", "--abbrev-ref", "HEAD"], text=True, timeout=5).strip()
        sha = subprocess.check_output([git, "-C", str(root), "rev-parse", "HEAD"], text=True, timeout=5).strip()
        return branch, sha
    except Exception as e:
        LOGGER.debug("Git state check failed: %s", e)
        return None


def git_dirty(root: Path) -> Optional[bool]:
    git = shutil.which("git")
    if not git:
        return None
    if not (root / ".git").exists():
        return None
    try:
        out = subprocess.check_output([git, "-C", str(root), "status", "--porcelain"], text=True, timeout=5)
        return bool(out.strip())
    except Exception as e:
        LOGGER.debug("Git dirty check failed: %s", e)
        return None


def log_exc(context: str, e: Exception) -> None:
    try:
        LOGGER.exception("%s: %s", context, e)
    except Exception:
        pass
