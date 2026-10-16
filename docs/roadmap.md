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
  `core.py`, `wide.py`, `segments.py`, `digits.py`); generation still
  breadth-first navigates (`core.py` `goto`) and places first-fit.
- **Vandevelo:** `_peel.py` is a sampled greedy cover.
- **Streetcode:** `_streetcode_folded` certifies the first of 34 folds by a
  breadth-first drive check. No fixed fold is safe on every table; a safe-cut
  rule needs a proof over the interpreter's junction detection.
- **`balanced_token_width`:** scans every token-run boundary. A closed-form
  width costs +4.0% side on 400 token lists, and four tests pin exact
  optimality.
- **Smallfuck:** `BAND = 3` is measured; band 5 is 6-10% smaller on random
  tables at n=8..11.
- **3x:** `_gain`'s constants were fitted on 148 tables, not derived.
- **Balance sweeps under the width contract:** `balance=True` must match
  the best supported width (`test_balance_reaches_the_supported_minimum`).
  Closed-form widths missed it on 90 sampled tables: INTERCAL 72, Alight 52
  (with its fold-plan search, `_plans`), Qoibl 25, Fargo 30 (15 on the
  sweep). Clockwise and Crement are unattempted.
- **Retry loops:** Piet's colour-phase retry (`raster_lookup/packing.py`),
  Dig's build-then-reject (`_layout.py` `except AssertionError`), Thisthat's
  three-step narrowing.
