# Changelog

## 0.1.0 — 2026-11-19

Initial release.

- Merge-base coordinate comparison of two branch diffs.
- `conflict` / `near` / `touch` / `same-change` classification with configurable
  proximity.
- Delete/modify and divergent-rename detection.
- Rename following via `git diff --find-renames`.
- Churn-weighted ranking, text and JSON output, `--top`, `--fail-on` gate.
- Demo script that builds a throwaway diverged repository.
- 30 tests over real temporary git repositories.
