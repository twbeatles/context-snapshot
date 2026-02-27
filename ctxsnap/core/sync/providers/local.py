from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from ctxsnap.app_storage import now_iso
from ctxsnap.core.sync.base import SyncPayload, SyncProvider, SyncProviderError


class LocalSyncProvider(SyncProvider):
    name = "local"

    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self.payload_path = self.root / "remote_payload.json"

    def _default_payload(self) -> Dict[str, Any]:
        return {
            "cursor": "",
            "index": {"snapshots": []},
            "snapshots": [],
        }

    def pull(self) -> SyncPayload:
        if not self.payload_path.exists():
            payload = self._default_payload()
        else:
            try:
                payload = json.loads(self.payload_path.read_text(encoding="utf-8"))
            except Exception as exc:
                raise SyncProviderError(f"Failed to read local sync payload: {exc}") from exc
        return SyncPayload(
            cursor=str(payload.get("cursor", "") or ""),
            index=payload.get("index", {"snapshots": []}) if isinstance(payload.get("index"), dict) else {"snapshots": []},
            snapshots=payload.get("snapshots", []) if isinstance(payload.get("snapshots"), list) else [],
        )

    def push(self, payload: SyncPayload) -> str:
        cursor = now_iso()
        raw = {
            "cursor": cursor,
            "index": payload.index,
            "snapshots": payload.snapshots,
        }
        try:
            self.payload_path.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as exc:
            raise SyncProviderError(f"Failed to write local sync payload: {exc}") from exc
        return cursor
