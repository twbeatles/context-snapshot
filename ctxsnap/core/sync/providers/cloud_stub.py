from __future__ import annotations

from ctxsnap.core.sync.base import SyncPayload, SyncProvider, SyncProviderError


class CloudStubSyncProvider(SyncProvider):
    name = "cloud_stub"

    def pull(self) -> SyncPayload:
        raise SyncProviderError("Cloud provider is not implemented in this phase.")

    def push(self, payload: SyncPayload) -> str:
        raise SyncProviderError("Cloud provider is not implemented in this phase.")
