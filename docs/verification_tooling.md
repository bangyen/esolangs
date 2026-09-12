# Verification and mutation tooling

`scripts/verify.py` is authoritative.  Run `just test` for branch-scoped
verification and `just test-full` before release work.

## Mutation

- `mutate_one.py` mutates a dependency-closed bundled interpreter; mutating
  an installed package is not reliable.
- mutmut is pinned at 3.7.0 -- earlier versions missed class-method mutants
  and emitted no-op mutants.
- A score below 76.7% is a broken measurement, not a reportable result.

For triage, trust the harness first: use the worktree's source, compare
complete snapshots, test exact error messages, retain positive controls.
Remove redundant or unobservable code rather than writing vacuous tests for
it.  Re-run mutation after a refactor -- a cleaner expression can still
create an untestable branch.

## How the steps are scheduled

Not run in order.  `pre-commit` goes alone (it rewrites the files the rest
read), then `pytest` with the one-core steps in its shadow, then the
coverage gate, then the steps that are parallel in their own right.

Only one-core steps get the shadow.  Sharing it with the leak sweep cost
more than it saved: on a branch touching the four timeout-burning
interpreters, run back to back under the same external load, 117.6s wall
against 84.8s, with `pytest` itself 111.3s against 48.3s for the same
tests.  The win is the busy machine -- idle, four xdist workers and two
sweep workers roughly fit the eight performance cores.

## What CI runs

| Trigger | Selection | Coverage gate |
| --- | --- | --- |
| push, pull request | `-m "not slow"`, on 3.12/3.13/3.14 | reports (`--partial`) |
| Mondays 06:00 UTC, or by hand | the whole suite, same three | none -- it is diff-scoped, and a scheduled run on `main` has no merge base |

The split is a wall-time call, not a confidence one.  Measured locally at
two workers: `-m "not slow"` is 10314 tests in 81s, `-m slow` is 335 in
289s.  There is no worker count to raise: `-n auto` is already every vCPU
the runner has, since psutil is absent and xdist falls back to
`os.cpu_count()`.

The slow band was 467s before three fixes, none of which weakened an
assertion -- what they removed was repeated work and dead waiting:

| Fix | Saved |
| --- | --- |
| Qoibl caches its tokenization by source; `verify` was paying the identical search once per row | 90s |
| `test_generic_verifier`'s termination bound 5.0s -> 1.0s; the diverging rows had already decided and the slowest *halting* row measures 0.000s | 60s |
| `test_wrap`'s run bound 5.0s -> 2.0s; the slowest halting run in that corpus is 0.296s | 28s |

The same pattern is worth checking first whenever a test's duration is a
round multiple of a timeout: `mixed-123` measured 60.01s, which is six
one-rows times two programs times 5.0.

The cost is that `check_diff_coverage.py` reports instead of failing on a
PR: with a subset selected, an uncovered line may just belong to a test
that did not run.  The blocking form is the local command that report
prints.

## Notes

- Python 3.14 makes branch coverage inexpensive through `sys.monitoring`.
- Step output is replayed only where a step failed.  A single-step run
  (`just test-py`) streams live instead; `--verbose` and `--quiet` force it
  either way.
- Full exception-leak sweeps are bounded by subprocess timeouts where
  parsing or unbounded growth cannot be safely interrupted by a step cap: a
  SIGALRM cannot land inside sympy's uninterruptible C, which is also why
  Factor is screened by operand size rather than by a cap.
