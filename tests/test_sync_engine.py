from __future__ import annotations

import json
from pathlib import Path

from ctxsnap.app_storage import save_json, save_snapshot_file
from ctxsnap.core.sync.engine import SyncEngine
from ctxsnap.core.sync.providers.local import LocalSyncProvider


def _write_snapshot(path: Path, sid: str, title: str, rev: int, updated_at: str) -> dict:
    snap = {
        "id": sid,
        "title": title,
        "created_at": "2026-01-01T00:00:00",
        "updated_at": updated_at,
        "rev": rev,
        "root": "C:/repo",
        "vscode_workspace": "",
        "note": "",
        "todos": ["", "", ""],
        "tags": [],
        "pinned": False,
        "archived": False,
        "recent_files": [],
        "processes": [],
        "running_apps": [],
        "source": "",
        "trigger": "",
        "git_state": {},
        "auto_fingerprint": "",
        "schema_version": 2,
        "sensitive": {},
    }
    save_snapshot_file(path / f"{sid}.json", snap)
    return snap


def test_sync_prefers_higher_revision(tmp_path: Path) -> None:
    base = tmp_path / "local"
    snaps = base / "snapshots"
    snaps.mkdir(parents=True, exist_ok=True)
    index_path = base / "index.json"
    save_json(index_path, {"snapshots": [], "schema_version": 2, "rev": 1, "updated_at": "2026-01-01T00:00:00", "search_meta": {}})

    _write_snapshot(snaps, "s1", "local-old", 1, "2026-01-01T00:00:00")

    remote_root = tmp_path / "remote"
    provider = LocalSyncProvider(remote_root)
    remote_snap = _write_snapshot(tmp_path, "s1", "remote-new", 2, "2026-01-02T00:00:00")
    payload = {
        "cursor": "",
        "index": {"snapshots": []},
        "snapshots": [remote_snap],
    }
    (remote_root / "remote_payload.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    engine = SyncEngine(
        provider=provider,
        local_index_path=index_path,
        local_snaps_dir=snaps,
        conflicts_path=base / "sync_conflicts.json",
        state_path=base / "sync_state.json",
    )
    result = engine.sync()
    assert result["snapshot_count"] == 1
    merged = json.loads((snaps / "s1.json").read_text(encoding="utf-8"))
    assert merged["title"] == "remote-new"
    assert merged["rev"] == 2


def test_sync_records_conflict_for_same_rev_and_timestamp(tmp_path: Path) -> None:
    base = tmp_path / "local"
    snaps = base / "snapshots"
    snaps.mkdir(parents=True, exist_ok=True)
    index_path = base / "index.json"
    save_json(index_path, {"snapshots": [], "schema_version": 2, "rev": 1, "updated_at": "2026-01-01T00:00:00", "search_meta": {}})

    _write_snapshot(snaps, "s1", "local-a", 2, "2026-01-03T00:00:00")

    remote_root = tmp_path / "remote"
    provider = LocalSyncProvider(remote_root)
    remote_snap = _write_snapshot(tmp_path, "s1", "remote-b", 2, "2026-01-03T00:00:00")
    payload = {"cursor": "", "index": {"snapshots": []}, "snapshots": [remote_snap]}
    (remote_root / "remote_payload.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    engine = SyncEngine(
        provider=provider,
        local_index_path=index_path,
        local_snaps_dir=snaps,
        conflicts_path=base / "sync_conflicts.json",
        state_path=base / "sync_state.json",
    )
    result = engine.sync()
    assert result["conflict_count"] == 1
    conflicts = json.loads((base / "sync_conflicts.json").read_text(encoding="utf-8"))
    assert conflicts["conflicts"][0]["snapshot_id"] == "s1"
    assert conflicts["conflicts"][0]["local_payload"]["title"] == "local-a"
    assert conflicts["conflicts"][0]["remote_payload"]["title"] == "remote-b"
    remote_after = json.loads((remote_root / "remote_payload.json").read_text(encoding="utf-8"))
    assert remote_after["snapshots"][0]["title"] == "remote-b"


def test_sync_applies_remote_tombstone_and_removes_local_snapshot(tmp_path: Path) -> None:
    base = tmp_path / "local"
    snaps = base / "snapshots"
    snaps.mkdir(parents=True, exist_ok=True)
    index_path = base / "index.json"
    save_json(
        index_path,
        {
            "snapshots": [],
            "tombstones": [],
            "schema_version": 2,
            "rev": 1,
            "updated_at": "2026-01-01T00:00:00",
            "search_meta": {},
        },
    )

    _write_snapshot(snaps, "s1", "local-old", 1, "2026-01-01T00:00:00")

    remote_root = tmp_path / "remote"
    provider = LocalSyncProvider(remote_root)
    payload = {
        "cursor": "",
        "index": {"snapshots": [], "tombstones": [{"id": "s1", "deleted_at": "2026-04-10T00:00:00"}]},
        "snapshots": [],
    }
    (remote_root / "remote_payload.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    engine = SyncEngine(
        provider=provider,
        local_index_path=index_path,
        local_snaps_dir=snaps,
        conflicts_path=base / "sync_conflicts.json",
        state_path=base / "sync_state.json",
    )
    result = engine.sync()
    assert result["snapshot_count"] == 0
    assert not (snaps / "s1.json").exists()
    merged_index = json.loads(index_path.read_text(encoding="utf-8"))
    assert merged_index["tombstones"] == [{"id": "s1", "deleted_at": "2026-04-10T00:00:00"}]


def test_sync_prunes_old_tombstones(tmp_path: Path) -> None:
    base = tmp_path / "local"
    snaps = base / "snapshots"
    snaps.mkdir(parents=True, exist_ok=True)
    index_path = base / "index.json"
    save_json(
        index_path,
        {
            "snapshots": [],
            "tombstones": [{"id": "s1", "deleted_at": "2026-01-01T00:00:00"}],
            "schema_version": 2,
            "rev": 1,
            "updated_at": "2026-02-15T00:00:00",
            "search_meta": {},
        },
    )

    remote_root = tmp_path / "remote"
    provider = LocalSyncProvider(remote_root)
    payload = {"cursor": "", "index": {"snapshots": [], "tombstones": []}, "snapshots": []}
    (remote_root / "remote_payload.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    engine = SyncEngine(
        provider=provider,
        local_index_path=index_path,
        local_snaps_dir=snaps,
        conflicts_path=base / "sync_conflicts.json",
        state_path=base / "sync_state.json",
    )
    engine.sync()
    merged_index = json.loads(index_path.read_text(encoding="utf-8"))
    assert merged_index["tombstones"] == []


def test_sync_skips_remote_snapshot_with_unsafe_id(tmp_path: Path) -> None:
    base = tmp_path / "local"
    snaps = base / "snapshots"
    snaps.mkdir(parents=True, exist_ok=True)
    index_path = base / "index.json"
    save_json(index_path, {"snapshots": [], "schema_version": 2, "rev": 1, "updated_at": "2026-01-01T00:00:00", "search_meta": {}})

    remote_root = tmp_path / "remote"
    provider = LocalSyncProvider(remote_root)
    payload = {
        "cursor": "",
        "index": {"snapshots": []},
        "snapshots": [{"id": "../evil", "title": "bad", "created_at": "2026-01-01T00:00:00"}],
    }
    (remote_root / "remote_payload.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    engine = SyncEngine(
        provider=provider,
        local_index_path=index_path,
        local_snaps_dir=snaps,
        conflicts_path=base / "sync_conflicts.json",
        state_path=base / "sync_state.json",
    )
    result = engine.sync()
    assert result["snapshot_count"] == 0
    assert not (tmp_path / "evil.json").exists()
