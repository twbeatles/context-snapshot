from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest

from ctxsnap import utils


def test_git_title_suggestion_timeout_returns_none(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # Pretend this is a git repo
    (tmp_path / ".git").mkdir()

    def fake_which(_name: str) -> str:
        return "git"

    def fake_check_output(*_args: Any, **_kwargs: Any) -> str:
        raise subprocess.TimeoutExpired(cmd="git", timeout=3)

    monkeypatch.setattr(utils.shutil, "which", fake_which)
    monkeypatch.setattr(utils.subprocess, "check_output", fake_check_output)

    assert utils.git_title_suggestion(tmp_path) is None

