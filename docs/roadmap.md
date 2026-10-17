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
  `test_gadget_suffix.py`). `_D_INITS`'s gadget outputs are a rule, the
  lexicographically first of 2,464 completing sequences
  (`test_digit_inits.py`); which init values spell them is a placement
  tie-break. Smallest trits exhaust a `g` value's walked addresses; first-fit
  over completing values builds and executes but takes 17.6 s.

## Language intake

First implementations from the 2026-10-17 screen of Category:Unimplemented
(pages with five or fewer backlinks); none built yet.

- **Bleh:** bitstring pattern matching with full stdin/stdout. The generator
  can match the input bits against patterns. How laziness interacts with
  `{}` blocks is unstated.
- **Stisp:** S-expression rewriting with an exact step rule. It has no IO:
  inputs are embedded in the program, and the result is the final
  expression.
- **Freestajlo:** a postfix stack language over an array of stacks. Admit it
  only if its generator does not re-spell `false`'s.

## Engineering

Dead-code leads, unmeasured against the
[10% size bar](CONTRIBUTING.md#what-makes-a-generator-optimization-worth-shipping).
A removal must leave the generated corpus byte-identical (tiled, constant and
ignored-input tables included).

- **Lines no fast, medium or slow test reaches**, and none of a corpus (n<=7,
  seven width/balance configs) or reachability sweeps (n<=10, widths
  1..100) did either:
  - ABCDirection `_balance`: the `floor >= flat` return.
  - BrainIf: the marker-sharing `break` in the level scan.
  - Brainfuck: two `return None` width fallbacks in the bank planner.
  - CVNC: the nasal after a vowel.
  - Malbolge `core`: `walked()` with no value.
  - Streetcode: the tree recursion past 32 entries and the column-cut `break`.
  - Dig: the width guard in `__init__` and the `return False`/`except`
    fallbacks in `_layout.py`.
  - Line: three `old`/`preceding` selections in `__init__` and `layout.py`'s
    `return None`.
  - Circuit Diagram: the odd-result pairing in `banks.py`, `hpool.py`'s
    input port, the `return None` exits in
    `sparse_banks.py`, `sparse_masks.py` and `folded_banks.py`, and
    `source_size.py`'s `return 0`.
- **Branch arms no corpus takes** (fast + medium bands, then n<=7..11 with
  widths 1/5/12/40 and balance; the other 18 of 22 are loop exits or taken,
  only outside the fast and medium bands):
  - Dig `_layout.py:179`: the `fits(high, 1) and fits(low, 0)` false arm.
  - Circuit Diagram `folded_banks.py:83`: `"0" in word` false (an all-ones
    word).
  - Minifuck `stored.py:32`: `write` with `count == 0`.
  - Algebraic Programming Language `_apl_narrow_layout`: `next_width is None`
    after the width test (provably never; kept for the `int | None` type).
- **`Decisions:` figures in generator docstrings and comments** (about 270)
  are one-off experiments with no harness; only the `Size:` anchors are
  regenerated by a test. Sampled 45 sub-10% claims by reading: each describes
  a rejected option or an n-slice of a route that clears the bar at larger n.
