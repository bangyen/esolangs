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
- Full exception-leak sweeps are bounded by subprocess timeouts where parsing
  or unbounded growth cannot be safely interrupted by a step cap.

For mutation triage, trust the harness first: use the worktree's source,
compare complete snapshots, test exact error messages, and retain positive
controls. Remove redundant or unobservable code rather than writing vacuous
tests for it. Re-run mutation after a refactor; a cleaner expression can still
create an untestable branch.
