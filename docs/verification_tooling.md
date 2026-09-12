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

## Notes

- Python 3.14 makes branch coverage inexpensive through `sys.monitoring`.
- Step output is replayed only where a step failed.  A single-step run
  (`just test-py`) streams live instead; `--verbose` and `--quiet` force it
  either way.
- Full exception-leak sweeps are bounded by subprocess timeouts where
  parsing or unbounded growth cannot be safely interrupted by a step cap: a
  SIGALRM cannot land inside sympy's uninterruptible C, which is also why
  Factor is screened by operand size rather than by a cap.
