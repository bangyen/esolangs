# Verification and mutation tooling

`scripts/verify.py` is authoritative.

- Python 3.14 makes branch coverage inexpensive through `sys.monitoring`.
- `mutate_one.py` mutates a dependency-closed bundled interpreter; mutating an installed package is not reliable.
- mutmut is pinned at 3.7.0 because earlier versions missed class-method mutants and emitted no-op mutants.
- A mutation score below 76.7% is treated as a broken measurement, not a reportable result.
- The stack is scheduled, not run in order: `pre-commit` alone (it rewrites the files the rest read), then `pytest` with the one-core steps in its shadow, then the coverage gate, then the steps that are parallel in their own right.
- Step output is replayed only where a step failed.
- Full exception-leak sweeps are bounded by subprocess timeouts where parsing or unbounded growth cannot be safely interrupted by a step cap: a SIGALRM cannot land inside sympy's uninterruptible C, which is also why Factor is screened by operand size rather than by a cap.

For mutation triage, trust the harness first: use the worktree's source, compare complete snapshots, test exact error messages, and retain positive controls.
