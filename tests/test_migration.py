from __future__ import annotations

from ctxsnap.app_storage import migrate_settings, migrate_snapshot


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


def test_migrate_snapshot_backfills_revision_and_git_state() -> None:
    snap = migrate_snapshot({"id": "x", "created_at": "2026-01-01T00:00:00"})
    assert snap["schema_version"] >= 2
    assert snap["rev"] >= 1
    assert snap["updated_at"] == "2026-01-01T00:00:00"
    assert snap["git_state"]["dirty"] is False
    assert snap["git_state"]["changed"] == 0
    assert snap["git_state"]["staged"] == 0
    assert snap["git_state"]["untracked"] == 0
