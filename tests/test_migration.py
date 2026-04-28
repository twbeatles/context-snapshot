from __future__ import annotations

import pytest

from ctxsnap.app_storage import migrate_settings, migrate_snapshot, safe_snapshot_path
from ctxsnap.constants import default_tags_for_language
from ctxsnap.services.snapshot_service import SnapshotService


def test_migrate_settings_adds_new_schema_and_feature_flags() -> None:
    settings = migrate_settings({"tags": ["업무"]})
    assert settings["schema_version"] >= 2
    assert settings["dev_flags"]["sync_enabled"] is False
    assert settings["dev_flags"]["security_enabled"] is False
    assert settings["sync"]["provider"] == "local"
    assert settings["security"]["dpapi_enabled"] is False
    assert settings["search"]["enable_field_query"] is True
    assert isinstance(settings["restore_profiles"], list)
    assert settings["capture_enforce_todos"] is True


def test_default_tags_follow_language_without_overwriting_existing_tags() -> None:
    assert default_tags_for_language("en") == ["Work", "Personal", "Real Estate", "Settlement"]
    assert default_tags_for_language("ko") == ["업무", "개인", "부동산", "정산"]
    assert migrate_settings({"language": "en"})["tags"] == ["Work", "Personal", "Real Estate", "Settlement"]
    assert migrate_settings({"language": "en", "tags": ["custom"]})["tags"] == ["custom"]


@pytest.mark.parametrize("sid", ["../x", "a/b", r"a\b", "C:escape", ""])
def test_safe_snapshot_path_rejects_unsafe_ids(tmp_path, sid: str) -> None:
    with pytest.raises(ValueError):
        safe_snapshot_path(tmp_path, sid)


def test_migrate_snapshot_backfills_revision_and_git_state() -> None:
    snap = migrate_snapshot({"id": "x", "created_at": "2026-01-01T00:00:00"})
    assert snap["schema_version"] >= 2
    assert snap["rev"] >= 1
    assert snap["updated_at"] == "2026-01-01T00:00:00"
    assert snap["git_state"]["dirty"] is False
    assert snap["git_state"]["changed"] == 0
    assert snap["git_state"]["staged"] == 0
    assert snap["git_state"]["untracked"] == 0


def test_migrate_index_clears_legacy_search_cache_and_normalizes_tombstones() -> None:
    service = SnapshotService()
    migrated = service.migrate_index(
        {
            "search_meta": {"engine": "blob", "version": 1},
            "snapshots": [
                {"id": "s1", "search_blob": "secret", "search_blob_mtime": 12.0},
            ],
            "tombstones": [
                {"id": "s1", "deleted_at": "2026-01-01T00:00:00"},
                {"id": "s1", "deleted_at": "2026-01-03T00:00:00"},
            ],
        }
    )
    assert migrated["search_meta"]["version"] == SnapshotService.SEARCH_BLOB_VERSION
    assert migrated["snapshots"][0]["search_blob"] == ""
    assert migrated["snapshots"][0]["search_blob_mtime"] == 0.0
    assert migrated["tombstones"] == [{"id": "s1", "deleted_at": "2026-01-03T00:00:00"}]


def test_latest_snapshot_item_prefers_created_at_then_updated_at_then_id() -> None:
    service = SnapshotService()
    item = service.latest_snapshot_item(
        [
            {"id": "a", "created_at": "2026-01-01T00:00:00", "updated_at": "2026-01-02T00:00:00"},
            {"id": "c", "created_at": "2026-01-03T00:00:00", "updated_at": "2026-01-03T00:00:00"},
            {"id": "b", "created_at": "2026-01-03T00:00:00", "updated_at": "2026-01-04T00:00:00"},
        ]
    )
    assert item is not None
    assert item["id"] == "b"
