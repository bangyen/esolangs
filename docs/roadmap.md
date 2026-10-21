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
Edit the `[proof_status]` section of the language's own `language.toml` and run
`python scripts/docs/generate.py docs` to update it. Proved limits remain
evidence, not optimization tasks.

- Polynomial has a documented language lower bound.
- Unary has a documented language lower bound.
- Befunge has a finite-source totality exception.

- **Malbolge:** generation at seventeen inputs is open (2026-10-20): a
  table cell cannot carry eight address-independent meanings, since the
  window conflict graph has independence number 8 and needs twelve classes
  ([limitations](limitations.md)). Reopen only with a decoder whose
  per-cell meaning is not a function of the window cell.
- **Vandevelo:** settle structural output scaling; generation time follows,
  since it includes writing the program and the shipped source is
  `Omega(T log n)` ([the audit](proofs/index.md#vandevelo-identifier-and-fallback-audit)).
  The peel's per-entry work is measured flat through n=15 (2026-10-20).
  The odd-prefix family does not bound the language: `x < m` is a union of
  one cube per 1-bit of `m`, an `O(n**2 log n)` program (324 characters at
  n=8 by hand, executed). A language-wide bound has to handle conditional
  reads, whose offset histories give one guard line exponentially many
  effective cosets, so it is open in both directions.

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
  `_PAIRS` is now a rule, the unique minimum cover (`test_pointer_pairs.py`);
  `_NEXTS` stays searched, one cell above the minimum `N` cover. Generation still breadth-first navigates (`core.py` `goto`: targets
  above 127 need multi-hop pointer paths) and places handlers and hub stubs
  first-fit. `digits.py`'s 16-op gadget is the unique minimum (closed form;
  `test_gadget_suffix.py`). `_D_INITS`'s gadget outputs are a rule, the
  lexicographically first of 2,464 completing sequences
  (`test_digit_inits.py`); which init values spell them is a placement
  tie-break. Smallest trits exhaust a `g` value's walked addresses; first-fit
  over completing values builds and executes but takes 17.6 s.

## Engineering

Dead-code leads, unmeasured against the
[10% size bar](CONTRIBUTING.md#what-makes-a-generator-optimization-worth-shipping).
A removal must leave the generated corpus byte-identical (tiled, constant and
ignored-input tables included).

- **Lines no fast, medium or slow test reaches**, and none of a corpus (n<=7,
  seven width/balance configs) or reachability sweeps (n<=10, widths
  1..100) did either:
  - Circuit Diagram: `hpool.py`'s input port, the `return None` exits in
    `sparse_masks.py` and the work-budget exits in `folded_banks.py`, and
    `source_size.py`'s `return 0`.
- **Generator mutant sweeps:** `just mutants rank` lists the largest generators
  `scripts/mutants_swept.toml` does not record (painfuck, unsquare, grapheme,
  fish, ... on 2026-10-20); sweep and triage them in batches of ten.
- **`Decisions:` figures** cannot be re-run (each needs its rejected option
  rebuilt). `just stale-figures` ranks the 99 docstring figure lines by
  package commits since each was written; the top one (Dimensional, 27) was
  stale. Re-measure from the top. Figures in comments are not ranked.
- **Plain-rewrite audits are one-off:** Streetcode and LaserFuck were each
  audited once -- write the plain canonical construction, price every
  bespoke trick against it, and remove the ones whose saving is a fixed
  amount rather than a genuine percentage (see
  [CONTRIBUTING](CONTRIBUTING.md#what-makes-a-generator-optimization-worth-shipping)):
  Streetcode's lift and tail overlap and LaserFuck's sized leaf retirement
  came out this way. The audit is repeatable per generator; Flowchart is
  the next candidate.
- **The S*bleq variants are interpreter-only, and stay so unless they
  are ever registered:** the interpreter runs the store targets `a`
  (base), `ab` (S*bl*q) and `b` (Subl*q), each also in an indirect
  form, but the generator emits base S*bleq only and no public path
  selects a variant (no registry entry, no dialect setting -- they are
  distinct languages, not readings of one spec). Not scheduled work:
  if the variants are ever registered, generalizing the hoisted tree
  and the packed decoder across the other two store targets belongs to
  that project, execution-gated per variant and re-audited afterwards,
  against the plain-rewrite sweep's S*bleq prices as the baseline. The
  indirect forms would stay out of scope even then: their operands are
  dereferenced, so a generated program can embed no literal address and
  every operand would need a materialized pointer cell -- a different
  construction, not a parameter of this one.
- **FRACTRAN's one-literal guards (retirement candidate #19) wait on the
  index:** writing each guard as one literal (`11*29` as `319`) leaves
  programs the interpreter's index refuses -- the literals are products of
  two of the program's primes and outgrow any linear cap on its bases
  (36,041 against a 4,337-character program at n=10), so runs scan the
  fraction list. It ships only with an index that factors guards over the
  program's own primes; its saving is 8.4% at n=10.
