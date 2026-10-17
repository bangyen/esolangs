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
