from __future__ import annotations

from ctxsnap.ui.main_window_sections.restore_actions import MainWindowRestoreActionsSection


def test_snapshot_export_payload_redacts_sensitive_fields() -> None:
    snap = {
        "id": "s1",
        "title": "demo",
        "note": "secret",
        "todos": ["a", "", ""],
        "processes": [{"name": "python"}],
        "running_apps": [{"name": "Code"}],
        "sensitive": {"enc": "dpapi"},
        "_security_error": "failed",
        "root": "C:/repo",
    }
    redacted = MainWindowRestoreActionsSection._snapshot_export_payload(snap, redacted=True)
    assert "note" not in redacted
    assert "todos" not in redacted
    assert "processes" not in redacted
    assert "running_apps" not in redacted
    assert "sensitive" not in redacted
    assert "_security_error" not in redacted
    assert redacted["root"] == "C:/repo"


def test_weekly_report_lines_redact_note_and_todos() -> None:
    lines = MainWindowRestoreActionsSection._weekly_report_lines(
        [
            {
                "title": "demo",
                "created_at": "2026-01-01T00:00:00",
                "root": "C:/repo",
                "tags": ["work"],
                "todos": ["secret task", "", ""],
                "note": "private note",
            }
        ],
        redacted=True,
    )
    report = "\n".join(lines)
    assert "- (redacted)" in report
    assert "private note" not in report
