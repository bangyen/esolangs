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

- **Malbolge:** settle generation at seventeen inputs and the first
  unreachable arity. Fixed-address native capture has passed scratch controls;
  a cheaper sixteen-readout layout and a three-read decoder are checked but
  unbuilt, and navigation in label dispatch is the cost to cut
  ([limitations](limitations.md)); see
  [the construction summary](proofs/index.md#malbolge-bound).
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
- **Piet:** `raster_lookup/packing.py` retries colour phases. A spacer row
  between lanes needs no retry but costs 32-64% area; choosing a start colour
  without it is itself a scan.
- **Dig:** `_layout.py` rejects a finished sharing layout on an
  `AssertionError`. After `bridge_entries` the rejection is live: at n=12 (300
  tables of random 64-bit leaf classes mixed with constant leaves, plus the
  repro) it fired in 131 of 602 lane and parallel layouts, a `_chain_lanes`
  corridor crossing another class's lane arrow or a branch `$`. A per-class
  gutter line (2026-10-16, unmerged) closes it by construction (0 fires; a
  no-gutter mutant re-fires 136) but recovers no sharing (26 to 24 lane
  layouts) and grows shared ones ~5%: a gutter spans the grid, so a crossed
  leaf or constant read row kills the layout. Compaction's check never fired
  (n<=12, ~5,600 layouts) but no proof covers it: a digit beside a reader
  across a deleted row is unargued. Proved: compaction cannot break a
  corridor; lane arrows (not digits) cannot change a reader's operand.
