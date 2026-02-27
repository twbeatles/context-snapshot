from __future__ import annotations

import copy
from datetime import datetime, timedelta
from pathlib import Path
from typing import List

from PySide6 import QtCore

from ctxsnap.app_storage import app_dir, load_json, now_iso, save_json, save_snapshot_file
from ctxsnap.constants import APP_NAME
from ctxsnap.core.logging import get_logger
from ctxsnap.core.sync import SyncEngine
from ctxsnap.core.sync.providers import CloudStubSyncProvider, LocalSyncProvider
from ctxsnap.core.worker import RecentFilesWorker
from ctxsnap.i18n import tr
from ctxsnap.utils import git_state, log_exc, safe_parse_datetime, snapshot_mtime

LOGGER = get_logger()


class MainWindowAutomationSection:
    def _auto_snapshot_prompt(self) -> None:
        if int(self.settings.get("auto_snapshot_minutes", 0)) <= 0:
            return
        self._run_auto_snapshot("timer")

    def _update_auto_snapshot_timer(self) -> None:
        minutes = int(self.settings.get("auto_snapshot_minutes", 0))
        if minutes <= 0:
            self.auto_timer.stop()
            return
        self.auto_timer.setInterval(minutes * 60_000)
        if not self.auto_timer.isActive():
            self.auto_timer.start()

    def _update_backup_timer(self) -> None:
        hours = int(self.settings.get("auto_backup_hours", 0))
        if hours <= 0:
            self.backup_timer.stop()
            return
        self.backup_timer.setInterval(hours * 60_000 * 60)
        if not self.backup_timer.isActive():
            self.backup_timer.start()

    def _init_sync_engine(self) -> None:
        sync_cfg = self.settings.get("sync", {})
        provider_name = str(sync_cfg.get("provider", "local") or "local").strip().lower()
        if provider_name == "local":
            local_root = Path(str(sync_cfg.get("local_root", app_dir() / "sync_local"))).expanduser()
            provider = LocalSyncProvider(local_root)
        else:
            provider = CloudStubSyncProvider()
        self.sync_engine = SyncEngine(
            provider=provider,
            local_index_path=self.index_path,
            local_snaps_dir=self.snaps_dir,
            conflicts_path=app_dir() / "sync_conflicts.json",
            state_path=app_dir() / "sync_state.json",
        )

    def _update_sync_timer(self) -> None:
        sync_enabled = bool(self.settings.get("dev_flags", {}).get("sync_enabled", False))
        minutes = int(self.settings.get("sync", {}).get("auto_interval_min", 0))
        if not sync_enabled or minutes <= 0:
            self.sync_timer.stop()
            return
        self.sync_timer.setInterval(minutes * 60_000)
        if not self.sync_timer.isActive():
            self.sync_timer.start()

    def _run_scheduled_sync(self) -> None:
        sync_enabled = bool(self.settings.get("dev_flags", {}).get("sync_enabled", False))
        if not sync_enabled or not self.sync_engine:
            return
        try:
            result = self.sync_engine.sync()
            self.settings.setdefault("sync", {})
            self.settings["sync"]["last_cursor"] = result.get("cursor", "")
            if not save_json(self.settings_path, self.settings):
                LOGGER.warning("Failed to save sync cursor.")
            self.index = self.snapshot_service.migrate_index(load_json(self.index_path))
            self.refresh_list(reset_page=False)
            self.statusBar().showMessage(
                tr("Sync done status").format(
                    snapshots=result.get("snapshot_count", 0),
                    conflicts=result.get("conflict_count", 0),
                ),
                3500,
            )
        except Exception as exc:
            log_exc("scheduled sync", exc if isinstance(exc, Exception) else Exception(str(exc)))
            self.statusBar().showMessage(tr("Sync failed status"), 3500)

    def _run_scheduled_backup(self) -> None:
        hours = int(self.settings.get("auto_backup_hours", 0))
        if hours <= 0:
            return
        last = self.settings.get("auto_backup_last", "")
        if last:
            try:
                last_dt = safe_parse_datetime(last)
                if last_dt and datetime.now() - last_dt < timedelta(hours=hours):
                    return
            except Exception:
                pass
        bkp = self._auto_backup_current()
        self.settings["auto_backup_last"] = now_iso()
        if not save_json(self.settings_path, self.settings):
            LOGGER.warning("Failed to persist auto backup timestamp.")
        self.statusBar().showMessage(f"Auto backup created: {bkp.name}", 3500)

        # Cleanup old backups (keep last 5)
        try:
            backups_dir = app_dir() / "backups"
            if backups_dir.exists():
                backups = sorted(backups_dir.glob(f"{APP_NAME}_autobackup_*.json"), key=lambda p: p.stat().st_mtime)
                while len(backups) > 5:
                    old = backups.pop(0)
                    try:
                        old.unlink()
                    except Exception:
                        pass
        except Exception as e:
            LOGGER.debug("Backup cleanup failed: %s", e)

    def _apply_archive_policy(self) -> None:
        days = int(self.settings.get("archive_after_days", 0))
        if days <= 0:
            return
        skip_pinned = bool(self.settings.get("archive_skip_pinned", True))
        cutoff = datetime.now() - timedelta(days=days)
        updated = False
        for it in self.index.get("snapshots", []):
            if skip_pinned and bool(it.get("pinned", False)):
                continue
            if bool(it.get("archived", False)):
                continue
            created_at = safe_parse_datetime(it.get("created_at", ""))
            if not created_at:
                continue
            if created_at >= cutoff:
                continue
            it["archived"] = True
            sid = it.get("id")
            if sid:
                snap = self.load_snapshot(sid)
                if snap:
                    snap["archived"] = True
                    if not save_snapshot_file(self.snap_path(sid), snap):
                        LOGGER.warning("Failed to persist archived snapshot: %s", sid)
            updated = True
        if updated:
            if not save_json(self.index_path, self.index):
                LOGGER.warning("Failed to persist archive policy updates.")

    def _check_git_change(self) -> None:
        if not bool(self.settings.get("auto_snapshot_on_git_change", False)):
            return
        root = Path(self.settings.get("default_root", str(Path.home())))
        state = git_state(root)
        if not state:
            return
        if self._last_git_state and self._last_git_state != state:
            self._run_auto_snapshot("git_change")
        self._last_git_state = state

    def _run_auto_snapshot(self, trigger: str) -> None:
        source = "auto_timer" if trigger == "timer" else "auto_git"
        root_raw = str(self.settings.get("default_root", "")).strip()
        if not root_raw:
            self.statusBar().showMessage("Auto snapshot skipped: default root is empty.", 3000)
            LOGGER.warning("Auto snapshot skipped: default_root is empty.")
            return

        root_path = Path(root_raw).expanduser()
        if not root_path.exists() or not root_path.is_dir():
            self.statusBar().showMessage("Auto snapshot skipped: default root is invalid.", 3000)
            LOGGER.warning("Auto snapshot skipped: invalid root=%s", root_path)
            return
        root_path = root_path.resolve()

        seed = self._auto_seed_snapshot(root_path)
        seed_workspace = str(seed.get("vscode_workspace", "")).strip() if seed else ""
        seed_note = str(seed.get("note", "")).strip() if seed else ""
        seed_todos = self._normalized_todos(seed.get("todos", ["", "", ""]) if seed else ["", "", ""])
        seed_tags = self._normalized_tags(seed.get("tags", []) if seed else [])

        if not seed_workspace:
            workspaces = list(root_path.glob("*.code-workspace"))
            if len(workspaces) == 1:
                seed_workspace = str(workspaces[0].resolve())

        capture_note = bool(self.settings.get("capture_note", True))
        capture_todos = bool(self.settings.get("capture_todos", True))
        note = seed_note if capture_note else ""
        todos = seed_todos if capture_todos else ["", "", ""]

        git_state_data = self._auto_git_state(root_path)
        auto_fp = self._auto_fingerprint(
            root=str(root_path),
            workspace=seed_workspace,
            note=note,
            todos=todos,
            tags=seed_tags,
            git_state_data=git_state_data,
        )
        if self._is_duplicate_auto_snapshot(root_path, auto_fp):
            self.statusBar().showMessage("Auto snapshot skipped: no changes detected.", 2500)
            return

        self._create_snapshot(
            str(root_path),
            self._auto_title(root_path),
            seed_workspace,
            note,
            todos,
            seed_tags,
            source=source,
            trigger=trigger,
            git_state_data=git_state_data,
            auto_fingerprint=auto_fp,
            check_duplicate=False,
            status_prefix="Auto snapshot saved",
        )

    def _start_recent_files_scan(self, sid: str, root: Path) -> None:
        if sid in self._recent_workers:
            return
        worker = RecentFilesWorker(
            sid,
            root,
            limit=int(self.settings.get("recent_files_limit", 30)),
            exclude_dirs=self.settings.get("recent_files_exclude", []),
            include_patterns=self.settings.get("recent_files_include", []),
            exclude_patterns=self.settings.get("recent_files_exclude_patterns", []),
            scan_limit=int(self.settings.get("recent_files_scan_limit", 20000)),
            scan_seconds=float(self.settings.get("recent_files_scan_seconds", 2.0)),
        )
        thread = QtCore.QThread(self)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(self._on_recent_files_ready)
        worker.failed.connect(self._on_recent_files_failed)
        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        worker.failed.connect(worker.deleteLater)
        thread.finished.connect(lambda: self._recent_workers.pop(sid, None))
        thread.finished.connect(thread.deleteLater)
        thread.worker = worker
        self._recent_workers[sid] = thread
        thread.start()

    def _on_recent_files_ready(self, sid: str, files: List[str]) -> None:
        snap = self.load_snapshot(sid)
        if not snap:
            return
        prev_snap = copy.deepcopy(snap)
        prev_index = copy.deepcopy(self.index)
        snap_path = self.snap_path(sid)
        try:
            snap["recent_files"] = files
            self._save_snapshot_or_raise(snap_path, snap, f"snapshot recent files {sid}")
            snap_mtime = snapshot_mtime(snap_path)
            for it in self.index.get("snapshots", []):
                if it.get("id") == sid:
                    it.update(self._index_entry_from_snapshot_data(snap, snap_mtime=snap_mtime))
                    break
            self.index = self.snapshot_service.touch_index(self.index)
            self._save_json_or_raise(self.index_path, self.index, "index")
            self.refresh_list(reset_page=False)
            self.statusBar().showMessage(tr("Recent files updated in background."), 2500)
        except Exception as exc:
            log_exc(f"recent files update ({sid})", exc if isinstance(exc, Exception) else Exception(str(exc)))
            self.index = prev_index
            try:
                self._save_snapshot_or_raise(snap_path, prev_snap, f"snapshot recent files rollback {sid}")
            except Exception as rollback_exc:
                log_exc("rollback recent files snapshot file", rollback_exc)
            if not save_json(self.index_path, self.index):
                LOGGER.error("Failed to rollback index after recent files update error.")

    def _on_recent_files_failed(self, sid: str, error: str) -> None:
        log_exc(f"recent files background scan ({sid})", Exception(error))

