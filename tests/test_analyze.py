from pathlib import Path

import pytest

from mergecast.analyze import ReportError, build_report, compare_hunk
from mergecast.gitio import Hunk

from conftest import commit, git, lines, replace_lines, scenario, write


def hunk(old_start, old_len, new_len=None, lines_=()):
    return Hunk(
        old_start=old_start,
        old_len=old_len,
        new_start=old_start,
        new_len=old_len if new_len is None else new_len,
        lines=tuple(lines_),
    )


def test_overlapping_ranges_are_conflicts(example_repo):
    report = build_report(example_repo, "main", "feature")
    assert len(report.files) == 1
    file = report.files[0]
    assert file.path == "src/app.py"
    assert file.level == "conflict"
    assert "overlapping" in file.reason
    assert file.a_churn == 5 and file.b_churn == 5
    assert report.counts()["conflict"] == 1


def test_separate_regions_touch(tmp_path):
    base = lines(40)
    repo = scenario(
        tmp_path,
        {"app.py": base},
        {"app.py": replace_lines(base, 3, 3, "main\n")},
        {"app.py": replace_lines(base, 30, 30, "feature\n")},
    )
    file = build_report(repo, "main", "feature").files[0]
    assert file.level == "touch"
    assert file.overlaps == ()


def test_near_window_is_respected(tmp_path):
    base = lines(40)
    repo = scenario(
        tmp_path,
        {"app.py": base},
        {"app.py": replace_lines(base, 10, 10, "main\n")},
        {"app.py": replace_lines(base, 14, 14, "feature\n")},
    )
    report = build_report(repo, "main", "feature", proximity=3)
    file = report.files[0]
    assert file.level == "near"
    assert file.overlaps[0].gap == 3

    strict = build_report(repo, "main", "feature", proximity=0)
    assert strict.files[0].level == "touch"


def test_identical_edits_are_low_risk(tmp_path):
    base = lines(10)
    edited = replace_lines(base, 4, 4, "same change\n")
    repo = scenario(tmp_path, {"a.txt": base}, {"a.txt": edited}, {"a.txt": edited})
    file = build_report(repo, "main", "feature").files[0]
    assert file.level == "same-change"
    assert file.overlaps[0].identical is True


def test_insertions_at_the_same_offset_conflict(tmp_path):
    base = lines(10)
    repo = scenario(
        tmp_path,
        {"a.txt": base},
        {"a.txt": base.replace("line 05\n", "line 05\nmain insert\n")},
        {"a.txt": base.replace("line 05\n", "line 05\nfeature insert\n")},
    )
    file = build_report(repo, "main", "feature").files[0]
    assert file.level == "conflict"


def test_delete_modify_is_a_conflict(tmp_path):
    repo = scenario(
        tmp_path,
        {"a.txt": lines(5), "b.txt": lines(5)},
        {"a.txt": None},
        {"a.txt": lines(5).replace("line 02\n", "changed\n")},
    )
    file = build_report(repo, "main", "feature").files[0]
    assert file.level == "conflict"
    assert "delete/modify" in file.reason


def test_divergent_rename_is_a_conflict(tmp_path):
    repo = tmp_path / "rename-repo"
    repo.mkdir()
    git(repo, "init", "-b", "main")
    git(repo, "config", "user.email", "test@example.com")
    git(repo, "config", "user.name", "Test")
    write(repo, "old.py", lines(5))
    commit(repo, "base")

    git(repo, "checkout", "-b", "feature")
    git(repo, "mv", "old.py", "new.py")
    commit(repo, "rename on feature")
    git(repo, "checkout", "main")
    git(repo, "mv", "old.py", "main.py")
    commit(repo, "rename on main")

    file = build_report(repo, "main", "feature").files[0]
    assert file.level == "conflict"
    assert "divergent-rename" in file.reason


def test_files_changed_on_one_side_are_counted(tmp_path):
    repo = scenario(
        tmp_path,
        {"a.txt": lines(5), "b.txt": lines(5)},
        {"a.txt": lines(6)},
        {"b.txt": lines(7)},
    )
    report = build_report(repo, "main", "feature")
    assert report.files == []
    assert (report.a_only, report.b_only) == (1, 1)
    assert report.counts()["conflict"] == 0


def test_results_are_sorted_by_risk(tmp_path):
    base = lines(40)
    repo = scenario(
        tmp_path,
        {"conflict.py": base, "touch.py": base},
        {
            "conflict.py": replace_lines(base, 5, 5, "m\n"),
            "touch.py": replace_lines(base, 2, 2, "m\n"),
        },
        {
            "conflict.py": replace_lines(base, 5, 5, "f\n"),
            "touch.py": replace_lines(base, 30, 30, "f\n"),
        },
    )
    files = build_report(repo, "main", "feature").files
    assert [f.path for f in files] == ["conflict.py", "touch.py"]
    assert files[0].score > files[1].score


def test_unknown_revision_raises(example_repo):
    with pytest.raises(ReportError, match="unknown revision"):
        build_report(example_repo, "main", "does-not-exist")


def test_non_repository_raises(tmp_path):
    with pytest.raises(ReportError, match="not a git repository"):
        build_report(tmp_path)


def test_negative_proximity_raises(example_repo):
    with pytest.raises(ReportError, match="proximity"):
        build_report(example_repo, "main", "feature", proximity=-1)


def test_compare_hunk_identical_requires_content():
    a = hunk(5, 1, lines_=("+x",))
    b = hunk(5, 1, lines_=("+x",))
    assert compare_hunk(a, b, 0).identical is True
    empty_a, empty_b = hunk(5, 0), hunk(5, 0)
    assert compare_hunk(empty_a, empty_b, 0) is not None
    assert compare_hunk(empty_a, empty_b, 0).level == "conflict"


def test_json_shape_is_stable(example_repo):
    data = build_report(example_repo, "main", "feature").to_dict()
    assert set(data) == {
        "base",
        "head",
        "merge_base",
        "proximity",
        "counts",
        "files_changed_one_side",
        "files",
    }
    assert data["files"][0]["level"] == "conflict"
    assert set(data["files"][0]["overlaps"][0]) == {
        "level",
        "base_start",
        "base_end",
        "a_span",
        "b_span",
        "gap",
        "identical",
    }
