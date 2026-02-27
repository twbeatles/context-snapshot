from __future__ import annotations

import json
from pathlib import Path

import pytest

from ctxsnap.app_storage import export_backup_to_file, import_backup_from_file, save_json
from ctxsnap.core.security import SecurityService


def test_encrypted_backup_roundtrip(tmp_path: Path) -> None:
    sec = SecurityService()
    if not sec.is_available():
        pytest.skip("DPAPI not available")

    snaps_dir = tmp_path / "snapshots"
    snaps_dir.mkdir(parents=True, exist_ok=True)
    (snaps_dir / "s1.json").write_text(
        json.dumps({"id": "s1", "created_at": "2026-01-01T00:00:00", "root": "C:/repo"}, ensure_ascii=False),
        encoding="utf-8",
    )
    index_path = tmp_path / "index.json"
    save_json(index_path, {"snapshots": [{"id": "s1", "title": "x", "created_at": "2026-01-01T00:00:00", "root": "C:/repo"}]})

    out_path = tmp_path / "backup.json"
    export_backup_to_file(
        out_path,
        settings={"tags": ["업무"]},
        snaps_dir=snaps_dir,
        index_path=index_path,
        include_snapshots=True,
        include_index=True,
        encrypt_backup=True,
    )
    raw = json.loads(out_path.read_text(encoding="utf-8"))
    assert raw.get("encrypted_backup") is True

    imported = import_backup_from_file(out_path)
    assert "settings" in imported
    assert imported["data"] is not None
