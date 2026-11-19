import os
import subprocess
from pathlib import Path

import pytest

GIT_ENV = {
    "GIT_AUTHOR_NAME": "Test",
    "GIT_AUTHOR_EMAIL": "test@example.com",
    "GIT_COMMITTER_NAME": "Test",
    "GIT_COMMITTER_EMAIL": "test@example.com",
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_SYSTEM": os.devnull,
    "GIT_TERMINAL_PROMPT": "0",
}


def git(repo: Path, *args: str, check: bool = True) -> str:
    env = dict(os.environ)
    env.update(GIT_ENV)
    proc = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        env=env,
    )
    if check and proc.returncode != 0:
        raise AssertionError(f"git {' '.join(args)} failed: {proc.stderr}")
    return proc.stdout


def commit(repo: Path, message: str = "commit") -> str:
    git(repo, "add", "-A")
    git(repo, "commit", "-m", message)
    return git(repo, "rev-parse", "HEAD").strip()


def write(repo: Path, name: str, content: str) -> None:
    path = repo / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def lines(count: int, prefix: str = "line") -> str:
    return "".join(f"{prefix} {i:02d}\n" for i in range(1, count + 1))


def scenario(tmp_path: Path, base_files: dict, main_files: dict, feature_files: dict):
    """Create a repo whose main and feature branches diverge from one base commit."""
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-b", "main")
    git(repo, "config", "user.email", "test@example.com")
    git(repo, "config", "user.name", "Test")
    for name, content in base_files.items():
        write(repo, name, content)
    commit(repo, "base")

    git(repo, "checkout", "-b", "feature")
    for name, content in feature_files.items():
        if content is None:
            git(repo, "rm", "-q", name)
        else:
            write(repo, name, content)
    commit(repo, "feature work")

    git(repo, "checkout", "main")
    for name, content in main_files.items():
        if content is None:
            git(repo, "rm", "-q", name)
        else:
            write(repo, name, content)
    commit(repo, "main work")
    return repo


def replace_lines(text: str, start: int, end: int, replacement: str) -> str:
    rows = text.splitlines(keepends=True)
    return "".join(rows[: start - 1] + [replacement] + rows[end:])


@pytest.fixture
def example_repo(tmp_path: Path) -> Path:
    base = lines(40)
    return scenario(
        tmp_path,
        {"src/app.py": base, "README.md": lines(40, "readme")},
        {"src/app.py": replace_lines(base, 5, 8, "main edit\n")},
        {"src/app.py": replace_lines(base, 5, 8, "feature edit\n")},
    )
