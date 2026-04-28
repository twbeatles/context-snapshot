from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6 import QtWidgets

from ctxsnap.ui.dialogs.history import RestoreHistoryDialog
from ctxsnap.ui.dialogs.snapshot import SnapshotDialog

_APP: QtWidgets.QApplication | None = None


def _app() -> QtWidgets.QApplication:
    global _APP
    app = QtWidgets.QApplication.instance()
    if isinstance(app, QtWidgets.QApplication):
        _APP = app
        return app
    _APP = QtWidgets.QApplication([])
    return _APP


def test_snapshot_dialog_accepts_empty_todos_when_todo_capture_disabled(tmp_path: Path) -> None:
    _app()
    parent = QtWidgets.QWidget()
    dlg = SnapshotDialog(
        parent,
        str(tmp_path),
        ["Work"],
        [],
        enforce_todos=True,
        todos_enabled=False,
    )
    dlg.validate_and_accept()
    assert dlg.result() == QtWidgets.QDialog.DialogCode.Accepted
    assert dlg.values()["todos"] == ["", "", ""]


def test_restore_history_dialog_emits_restore_again_request() -> None:
    _app()
    parent = QtWidgets.QWidget()
    dlg = RestoreHistoryDialog(
        parent,
        {"restores": [{"snapshot_id": "s1", "created_at": "2026-01-01T00:00:00"}]},
    )
    emitted: list[str] = []
    dlg.restoreRequested.connect(lambda sid: emitted.append(sid))
    dlg.listw.setCurrentRow(0)
    dlg._request_restore()
    assert emitted == ["s1"]
