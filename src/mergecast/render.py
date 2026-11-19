"""Text and JSON rendering for mergecast reports."""

from __future__ import annotations

import json

from .analyze import Report

LEGEND = """\
Risk levels (fixed, so a verdict means the same thing for every branch)

  conflict     both sides changed the same lines, or deleted / renamed the file
               on one side while editing it on the other
  near         changed ranges sit within the proximity window (default 3 lines)
               and are likely to conflict once one side shifts the file
  touch        both sides edited the same file but in separate regions
  same-change  both sides made the byte-identical edit; git merges it cleanly

Hunks are compared in merge-base coordinates. Pure insertions count as a
one-line point at the insertion offset, which is where git's conflict markers
appear. Renames are followed with `git diff --find-renames`.
"""


def render_json(report: Report) -> str:
    return json.dumps(report.to_dict(), indent=2, sort_keys=False) + "\n"


def render_text(report: Report, top: int | None = None) -> str:
    out: list[str] = []
    out.append(
        f"mergecast report — {report.base_ref} ({report.base_sha[:7]}) "
        f"→ {report.head_ref} ({report.head_sha[:7]})"
    )
    out.append(f"merge base {report.merge_base[:7]} · proximity {report.proximity} lines")
    out.append("")

    counts = report.counts()
    files = report.files if top is None else report.files[:top]
    summaries = " · ".join(
        f"{counts[level]} {level}"
        for level in ("conflict", "near", "touch", "same-change")
    )
    out.append(f"{len(report.files)} file(s) changed on both sides · {summaries}")
    out.append(
        f"{report.a_only} file(s) only on {report.base_ref} · "
        f"{report.b_only} only on {report.head_ref}"
    )
    out.append("")

    if not files:
        out.append("No file was changed by both sides: the branches touch disjoint files.")
        return "\n".join(out) + "\n"

    path_width = max(4, min(44, max(len(f.path) for f in files)))
    header = f"{'LEVEL':<12}{'FILE':<{path_width + 2}}{'BASE±':<9}{'HEAD±':<9}DETAIL"
    out.append(header)
    out.append("-" * len(header))
    for item in files:
        path = item.path if len(item.path) <= path_width else "…" + item.path[-(path_width - 1) :]
        out.append(
            f"{item.level:<12}{path:<{path_width + 2}}"
            f"{item.a_churn:<9}{item.b_churn:<9}"
            f"{item.reason}"
        )
        for overlap in item.overlaps[:3]:
            out.append(
                f"{'':<12}{'':<{path_width + 2}}"
                f"{overlap.a_span} vs {overlap.b_span}"
                + (f" (gap {overlap.gap})" if overlap.level == "near" else "")
            )
        if len(item.overlaps) > 3:
            out.append(f"{'':<12}{'':<{path_width + 2}}… {len(item.overlaps) - 3} more overlap(s)")
    return "\n".join(out) + "\n"
