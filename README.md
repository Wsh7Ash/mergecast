# mergecast

**Predict where a branch merge will hurt before you run `git merge`.**

`mergecast` compares two branches against their common ancestor, matches the
changed line ranges on both sides, and ranks the files most likely to conflict —
including "near misses" that do not conflict today but will as soon as one side
moves a line.

```text
mergecast report — main (7164f98) → feature/payments (18b74a5)
merge base 3239f90 · proximity 3 lines

3 file(s) changed on both sides · 2 conflict · 0 near · 1 touch · 0 same-change
0 file(s) only on main · 0 only on feature/payments

LEVEL       FILE                               BASE±    HEAD±    DETAIL
-----------------------------------------------------------------------
conflict    src/app.py                         10       7        overlapping changed line ranges
                                               lines 11-13 vs lines 11-13
                                               lines 51-54 vs lines 51-52
conflict    docs/legacy.md / docs/payments.md  12       0        delete/modify: one side removes the file the other edits
touch       src/config.py                      2        2        different regions of the same file
```

## The problem

`git merge --no-commit --no-ff` tells you about conflicts only after it has
modified your working tree, and reviewers looking at two pull requests in
isolation cannot see that both touch the same function. Teams merging long-lived
branches discover the overlap at the worst possible moment: during the merge.

## What it does

- Finds the merge base and diffs each side against it, so hunk ranges share one
  coordinate system.
- Compares every pair of hunks per file and classifies the file as
  `conflict`, `near`, `touch` or `same-change`.
- Follows renames (`--find-renames`) and flags divergent renames and
  delete/modify pairs.
- Treats pure insertions as a point at the insertion offset — where git actually
  raises the conflict.
- Weights the report by churn so the scariest files come first, and exposes
  `--fail-on conflict|near` for CI.

## Requirements

- Python 3.12+
- `git` on `PATH` (2.30+ recommended for `--find-renames` consistency)
- No Python dependencies

## Install

```shell
git clone https://github.com/Wsh7Ash/mergecast.git
cd mergecast
python -m pip install -e .
```

Or run it straight from the checkout without installing:

```shell
PYTHONPATH=src python -m mergecast report --base main --head feature
```

## Quick start

```shell
cd your-repository
mergecast report --base main --head feature/login
```

Use `--json` for machine-readable output and `--fail-on near` to block a merge
in CI:

```shell
mergecast report --base origin/main --head HEAD --fail-on conflict --json > mergecast.json
```

## Usage examples

Review a pull request branch from the branch's own checkout:

```shell
mergecast report --base main                    # --head defaults to HEAD
```

Widen the "will conflict soon" window:

```shell
mergecast report --base main --head release/2.4 --proximity 8
```

Show only the five riskiest files and explain the levels:

```shell
mergecast report --base main --head feature --top 5
mergecast explain
```

Example artifacts from a generated demo repository live in
[`results/`](results/): `mergecast-report.txt`, `report.json` and `gate.txt`.
Regenerate them with `python scripts/demo.py`.

## Configuration

There is no configuration file; every option is a flag.

| Flag | Default | Meaning |
|---|---|---|
| `--repo` | `.` | Path inside the git work tree |
| `--base` | `main` | Branch you are merging into |
| `--head` | `HEAD` | Branch you want to merge |
| `--proximity` | `3` | Line distance at which two ranges count as `near` |
| `--top` | all | Limit rows in the text report |
| `--json` | off | Emit JSON instead of a table |
| `--fail-on` | `none` | Exit 1 when this level or worse exists |

## Testing

```shell
python -m pip install -e ".[dev]"
PYTHONPATH=src python -m pytest tests -v
```

The suite builds real temporary git repositories (30 tests) covering overlapping
edits, insertions at the same offset, identical edits, proximity thresholds,
delete/modify, divergent renames, JSON shape, exit codes and argument errors.

## Project structure

```text
mergecast/
├─ src/mergecast/
│  ├─ gitio.py      # read-only git wrapper + unified-diff parser
│  ├─ analyze.py    # hunk comparison and risk ranking
│  ├─ render.py     # text table, JSON, legend
│  └─ cli.py        # argparse entry point
├─ scripts/demo.py  # builds a throwaway diverged repo and captures results
├─ tests/           # pytest suite (real git repositories)
├─ examples/        # demo scenario description
├─ results/         # observed output from scripts/demo.py
└─ docs/            # architecture, usage, project spec
```

## Limitations

- Line-based analysis only. Two sides can touch different lines and still
  conflict semantically (renamed functions, changed signatures).
- Paths containing the exact substring ` b/` are parsed best-effort because they
  are ambiguous in `diff --git` headers; git's quoted paths are unquoted but
  exotic escapes may not round-trip.
- Binary files are diffed with `-U0` and usually report no hunks, so they appear
  as `touch` at most.
- Rename detection depends on git's similarity threshold; a heavily rewritten
  rename is seen as delete + add.
- Files changed on only one side are counted, not analysed.
- No three-way or recursive merge simulation: the report is a risk signal, not a
  merge oracle.

## Roadmap

- Compare a whole PR stack (`base..ref1..ref2`) and report cross-PR overlaps.
- Optional `--include-single-side` to list heavy churn files even when only one
  side touched them.
- SARIF output for code-scanning annotations.
- Cache diffs between runs for very large repositories.

## License

MIT — see [LICENSE](LICENSE).
