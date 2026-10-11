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
  loader rewind, paying for joins. Parity at n=8 occupies 15,132,000 pixels
  at scale 1 against the tree's 17,472,000; all 256 rows execute natively.
  Dense tables and majority still keep the smaller tree: the layered bus
  is area-admitted, not a linear-area sharing construction. The measured
  40.3% repeated-subtree upside remains open. Controls in
  `tests/tools/test_boolean_line_forward.py` and
  `tests/tools/test_boolean_line_share_scope.py`.
- **Circuit Diagram:** wall (measured). The cofactor-sharing bus fold is
  area-smaller than the H-layout but not linear-area. Its node-count cutoff
  (`nodes**2 <= 4*T`) rejects the dense n=8 fold (75 nodes) although the
  shared model is 194,775 cells against the H-layout's 1,946,024, so the
  public build emits the unshared lattice and jumps x26.4 in area from n=7
  (73,809) to n=8. Removing the cutoff admits folds whose same-parity growth
  n=8->10 is x4.93, over the x4.4 contract; banding lowers the constant but
  not the exponent (x4.79), and the H-layout's own is x4.37. Sharing would
  have to be grafted onto the H-recursion -- one lattice site per distinct
  residual, parents' buses routed to it -- a new construction, not a parameter
  change. Controls in
  `tests/generators/test_boolean_circuit_diagram_share.py`.

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
