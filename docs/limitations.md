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

## Text generator blockers

| Language | Why it cannot emit arbitrary text |
| --- | --- |
| A Painter Ant | No I/O; its grid dump is limited to raster symbols. |
| Algebraic Programming Language | Executed lines print numeric results only. |
| ArrowQueue | Has no output. |
| Back | Its halting tape dump has only `0`, `1`, and spaces. |
| BF-PDA | Output is one bit at a time. |
| Bitdeque | Its interpreter-only deque dump is numeric. |
| COD | Its sink prints decimal integers only. |
| Circuit Diagram | Output is a bit string only. |
| Fargo | `$` prints the output register as a number. |
| Flowchart | Its output node emits one bit; the spec's truth machine fixes that convention. |
| Grapheme | String mode cannot contain `E`, and strings cannot be concatenated. |
| Inject | `send` appends a newline to every emitted line, so texts without a final newline are unreachable. |
| Jaune | `^` prints cells as decimal integers only. |
| Lamfunc | Whitespace tokenization and no concatenation prevent arbitrary text. |
| Minsky Swap | It has no output command; the halting register dump is numeric. |
| Point Break | Has no output. |
| RAM0 | Its fixed-format final dump cannot address arbitrary text. |

Current caps are deliberate:

- **6-5:** 35 addressable branch labels; a structural language wall.
- **`%^2^-1`:** generic samples build through eleven inputs; its twelve-input
  ladder limit is open research, not a wall.
- **NoComment, Factor:** host/runtime configuration limits.
- **Polynomial, WII2D, ZTOALC L:** program-cost guards, not capability claims.
- **Route hybrids:** CV(N)(C), Polynomial, Circlefuck, `%^2^-1`, and WII2D
  alternatives were rejected. Occasional smaller output did not repay slower
  generation: 1.25x, 1.08x, 29x, 3,100x, and 1.85x on their audit cases.
  The tree-prefix/DAG-suffix Polynomial hybrid is the exception and now
  ships: a table whose residuals merge within a top-level split but not
  across it defeats both parent constructions. It shortens 8 of 256
  three-input tables (24-30%) and 718 of 65,536 four-input ones (median
  15.5%, best 38.2%, smallest 2.0%); none grow, and none previously refused
  becomes renderable. An instruction-count screen holds generation to
  1.01-1.12x by rendering only a candidate that could win; comparing every
  render costs 4.94x. The screen is conservative, so those counts are lower
  bounds.

## Spec and engine boundaries

- 6-5's interpreter accepts operands outside the specification; generators
  must stay in `0..35`.
- RISC-V compilers agree with unbounded Python integers only within their
  fixed machine-word range.
- Jaune's dispatch to an undefined marker is unspecified; its interpreter and
  compiler deliberately choose different outcomes.

All generator output claims require execution through the interpreter. Do not
use permissive interpreter behavior or a bounded search as a new capability.
