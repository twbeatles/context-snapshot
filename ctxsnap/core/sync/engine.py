from __future__ import annotations

import copy
import hashlib
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ctxsnap.app_storage import load_json, migrate_snapshot, now_iso, save_json, save_snapshot_file
from ctxsnap.constants import APP_NAME
from ctxsnap.core.sync.base import SyncConflict, SyncPayload, SyncProvider, snapshot_sort_key
from ctxsnap.utils import build_search_blob

LOGGER = logging.getLogger(APP_NAME)


class SyncEngine:
    """Bidirectional sync engine with conflict queue recording."""

    def __init__(
        self,
        *,
        provider: SyncProvider,
        local_index_path: Path,
        local_snaps_dir: Path,
        conflicts_path: Path,
        state_path: Path,
    ) -> None:
        self.provider = provider
        self.local_index_path = local_index_path
        self.local_snaps_dir = local_snaps_dir
        self.conflicts_path = conflicts_path
        self.state_path = state_path

    @staticmethod
    def _entry_from_snapshot(snap: Dict[str, Any]) -> Dict[str, Any]:
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
            "search_blob_mtime": 0.0,
            "source": snap.get("source", ""),
            "trigger": snap.get("trigger", ""),
            "git_state": snap.get("git_state", {}),
            "auto_fingerprint": snap.get("auto_fingerprint", ""),
        }

    @staticmethod
    def _hash_snapshot(snap: Dict[str, Any]) -> str:
        raw = json.dumps(snap, ensure_ascii=False, sort_keys=True)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _load_local_snapshots(self) -> Dict[str, Dict[str, Any]]:
        snaps: Dict[str, Dict[str, Any]] = {}
        for p in sorted(self.local_snaps_dir.glob("*.json")):
            try:
                snap = migrate_snapshot(json.loads(p.read_text(encoding="utf-8")))
            except Exception as exc:
                LOGGER.warning("sync_pull skip corrupted local snapshot %s: %s", p.name, exc)
                continue
            sid = str(snap.get("id") or "").strip()
            if not sid:
                continue
            snaps[sid] = snap
        return snaps

    @staticmethod
    def _payload_map(snaps: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        out: Dict[str, Dict[str, Any]] = {}
        for raw in snaps or []:
            if not isinstance(raw, dict):
                continue
            snap = migrate_snapshot(dict(raw))
            sid = str(snap.get("id") or "").strip()
            if not sid:
                continue
            out[sid] = snap
        return out

    def _choose_winner(
        self,
        sid: str,
        local: Optional[Dict[str, Any]],
        remote: Optional[Dict[str, Any]],
    ) -> Tuple[Optional[Dict[str, Any]], Optional[SyncConflict]]:
        if local and not remote:
            return local, None
        if remote and not local:
            return remote, None
        if not local and not remote:
            return None, None

        local_key = snapshot_sort_key(local or {})
        remote_key = snapshot_sort_key(remote or {})

        if local_key > remote_key:
            return local, None
        if remote_key > local_key:
            return remote, None

        # Same rev/updated_at: detect byte-level difference.
        local_hash = self._hash_snapshot(local or {})
        remote_hash = self._hash_snapshot(remote or {})
        if local_hash == remote_hash:
            return local, None

        conflict = SyncConflict(
            snapshot_id=sid,
            reason="same_rev_and_updated_at_with_different_payload",
            local_rev=int((local or {}).get("rev", 0) or 0),
            remote_rev=int((remote or {}).get("rev", 0) or 0),
            local_updated_at=str((local or {}).get("updated_at", "") or ""),
            remote_updated_at=str((remote or {}).get("updated_at", "") or ""),
        )
        # deterministic fallback: prefer local
        return local, conflict

    def _record_conflicts(self, conflicts: List[SyncConflict]) -> None:
        if not conflicts:
            return
        history = load_json(self.conflicts_path, default={"conflicts": []})
        items = history.get("conflicts", []) if isinstance(history.get("conflicts"), list) else []
        stamp = now_iso()
        for c in conflicts:
            items.insert(
                0,
                {
                    "at": stamp,
                    "provider": self.provider.name,
                    "snapshot_id": c.snapshot_id,
                    "reason": c.reason,
                    "local_rev": c.local_rev,
                    "remote_rev": c.remote_rev,
                    "local_updated_at": c.local_updated_at,
                    "remote_updated_at": c.remote_updated_at,
                },
            )
        history["conflicts"] = items[:500]
        save_json(self.conflicts_path, history)

    def sync(self) -> Dict[str, Any]:
        LOGGER.info("sync_pull provider=%s", self.provider.name)
        remote = self.provider.pull()
        local_index = load_json(self.local_index_path, default={"snapshots": []})
        local_map = self._load_local_snapshots()
        remote_map = self._payload_map(remote.snapshots)

        merged: Dict[str, Dict[str, Any]] = {}
        conflicts: List[SyncConflict] = []

        for sid in sorted(set(local_map.keys()) | set(remote_map.keys())):
            winner, conflict = self._choose_winner(sid, local_map.get(sid), remote_map.get(sid))
            if winner:
                merged[sid] = winner
            if conflict:
                conflicts.append(conflict)
                LOGGER.warning("sync_conflict sid=%s reason=%s", sid, conflict.reason)

        # Persist local snapshots and regenerate local index entries.
        for sid, snap in merged.items():
            save_snapshot_file(self.local_snaps_dir / f"{sid}.json", snap)

        merged_index = copy.deepcopy(local_index if isinstance(local_index, dict) else {"snapshots": []})
        merged_index["schema_version"] = max(2, int(merged_index.get("schema_version", 1) or 1))
        merged_index["updated_at"] = now_iso()
        merged_index["rev"] = int(merged_index.get("rev", 1) or 1) + 1
        merged_index["search_meta"] = merged_index.get("search_meta") if isinstance(merged_index.get("search_meta"), dict) else {"engine": "blob", "version": 1}
        merged_index["snapshots"] = [self._entry_from_snapshot(s) for _, s in sorted(merged.items(), key=lambda kv: kv[1].get("created_at", ""), reverse=True)]
        save_json(self.local_index_path, merged_index)

        payload = SyncPayload(
            cursor=remote.cursor,
            index=merged_index,
            snapshots=list(merged.values()),
        )
        LOGGER.info("sync_push provider=%s", self.provider.name)
        cursor = self.provider.push(payload)

        state = {
            "provider": self.provider.name,
            "last_cursor": cursor,
            "synced_at": now_iso(),
            "snapshot_count": len(merged),
            "conflict_count": len(conflicts),
        }
        save_json(self.state_path, state)
        self._record_conflicts(conflicts)

        return {
            "cursor": cursor,
            "snapshot_count": len(merged),
            "conflict_count": len(conflicts),
        }
