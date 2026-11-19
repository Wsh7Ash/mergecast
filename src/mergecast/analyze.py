"""Turn two branch diffs into a ranked merge-risk report.

The central idea is that a merge conflict is decided by *line ranges*, not by
file names.  Both sides' diffs are expressed against the merge base, so their
hunk ranges share one coordinate system and can be compared directly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .gitio import FileDiff, GitError, diff_against_base, merge_base, repo_root, resolve_commit

LEVEL_RANK = {"same-change": 0, "touch": 1, "near": 2, "conflict": 3}
LEVEL_LABEL = {
    "same-change": "same-change",
    "touch": "touch",
    "near": "near",
    "conflict": "conflict",
}


class ReportError(RuntimeError):
    """Raised when a report cannot be produced."""


@dataclass(frozen=True)
class Overlap:
    level: str
    base_start: int
    base_end: int
    a_span: str
    b_span: str
    gap: int
    identical: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "level": self.level,
            "base_start": self.base_start,
            "base_end": self.base_end,
            "a_span": self.a_span,
            "b_span": self.b_span,
            "gap": self.gap,
            "identical": self.identical,
        }


@dataclass(frozen=True)
class FileRisk:
    path: str
    base_path: str
    level: str
    reason: str
    a_churn: int
    b_churn: int
    a_range: str
    b_range: str
    overlaps: tuple[Overlap, ...] = ()
    score: int = 0

    @property
    def churn(self) -> int:
        return self.a_churn + self.b_churn

    def to_dict(self) -> dict[str, object]:
        return {
            "path": self.path,
            "base_path": self.base_path,
            "level": self.level,
            "reason": self.reason,
            "a_churn": self.a_churn,
            "b_churn": self.b_churn,
            "a_range": self.a_range,
            "b_range": self.b_range,
            "overlaps": [o.to_dict() for o in self.overlaps],
            "score": self.score,
        }


@dataclass
class Report:
    base_ref: str
    head_ref: str
    base_sha: str
    head_sha: str
    merge_base: str
    files: list[FileRisk] = field(default_factory=list)
    proximity: int = 3
    a_only: int = 0
    b_only: int = 0

    def counts(self) -> dict[str, int]:
        counts = {level: 0 for level in LEVEL_RANK}
        for item in self.files:
            counts[item.level] += 1
        return counts

    @property
    def level(self) -> str:
        """Worst level present, used for the exit-code gate."""
        if not self.files:
            return "same-change"
        return max((f.level for f in self.files), key=LEVEL_RANK.__getitem__)

    def to_dict(self) -> dict[str, object]:
        return {
            "base": {"ref": self.base_ref, "sha": self.base_sha},
            "head": {"ref": self.head_ref, "sha": self.head_sha},
            "merge_base": self.merge_base,
            "proximity": self.proximity,
            "counts": self.counts(),
            "files_changed_one_side": {"base_side": self.a_only, "head_side": self.b_only},
            "files": [f.to_dict() for f in self.files],
        }


def _ranges(hunks) -> str:
    if not hunks:
        return "-"
    return ", ".join(h.span() for h in hunks)


def compare_hunk(a, b, proximity: int) -> Overlap | None:
    """Return an Overlap when two hunks are close enough to matter."""
    identical = a.lines == b.lines and bool(a.lines)
    if identical:
        return Overlap(
            level="same-change",
            base_start=min(a.old_start, b.old_start),
            base_end=max(a.old_end, b.old_end),
            a_span=a.span(),
            b_span=b.span(),
            gap=0,
            identical=True,
        )

    a_start, a_end = a.old_start, a.old_end
    b_start, b_end = b.old_start, b.old_end
    if a_start < b_end and b_start < a_end:
        return Overlap(
            level="conflict",
            base_start=max(a_start, b_start),
            base_end=min(a_end, b_end),
            a_span=a.span(),
            b_span=b.span(),
            gap=0,
            identical=False,
        )
    gap = max(a_start, b_start) - min(a_end, b_end)
    if gap <= proximity:
        return Overlap(
            level="near",
            base_start=min(a_start, b_start),
            base_end=max(a_end, b_end),
            a_span=a.span(),
            b_span=b.span(),
            gap=gap,
            identical=False,
        )
    return None


def _file_level(overlaps: tuple[Overlap, ...]) -> str:
    if not overlaps:
        return "touch"
    return max((o.level for o in overlaps), key=LEVEL_RANK.__getitem__)


def _reason(level: str, overlaps: tuple[Overlap, ...], a: FileDiff, b: FileDiff) -> str:
    if a.deleted and b.deleted:
        return "both sides delete the file"
    if a.deleted or b.deleted:
        return "delete/modify: one side removes the file the other edits"
    if a.path != b.path:
        return f"divergent-rename: {a.base_path} -> {a.path} / {b.path}"
    if level == "conflict":
        return "overlapping changed line ranges"
    if level == "near":
        return "changed ranges within the proximity window"
    if level == "same-change":
        return "both sides made the identical edit"
    return "different regions of the same file"


def _score(level: str, overlaps: tuple[Overlap, ...], churn: int) -> int:
    base = {"conflict": 3000, "near": 2000, "touch": 1000, "same-change": 0}[level]
    return base + churn + 25 * len(overlaps)


def build_report(
    repo: str | Path,
    base_ref: str = "main",
    head_ref: str = "HEAD",
    proximity: int = 3,
) -> Report:
    if proximity < 0:
        raise ReportError("proximity must be zero or greater")
    try:
        root = repo_root(repo)
        base_sha = resolve_commit(root, base_ref)
        head_sha = resolve_commit(root, head_ref)
        ancestor = merge_base(root, base_ref, head_ref)
    except GitError as exc:
        raise ReportError(str(exc)) from exc

    a_side = diff_against_base(root, ancestor, base_sha)
    b_side = diff_against_base(root, ancestor, head_sha)

    a_map = {f.base_path: f for f in a_side}
    b_map = {f.base_path: f for f in b_side}

    report = Report(
        base_ref=base_ref,
        head_ref=head_ref,
        base_sha=base_sha,
        head_sha=head_sha,
        merge_base=ancestor,
        proximity=proximity,
    )
    report.a_only = len(set(a_map) - set(b_map))
    report.b_only = len(set(b_map) - set(a_map))

    for path in sorted(set(a_map) & set(b_map)):
        a, b = a_map[path], b_map[path]
        overlaps: list[Overlap] = []
        for ha in a.hunks:
            for hb in b.hunks:
                found = compare_hunk(ha, hb, proximity)
                if found is not None:
                    overlaps.append(found)
        overlaps.sort(key=lambda o: (-LEVEL_RANK[o.level], o.base_start))
        overlap_tuple = tuple(overlaps)
        if a.deleted or b.deleted:
            level = "conflict"
            overlap_tuple = ()
        elif a.path != b.path:
            level = "conflict"
        else:
            level = _file_level(overlap_tuple)
        churn = a.churn + b.churn
        report.files.append(
            FileRisk(
                path=a.path if a.path == b.path else f"{a.path} / {b.path}",
                base_path=path,
                level=level,
                reason=_reason(level, overlap_tuple, a, b),
                a_churn=a.churn,
                b_churn=b.churn,
                a_range=_ranges(a.hunks),
                b_range=_ranges(b.hunks),
                overlaps=overlap_tuple,
                score=_score(level, overlap_tuple, churn),
            )
        )

    report.files.sort(key=lambda f: (-f.score, f.path))
    return report
