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
- **Circuit Diagram:** fixed-size cofactor pools share locally inside
  a prefix H recursion; cell guards and coordinate buckets give linear
  expected work and area. Seven/eight-input atoms use fixed footer routing;
  dense n=8 occupies 194,775 cells / 147,264 characters against the minterm lattice's
  1,946,024 / 1,780,773; every row executes natively. Three- and four-input
  pools and larger atoms keep both arity parities inside the measured growth gate. Global
  complete cofactors share through four/eight predicate-and-function banks:
  the n=10 ABBA control occupies 387,711 cells against 492,826; all 1,024
  native rows pass. Repeated seven/eight-input classes now share across all
  prefixes through H masks, admitted by a conservative workspace gate bound.
  The n=13 sixteen-class witness occupies 2,453,905 cells against 35,581,224;
  both execute 33 native rows. The n=13 eight-class witness drops
  from 1,530,528 to 1,160,811 cells and 1,064 to 874 gates; both execute 33 native rows, with
  all three global fold orders rejected and all eight top-level banks distinct.
  A bounded multi-output forest now shares internal residuals between class roots.
  Counted mask/body gates admit 202 sparse classes at n=15 in 8,749,827 cells;
  607 native rows cover every class within 20 commands. Forest area floors
  skip oversized assembly. Binary-carry OR returns retain one root per level.
  Repeats beyond the fixed class cap or gate budget remain open when all three fixed
  fold orders exceed the node-count budget. Moving three/four tail inputs first avoids the
  expander control's original graph: n=12 drops from 221 to 60 fold nodes
  and executes in 138,953 cells. Controls in
  `tests/generators/test_boolean_circuit_diagram_banks.py`,
  `tests/generators/test_boolean_circuit_diagram_classes.py`,
  `tests/generators/test_boolean_circuit_diagram_class_budget.py`,
  `tests/generators/test_boolean_circuit_diagram_forest.py`,
  `tests/generators/test_boolean_circuit_diagram_hcells.py`,
  `tests/generators/test_boolean_circuit_diagram_order.py`,
  `tests/generators/test_boolean_circuit_diagram_pool.py` and
  `tests/generators/test_boolean_circuit_diagram_share.py`.

## Generator linearity

For truth-table length `T`, target O(T) generation time and emitted size.
Generation includes input ordering and writing the program. Close a gap with
an executed, loop-less construction or a language-wide lower bound; measured
scaling alone does not prove linearity. Preserve totality, execution, and
workspace contracts.

The [scaling status](proofs/index.md#scaling-status) records current verdicts.
Edit `src/esolangs/proof_status.toml` and run
`python scripts/docs/generate.py docs` to update it. Factor, Polynomial and Unary
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
