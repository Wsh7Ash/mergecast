# Project spec

**Name:** mergecast
**Category:** dev-tool
**Target user:** developers and reviewers on a team that merges feature or
release branches into a long-lived mainline.

**Problem:** a conflict is discovered only when the merge is attempted, after
the working tree is already dirty. Reviewers of separate pull requests cannot
see that two branches edit the same lines.

**Solution:** diff both branches against their merge base, compare hunk ranges
per file, and produce a ranked risk report before the merge.

**Core workflow:**

1. `mergecast report --base main --head feature`
2. The tool finds the merge base and diffs both sides against it.
3. Files touched by both sides are classified and ranked.
4. The developer merges the `conflict` files first, or gates CI with
   `--fail-on conflict`.

**Must-have features (implemented):**

- merge-base coordinate comparison of side diffs
- conflict / near / touch / same-change classification with proximity window
- delete/modify and divergent-rename detection
- rename following
- churn-weighted ranking, `--top`, text and JSON output
- exit-code gate
- real-repository test suite

**Nice-to-have (not implemented):** PR-stack comparison, SARIF output, caching,
single-side churn listing.

**Stack:** Python 3.12+, standard library only, git CLI.

**Test strategy:** build temporary git repositories for each scenario; assert
level, ranges, churn, counts, exit codes and JSON shape. Parser unit tests use
literal diff text. No test touches the network or the project's own history.

**Demo/result strategy:** `scripts/demo.py` builds a throwaway repo with a
genuine overlap, an independent edit and a delete/modify pair, then captures
text, JSON and gate output in `results/`.

**Safety considerations:** read-only git commands, no credential prompts, no
external diff drivers, no network.

**Definition of done:** tests green, demo output committed, docs complete,
secret scan clean, repository published.
