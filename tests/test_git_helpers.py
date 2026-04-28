from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from ctxsnap.utils import git_state_details, git_state_key, git_title_suggestion


def _run(cmd: list[str], cwd: Path) -> None:
    subprocess.check_call(cmd, cwd=str(cwd), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def test_git_helpers_support_repository_subdirectories(tmp_path: Path) -> None:
    git = shutil.which("git")
    if not git:
        pytest.skip("git not available")

    repo = tmp_path / "repo"
    repo.mkdir()
    _run([git, "init"], repo)
    _run([git, "config", "user.email", "test@example.com"], repo)
    _run([git, "config", "user.name", "Test User"], repo)
    (repo / "README.md").write_text("hello", encoding="utf-8")
    _run([git, "add", "README.md"], repo)
    _run([git, "commit", "-m", "initial"], repo)

    subdir = repo / "src"
    subdir.mkdir()
    (subdir / "new.py").write_text("print('x')", encoding="utf-8")

    details = git_state_details(subdir)
    assert details is not None
    assert details["untracked"] == 1
    assert git_state_key(subdir) is not None
    assert git_title_suggestion(subdir) is not None
