# Roadmap

This page lists work that is still open. Finished work lives in the git
history; standing rules and proved limits are in [limitations](limitations.md).

## Canonical generator gaps

Ignored inputs must be dropped, constant subtrees folded, and repeated
subtrees shared under the existing execution and workspace contracts.
Current sharing helpers and selected controls do not establish completeness.
Close each gap with a named construction and native execution, or an
exemption supported by a structural proof or the measured criterion in
[Contributing](CONTRIBUTING.md#what-makes-a-generator-optimization-worth-shipping).

- **Line:** forward residual stems now share same-level duplicates within
  the existing 5n command and workspace bounds. Streaming reads overwrite
  cell zero in input order; constant tails drain the remaining reads. Parity
  at n=8 occupies 1,534,400 pixels at scale 1 against the tree's 17,472,000;
  all 256 rows execute natively. Majority at n=8 occupies 3,952,000 pixels,
  with all 256 rows checked. Descending tests also save the loader rewind,
  paying for joins.
  Majority at n=9 shares in 13,438,400 pixels against 28,492,800; all 512
  rows execute. Disjoint arrivals/joins reuse channel rows; shared destination
  moves narrow nonterminal forks. The n=22 majority control occupies
  53,875,200 pixels at scale 1 against 87,270,400, with 36 native rows checked.
  Dense tables still keep the smaller tree: the layered bus
  is area-admitted, not a linear-area sharing construction. The measured
  40.3% repeated-subtree upside remains open. Controls in
  `tests/generators/test_boolean_line_forward.py`,
  `tests/generators/test_boolean_line_destination.py`,
  `tests/generators/test_boolean_line_streaming.py`,
  `tests/generators/test_boolean_line_join_lanes.py` and
  `tests/generators/test_boolean_line_share_scope.py`.

## Generator linearity

For truth-table length `T`, target O(T) generation time and emitted size.
Generation includes input ordering and writing the program. Close a gap with
an executed, loop-less construction or a language-wide lower bound; measured
scaling alone does not prove linearity. Preserve totality, execution, and
workspace contracts.

The [scaling status](proofs/index.md#scaling-status) records current verdicts.
Edit `src/esolangs/proof_status.toml` and run
`python scripts/docs/generate.py docs` to update it. Proved limits remain
evidence, not optimization tasks.

- Factor has a documented language lower bound.
- Polynomial has a documented language lower bound.
- Unary has a documented language lower bound.
- Befunge has a finite-source totality exception.

- **Malbolge:** settle generation at seventeen inputs and the first
  unreachable arity. Share initialization and query control, then relocate
  records before capture; see [the construction summary](proofs/index.md#malbolge-bound).
- **Vandevelo:** settle generation time and structural output scaling via
  the `O(log n)` DNF-of-parities gap; see [the audit](proofs/index.md#vandevelo-identifier-and-fallback-audit).

Keep the registry-wide scaling regressions in `tests/proofs/deep/linearity.py`.
An unresolved bound stays open; it does not authorize removing its regression
check or weakening a contract.
