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
  a cheaper sixteen-readout layout is checked but unbuilt, and label dispatch
  is the cost to cut ([limitations](limitations.md)); see
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
  first-fit. `digits.py`'s 16-op gadget resists derivation: it is a
  trit-0 program (`p` with `A=2` or a bit gives `2*not x`; the rest folds `z`
  into cells 1, 2) whose 3-bit -> (u, v) map is an arbitrary injection into
  nine values (missing `(2,2)`), so no rule picks this sequence over other
  injective gadgets; it needs trit 0 of the three inits in {0, 1}.
- **Vandevelo:** `_peel.py` is a sampled greedy cover. A deterministic
  axis-cube merge is O(n T) but emits 2.1x the peel's text at n=8 (5.6x on
  n=10 majority).
- **3x:** `_gain`'s constants were fitted on 148 tables. The exact saving has
  no closed form: a key's length depends on its global use rank, and the body
  cost on content (127 cost pairs over 2,000 random 16-row blocks). Exact means
  trial emission, the retired greedy loop (1.4%).
- **Piet:** `raster_lookup/packing.py` retries colour phases. A spacer row
  between lanes needs no retry but costs 32-64% area; choosing a start colour
  without it is itself a scan.
- **Dig:** `_layout.py` rejects a finished sharing layout on an
  `AssertionError`. After `bridge_entries` the rejection is live: at n=12
  (random 64-bit leaf classes mixed with constant leaves) it fired in 55 of
  ~300 layouts, a `_chain_lanes` corridor crossing another class's lane arrow
  or a branch `$`; nothing bounds a chain's line against foreign cells.
  Compaction's check never fired (n<=12, ~5,600 layouts) but no proof covers
  it: a digit beside a reader across a deleted row is unargued. Proved:
  compaction cannot break a corridor; lane arrows (not digits) cannot change
  a reader's operand.
