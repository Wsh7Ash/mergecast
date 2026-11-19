"""Build a throwaway repository with two diverged branches and run mergecast.

Usage:  python scripts/demo.py [--out results]

The repository is created inside a temporary directory, so the demo never
touches the mergecast checkout itself.  Outputs are written to results/.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

ENV = {
    "GIT_AUTHOR_NAME": "Demo",
    "GIT_AUTHOR_EMAIL": "demo@example.com",
    "GIT_COMMITTER_NAME": "Demo",
    "GIT_COMMITTER_EMAIL": "demo@example.com",
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_SYSTEM": os.devnull,
}


def git(repo: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, env={**os.environ, **ENV}
    )
    if proc.returncode != 0:
        raise SystemExit(f"git {' '.join(args)} failed:\n{proc.stderr}")
    return proc.stdout


def write(repo: Path, name: str, content: str) -> None:
    path = repo / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def numbered(count: int, prefix: str = "line") -> str:
    return "".join(f"{prefix} {i:02d}\n" for i in range(1, count + 1))


def replace(text: str, start: int, end: int, replacement: str) -> str:
    rows = text.splitlines(keepends=True)
    return "".join(rows[: start - 1] + [replacement] + rows[end:])


def build_repo(repo: Path) -> None:
    repo.mkdir(parents=True)
    git(repo, "init", "-b", "main")
    git(repo, "config", "user.email", "demo@example.com")
    git(repo, "config", "user.name", "Demo")

    app = numbered(60)
    write(repo, "src/app.py", app)
    write(repo, "src/config.py", numbered(40, "setting"))
    write(repo, "README.md", numbered(30, "readme"))
    write(repo, "docs/legacy.md", numbered(12, "legacy"))
    git(repo, "add", "-A")
    git(repo, "commit", "-m", "base: initial application")

    # The feature branch: overlapping edit, a second near-miss edit, a free
    # rename, and one file it leaves alone.
    git(repo, "checkout", "-b", "feature/payments")
    write(repo, "src/app.py", replace(replace(app, 11, 13, "    return charge_v2(order)\n"), 49, 50, "    audit('payment')\n"))
    write(repo, "src/config.py", replace(numbered(40, "setting"), 30, 30, "RETRY_LIMIT = 5\n"))
    git(repo, "mv", "docs/legacy.md", "docs/payments.md")
    git(repo, "add", "-A")
    git(repo, "commit", "-m", "feature: v2 charge path and payment docs")

    # main: overlapping edit in app.py, independent edit in config.py, and a
    # delete of the file the feature branch renamed.
    git(repo, "checkout", "main")
    write(repo, "src/app.py", replace(replace(app, 11, 13, "    return charge_v3(order)\n"), 49, 52, "    audit('order')\n    metrics()\n"))
    write(repo, "src/config.py", replace(numbered(40, "setting"), 4, 4, "TIMEOUT = 30\n"))
    git(repo, "rm", "-q", "docs/legacy.md")
    git(repo, "add", "-A")
    git(repo, "commit", "-m", "main: v3 charge path, retire legacy docs")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="results", help="output directory (default: results)")
    args = parser.parse_args(argv)
    out = Path(args.out)
    if not out.is_absolute():
        out = ROOT / out
    out.mkdir(parents=True, exist_ok=True)

    workspace = Path(tempfile.mkdtemp(prefix="mergecast-demo-"))
    try:
        repo = workspace / "shop"
        build_repo(repo)
        base = ["report", "--repo", str(repo), "--base", "main", "--head", "feature/payments"]
        env = {**os.environ, "PYTHONPATH": str(ROOT / "src"), "PYTHONIOENCODING": "utf-8"}

        text = subprocess.run(
            [sys.executable, "-m", "mergecast", *base],
            capture_output=True,
            text=True,
            env=env,
        )
        if text.returncode != 0:
            print(text.stderr, file=sys.stderr)
            return 1
        (out / "mergecast-report.txt").write_text(text.stdout, encoding="utf-8", newline="\n")

        as_json = subprocess.run(
            [sys.executable, "-m", "mergecast", *base, "--json"],
            capture_output=True,
            text=True,
            env=env,
        )
        if as_json.returncode != 0:
            print(as_json.stderr, file=sys.stderr)
            return 1
        data = json.loads(as_json.stdout)
        (out / "report.json").write_text(
            json.dumps(data, indent=2) + "\n", encoding="utf-8", newline="\n"
        )

        gate = subprocess.run(
            [sys.executable, "-m", "mergecast", *base, "--fail-on", "conflict"],
            capture_output=True,
            text=True,
            env=env,
        )
        (out / "gate.txt").write_text(
            f"command: mergecast report --base main --head feature/payments --fail-on conflict\n"
            f"exit code: {gate.returncode}\n",
            encoding="utf-8",
            newline="\n",
        )
        print(text.stdout, end="")
        print(f"gate exit code: {gate.returncode} (1 means conflicts were found)")
        print(f"artifacts written to {out}")
        return 0
    finally:
        shutil.rmtree(workspace, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
