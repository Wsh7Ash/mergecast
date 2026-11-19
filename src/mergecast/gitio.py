"""Thin, dependency-free wrapper around the git command line.

Only read-only operations are exposed.  Every command is run with a scrubbed,
non-interactive environment so the tool can never block on a credential prompt.
"""

from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

HUNK_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")
DIFF_RE = re.compile(r"^diff --git a/(.*?) b/(.*)$")


class GitError(RuntimeError):
    """Raised when a git command fails or the directory is not a repository."""


def _env() -> dict[str, str]:
    env = dict(os.environ)
    env.update(
        {
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_PAGER": "cat",
            "GIT_OPTIONAL_LOCKS": "0",
            "LC_ALL": "C",
        }
    )
    # Never let an ambient configuration redirect output formatting.
    env.pop("GIT_EXTERNAL_DIFF", None)
    return env


def run_git(root: str | Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=_env(),
    )
    if proc.returncode != 0:
        detail = proc.stderr.strip() or proc.stdout.strip()
        raise GitError(detail or f"git {' '.join(args)} failed")
    return proc.stdout


def repo_root(path: str | Path) -> Path:
    """Return the absolute work-tree root for ``path``."""
    target = Path(path)
    if not target.is_dir():
        raise GitError(f"not a directory: {target}")
    try:
        out = run_git(target, "rev-parse", "--show-toplevel")
    except GitError as exc:
        raise GitError(f"not a git repository: {target} ({exc})") from exc
    return Path(out.strip())


def resolve_commit(root: str | Path, ref: str) -> str:
    try:
        out = run_git(root, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}")
    except GitError:
        raise GitError(f"unknown revision: {ref}") from None
    sha = out.strip()
    if not sha:
        raise GitError(f"unknown revision: {ref}")
    return sha


def merge_base(root: str | Path, left: str, right: str) -> str:
    try:
        out = run_git(root, "merge-base", left, right)
    except GitError:
        raise GitError(f"no common ancestor for {left} and {right}") from None
    sha = out.strip()
    if not sha:
        raise GitError(f"no common ancestor for {left} and {right}")
    return sha


def short_sha(sha: str) -> str:
    return sha[:7]


@dataclass(frozen=True)
class Hunk:
    """A changed line range, expressed in the merge-base coordinate system."""

    old_start: int
    old_len: int
    new_start: int
    new_len: int
    lines: tuple[str, ...] = ()

    @property
    def old_end(self) -> int:
        return self.old_start + max(self.old_len, 1)

    @property
    def added(self) -> int:
        return self.new_len

    @property
    def removed(self) -> int:
        return self.old_len

    def span(self) -> str:
        if self.old_len == 0:
            return f"insert at {self.old_start}"
        if self.old_len == 1:
            return f"line {self.old_start}"
        return f"lines {self.old_start}-{self.old_start + self.old_len - 1}"


@dataclass
class FileDiff:
    """One file's diff on one side of the merge, relative to the merge base."""

    base_path: str
    path: str
    deleted: bool = False
    hunks: list[Hunk] = field(default_factory=list)

    @property
    def added(self) -> int:
        return sum(h.added for h in self.hunks)

    @property
    def removed(self) -> int:
        return sum(h.removed for h in self.hunks)

    @property
    def churn(self) -> int:
        return self.added + self.removed


def parse_diff(text: str) -> list[FileDiff]:
    """Parse ``git diff -U0`` output into per-file hunks.

    Paths are taken from the ``diff --git`` header.  Git quotes unusual paths
    (C-style escapes); quoted paths are unquoted when possible and otherwise
    kept verbatim, which is documented as a limitation.
    """
    files: list[FileDiff] = []
    current: FileDiff | None = None
    current_hunk: dict[str, object] | None = None
    deleted = False

    def flush_hunk() -> None:
        nonlocal current_hunk
        if current is not None and current_hunk is not None:
            current.hunks.append(
                Hunk(
                    old_start=int(current_hunk["old_start"]),
                    old_len=int(current_hunk["old_len"]),
                    new_start=int(current_hunk["new_start"]),
                    new_len=int(current_hunk["new_len"]),
                    lines=tuple(current_hunk["lines"]),  # type: ignore[arg-type]
                )
            )
        current_hunk = None

    for raw in text.splitlines():
        line = raw.rstrip("\r")
        if line.startswith("diff --git "):
            flush_hunk()
            match = DIFF_RE.match(line)
            if not match:
                current = None
                continue
            old, new = _unquote(match.group(1)), _unquote(match.group(2))
            current = FileDiff(base_path=old, path=new)
            deleted = False
            files.append(current)
            continue
        if current is None:
            continue
        if line.startswith("deleted file mode"):
            deleted = True
            current.deleted = True
            continue
        if line.startswith("new file mode"):
            deleted = False
            current.deleted = False
            continue
        if line.startswith("rename from "):
            current.base_path = _unquote(line[len("rename from ") :])
            continue
        if line.startswith("rename to "):
            current.path = _unquote(line[len("rename to ") :])
            continue
        if line.startswith("+++ /dev/null"):
            deleted = True
            current.deleted = True
            continue
        if line.startswith("--- "):
            continue
        if line.startswith("+++ "):
            continue
        match = HUNK_RE.match(line)
        if match:
            flush_hunk()
            old_start = int(match.group(1))
            old_len = int(match.group(2)) if match.group(2) is not None else 1
            new_start = int(match.group(3))
            new_len = int(match.group(4)) if match.group(4) is not None else 1
            current_hunk = {
                "old_start": old_start,
                "old_len": old_len,
                "new_start": new_start,
                "new_len": new_len,
                "lines": [],
            }
            continue
        if current_hunk is not None and line[:1] in ("+", "-"):
            current_hunk["lines"].append(line)  # type: ignore[union-attr]
    flush_hunk()
    _ = deleted
    return files


def _unquote(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value.startswith('"') and value.endswith('"'):
        body = value[1:-1]
        try:
            return body.encode("latin-1", "backslashreplace").decode("unicode_escape")
        except (UnicodeDecodeError, UnicodeEncodeError):
            return body
    return value


def diff_against_base(root: str | Path, base_sha: str, side_sha: str) -> list[FileDiff]:
    """Diff one side against the merge base, with rename detection."""
    text = run_git(
        root,
        "diff",
        "-U0",
        "--no-color",
        "--no-ext-diff",
        "--find-renames",
        "--no-textconv",
        base_sha,
        side_sha,
    )
    return parse_diff(text)


def file_at(root: str | Path, sha: str, path: str) -> str | None:
    """Return file contents at ``sha``, or ``None`` when absent."""
    try:
        return run_git(root, "show", f"{sha}:{path}")
    except GitError:
        return None
