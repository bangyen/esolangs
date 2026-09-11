# Verification and mutation tooling

`scripts/verify.py` is authoritative. Run `just test` for branch-scoped
verification and `just test-full` before release work.

- Python 3.14 makes branch coverage inexpensive through `sys.monitoring`.
- `mutate_one.py` mutates a dependency-closed bundled interpreter; mutating
  an installed package is not reliable.
- mutmut is pinned at 3.7.0 because earlier versions missed class-method
  mutants and emitted no-op mutants.
- A mutation score below 76.7% is treated as a broken measurement, not a
  reportable result.
- The stack is scheduled, not run in order: `pre-commit` alone (it rewrites
  the files the rest read), then `pytest` with the one-core steps in its
  shadow, then the coverage gate, then the steps that are parallel in their
  own right. Only steps that use one core get the shadow. Sharing it with
  the leak sweep cost more than it saved — on a branch touching the four
  timeout-burning interpreters, run back to back under the same external
  load, 117.6s wall against 84.8s, with `pytest` itself 111.3s against 48.3s
  for the same tests. The win is the busy machine; idle, four xdist workers
  and two sweep workers roughly fit the eight performance cores.
- Step output is replayed only where a step failed. A run of a single step
  (`just test-py`) streams live instead; `--verbose` and `--quiet` force it
  either way.
- Full exception-leak sweeps are bounded by subprocess timeouts where
  parsing or unbounded growth cannot be safely interrupted by a step cap: a
  SIGALRM cannot land inside sympy's uninterruptible C, which is also why
  Factor is screened by operand size rather than by a cap.

For mutation triage, trust the harness first: use the worktree's source,
compare complete snapshots, test exact error messages, and retain positive
controls. Remove redundant or unobservable code rather than writing vacuous
tests for it. Re-run mutation after a refactor; a cleaner expression can still
create an untestable branch.
