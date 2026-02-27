from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from PySide6 import QtCore, QtWidgets

from ctxsnap.app_storage import Snapshot, gen_id, migrate_snapshot, now_iso, save_json, save_snapshot_file
from ctxsnap.constants import DEFAULT_TAGS
from ctxsnap.core.logging import get_logger
from ctxsnap.i18n import tr
from ctxsnap.ui.dialogs.snapshot import EditSnapshotDialog, SnapshotDialog
from ctxsnap.utils import (
    build_search_blob,
    git_state_details,
    list_processes_filtered,
    list_running_apps,
    log_exc,
    recent_files_under,
    snapshot_mtime,
)

LOGGER = get_logger()


class MainWindowSnapshotCrudSection:
    def snap_path(self, sid: str) -> Path:
        return self.snaps_dir / f"{sid}.json"

    def _save_json_or_raise(self, path: Path, data: Dict[str, Any], label: str) -> None:
        if not save_json(path, data):
            raise RuntimeError(f"Failed to save {label}: {path}")

    def _save_snapshot_or_raise(self, path: Path, snap: Dict[str, Any], label: str) -> None:
        if not save_snapshot_file(path, snap):
            raise RuntimeError(f"Failed to save {label}: {path}")

    @staticmethod
    def _index_entry_from_snapshot_data(snap: Dict[str, Any], *, snap_mtime: float = 0.0) -> Dict[str, Any]:
        return {
            "id": snap.get("id", ""),
            "title": snap.get("title", ""),
            "created_at": snap.get("created_at", ""),
            "updated_at": snap.get("updated_at", snap.get("created_at", "")),
            "rev": int(snap.get("rev", 1) or 1),
            "root": snap.get("root", ""),
            "vscode_workspace": snap.get("vscode_workspace", ""),
            "tags": snap.get("tags", []),
            "pinned": bool(snap.get("pinned", False)),
            "archived": bool(snap.get("archived", False)),
            "search_blob": build_search_blob(snap),
            "search_blob_mtime": snap_mtime,
            "source": snap.get("source", ""),
            "trigger": snap.get("trigger", ""),
            "git_state": snap.get("git_state", {}),
            "auto_fingerprint": snap.get("auto_fingerprint", ""),
        }

    @staticmethod
    def _normalized_todos(todos: List[str]) -> List[str]:
        out = [str(t or "").strip() for t in todos[:3]]
        while len(out) < 3:
            out.append("")
        return out

    @staticmethod
    def _normalized_tags(tags: List[str]) -> List[str]:
        return [str(t).strip() for t in tags if str(t).strip()]

    @staticmethod
    def _auto_title(root_path: Path) -> str:
        return f"Auto: {root_path.name or str(root_path)} @ {datetime.now().strftime('%Y-%m-%d %H:%M')}"

    @staticmethod
    def _safe_path_equals(path_a: str, path_b: Path) -> bool:
        try:
            return Path(path_a).resolve() == path_b.resolve()
        except Exception:
            return False

    def _auto_seed_snapshot(self, root_path: Path) -> Optional[Dict[str, Any]]:
        # 1) latest snapshot for the same root, 2) latest snapshot globally
        for it in self.index.get("snapshots", []):
            if not self._safe_path_equals(str(it.get("root", "")), root_path):
                continue
            sid = str(it.get("id") or "").strip()
            if not sid:
                continue
            snap = self.load_snapshot(sid)
            if snap:
                return snap
        for it in self.index.get("snapshots", []):
            sid = str(it.get("id") or "").strip()
            if not sid:
                continue
            snap = self.load_snapshot(sid)
            if snap:
                return snap
        return None

    def _auto_git_state(self, root_path: Path) -> Dict[str, Any]:
        state = git_state_details(root_path)
        if not state:
            return {}
        return {
            "branch": str(state.get("branch", "")),
            "sha": str(state.get("sha", "")),
            "dirty": bool(state.get("dirty", False)),
            "changed": int(state.get("changed", 0) or 0),
            "staged": int(state.get("staged", 0) or 0),
            "untracked": int(state.get("untracked", 0) or 0),
        }

    def _auto_fingerprint(
        self,
        *,
        root: str,
        workspace: str,
        note: str,
        todos: List[str],
        tags: List[str],
        git_state_data: Dict[str, Any],
    ) -> str:
        payload = {
            "root": root,
            "workspace": workspace,
            "note": note,
            "todos": self._normalized_todos(todos),
            "tags": self._normalized_tags(tags),
            "git_state": git_state_data,
        }
        raw = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _is_duplicate_auto_snapshot(self, root_path: Path, auto_fingerprint: str) -> bool:
        root = str(root_path.resolve())
        for it in self.index.get("snapshots", []):
            if str(it.get("root", "")) != root:
                continue
            source = str(it.get("source", ""))
            if source not in {"auto_timer", "auto_git"}:
                continue
            return str(it.get("auto_fingerprint", "")) == auto_fingerprint
        return False

    def load_snapshot(self, sid: str) -> Optional[Dict[str, Any]]:
        p = self.snap_path(sid)
        if not p.exists():
            return None
        try:
            snap = migrate_snapshot(json.loads(p.read_text(encoding="utf-8")))
            return self.security_service.decrypt_snapshot_sensitive_fields(snap)
        except (json.JSONDecodeError, Exception) as e:
            log_exc(f"load snapshot {sid}", e)
            return None

    def save_snapshot(self, snap: Snapshot) -> bool:
        snap_path = self.snap_path(snap.id)
        prev_index = copy.deepcopy(self.index)
        prev_settings = copy.deepcopy(self.settings)
        prev_snapshot_raw = snap_path.read_text(encoding="utf-8") if snap_path.exists() else None

        try:
            snap_data = self.snapshot_service.prepare_new_snapshot(asdict(snap))
            if not snap_data.get("updated_at"):
                snap_data["updated_at"] = now_iso()
            if bool(self.settings.get("dev_flags", {}).get("security_enabled", False)):
                snap_data = self.security_service.encrypt_snapshot_sensitive_fields(snap_data, self.settings)
                LOGGER.info("security_encrypt snapshot_id=%s", snap.id)
            self._save_snapshot_or_raise(snap_path, snap_data, f"snapshot {snap.id}")
            snap_mtime = snapshot_mtime(snap_path)
            self.index["snapshots"].insert(
                0,
                self._index_entry_from_snapshot_data(snap_data, snap_mtime=snap_mtime),
            )
            self.index = self.snapshot_service.touch_index(self.index)
            self._save_json_or_raise(self.index_path, self.index, "index")
            self.settings["default_root"] = snap.root
            self._save_json_or_raise(self.settings_path, self.settings, "settings")
            return True
        except Exception as exc:
            log_exc("save snapshot", exc if isinstance(exc, Exception) else Exception(str(exc)))
            self.index = prev_index
            self.settings = prev_settings
            try:
                if prev_snapshot_raw is None:
                    snap_path.unlink(missing_ok=True)
                else:
                    snap_path.write_text(prev_snapshot_raw, encoding="utf-8")
            except Exception as rollback_exc:
                log_exc("rollback snapshot file", rollback_exc)
            if not save_json(self.index_path, self.index):
                LOGGER.error("Failed to rollback index file after snapshot save error.")
            if not save_json(self.settings_path, self.settings):
                LOGGER.error("Failed to rollback settings file after snapshot save error.")
            return False

    # ----- selection rendering -----
    def on_select(self, current: QtCore.QModelIndex, previous: QtCore.QModelIndex) -> None:
        if not current.isValid():
            self.detail_title.setText(tr("No snapshot selected"))
            self.detail_meta.setText("")
            self.detail.setText(tr("Select a snapshot to see details."))
            return
        sid = self.selected_id()
        if not sid:
            return
        snap = self.load_snapshot(sid)
        if not snap:
            self.detail_title.setText("Snapshot file missing")
            self.detail_meta.setText("")
            self.detail.setText("")
            return

        self.detail_title.setText(snap.get("title", sid))
        tags = snap.get("tags", [])
        pinned = "📌" if bool(snap.get("pinned", False)) else ""
        archived = "🗄️ " if bool(snap.get("archived", False)) else ""
        ws = snap.get("vscode_workspace", "")
        ws_line = f"  •  workspace: {ws}" if ws else ""
        tag_line = f"  •  tags: {', '.join(tags)}" if tags else ""
        self.detail_meta.setText(
            f"{archived}{pinned}{snap.get('created_at','')}  •  {snap.get('root','')}{ws_line}{tag_line}"
        )

        todos = snap.get("todos", [])
        recent = snap.get("recent_files", [])
        proc = snap.get("processes", [])
        running_apps = snap.get("running_apps", [])
        
        text = (
            f"NOTE:\n{snap.get('note','') or '(none)'}\n\n"
            f"TODOs:\n"
            f"  1) {todos[0] if len(todos)>0 else ''}\n"
            f"  2) {todos[1] if len(todos)>1 else ''}\n"
            f"  3) {todos[2] if len(todos)>2 else ''}\n\n"
            f"Recent files (top 12):\n" +
            "".join([f"  - {p}\n" for p in recent[:12]]) +
            f"\nProcesses (filtered, {len(proc)}):\n" +
            "".join([f"  - {p.get('name','')}   {p.get('exe','')}\n" for p in proc[:20]]) +
            f"\nRunning apps (taskbar, {len(running_apps)}):\n" +
            "".join([f"  - {p.get('name','')}   {p.get('exe','')}\n" for p in running_apps[:20]])
        )
        self.detail.setText(text)

    # ----- actions -----
    def edit_selected(self) -> None:
        """Open edit dialog for the selected snapshot."""
        sid = self.selected_id()
        if not sid:
            self.statusBar().showMessage(tr("No snapshot selected"), 2000)
            return
        snap = self.load_snapshot(sid)
        if not snap:
            QtWidgets.QMessageBox.warning(self, tr("Error"), tr("Snapshot file missing"))
            return
        
        dlg = EditSnapshotDialog(
            self,
            snap,
            self.settings.get("tags", DEFAULT_TAGS),
            self.settings.get("templates", []),
            enforce_todos=bool(self.settings.get("capture_enforce_todos", True)),
        )
        if dlg.exec() != QtWidgets.QDialog.Accepted:
            return
        
        v = dlg.values()
        self._update_snapshot(
            sid,
            title=v["title"],
            root=v["root"],
            workspace=v["workspace"],
            note=v["note"],
            todos=v["todos"],
            tags=v["tags"],
        )
        self.statusBar().showMessage(tr("Snapshot Updated"), 2500)
    
    def _update_snapshot(
        self,
        sid: str,
        *,
        title: str,
        root: str,
        workspace: str,
        note: str,
        todos: List[str],
        tags: List[str],
    ) -> None:
        """Update an existing snapshot with new data."""
        snap = self.load_snapshot(sid)
        if not snap:
            return

        prev_snap = copy.deepcopy(snap)
        prev_index = copy.deepcopy(self.index)
        prev_settings = copy.deepcopy(self.settings)
        snap_path = self.snap_path(sid)

        try:
            # Update snapshot fields
            snap["title"] = title
            snap["root"] = root
            snap["vscode_workspace"] = workspace
            snap["note"] = note
            snap["todos"] = self._normalized_todos(todos)
            snap["tags"] = self._normalized_tags(tags)
            snap = self.snapshot_service.touch_snapshot(snap)
            if bool(self.settings.get("dev_flags", {}).get("security_enabled", False)):
                snap = self.security_service.encrypt_snapshot_sensitive_fields(snap, self.settings)
                LOGGER.info("security_encrypt snapshot_id=%s", sid)

            # Write updated snapshot file
            self._save_snapshot_or_raise(snap_path, snap, f"snapshot {sid}")
            snap_mtime = snapshot_mtime(snap_path)

            # Update index entry
            for it in self.index.get("snapshots", []):
                if it.get("id") == sid:
                    it.update(self._index_entry_from_snapshot_data(snap, snap_mtime=snap_mtime))
                    break
            self.index = self.snapshot_service.touch_index(self.index)
            self._save_json_or_raise(self.index_path, self.index, "index")

            # Update default_root setting
            self.settings["default_root"] = root
            self._save_json_or_raise(self.settings_path, self.settings, "settings")
        except Exception as exc:
            log_exc("update snapshot", exc if isinstance(exc, Exception) else Exception(str(exc)))
            self.index = prev_index
            self.settings = prev_settings
            try:
                self._save_snapshot_or_raise(snap_path, prev_snap, f"snapshot rollback {sid}")
            except Exception as rollback_exc:
                log_exc("rollback snapshot update file", rollback_exc)
            if not save_json(self.index_path, self.index):
                LOGGER.error("Failed to rollback index file after update error.")
            if not save_json(self.settings_path, self.settings):
                LOGGER.error("Failed to rollback settings file after update error.")
            QtWidgets.QMessageBox.warning(self, tr("Error"), f"Failed to update snapshot: {sid}")
            return

        # Refresh UI
        self.refresh_list(reset_page=False)
        self.on_select(self.listw.currentIndex(), QtCore.QModelIndex())

    def new_snapshot(self) -> None:
        dlg = SnapshotDialog(
            self,
            self.settings.get("default_root", str(Path.home())),
            self.settings.get("tags", DEFAULT_TAGS),
            self.settings.get("templates", []),
            enforce_todos=bool(self.settings.get("capture_enforce_todos", True)),
        )
        if dlg.exec() != QtWidgets.QDialog.Accepted:
            return
        v = dlg.values()
        self._create_snapshot(v["root"], v["title"], v["workspace"], v["note"], v["todos"], v["tags"])

    def quick_snapshot(self) -> None:
        dlg = SnapshotDialog(
            self,
            self.settings.get("default_root", str(Path.home())),
            self.settings.get("tags", DEFAULT_TAGS),
            self.settings.get("templates", []),
            enforce_todos=bool(self.settings.get("capture_enforce_todos", True)),
        )
        dlg.setWindowTitle(f"{tr('Quick Snapshot')} ({self.hotkey_label()})")

        if dlg.exec() != QtWidgets.QDialog.Accepted:
            return
        v = dlg.values()
        self._create_snapshot(v["root"], v["title"], v["workspace"], v["note"], v["todos"], v["tags"])

    def _create_snapshot(
        self,
        root: str,
        title: str,
        workspace: str,
        note: str,
        todos: List[str],
        tags: List[str],
        *,
        source: str = "",
        trigger: str = "",
        git_state_data: Optional[Dict[str, str]] = None,
        auto_fingerprint: str = "",
        check_duplicate: bool = True,
        status_prefix: str = "Saved snapshot",
    ) -> None:
        root_path = Path(root).resolve()

        # Check for duplication (same root and title in active snapshots)
        if check_duplicate:
            for it in self.index.get("snapshots", []):
                if bool(it.get("archived", False)):
                    continue
                if it.get("title") == title and self._safe_path_equals(str(it.get("root", "")), root_path):
                    r = QtWidgets.QMessageBox.warning(
                        self,
                        tr("Duplicate Snapshot"),
                        tr("Duplicate snapshot warn"),
                        QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
                    )
                    if r != QtWidgets.QMessageBox.Yes:
                        return
                    break
        ws = workspace.strip()
        if not ws:
            # if exactly one workspace file exists under root, use it
            wss = list(root_path.glob("*.code-workspace"))
            if len(wss) == 1:
                ws = str(wss[0].resolve())
        sid = gen_id()
        capture = self.settings.get("capture", {})
        capture_recent = bool(capture.get("recent_files", True))
        capture_processes = bool(capture.get("processes", True))
        capture_running_apps = bool(capture.get("running_apps", True))
        capture_note = bool(self.settings.get("capture_note", True))
        capture_todos = bool(self.settings.get("capture_todos", True))
        background_recent = bool(self.settings.get("recent_files_background", False))
        recent_files: List[str] = []
        if capture_recent and not background_recent:
            recent_files = recent_files_under(
                root_path,
                limit=int(self.settings.get("recent_files_limit", 30)),
                exclude_dirs=self.settings.get("recent_files_exclude", []),
                include_patterns=self.settings.get("recent_files_include", []),
                exclude_patterns=self.settings.get("recent_files_exclude_patterns", []),
                scan_limit=int(self.settings.get("recent_files_scan_limit", 20000)),
                scan_seconds=float(self.settings.get("recent_files_scan_seconds", 2.0)),
            )
        snapshot_note = note if capture_note else ""
        snapshot_todos = self._normalized_todos(todos) if capture_todos else ["", "", ""]
        process_keywords = self.settings.get("process_keywords", [])
        effective_git_state = git_state_data if git_state_data is not None else self._auto_git_state(root_path)
        snap = Snapshot(
            id=sid,
            title=title,
            created_at=now_iso(),
            root=str(root_path),
            vscode_workspace=ws,
            note=snapshot_note,
            todos=snapshot_todos,
            tags=self._normalized_tags(tags),
            pinned=False,
            archived=False,
            recent_files=recent_files,
            processes=list_processes_filtered(process_keywords) if capture_processes else [],
            running_apps=list_running_apps() if capture_running_apps else [],
            source=source,
            trigger=trigger,
            git_state=effective_git_state or {},
            auto_fingerprint=auto_fingerprint,
        )
        if not self.save_snapshot(snap):
            QtWidgets.QMessageBox.warning(self, tr("Error"), f"Failed to save snapshot: {sid}")
            return
        if capture_recent and background_recent:
            self._start_recent_files_scan(sid, root_path)
        self._reset_pagination_and_refresh()
        if self.list_model.rowCount() > 0:
            self.listw.setCurrentIndex(self.list_model.index(0, 0))
        self.statusBar().showMessage(f"{status_prefix}: {sid}", 3500)

    def _update_snapshot_meta(
        self,
        sid: str,
        *,
        pinned: Optional[bool] = None,
        archived: Optional[bool] = None,
        tags: Optional[List[str]] = None,
    ) -> None:
        """Update snapshot file + index with given metadata."""
        snap = self.load_snapshot(sid)
        if not snap:
            return
        prev_snap = copy.deepcopy(snap)
        prev_index = copy.deepcopy(self.index)
        snap_path = self.snap_path(sid)
        try:
            if pinned is not None:
                snap["pinned"] = bool(pinned)
            if archived is not None:
                snap["archived"] = bool(archived)
            if tags is not None:
                snap["tags"] = self._normalized_tags(tags)
            snap = self.snapshot_service.touch_snapshot(snap)
            if bool(self.settings.get("dev_flags", {}).get("security_enabled", False)):
                snap = self.security_service.encrypt_snapshot_sensitive_fields(snap, self.settings)
            self._save_snapshot_or_raise(snap_path, snap, f"snapshot meta {sid}")
            snap_mtime = snapshot_mtime(snap_path)

            # update index
            for it in self.index.get("snapshots", []):
                if it.get("id") == sid:
                    it.update(self._index_entry_from_snapshot_data(snap, snap_mtime=snap_mtime))
                    break
            self.index = self.snapshot_service.touch_index(self.index)
            self._save_json_or_raise(self.index_path, self.index, "index")
        except Exception as exc:
            log_exc("update snapshot meta", exc if isinstance(exc, Exception) else Exception(str(exc)))
            self.index = prev_index
            try:
                self._save_snapshot_or_raise(snap_path, prev_snap, f"snapshot meta rollback {sid}")
            except Exception as rollback_exc:
                log_exc("rollback snapshot meta file", rollback_exc)
            if not save_json(self.index_path, self.index):
                LOGGER.error("Failed to rollback index file after meta update error.")
            QtWidgets.QMessageBox.warning(self, tr("Error"), f"Failed to update snapshot metadata: {sid}")

    def toggle_pin(self) -> None:
        sid = self.selected_id()
        if not sid:
            return
        snap = self.load_snapshot(sid)
        if not snap:
            return
        new_state = not bool(snap.get("pinned", False))
        self._update_snapshot_meta(sid, pinned=new_state)
        self.refresh_list(reset_page=False)
        self.statusBar().showMessage("Pinned." if new_state else "Unpinned.", 2000)

    def toggle_archive(self) -> None:
        sid = self.selected_id()
        if not sid:
            return
        snap = self.load_snapshot(sid)
        if not snap:
            return
        new_state = not bool(snap.get("archived", False))
        self._update_snapshot_meta(sid, archived=new_state)
        self._reset_pagination_and_refresh()
        self.statusBar().showMessage("Archived." if new_state else "Unarchived.", 2000)

    def delete_selected(self) -> None:
        sid = self.selected_id()
        if not sid:
            return
        r = QtWidgets.QMessageBox.question(
            self,
            tr("Delete snapshot?"),
            tr("Delete confirm msg"),
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
        )
        if r != QtWidgets.QMessageBox.Yes:
            return
        p = self.snap_path(sid)
        if p.exists():
            try:
                p.unlink()
            except Exception as e:
                log_exc("delete snapshot file", e)
                QtWidgets.QMessageBox.warning(
                    self,
                    tr("Error"),
                    tr("Failed to delete snapshot file") + f": {e}"
                )
                return
        self.index["snapshots"] = [x for x in self.index.get("snapshots", []) if x.get("id") != sid]
        self.index = self.snapshot_service.touch_index(self.index)
        if not save_json(self.index_path, self.index):
            QtWidgets.QMessageBox.warning(self, tr("Error"), "Failed to save index after delete.")
            return
        self._reset_pagination_and_refresh()
        if self.list_model.rowCount() > 0:
            self.listw.setCurrentIndex(self.list_model.index(0, 0))
        else:
            self.on_select(QtCore.QModelIndex(), QtCore.QModelIndex())
        self.statusBar().showMessage(tr("Deleted"), 2000)

