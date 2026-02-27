from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

from ctxsnap.app_storage import export_backup_to_file, import_backup_from_file


class BackupService:
    """Thin wrapper around storage backup APIs with encryption options."""

    def export_backup(
        self,
        path: Path,
        *,
        settings: Dict[str, Any],
        snaps_dir: Path,
        index_path: Path,
        include_snapshots: bool,
        include_index: bool,
        encrypt_backup: bool = False,
    ) -> None:
        export_backup_to_file(
            path,
            settings=settings,
            snaps_dir=snaps_dir,
            index_path=index_path,
            include_snapshots=include_snapshots,
            include_index=include_index,
            encrypt_backup=encrypt_backup,
        )

    def import_backup(self, path: Path) -> Dict[str, Any]:
        return import_backup_from_file(path)
