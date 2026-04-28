from __future__ import annotations

from ctxsnap.ui.main_window_sections.automation import MainWindowAutomationSection


class _StatusBar:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def showMessage(self, message: str, _timeout: int = 0) -> None:
        self.messages.append(message)


class _Window(MainWindowAutomationSection):
    def __init__(self) -> None:
        self.settings = {"auto_backup_hours": 1, "auto_backup_last": ""}
        self.status = _StatusBar()

    def statusBar(self) -> _StatusBar:
        return self.status

    def _auto_backup_current(self):
        return "backup.json", False, "disk full"


def test_auto_backup_failure_does_not_update_last_timestamp() -> None:
    win = _Window()
    win._run_scheduled_backup()
    assert win.settings["auto_backup_last"] == ""
    assert "Auto backup failed" in win.status.messages[-1]
