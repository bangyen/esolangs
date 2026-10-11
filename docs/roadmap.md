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
  the existing 5n command and workspace bounds. Descending tests save the
  loader rewind, paying for joins. Parity at n=8 occupies 7,002,000 pixels
  at scale 1 against the tree's 17,472,000; all 256 rows execute natively.
  Majority at n=9 shares in 18,803,200 pixels against 28,492,800; all 512
  rows execute. Dense tables still keep the smaller tree: the layered bus
  is area-admitted, not a linear-area sharing construction. The measured
  40.3% repeated-subtree upside remains open. Controls in
  `tests/tools/test_boolean_line_forward.py` and
  `tests/tools/test_boolean_line_share_scope.py`.
- **Circuit Diagram:** fixed-size cofactor pools now share locally inside
  a prefix H recursion with linear work and area. Dense n=8 occupies
  1,290,226 cells / 1,176,281 characters against the minterm lattice's
  1,946,024 / 1,780,773; every row executes natively. Three- and four-input
  pools keep both arity parities inside the measured growth gate. Global
  repeats across pools remain open: the full bus fold still exceeds its
  node-count budget. Controls in
  `tests/tools/test_boolean_circuit_diagram_pool.py` and
  `tests/tools/test_boolean_circuit_diagram_share.py`.

## Generator linearity

For truth-table length `T`, target O(T) generation time and emitted size.
Generation includes input ordering and writing the program. Close a gap with
an executed, loop-less construction or a language-wide lower bound; measured
scaling alone does not prove linearity. Preserve totality, execution, and
workspace contracts.

The [scaling status](proofs/index.md#scaling-status) records current verdicts.
Edit `src/esolangs/proof_status.toml` and run
`python scripts/docs/generate.py docs` to update it. Factor and Polynomial
have documented language lower bounds; Befunge has a finite-source totality
exception. Those limits remain evidence, not optimization tasks.

- **Malbolge:** settle generation at seventeen inputs and the first
  unreachable arity. Share initialization and query control, then relocate
  records before capture; see [the layout gap](proofs/malbolge-scaling.md#native-components-and-layout-gap-2026-10-09).
- **Vandevelo:** settle generation time and structural output scaling via
  the `O(log n)` DNF-of-parities gap; see [the audit](proofs/index.md#vandevelo-identifier-and-fallback-audit).

Keep the registry-wide scaling regressions in `tests/proofs/deep/linearity.py`.
An unresolved bound stays open; it does not authorize removing its regression
check or weakening a contract.
