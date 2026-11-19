# Architecture

`mergecast` is a three-stage pipeline: read git data, compare ranges, render.

```text
CLI (cli.py)
  └─ analyze.build_report()
        ├─ gitio.repo_root / resolve_commit / merge_base
        ├─ gitio.diff_against_base × 2   (base side, head side)
        └─ compare_hunk × hunks
  └─ render.render_text / render_json
```

## Why the merge base is the coordinate system

A diff between the base branch tip and the feature branch tip mixes two kinds of
change: what the feature did, and what the base branch did since the branches
split. Comparing hunks from that diff would attribute base-branch edits to the
feature branch.

Instead both sides are diffed against the merge base:

```text
            ┌── A1 ── A2   (base branch)
base ───────┤
            └── B1 ── B2   (feature branch)

diff(base, A2) → hunks in base coordinates
diff(base, B2) → hunks in base coordinates   ← directly comparable
```

Because `git diff -U0` reports old-file line numbers, every hunk carries an
interval `[old_start, old_start + old_len)` in base coordinates. Those intervals
are what `compare_hunk` intersects.

## Risk classification

For each file touched by both sides, every hunk pair is compared:

| Condition | Level |
|---|---|
| Identical patch text in both sides' hunks | `same-change` |
| Intervals intersect | `conflict` |
| Gap between intervals ≤ proximity | `near` |
| Otherwise | `touch` |

A file's level is the worst overlap level, defaulting to `touch` when both sides
edited the file in separate regions. Two structural cases override the hunk
comparison:

- one side deleted the file and the other edited it → `conflict`;
- both sides renamed the file to different paths → `conflict`.

Pure insertions have `old_len == 0`. They are modelled as a one-line point at
`old_start`, because that is where git places conflict markers when both sides
insert at the same offset.

`same-change` is deliberately the lowest level: if both branches made the
byte-identical edit, git merges the file without conflict markers, so warning
about it would train users to ignore the report.

## Scoring

`score = level_weight + churn + 25 × overlap_count` with weights
`conflict 3000`, `near 2000`, `touch 1000`, `same-change 0`. Churn is the sum of
added and removed lines across both sides, computed from hunk lengths rather
than `--numstat`, so it is consistent with the ranges shown.

## Failure modes

- Missing refs, non-repositories and missing merge bases raise `ReportError`,
  which the CLI turns into exit code 2 and a one-line message.
- The git wrapper never prompts for credentials (`GIT_TERMINAL_PROMPT=0`) and
  disables external diff drivers, pagers and text conversion, so output cannot
  be hijacked by local configuration.
- No repository state is modified: every git invocation is `rev-parse`,
  `merge-base` or `diff`.
