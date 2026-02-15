from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest

from ctxsnap import utils


def test_git_dirty_timeout_returns_none(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()

    monkeypatch.setattr(utils.shutil, "which", lambda _name: "git")

    def fake_check_output(*_args: Any, **_kwargs: Any) -> str:
        raise subprocess.TimeoutExpired(cmd="git", timeout=5)

    monkeypatch.setattr(utils.subprocess, "check_output", fake_check_output)
    assert utils.git_dirty(tmp_path) is None

