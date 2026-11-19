"""mergecast — predict merge pain between two git branches from their diffs."""

from .analyze import LEVEL_LABEL, LEVEL_RANK, FileRisk, Report, ReportError, build_report, compare_hunk
from .gitio import FileDiff, GitError, Hunk, parse_diff

__version__ = "0.1.0"

__all__ = [
    "FileDiff",
    "FileRisk",
    "GitError",
    "Hunk",
    "LEVEL_LABEL",
    "LEVEL_RANK",
    "Report",
    "ReportError",
    "build_report",
    "compare_hunk",
    "parse_diff",
    "__version__",
]
