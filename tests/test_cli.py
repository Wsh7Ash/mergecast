import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(args, cwd):
    return subprocess.run(
        [sys.executable, "-m", "mergecast", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        env={**_env(), "PYTHONPATH": str(ROOT / "src")},
    )


def _env():
    import os

    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    return env


def test_report_prints_table(example_repo):
    proc = run(["report", "--base", "main", "--head", "feature"], example_repo)
    assert proc.returncode == 0, proc.stderr
    assert "mergecast report" in proc.stdout
    assert "src/app.py" in proc.stdout
    assert "conflict" in proc.stdout


def test_json_output(example_repo):
    proc = run(["report", "--base", "main", "--head", "feature", "--json"], example_repo)
    assert proc.returncode == 0, proc.stderr
    data = json.loads(proc.stdout)
    assert data["files"][0]["level"] == "conflict"
    assert data["proximity"] == 3


def test_gate_exits_one_on_conflict(example_repo):
    proc = run(["report", "--head", "feature", "--fail-on", "conflict"], example_repo)
    assert proc.returncode == 1


def test_gate_passes_when_only_touch(tmp_path):
    from conftest import lines, replace_lines, scenario

    base = lines(40)
    repo = scenario(
        tmp_path,
        {"a.txt": base},
        {"a.txt": replace_lines(base, 2, 2, "m\n")},
        {"a.txt": replace_lines(base, 30, 30, "f\n")},
    )
    proc = run(["report", "--base", "main", "--head", "feature", "--fail-on", "near"], repo)
    assert proc.returncode == 0, proc.stdout
    assert "0 conflict" in proc.stdout


def test_explain(example_repo):
    proc = run(["explain"], example_repo)
    assert proc.returncode == 0
    assert "same-change" in proc.stdout


def test_bad_ref_exits_two(example_repo):
    proc = run(["report", "--base", "nope"], example_repo)
    assert proc.returncode == 2
    assert "unknown revision" in proc.stderr


def test_bad_top_exits_two(example_repo):
    proc = run(["report", "--top", "0"], example_repo)
    assert proc.returncode == 2


def test_leading_program_token_is_tolerated(example_repo):
    proc = run(["mergecast", "report", "--json"], example_repo)
    assert proc.returncode == 0, proc.stderr
    assert "files" in json.loads(proc.stdout)


def test_top_limits_rows(tmp_path):
    from conftest import lines, replace_lines, scenario

    base = lines(40)
    repo = scenario(
        tmp_path,
        {"a.txt": base, "b.txt": base},
        {"a.txt": replace_lines(base, 5, 5, "m\n"), "b.txt": replace_lines(base, 6, 6, "m\n")},
        {"a.txt": replace_lines(base, 5, 5, "f\n"), "b.txt": replace_lines(base, 6, 6, "f\n")},
    )
    proc = run(["report", "--head", "feature", "--top", "1"], repo)
    assert proc.returncode == 0
    assert proc.stdout.count(".txt") == 1


def test_runs_against_current_directory_by_default(example_repo):
    proc = run(["report"], example_repo)
    assert proc.returncode == 0
    assert "main" in proc.stdout
