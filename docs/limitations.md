# Limitations and contracts

This is the current boundary ledger. Live work is in [the roadmap](roadmap.md);
structural arguments are in [walls](walls.md).

## Interpreter conventions

- Empty input is a no-op unless the language requires a seed or grid.
- Exhausted input raises `EOFError`, except where the specification defines
  another sentinel. Malformed programs raise `ValueError`; runtime failure
  raises `HaltError`.
- Character input is line-delimited: one line supplies one character.
- Explicit frame stacks make supported recursion uncapped. Forbin calls in
  expression position remain host-recursive and report their documented limit.

## Generator boundaries

Text generators are absent where the language has no output, only a binary or
numeric output alphabet, or cannot emit arbitrary byte sequences. Boolean
construction is parameterized for 123 and `%^2^-1`; no program reading its
own inputs overcomes the latter's two-input wall.

Current caps are deliberate:

- **6-5:** 35 addressable branch labels; a structural language wall.
- **`%^2^-1`:** generic samples build through eleven inputs; its twelve-input
  ladder limit is open research, not a wall.
- **NoComment, Factor:** host/runtime configuration limits.
- **Polynomial, WII2D, ZTOALC L:** program-cost guards, not capability claims.

## Spec and engine boundaries

- 6-5's interpreter accepts operands outside the specification; generators
  must stay in `0..35`.
- RISC-V compilers agree with unbounded Python integers only within their
  fixed machine-word range.
- Jaune's dispatch to an undefined marker is unspecified; its interpreter and
  compiler deliberately choose different outcomes.

All generator output claims require execution through the interpreter. Do not
use permissive interpreter behavior or a bounded search as a new capability.
