from __future__ import annotations

from pathlib import Path

import pytest

from ctxsnap.restore import build_terminal_argv


def test_build_terminal_argv_cmd() -> None:
    p = Path(r"C:\Work")
    argv = build_terminal_argv(p, {"mode": "cmd"})
    assert argv[0].lower().endswith("cmd.exe")
    assert "/K" in argv
    assert "cd /d" in " ".join(argv)


def test_build_terminal_argv_custom_substitutes_path() -> None:
    p = Path(r"C:\Work")
    argv = build_terminal_argv(p, {"mode": "custom", "custom_argv": ["foo", "{path}", "bar"]})
    assert argv == ["foo", str(p), "bar"]


def test_build_terminal_argv_wt_uses_which(monkeypatch: pytest.MonkeyPatch) -> None:
    p = Path(r"C:\Work")
    monkeypatch.setattr("ctxsnap.restore.shutil.which", lambda name: "wt" if name == "wt" else None)
    argv = build_terminal_argv(p, {"mode": "wt"})
    assert argv == ["wt", "-d", str(p)]

