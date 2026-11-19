"""Command line entry point for mergecast."""

from __future__ import annotations

import argparse
import sys

from .analyze import LEVEL_RANK, ReportError, build_report
from .render import LEGEND, render_json, render_text


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mergecast",
        description="Predict merge pain between two git branches from their diffs.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    report = sub.add_parser("report", help="analyse two branches")
    report.add_argument("--repo", default=".", help="path inside the git work tree (default: .)")
    report.add_argument("--base", default="main", help="branch to merge into (default: main)")
    report.add_argument("--head", default="HEAD", help="branch you want to merge (default: HEAD)")
    report.add_argument("--proximity", type=int, default=3, help="lines treated as 'near' (default: 3)")
    report.add_argument("--top", type=int, default=None, help="show only the N riskiest files")
    report.add_argument("--json", action="store_true", help="machine-readable output")
    report.add_argument(
        "--fail-on",
        choices=("none", "near", "conflict"),
        default="none",
        help="exit 1 when a file at this level or worse exists",
    )

    sub.add_parser("explain", help="print the risk legend")
    return parser


def _print(safe: str) -> None:
    try:
        sys.stdout.write(safe)
    except UnicodeEncodeError:
        sys.stdout.buffer.write(safe.encode("utf-8", "replace"))
        sys.stdout.flush()


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    # Tolerate a leading "mergecast" token (e.g. `python -m mergecast mergecast report`).
    if argv and argv[0] == "mergecast":
        argv = argv[1:]
    if not argv:
        argv = ["report"]
    args = _parser().parse_args(argv)

    if args.command == "explain":
        _print(LEGEND)
        return 0

    if args.top is not None and args.top < 1:
        print("mergecast: --top must be at least 1", file=sys.stderr)
        return 2

    try:
        report = build_report(args.repo, base_ref=args.base, head_ref=args.head, proximity=args.proximity)
    except ReportError as exc:
        print(f"mergecast: {exc}", file=sys.stderr)
        return 2

    _print(render_json(report) if args.json else render_text(report, top=args.top))

    if args.fail_on != "none":
        floor = LEVEL_RANK[args.fail_on]
        if any(LEVEL_RANK[f.level] >= floor for f in report.files):
            return 1
    return 0
