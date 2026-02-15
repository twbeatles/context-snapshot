from __future__ import annotations

from pathlib import Path
from typing import Any, List

import pytest

from ctxsnap import restore


def test_open_vscode_files_uses_cmd_wrapper_for_cmd_script(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    f1 = tmp_path / "a.py"
    f2 = tmp_path / "b.py"
    f1.write_text("a", encoding="utf-8")
    f2.write_text("b", encoding="utf-8")

    monkeypatch.setattr(restore, "resolve_code_cmd", lambda: "code.cmd")

    calls: List[List[str]] = []

    def fake_popen(argv: List[str], shell: bool = False, **_kw: Any) -> None:
        calls.append([str(x) for x in argv])

    monkeypatch.setattr(restore.subprocess, "Popen", fake_popen)

    ok, err = restore.open_vscode_files([f1, f2])
    assert ok is True
    assert err == ""
    assert calls
    assert calls[0][0:3] == ["cmd.exe", "/c", "code.cmd"]
    assert "--reuse-window" in calls[0]
    assert "-g" in calls[0]
    assert str(f1) in calls[0]
    assert str(f2) in calls[0]

