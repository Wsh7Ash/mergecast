# Usage

## Typical workflow

```shell
git fetch origin
git switch feature/login

mergecast report --base origin/main --head HEAD
```

Exit code `0` means the report was produced; read the table for the risk levels.
Add a gate so CI fails on real overlap:

```shell
mergecast report --base origin/main --head HEAD --fail-on conflict
```

`--fail-on near` is stricter and useful when branches live for weeks.

## Reading the report

```text
LEVEL       FILE                               BASE±    HEAD±    DETAIL
conflict    src/app.py                         10       7        overlapping changed line ranges
                                               lines 11-13 vs lines 11-13
```

- `BASE±` / `HEAD±` are added plus removed lines on each side.
- The indented rows show the specific base-coordinate ranges that came close.
  `gap N` on a `near` row is the number of unchanged lines between the ranges.

Levels:

| Level | Meaning | Action |
|---|---|---|
| `conflict` | overlapping ranges, delete/modify, divergent rename | merge first, in isolation |
| `near` | ranges within `--proximity` lines | merge early; conflicts are likely next rebase |
| `touch` | same file, distant regions | review together, usually safe |
| `same-change` | identical edits on both sides | no action |

## JSON output

```json
{
  "base": {"ref": "main", "sha": "..."},
  "head": {"ref": "feature", "sha": "..."},
  "merge_base": "...",
  "proximity": 3,
  "counts": {"same-change": 0, "touch": 1, "near": 0, "conflict": 2},
  "files_changed_one_side": {"base_side": 0, "head_side": 0},
  "files": [
    {
      "path": "src/app.py",
      "base_path": "src/app.py",
      "level": "conflict",
      "reason": "overlapping changed line ranges",
      "a_churn": 10,
      "b_churn": 7,
      "a_range": "lines 11-13, lines 51-54",
      "b_range": "lines 11-13, lines 51-52",
      "overlaps": [
        {
          "level": "conflict",
          "base_start": 11,
          "base_end": 14,
          "a_span": "lines 11-13",
          "b_span": "lines 11-13",
          "gap": 0,
          "identical": false
        }
      ],
      "score": 3042
    }
  ]
}
```

The JSON shape is asserted by tests; treat it as stable for the 0.x series.

## Choosing a proximity

`--proximity 0` reports only actual overlaps. `3` (the default) catches the
common "both sides edited adjacent lines" case. `8`–`10` suits large, slow-moving
branches, at the cost of more noise.

## Demo

```shell
python scripts/demo.py
```

This creates a temporary repository named `shop` with two diverged branches,
prints the report, and writes `results/mergecast-report.txt`,
`results/report.json` and `results/gate.txt`. It does not touch your checkout.
