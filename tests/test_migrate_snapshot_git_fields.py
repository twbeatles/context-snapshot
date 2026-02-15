from __future__ import annotations

from ctxsnap.app_storage import migrate_snapshot


def test_migrate_snapshot_backfills_git_fields() -> None:
    snap = migrate_snapshot({"id": "1", "root": "C:\\", "title": "t", "created_at": "x"})
    assert "git_branch" in snap
    assert "git_sha" in snap
    assert "git_dirty" in snap
    assert isinstance(snap["git_dirty"], bool)

