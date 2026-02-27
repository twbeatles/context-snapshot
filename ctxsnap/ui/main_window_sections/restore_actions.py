from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List

from PySide6 import QtWidgets

from ctxsnap.app_storage import append_restore_history, app_dir, now_iso, save_snapshot_file
from ctxsnap.i18n import tr
from ctxsnap.restore import open_folder, open_terminal_at, open_vscode_at, resolve_vscode_target
from ctxsnap.ui.dialogs.history import CompareDialog, RestoreHistoryDialog
from ctxsnap.ui.dialogs.restore import ChecklistDialog, RestorePreviewDialog
from ctxsnap.utils import restore_running_apps, safe_parse_datetime


class MainWindowRestoreActionsSection:
    def open_selected_root(self) -> None:
        sid = self.selected_id()
        if not sid:
            return
        snap = self.load_snapshot(sid)
        if not snap:
            return
        open_folder(Path(snap["root"]))

    def open_selected_vscode(self) -> None:
        sid = self.selected_id()
        if not sid:
            return
        snap = self.load_snapshot(sid)
        if not snap:
            return
        target = resolve_vscode_target(snap)
        success, msg = open_vscode_at(target)
        if not success:
            QtWidgets.QMessageBox.information(self, tr("VSCode not found title"), msg or tr("VSCode command missing"))

    def export_selected_snapshot(self) -> None:
        sid = self.selected_id()
        if not sid:
            return
        snap = self.load_snapshot(sid)
        if not snap:
            return
        default_name = f"snapshot_{sid}.json"
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Export snapshot", str(Path.home() / default_name), "JSON files (*.json)"
        )
        if not path:
            return
        if save_snapshot_file(Path(path), snap):
            self.statusBar().showMessage("Snapshot exported.", 2500)
        else:
            QtWidgets.QMessageBox.warning(self, tr("Error"), "Failed to export snapshot.")

    def export_weekly_report(self) -> None:
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Export weekly report", str(Path.home() / "ctxsnap_weekly_report.md"), "Markdown files (*.md)"
        )
        if not path:
            return
        cutoff = datetime.now() - timedelta(days=7)
        lines = ["# Weekly Snapshot Report", f"Generated: {now_iso()}", ""]
        for it in self.index.get("snapshots", []):
            created_at = safe_parse_datetime(it.get("created_at", ""))
            if not created_at:
                continue
            if created_at < cutoff:
                continue
            snap = self.load_snapshot(it.get("id", "")) or {}
            lines.append(f"## {snap.get('title','(no title)')}")
            lines.append(f"- Created: {snap.get('created_at','')}")
            lines.append(f"- Root: {snap.get('root','')}")
            tags = snap.get("tags", [])
            if tags:
                lines.append(f"- Tags: {', '.join(tags)}")
            todos = [t for t in snap.get("todos", []) if t]
            if todos:
                lines.append("### TODOs")
                lines.extend([f"- {t}" for t in todos])
            note = snap.get("note", "")
            if note:
                lines.append("### Note")
                lines.append(note)
            lines.append("")
        Path(path).write_text("\n".join(lines), encoding="utf-8")
        self.statusBar().showMessage("Weekly report exported.", 2500)

    def open_compare_dialog(self) -> None:
        snapshots = [s for s in self.index.get("snapshots", []) if s.get("id")]
        if len(snapshots) < 2:
            QtWidgets.QMessageBox.information(self, tr("Compare"), tr("Need at least two snapshots to compare"))
            return
        dlg = CompareDialog(self, snapshots, loader=self.load_snapshot)
        dlg.exec()

    def open_restore_history(self) -> None:
        history_path = app_dir() / "restore_history.json"
        if not history_path.exists():
            QtWidgets.QMessageBox.information(self, tr("Restore History"), tr("No restore history yet"))
            return
        try:
            history = json.loads(history_path.read_text(encoding="utf-8"))
        except Exception:
            history = {"restores": []}
        dlg = RestoreHistoryDialog(self, history)
        dlg.exec()

    def restore_last(self) -> None:
        items = self.index.get("snapshots", [])
        if not items:
            return
        sid = items[0].get("id")
        if not sid:
            return
        self._restore_by_id(sid)

    def restore_selected(self) -> None:
        sid = self.selected_id()
        if not sid:
            return
        self._restore_by_id(sid)

    def _restore_by_id(self, sid: str) -> None:
        snap = self.load_snapshot(sid)
        if not snap:
            QtWidgets.QMessageBox.warning(self, tr("Error"), tr("Snapshot file missing"))
            return

        restore_defaults = self.restore_service.default_restore_options(self.settings)
        open_folder_default = bool(restore_defaults.get("open_folder", True))
        open_terminal_default = bool(restore_defaults.get("open_terminal", True))
        open_vscode_default = bool(restore_defaults.get("open_vscode", True))
        open_running_apps_default = bool(restore_defaults.get("open_running_apps", False))
        show_checklist_default = bool(restore_defaults.get("show_checklist", True))
        profile_default = str(restore_defaults.get("profile_name", "") or "")
        profile_enabled = bool(self.settings.get("dev_flags", {}).get("restore_profiles_enabled", False))
        profiles = self.restore_service.normalize_profiles(self.settings.get("restore_profiles", [])) if profile_enabled else []
        preview_default = bool(self.settings.get("restore_preview_default", True))

        if preview_default:
            dlg = RestorePreviewDialog(
                self,
                snap,
                open_folder_default,
                open_terminal_default,
                open_vscode_default,
                open_running_apps_default,
                profiles=profiles,
                selected_profile=profile_default,
            )
            if dlg.exec() != QtWidgets.QDialog.Accepted:
                return
            ch = dlg.choices()
            if ch.get("profile_name"):
                ch = self.restore_service.apply_profile(self.settings, str(ch.get("profile_name")), ch)
        else:
            ch = {
                "open_folder": open_folder_default,
                "open_terminal": open_terminal_default,
                "open_vscode": open_vscode_default,
                "open_running_apps": open_running_apps_default,
                "show_checklist": show_checklist_default,
                "profile_name": profile_default,
            }
        show_checklist = bool(ch.get("show_checklist", show_checklist_default))

        root = Path(snap["root"]).expanduser()
        root_missing = False
        errors: List[str] = []

        if ch.get("open_folder"):
            success, error = open_folder(root)
            if not success:
                root_missing = True
                errors.append(f"{tr('Restore open folder failed')} {error}")

        if ch.get("open_terminal"):
            success, error = open_terminal_at(root)
            if not success:
                root_missing = True
                errors.append(f"{tr('Restore open terminal failed')} {error}")

        vscode_opened = False
        if ch.get("open_vscode"):
            target = resolve_vscode_target(snap)
            success, error = open_vscode_at(target)
            vscode_opened = success
            if not success:
                errors.append(f"{tr('Restore open vscode failed')} {error}")

        requested_apps = []
        if ch.get("open_running_apps"):
            requested_apps = ch.get("running_apps") or snap.get("running_apps", [])
            running_app_failures = restore_running_apps(requested_apps, parent=self)
        else:
            running_app_failures = []

        append_restore_history(
            {
                "snapshot_id": sid,
                "created_at": now_iso(),
                "profile_name": str(ch.get("profile_name", "") or ""),
                "open_folder": bool(ch.get("open_folder")),
                "open_terminal": bool(ch.get("open_terminal")),
                "open_vscode": bool(ch.get("open_vscode")),
                "open_running_apps": bool(ch.get("open_running_apps")),
                "running_apps_requested": len(requested_apps),
                "running_apps_failed": running_app_failures,
                "running_apps_failed_count": len(running_app_failures),
                "root_missing": root_missing,
                "vscode_opened": vscode_opened,
            }
        )

        if errors:
            QtWidgets.QMessageBox.warning(
                self,
                tr("Restore"),
                tr("Restore failed for some items:") + "\n" + "\n".join(errors),
            )

        if show_checklist:
            todos = snap.get("todos", [])
            if any(todos):
                dlg = ChecklistDialog(self, [t for t in todos if t])
                dlg.exec()
        self.statusBar().showMessage("Restore triggered.", 2500)
