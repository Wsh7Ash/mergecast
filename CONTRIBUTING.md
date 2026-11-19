# Contributing

Thanks for taking a look at `mergecast`.

## Development setup

```shell
git clone https://github.com/Wsh7Ash/mergecast.git
cd mergecast
python -m pip install -e ".[dev]"
```

There are no runtime dependencies. Keep it that way unless a dependency removes
a substantial amount of code.

## Running checks

```shell
PYTHONPATH=src python -m pytest tests -v
python scripts/demo.py
```

The test suite creates real git repositories under pytest's temporary directory.
It must stay network-free and must not depend on the developer's git identity;
use the helpers in `tests/conftest.py`.

## Guidelines

- Every behaviour change needs a test that fails before the change.
- Risk-level semantics are fixed. Changing a level, threshold default or score
  weight is a breaking change: update `LEGEND`, the README table and the docs.
- Keep git invocations read-only and non-interactive.
- Public functions get type annotations and a short docstring explaining why,
  not just what.

## Submitting a change

Open a pull request with a short description of the problem, the chosen
trade-off, and the commands you ran. Screenshots are not needed for CLI output;
paste the observed report instead.
