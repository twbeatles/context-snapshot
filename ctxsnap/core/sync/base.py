from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Protocol


@dataclass
class SyncPayload:
    cursor: str
    index: Dict[str, Any]
    snapshots: List[Dict[str, Any]]


@dataclass
class SyncConflict:
    snapshot_id: str
    reason: str
    local_rev: int
    remote_rev: int
    local_updated_at: str
    remote_updated_at: str


class SyncProvider(Protocol):
    name: str

    def pull(self) -> SyncPayload:
        ...

    def push(self, payload: SyncPayload) -> str:
        ...


class SyncProviderError(RuntimeError):
    pass


def snapshot_sort_key(snap: Dict[str, Any]) -> tuple[int, str]:
    rev = int(snap.get("rev", 0) or 0)
    updated_at = str(snap.get("updated_at", "") or "")
    return rev, updated_at
