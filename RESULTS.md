# Results

## Environment

- OS: Windows 11 (win32, Git Bash)
- Python: 3.14.3
- Git: 2.55.0.windows.3
- Test runner: pytest 9.1.1
- Dependency manager: pip (no runtime dependencies)

## Validation performed

- install: PASS (`python -m pip install -e ".[dev]"` is not required to run from source; `PYTHONPATH=src` works)
- build: PASS (package imports; `python -m mergecast explain` runs)
- unit tests: PASS (30/30)
- integration tests: PASS (tests build real temporary git repositories)
- lint: N/A (no linter configured; the project is stdlib-only and formatted by hand)
- type check: N/A (no type checker configured; annotations are used throughout)
- demo run: PASS (`python scripts/demo.py`)

## Commands executed

```shell
PYTHONPATH=src python -m pytest tests -q
python scripts/demo.py
PYTHONPATH=src python -m mergecast explain
```

## Observed result

```text
..............................                                           [100%]
30 passed in 28.77s
```

The demo repository contains a real overlapping edit in `src/app.py`, a second
overlapping pair further down the same file, an independent edit in
`src/config.py`, and a file that `main` deleted while the feature branch renamed
it. Observed report:

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

`--fail-on conflict` exited with code 1 on this repository, as recorded in
`results/gate.txt`.

## Generated artifacts

- `results/mergecast-report.txt` — captured text report
- `results/report.json` — captured JSON report
- `results/gate.txt` — gate command and observed exit code

## Known limitations

- Line-level analysis; semantic conflicts on untouched lines are invisible.
- Binary files produce no hunks and therefore never exceed `touch`.
- Renames below git's similarity threshold are treated as delete + add.
- Only files changed on both sides are analysed.
- Paths containing ` b/` are parsed best-effort.
