from __future__ import annotations
from pathlib import Path

from ctxsnap.app_storage import load_json, migrate_settings, save_json


def test_save_json_roundtrip_large_payload(tmp_path: Path) -> None:
    p = tmp_path / "big.json"
    data = {"big": "x" * 5_000_000, "n": 123, "arr": list(range(1000))}
    assert save_json(p, data) is True
    loaded = load_json(p)
    assert loaded == data


def test_load_json_corrupted_file_is_backed_up_with_unique_name(tmp_path: Path) -> None:
    p = tmp_path / "settings.json"
    p.write_text("{ not valid json", encoding="utf-8")

    default = {"ok": True}
    loaded = load_json(p, default=default)
    assert loaded == default

    # Original path should have been moved away.
    assert not p.exists()

    backups = list(tmp_path.glob("settings.json.corrupted.*.json"))
    assert len(backups) == 1
    assert "{ not valid json" in backups[0].read_text(encoding="utf-8")


def test_migrate_settings_backfills_new_keys() -> None:
    s = migrate_settings({})
    assert "capture_enforce_todos" in s
    assert isinstance(s["capture_enforce_todos"], bool)
    assert "last_snapshot_form" in s
    form = s["last_snapshot_form"]
    assert isinstance(form, dict)
    assert isinstance(form.get("todos"), list)
    assert len(form.get("todos")) == 3
