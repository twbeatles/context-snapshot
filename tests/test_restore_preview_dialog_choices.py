from __future__ import annotations

import os
import sys

from PySide6 import QtCore, QtWidgets

from ctxsnap.ui.dialogs.restore import RestorePreviewDialog


def _ensure_qt_app() -> None:
    # Some Qt builds on Windows don't ship the "offscreen" plugin.
    if sys.platform != "win32":
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    if QtWidgets.QApplication.instance() is None:
        QtWidgets.QApplication([])


def test_restore_preview_dialog_choices_includes_selected_apps() -> None:
    _ensure_qt_app()
    parent = QtWidgets.QWidget()
    snap = {
        "title": "t",
        "root": "C:\\",
        "created_at": "2026-02-15T00:00:00",
        "note": "",
        "todos": ["a", "b", "c"],
        "running_apps": [
            {"name": "code.exe", "exe": "C:\\Code.exe", "title": "VSCode", "cmdline": ["C:\\Code.exe"]},
            {"name": "chrome.exe", "exe": "C:\\Chrome.exe", "title": "Chrome", "cmdline": ["C:\\Chrome.exe"]},
        ],
    }
    dlg = RestorePreviewDialog(
        parent,
        snap,
        {
            "open_folder": True,
            "open_terminal": True,
            "open_vscode": True,
            "open_running_apps": True,
            "open_recent_files": False,
        },
    )

    ch0 = dlg.choices()
    assert ch0["open_running_apps"] is True
    assert isinstance(ch0["running_apps"], list)
    assert len(ch0["running_apps"]) == 2

    # Uncheck the first app.
    it0 = dlg.apps_list.item(0)
    it0.setCheckState(QtCore.Qt.Unchecked)
    ch1 = dlg.choices()
    assert len(ch1["running_apps"]) == 1
