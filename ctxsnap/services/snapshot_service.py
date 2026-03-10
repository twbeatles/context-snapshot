from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict

from ctxsnap.app_storage import now_iso


class SnapshotService:
    """Snapshot/index metadata helpers (schema/rev/updated_at)."""

    SNAPSHOT_SCHEMA_VERSION = 2
    INDEX_SCHEMA_VERSION = 2

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
        if not isinstance(out.get("search_meta"), dict):
            out["search_meta"] = {"engine": "blob", "version": 1}
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
