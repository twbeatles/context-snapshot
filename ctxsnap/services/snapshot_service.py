from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta
from typing import Any, Dict

from ctxsnap.app_storage import now_iso


class SnapshotService:
    """Snapshot/index metadata helpers (schema/rev/updated_at)."""

    SNAPSHOT_SCHEMA_VERSION = 2
    INDEX_SCHEMA_VERSION = 2
    SEARCH_BLOB_VERSION = 2
    TOMBSTONE_RETENTION_DAYS = 30

    @staticmethod
    def _to_int(value: Any, default: int) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    def prepare_new_snapshot(self, snap: Dict[str, Any]) -> Dict[str, Any]:
        out = deepcopy(snap)
        out["schema_version"] = self.SNAPSHOT_SCHEMA_VERSION
        out["rev"] = max(1, self._to_int(out.get("rev", 1), 1))
        out["updated_at"] = now_iso()
        return out

    def touch_snapshot(self, snap: Dict[str, Any]) -> Dict[str, Any]:
        out = deepcopy(snap)
        out["schema_version"] = self.SNAPSHOT_SCHEMA_VERSION
        out["rev"] = max(1, self._to_int(out.get("rev", 1), 1)) + 1
        out["updated_at"] = now_iso()
        return out

    def migrate_index(self, index: Dict[str, Any]) -> Dict[str, Any]:
        source = index if isinstance(index, dict) else {}
        out: Dict[str, Any] = deepcopy(source)
        if not isinstance(out.get("snapshots"), list):
            out["snapshots"] = []
        search_meta = out.get("search_meta")
        if not isinstance(search_meta, dict):
            search_meta = {}
        version = self._to_int(search_meta.get("version", 0), 0)
        search_meta["engine"] = str(search_meta.get("engine") or "blob")
        search_meta["version"] = max(self.SEARCH_BLOB_VERSION, version)
        if version < self.SEARCH_BLOB_VERSION:
            for item in out.get("snapshots", []):
                if not isinstance(item, dict):
                    continue
                item["search_blob"] = ""
                item["search_blob_mtime"] = 0.0
        out["search_meta"] = search_meta
        out["tombstones"] = self.normalize_tombstones(out.get("tombstones", []))
        out["schema_version"] = max(2, self._to_int(out.get("schema_version", 1), 1))
        out["rev"] = max(1, self._to_int(out.get("rev", 1), 1))
        if not str(out.get("updated_at", "")).strip():
            out["updated_at"] = now_iso()
        return out

    def touch_index(self, index: Dict[str, Any]) -> Dict[str, Any]:
        out = self.migrate_index(index)
        out["rev"] = max(1, self._to_int(out.get("rev", 1), 1)) + 1
        out["updated_at"] = now_iso()
        return out

    def normalize_tombstones(self, tombstones: Any) -> list[Dict[str, str]]:
        merged: Dict[str, str] = {}
        if not isinstance(tombstones, list):
            return []
        for raw in tombstones:
            if not isinstance(raw, dict):
                continue
            sid = str(raw.get("id") or "").strip()
            deleted_at = str(raw.get("deleted_at") or "").strip()
            if not sid or not deleted_at:
                continue
            previous = merged.get(sid, "")
            if deleted_at > previous:
                merged[sid] = deleted_at
        return [
            {"id": sid, "deleted_at": deleted_at}
            for sid, deleted_at in sorted(merged.items(), key=lambda item: (item[1], item[0]), reverse=True)
        ]

    def prune_tombstones(self, tombstones: Any, *, now: str | None = None) -> list[Dict[str, str]]:
        normalized = self.normalize_tombstones(tombstones)
        now_dt = self._parse_datetime(now or now_iso())
        if now_dt is None:
            return normalized
        cutoff = now_dt - timedelta(days=self.TOMBSTONE_RETENTION_DAYS)
        kept: list[Dict[str, str]] = []
        for item in normalized:
            deleted_at_dt = self._parse_datetime(item.get("deleted_at", ""))
            if deleted_at_dt is None or deleted_at_dt >= cutoff:
                kept.append(item)
        return kept

    def upsert_tombstone(self, index: Dict[str, Any], sid: str, *, deleted_at: str | None = None) -> Dict[str, Any]:
        out = self.migrate_index(index)
        stamp = str(deleted_at or now_iso())
        merged = {item["id"]: item["deleted_at"] for item in out.get("tombstones", []) if isinstance(item, dict) and item.get("id")}
        previous = merged.get(sid, "")
        if stamp > previous:
            merged[sid] = stamp
        out["tombstones"] = self.normalize_tombstones(
            [{"id": tombstone_id, "deleted_at": value} for tombstone_id, value in merged.items()]
        )
        return out

    @staticmethod
    def snapshot_timestamp(snap: Dict[str, Any]) -> str:
        return str(snap.get("updated_at") or snap.get("created_at") or "")

    @staticmethod
    def latest_snapshot_item(items: Any) -> Dict[str, Any] | None:
        if not isinstance(items, list):
            return None
        candidates = [item for item in items if isinstance(item, dict) and str(item.get("id") or "").strip()]
        if not candidates:
            return None
        return max(
            candidates,
            key=lambda item: (
                str(item.get("created_at") or ""),
                str(item.get("updated_at") or item.get("created_at") or ""),
                str(item.get("id") or ""),
            ),
        )

    @staticmethod
    def _parse_datetime(value: str) -> datetime | None:
        raw = str(value or "").strip()
        if not raw:
            return None
        try:
            return datetime.strptime(raw, "%Y-%m-%dT%H:%M:%S")
        except ValueError:
            return None
