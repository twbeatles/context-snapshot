from __future__ import annotations

import copy
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from PySide6 import QtWidgets

from ctxsnap.app_storage import app_dir, migrate_settings, migrate_snapshot, save_json
from ctxsnap.constants import APP_NAME
from ctxsnap.core.logging import get_logger
from ctxsnap.i18n import tr
from ctxsnap.ui.dialogs.settings import SettingsDialog
from ctxsnap.utils import log_exc, snapshot_mtime

LOGGER = get_logger()


class MainWindowSettingsBackupSection:
    def apply_settings(self, vals: Dict[str, Any], *, save: bool = True) -> bool:
        """Apply settings immediately (UI + hotkey)."""
        vals = migrate_settings(vals)
        vals["restore_profiles"] = self.restore_service.normalize_profiles(vals.get("restore_profiles", []))
        vals.setdefault("default_root", self.settings.get("default_root", str(Path.home())))
        vals.setdefault("onboarding_shown", self.settings.get("onboarding_shown", False))
        self.settings = vals
        if save:
            if not save_json(self.settings_path, self.settings):
                log_exc("save settings", RuntimeError("save_json returned False"))
                QtWidgets.QMessageBox.warning(self, tr("Error"), "Failed to save settings.")
                return False

        self._build_tag_menu()
        self._reset_pagination_and_refresh()

        if hasattr(self, "btn_quick"):
            self.btn_quick.setText(f"Quick Snapshot ({self.hotkey_label()})")
        self._build_menus()

        if callable(self.on_settings_applied):
            self.on_settings_applied()
        self._init_sync_engine()
        self._update_auto_snapshot_timer()
        self._update_backup_timer()
        self._update_sync_timer()
        self._apply_archive_policy()
        return True

    def _auto_backup_current(self) -> Path:
        backups = app_dir() / "backups"
        backups.mkdir(parents=True, exist_ok=True)
        bkp = backups / f"{APP_NAME}_autobackup_{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
        try:
            self.backup_service.export_backup(
                bkp,
                settings=self.settings,
                snaps_dir=self.snaps_dir,
                index_path=self.index_path,
                include_snapshots=True,
                include_index=True,
                encrypt_backup=False,
            )
        except Exception as e:
            log_exc("auto backup", e)
        return bkp

    def apply_imported_backup(self, payload: Dict[str, Any]) -> bool:
        """Apply imported backup: optionally merge/overwrite snapshots/index, then apply settings."""
        data = payload.get("data")
        safety_backup: Optional[Path] = None
        prev_index = copy.deepcopy(self.index)
        prev_settings = copy.deepcopy(self.settings)
        prev_snapshot_files: Dict[str, str] = {}

        try:
            if data:
                safety_backup = self._auto_backup_current()
                self.statusBar().showMessage(f"Safety backup created: {safety_backup.name}", 3500)

                msg = QtWidgets.QMessageBox(self)
                msg.setWindowTitle(tr("Import snapshots"))
                msg.setText(tr("Import snapshots strategy"))
                msg.setInformativeText(
                    tr("Merge strategy")
                    + "\n"
                    + tr("Overwrite strategy")
                    + "\n"
                    + tr("Replace strategy")
                )
                btn_merge = msg.addButton("Merge", QtWidgets.QMessageBox.AcceptRole)
                btn_overwrite = msg.addButton("Overwrite", QtWidgets.QMessageBox.DestructiveRole)
                btn_replace = msg.addButton("Replace all", QtWidgets.QMessageBox.DestructiveRole)
                btn_cancel = msg.addButton(tr("Cancel"), QtWidgets.QMessageBox.RejectRole)
                msg.exec()
                clicked = msg.clickedButton()
                if clicked == btn_cancel:
                    return False
                strategy = "merge" if clicked == btn_merge else ("overwrite" if clicked == btn_overwrite else "replace")

                imported_snaps = data.get("snapshots") or []
                imported_index = data.get("index") if isinstance(data.get("index"), dict) else None
                if not isinstance(imported_snaps, list):
                    raise ValueError("Invalid backup: snapshots field must be a list.")

                for f in self.snaps_dir.glob("*.json"):
                    prev_snapshot_files[f.name] = f.read_text(encoding="utf-8")

                if strategy == "replace":
                    for f in self.snaps_dir.glob("*.json"):
                        f.unlink(missing_ok=True)
                    self.index = {"snapshots": []}

                existing_ids = {str(it.get("id")) for it in self.index.get("snapshots", []) if it.get("id")}

                for raw_snap in imported_snaps:
                    if not isinstance(raw_snap, dict):
                        continue
                    snap = migrate_snapshot(dict(raw_snap))
                    sid = str(snap.get("id") or "").strip()
                    if not sid:
                        continue
                    if strategy == "merge" and sid in existing_ids:
                        continue

                    snap_path = self.snap_path(sid)
                    self._save_snapshot_or_raise(snap_path, snap, f"imported snapshot {sid}")
                    snap_mtime = snapshot_mtime(snap_path)
                    entry = self._index_entry_from_snapshot_data(snap, snap_mtime=snap_mtime)
                    if sid not in existing_ids:
                        self.index.setdefault("snapshots", []).append(entry)
                        existing_ids.add(sid)
                    elif strategy == "overwrite":
                        for it in self.index.get("snapshots", []):
                            if it.get("id") == sid:
                                it.update(entry)
                                break

                if imported_index and strategy in ("overwrite", "replace"):
                    migrated_index = {"snapshots": []}
                    for raw_item in imported_index.get("snapshots", []):
                        if not isinstance(raw_item, dict):
                            continue
                        item = dict(raw_item)
                        item.setdefault("tags", [])
                        item.setdefault("pinned", False)
                        item.setdefault("archived", False)
                        item.setdefault("vscode_workspace", "")
                        item.setdefault("source", "")
                        item.setdefault("trigger", "")
                        item.setdefault("auto_fingerprint", "")
                        item.setdefault("rev", 1)
                        item.setdefault("updated_at", item.get("created_at", ""))
                        if not isinstance(item.get("git_state"), dict):
                            item["git_state"] = {}
                        migrated_index["snapshots"].append(item)
                    self.index = migrated_index

                seen = set()
                dedup = []
                for it in self.index.get("snapshots", []):
                    sid = str(it.get("id") or "")
                    if not sid or sid in seen:
                        continue
                    seen.add(sid)
                    dedup.append(it)
                self.index["snapshots"] = dedup
                self.index = self.snapshot_service.touch_index(self.index)
                self._save_json_or_raise(self.index_path, self.index, "index after import")
                self._reset_pagination_and_refresh()

            if not self.apply_settings(payload.get("settings", {}), save=True):
                raise RuntimeError("Failed to apply imported settings.")
            return True

        except Exception as exc:
            log_exc("apply imported backup", exc if isinstance(exc, Exception) else Exception(str(exc)))

            try:
                if data:
                    for f in self.snaps_dir.glob("*.json"):
                        f.unlink(missing_ok=True)
                    for name, raw in prev_snapshot_files.items():
                        (self.snaps_dir / name).write_text(raw, encoding="utf-8")
            except Exception as rollback_exc:
                log_exc("rollback imported snapshots", rollback_exc)

            self.index = prev_index
            self.settings = prev_settings
            if not save_json(self.index_path, self.index):
                LOGGER.error("Failed to rollback index after import failure.")
            if not save_json(self.settings_path, self.settings):
                LOGGER.error("Failed to rollback settings after import failure.")
            self._reset_pagination_and_refresh()

            msg = "Import failed. Changes were rolled back."
            if safety_backup:
                msg += f"\nSafety backup: {safety_backup}"
            QtWidgets.QMessageBox.warning(self, tr("Error"), msg)
            return False

    def open_settings(self) -> None:
        dlg = SettingsDialog(self, self.settings, index_path=self.index_path, snaps_dir=self.snaps_dir)
        dlg.settingsImported.connect(self.apply_imported_backup)
        dlg.syncRequested.connect(self._run_scheduled_sync)
        if dlg.exec() != QtWidgets.QDialog.Accepted:
            return

        vals = dlg.values()
        payload = dlg.imported_payload()

        if payload and not dlg.import_apply_now():
            if not self.apply_imported_backup(payload):
                return
        else:
            if not self.apply_settings(vals, save=True):
                return

        self.statusBar().showMessage(tr("Settings applied status"), 2500)
