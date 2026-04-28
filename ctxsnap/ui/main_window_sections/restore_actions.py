from __future__ import annotations

# pyright: reportAttributeAccessIssue=false

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, cast

from PySide6 import QtWidgets

from ctxsnap.app_storage import append_restore_history, app_dir, now_iso, save_snapshot_file
from ctxsnap.i18n import tr
from ctxsnap.restore import open_folder, open_terminal_at, open_vscode_at, resolve_vscode_target
from ctxsnap.ui.dialogs.history import CompareDialog, RestoreHistoryDialog, SyncConflictsDialog
from ctxsnap.ui.dialogs.restore import ChecklistDialog, RestorePreviewDialog
from ctxsnap.utils import restore_running_apps, safe_parse_datetime


class MainWindowRestoreActionsSection:
    @staticmethod
    def _parent_widget(instance: object) -> QtWidgets.QWidget:
        return cast(QtWidgets.QWidget, instance)

    def _prompt_sensitive_export_mode(
        self,
        *,
        title: str,
        has_sensitive: bool,
        has_security_error: bool,
    ) -> Optional[str]:
        if not has_sensitive and not has_security_error:
            return "full"
        msg = QtWidgets.QMessageBox(self._parent_widget(self))
        msg.setWindowTitle(title)
        msg.setIcon(QtWidgets.QMessageBox.Icon.Warning)
        msg.setText("This export may include sensitive data.")
        details: List[str] = []
        if has_sensitive:
            details.append("Sensitive note, TODO, process, or running-app data is included.")
        if has_security_error:
            details.append("Some encrypted fields could not be decrypted on this machine.")
        details.append("Choose a redacted export to remove sensitive content.")
        msg.setInformativeText("\n".join(details))
        btn_full = msg.addButton("Full export", QtWidgets.QMessageBox.ButtonRole.AcceptRole)
        btn_redacted = msg.addButton("Redacted export", QtWidgets.QMessageBox.ButtonRole.ActionRole)
        msg.addButton(tr("Cancel"), QtWidgets.QMessageBox.ButtonRole.RejectRole)
        msg.exec()
        clicked = msg.clickedButton()
        if clicked == btn_full:
            return "full"
        if clicked == btn_redacted:
            return "redacted"
        return None

    @staticmethod
    def _snapshot_has_sensitive_payload(snap: Dict[str, Any]) -> bool:
        if not isinstance(snap, dict):
            return False
        if str(snap.get("note", "") or "").strip():
            return True
        if any(str(item or "").strip() for item in (snap.get("todos", []) or [])):
            return True
        if bool(snap.get("processes")) or bool(snap.get("running_apps")):
            return True
        if str(snap.get("root", "") or "").strip() or str(snap.get("vscode_workspace", "") or "").strip():
            return True
        if bool(snap.get("recent_files")) or bool(snap.get("git_state")):
            return True
        envelope = snap.get("sensitive")
        return isinstance(envelope, dict) and bool(envelope)

    @staticmethod
    def _snapshot_export_payload(snap: Dict[str, Any], *, redacted: bool) -> Dict[str, Any]:
        out = dict(snap)
        out.pop("_security_error", None)
        if not redacted:
            return out
        out.pop("sensitive", None)
        out.pop("note", None)
        out.pop("todos", None)
        out.pop("processes", None)
        out.pop("running_apps", None)
        out.pop("root", None)
        out.pop("vscode_workspace", None)
        out.pop("recent_files", None)
        out.pop("git_state", None)
        out.pop("auto_fingerprint", None)
        out.pop("source", None)
        out.pop("trigger", None)
        out["title"] = "(redacted snapshot)"
        out["tags"] = []
        return out

    @staticmethod
    def _weekly_report_lines(snaps: List[Dict[str, Any]], *, redacted: bool) -> List[str]:
        lines = ["# Weekly Snapshot Report", f"Generated: {now_iso()}", ""]
        for snap in snaps:
            lines.append("## (redacted snapshot)" if redacted else f"## {snap.get('title','(no title)')}")
            lines.append(f"- Created: {snap.get('created_at','')}")
            if redacted:
                lines.append("- Root: (redacted)")
            else:
                lines.append(f"- Root: {snap.get('root','')}")
            tags = [] if redacted else snap.get("tags", [])
            if tags:
                lines.append(f"- Tags: {', '.join(str(tag) for tag in tags)}")
            todos = [str(t) for t in snap.get("todos", []) if str(t).strip()]
            if todos:
                lines.append("### TODOs")
                if redacted:
                    lines.append("- (redacted)")
                else:
                    lines.extend([f"- {t}" for t in todos])
            note = str(snap.get("note", "") or "")
            if note:
                lines.append("### Note")
                lines.append("(redacted)" if redacted else note)
            lines.append("")
        return lines

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
            QtWidgets.QMessageBox.information(
                self._parent_widget(self),
                tr("VSCode not found title"),
                msg or tr("VSCode command missing"),
            )

    def export_selected_snapshot(self) -> None:
        sid = self.selected_id()
        if not sid:
            return
        snap = self.load_snapshot(sid)
        if not snap:
            return
        export_mode = self._prompt_sensitive_export_mode(
            title="Export snapshot",
            has_sensitive=self._snapshot_has_sensitive_payload(snap),
            has_security_error=bool(str(snap.get("_security_error", "") or "").strip()),
        )
        if not export_mode:
            return
        default_name = f"snapshot_{sid}.json"
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self._parent_widget(self),
            "Export snapshot",
            str(Path.home() / default_name),
            "JSON files (*.json)",
        )
        if not path:
            return
        if save_snapshot_file(
            Path(path),
            self._snapshot_export_payload(snap, redacted=(export_mode == "redacted")),
        ):
            self.statusBar().showMessage("Snapshot exported.", 2500)
        else:
            QtWidgets.QMessageBox.warning(
                self._parent_widget(self),
                tr("Error"),
                "Failed to export snapshot.",
            )

    def export_weekly_report(self) -> None:
        cutoff = datetime.now() - timedelta(days=7)
        snaps: List[Dict[str, Any]] = []
        has_sensitive = False
        has_security_error = False
        for it in self.index.get("snapshots", []):
            created_at = safe_parse_datetime(it.get("created_at", ""))
            if not created_at:
                continue
            if created_at < cutoff:
                continue
            snap = self.load_snapshot(it.get("id", "")) or {}
            snaps.append(snap)
            has_sensitive = has_sensitive or self._snapshot_has_sensitive_payload(snap)
            has_security_error = has_security_error or bool(str(snap.get("_security_error", "") or "").strip())
        export_mode = self._prompt_sensitive_export_mode(
            title="Export weekly report",
            has_sensitive=has_sensitive,
            has_security_error=has_security_error,
        )
        if not export_mode:
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self._parent_widget(self),
            "Export weekly report",
            str(Path.home() / "ctxsnap_weekly_report.md"),
            "Markdown files (*.md)",
        )
        if not path:
            return
        lines = self._weekly_report_lines(snaps, redacted=(export_mode == "redacted"))
        Path(path).write_text("\n".join(lines), encoding="utf-8")
        self.statusBar().showMessage("Weekly report exported.", 2500)

    def open_compare_dialog(self) -> None:
        snapshots = [s for s in self.index.get("snapshots", []) if s.get("id")]
        if len(snapshots) < 2:
            QtWidgets.QMessageBox.information(
                self._parent_widget(self),
                tr("Compare"),
                tr("Need at least two snapshots to compare"),
            )
            return
        dlg = CompareDialog(self._parent_widget(self), snapshots, loader=self.load_snapshot)
        dlg.exec()

    def open_restore_history(self) -> None:
        history_path = app_dir() / "restore_history.json"
        if not history_path.exists():
            QtWidgets.QMessageBox.information(
                self._parent_widget(self),
                tr("Restore History"),
                tr("No restore history yet"),
            )
            return
        try:
            history = json.loads(history_path.read_text(encoding="utf-8"))
        except Exception:
            history = {"restores": []}
        dlg = RestoreHistoryDialog(self._parent_widget(self), history)
        dlg.restoreRequested.connect(self._restore_by_id)
        dlg.exec()

    def open_sync_conflicts(self) -> None:
        conflicts_path = app_dir() / "sync_conflicts.json"
        if not conflicts_path.exists():
            QtWidgets.QMessageBox.information(
                self._parent_widget(self),
                tr("Sync Conflicts"),
                tr("No sync conflicts yet"),
            )
            return
        try:
            conflicts = json.loads(conflicts_path.read_text(encoding="utf-8"))
        except Exception:
            conflicts = {"conflicts": []}
        if not conflicts.get("conflicts"):
            QtWidgets.QMessageBox.information(
                self._parent_widget(self),
                tr("Sync Conflicts"),
                tr("No sync conflicts yet"),
            )
            return
        dlg = SyncConflictsDialog(self._parent_widget(self), conflicts)
        dlg.exec()

    def restore_last(self) -> None:
        item = self.snapshot_service.latest_snapshot_item(self.index.get("snapshots", []))
        if not item:
            return
        sid = item.get("id")
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
            QtWidgets.QMessageBox.warning(
                self._parent_widget(self),
                tr("Error"),
                tr("Snapshot file missing"),
            )
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
                self._parent_widget(self),
                snap,
                open_folder_default,
                open_terminal_default,
                open_vscode_default,
                open_running_apps_default,
                show_checklist=show_checklist_default,
                profiles=profiles,
                selected_profile=profile_default,
            )
            if dlg.exec() != QtWidgets.QDialog.DialogCode.Accepted:
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
            running_app_failures = restore_running_apps(
                requested_apps,
                parent=self._parent_widget(self),
            )
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
                self._parent_widget(self),
                tr("Restore"),
                tr("Restore failed for some items:") + "\n" + "\n".join(errors),
            )

        if show_checklist:
            todos = snap.get("todos", [])
            if any(todos):
                dlg = ChecklistDialog(self._parent_widget(self), [t for t in todos if t])
                dlg.exec()
        self.statusBar().showMessage("Restore triggered.", 2500)
