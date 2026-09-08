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
- **`%^2^-1`:** generic samples build through thirteen inputs; a
  fourteen-input table would need a twelve-input prefix ladder, which is
  open research, not a wall.
- **NoComment, Factor:** host/runtime configuration limits.
- **Polynomial, WII2D, ZTOALC L:** program-cost guards, not capability claims.
- **Route hybrids:** CV(N)(C), Polynomial, Circlefuck, `%^2^-1`, and WII2D
  alternatives were rejected on the grounds that occasional smaller output
  did not repay slower generation — 1.25x, 1.08x, 29x, 3,100x, and 1.85x on
  their audit cases. **Treat those five numbers as unverified**: the harness
  was not kept, and no measurement here reproduces one. Polynomial's figure is
  known wrong — its hybrid was reimplemented and ships (below), which was
  possible only because the bullet named the construction. CV(N)(C) and
  Circlefuck still build competing routes in-tree and were re-priced from
  that code: direct wins 202 of 256 at n=3 against stored's 54, and
  Circlefuck's greedy route never wins on size while costing about twice as
  much to build. Both verdicts stand on those measurements, not on the
  ratios. WII2D and `%^2^-1` both had a *committed* predecessor, recoverable
  from the commit that retired it: `ea65a170` removed WII2D's beam decode
  and `56c0d850` removed `%^2^-1`'s `_fold_search`, `_fold_beam` and
  `_fold_to_cofactors`. The current sources say those constructions keep no
  alternative and never backtrack, which describes what they are now, not
  what was tried. Both were recovered and re-measured, and neither ships.
  WII2D's beam does shorten output — as an optional second decode it shrank
  19,864 of 66,108 tables, none grown, median 5.2% — but it costs 9.8x
  generation at n=5 and reintroduces into a deterministic construction the
  search `ea65a170` removed; the size is not worth that. `%^2^-1`'s descent
  loses outright: over 40 five-input fold states the shipped rules plan all
  40 while the descent plans 5 at width 1 and 13 at width 4, slower at both.
  Recovering a predecessor does not re-derive the recorded ratio — the
  audited variants
  lived in a worktree and may differ — but it does mean these were never
  guesswork to retry.

  Polynomial is the exception. Its tree and state machine are the endpoints
  of one family — `k` tree levels above one machine per residual — and the
  interior wins where both lose: a table whose residuals merge within a
  top-level split but not across it. Shipping the whole family shortens 36
  of 256 three-input tables (median 3.6%, best 30.3%) and 3,846 of 65,536
  four-input ones (median 6.5%, best 39.8%); none grow, and none previously
  refused becomes renderable. Selection is on rendered characters, since
  instruction count disagrees with them; the count screens which candidates
  are worth rendering, costing 2.54x at n=3 (0.3s across 256 programs) and
  1.09x at n=4. The screen's slack is arity-dependent and measured, not
  derived — 6 at n<=3 but 9 at n=4 — so the counts are lower bounds.

## Spec and engine boundaries

- 6-5's interpreter accepts operands outside the specification; generators
  must stay in `0..35`.
- RISC-V compilers agree with unbounded Python integers only within their
  fixed machine-word range.
- Jaune's dispatch to an undefined marker is unspecified; its interpreter and
  compiler deliberately choose different outcomes.

All generator output claims require execution through the interpreter. Do not
use permissive interpreter behavior or a bounded search as a new capability.
