from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict

from ctxsnap.app_storage import now_iso


class SnapshotService:
    """Snapshot/index metadata helpers (schema/rev/updated_at)."""

    SNAPSHOT_SCHEMA_VERSION = 2
    INDEX_SCHEMA_VERSION = 2

    def prepare_new_snapshot(self, snap: Dict[str, Any]) -> Dict[str, Any]:
        out = deepcopy(snap)
        out["schema_version"] = self.SNAPSHOT_SCHEMA_VERSION
        out["rev"] = max(1, int(out.get("rev", 1) or 1))
        out["updated_at"] = now_iso()
        return out

    def touch_snapshot(self, snap: Dict[str, Any]) -> Dict[str, Any]:
        out = deepcopy(snap)
        out["schema_version"] = self.SNAPSHOT_SCHEMA_VERSION
        out["rev"] = max(1, int(out.get("rev", 1) or 1)) + 1
        out["updated_at"] = now_iso()
        return out

    def migrate_index(self, index: Dict[str, Any]) -> Dict[str, Any]:
        out = deepcopy(index if isinstance(index, dict) else {"snapshots": []})
        out.setdefault("snapshots", [])
        out.setdefault("search_meta", {"engine": "blob", "version": 1})
        out["schema_version"] = max(2, int(out.get("schema_version", 1) or 1))
        out["rev"] = max(1, int(out.get("rev", 1) or 1))
        out.setdefault("updated_at", now_iso())
        return out

    def touch_index(self, index: Dict[str, Any]) -> Dict[str, Any]:
        out = self.migrate_index(index)
        out["rev"] = max(1, int(out.get("rev", 1) or 1)) + 1
        out["updated_at"] = now_iso()
        return out
