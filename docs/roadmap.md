# Roadmap

This page lists work that is still open. Finished work lives in the git
history; standing rules and proved limits are in [limitations](limitations.md).

## Generator linearity

For truth-table length `T`, target O(T) generation time and emitted size.
Generation includes input ordering and writing the program. Close a gap with
an executed, loop-less construction or a language-wide lower bound; measured
scaling alone does not prove linearity. Preserve totality, execution, and
workspace contracts.

The [scaling status](proofs/index.md#scaling-status) records current verdicts.
Edit `ledgers/proof_status.toml` and run
`python scripts/docs/generate.py docs` to update it. Proved limits remain
evidence, not optimization tasks.

- Polynomial has a documented language lower bound.
- Unary has a documented language lower bound.
- Befunge has a finite-source totality exception.

- **Malbolge:** generation at seventeen inputs is open and unfunded
  (2026-10-16): label dispatch overruns the main line by ~640 cells
  ([limitations](limitations.md)). Reopen only with a new layout.
- **Vandevelo:** settle generation time and structural output scaling via
  the `O(log n)` DNF-of-parities gap; see [the audit](proofs/index.md#vandevelo-identifier-and-fallback-audit).

Keep the registry-wide scaling regressions in `tests/proofs/deep/linearity.py`.
An unresolved bound stays open; it does not authorize removing its regression
check or weakening a contract.

## Loop-less constructions

Searches and searched tables that a named rule has not yet replaced
([code shape](CONTRIBUTING.md#code-shape)). Keep each search as the test
oracle when it goes.

- **Malbolge:** the mixer, label, readout and digit tables were found by
  annealing, CP-SAT and breadth-first search (`skeleton.py`, `cascade.py`,
  `core.py`, `wide.py`, `segments.py`, `digits.py`). The mixers are chaotic:
  random inits pass 2/300 under the shipped schedule, random schedules 0/300.
  `_PAIRS` covers the eight op residues mod 94 with 17 pairs against a bound
  of 12. Generation still breadth-first navigates (`core.py` `goto`: targets
  above 127 need multi-hop pointer paths) and places handlers and hub stubs
  first-fit. `digits.py`'s 16-op gadget is the unique minimum (closed form;
  `test_gadget_suffix.py`). `_D_INITS` inverts a fixed 94-permutation of walked
  values with a tie-break: no closed form in the literature (Scheffer; Ando et
  al. IEICE SS2012-37 find gadgets by SAT); a lookahead-1 greedy reproduces
  groups 0, 2, 3, 4 but changes group 1.
- **Vandevelo:** `_peel.py` is a sampled greedy cover. A deterministic
  axis-cube merge is O(n T) but emits 2.1x the peel's text at n=8 (5.6x on
  n=10 majority).
