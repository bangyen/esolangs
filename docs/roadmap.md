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

- **Line:** exempt (measured). The canonical share is present (`shared_tree`),
  but the measured 40.3% is same-level duplication an ancestor return cannot
  express: every share must re-descend a *test-free* arm. The structured
  cases that dominate that measure carry no reachable fork at all -- parity
  repeats 240 of 255 nodes at n=8, majority 105, and neither has a fork whose
  test-free arm reaches a recurring residual. On random n=5..8 no generated
  program emits a loop-back, though reachable fork candidates exist (854 over
  200 n=7 tables), so the wall is return overhead and layout: a second return
  target needs bus routing Line's crossing-free strokes forbid. Controls in
  `tests/generators/test_boolean_line_share_scope.py`.
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
- **FRACTRAN:** complete verification of the bit-linear direct mapping
  pipeline. Packed decimal counters and power-of-ten blocks account for
  scalar addresses; native loading and decoding avoid the growing sieve
  and repeated mapping bisections. The full gate still exceeds its
  sixty-second limit. See
  [direct mapping numerators](proofs/fractran.md#direct-mapping-numerators).

Keep the registry-wide scaling regressions in `tests/proofs/deep/linearity.py`.
An unresolved bound stays open; it does not authorize removing its regression
check or weakening a contract.
