from __future__ import annotations
from pathlib import Path
from typing import List
from PySide6 import QtCore
from ctxsnap.utils import recent_files_under


class RecentFilesWorker(QtCore.QObject):
    finished = QtCore.Signal(str, list)
    failed = QtCore.Signal(str, str)

    def __init__(
        self,
        sid: str,
        root: Path,
        *,
        limit: int,
        exclude_dirs: List[str],
        include_patterns: List[str],
        exclude_patterns: List[str],
        scan_limit: int,
        scan_seconds: float,
    ) -> None:
        super().__init__()
        self.sid = sid
        self.root = root
        self.limit = limit
        self.exclude_dirs = exclude_dirs
        self.include_patterns = include_patterns
        self.exclude_patterns = exclude_patterns
        self.scan_limit = scan_limit
        self.scan_seconds = scan_seconds

    @QtCore.Slot()
    def run(self) -> None:
        try:
            files = recent_files_under(
                self.root,
                limit=self.limit,
                exclude_dirs=self.exclude_dirs,
                include_patterns=self.include_patterns,
                exclude_patterns=self.exclude_patterns,
                scan_limit=self.scan_limit,
                scan_seconds=self.scan_seconds,
            )
            self.finished.emit(self.sid, files)
        except Exception as exc:
            self.failed.emit(self.sid, str(exc))
