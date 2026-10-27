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
`just docs` to update it. Proved limits remain
evidence, not optimization tasks.

- Polynomial has a documented language lower bound.
- Unary has a documented language lower bound.
- Befunge has a finite-source totality exception.

- **Malbolge:** generation at seventeen inputs is open (2026-10-26): a
  table cell cannot carry eight address-independent meanings (window
  conflict graph: independence number 8, twelve classes), lockstep
  adjacent-cell reads reach 110 of 512 triples a phase, and the
  seven-meaning build's 1,994 gotos have 2.77 cells each in the
  complement against a 3.6-cell annealed routing floor (certified
  at least 2.99). The composition routes priced since -- hub
  substrates in the shipped and re-addressed geometries, marching
  and data-initialized decoders, threaded and streaming emission,
  membership dispatch, the permutation families -- are closed in
  [limitations](limitations.md) on eligibility, mechanism or
  measured rates. Reopen only with a decoder variant whose
  word-mediated landing is realized in a full build that passes its
  gates (parity contract, per-row cases and a fresh census at the new
  window embedding, then placement and threaded rates inside the
  9,897-cell complement), or with new mathematics toward the 46,076
  bits an impossibility proof needs beyond counting.
  Lead (2026-10-27): a `p` or `*` run during the initial walk or a
  lockstep sweep deposits a full word for one source cell, against 25-30
  in the shipped label phase; its words fall in five value bands, so one
  window sweep places about 30 labels and leaves 29 of 94 residues
  uncovered. Untested: steering the sweep from words prepared in the
  window.
- **Open worst-case bounds** (2026-10-22): these cells have a route to
  `worst`. The rest of the 56 cells `at most` throughout and 24 past an
  exact range are in [limitations](limitations.md#run-time-and-memory).
  - Partial range: SMU scaling past n = 16 (names rank by distinct
    parents, but each occurrence pays a reference: a level n - 4 pair
    repeated twice under a three-letter name fails the macro test and is
    written out at both places, so its subtables collect two references
    per parent. Repeating the 209 two-letter subtables' pairs while the
    47 one-letter subtables keep distinct pairs, with mixed pairs tuning
    the ranking from n = 19, measures 116,224 > 115,170 at n = 17,
    228,825 at n = 18, 454,881 > 450,210 at n = 19 and 902,617 at n = 20
    against a recorded 905,770; at n = 21 the 131,072 places exceed the
    98,929 distinct pairs at multiplicities (1, 1, 2) and every
    completion of the family either defines the repeated pairs or hands
    the one-letter names to the high-reference subtables, so the
    recorded +12,087 there sits outside the family. The split, the 194
    two-letter-named pairs that are defined anyway, and the ranking
    margin are chosen per arity: the worst is a design optimum, no rule
    found -- the binding choice itself changes with arity (the split
    at 17, tie-breaks and the defined-pair cohort at 18, the mixed
    share at 19, XX multiplicity against the uses ceiling at 20), and
    at 21 the family's capacity fails outright: 98,929 pair slots at
    the exhibited multiplicities for 131,072 places, the overflow
    forced onto pairs the keep test defines and collapses), Codesick
    scaling past n = 132 (exact to 132: from n = 37 the
    transition level holds 2^32 - 2 ranks, ids of widths 5..10 from
    65,806, covering binds first and the spares stay inside the
    10-digit pairs at every arity; from n = 70 the capped level drops
    to n - 6 and freezes at 2^64 - 2 ranks of widths 10..20, covering
    binds with exactly one spare pair, and the spares fit the fixed
    20-digit-pair supply through n = 132 (ratio 0.5962); at 133 the
    spares outgrow that supply, so the era past 132 needs a
    width-class rule this form does not have), 1 + i workspace past n = 27 (exact to 27:
    the constant half's peak is executed at 25..27, the concatenation
    rival is executed at its own lower value at 27 and the swapped
    shape at its value at 25/26; at 28 the witness program runs to
    ~1.2G characters and generating it is OOM-killed on this machine,
    so the range ends at the witness's memory, not the accounting), INTERCAL
    execution past n = 26 (exact to 26: the witness builds there, its
    1,115,186 statements counted from the generated text, and rows are
    executed to 25; at 26 the VM's load of that program is OOM-killed on
    this machine, RSS past 6 GB without the load completing, and at 27
    generation itself is OOM-killed, its peak doubling from the 3,991 MB
    n = 26 took), workspace past n = 26 (exact to 26: past 20 the names
    past .65535 spill to arrays, which cost fewer bits than a scalar, so
    the old sum was only a bound; the closed form — scalars capped at
    .65535, the A arrays priced by key, width and 0-based (index, value)
    pairs — matches final snapshots at 21, 22 and 25, and at 26 the
    generated text's own DIMENSION statements: 1,024 arrays of width
    1,025, the last holding 50) and scaling past n = 19 (exact to 19: the
    witness builder's third-read padding indexed negatively and raised
    from n = 13; with third reads re-placed on the longest-named rows the
    generated program reaches U at every arity to 19, and at 20 level
    n - 4 would need 2**16 distinct parents from the capped level's
    240 * 239 ordered pairs, so the shape ends -- fenced, not merely
    unextended: the need is 2^(n-4) parents against 57,360 pairs,
    failing at 20 and at every arity after, so reaching the bound
    past 19 needs a successor shape, not this one).
  - Per-level bounds (2026-10-22): Stisp is exact to n = 20 (3,554 at n = 9,
    6,952 at n = 10, 13,478, 20,652, 35,879, 67,629, 131,123, 258,105, 532,028,
    1,089,090, 2,199,893, 4,477,971), Quassaunt to n = 21 (31,842, 59,978, 114,994, 171,634, 285,380, 513,732, 970,436, 1,883,844, 3,723,970, 7,410,370, 14,780,586, 29,530,680, 44,538,424) and Bleh to n = 23
    (6,016, 11,582, 21,315, 32,899, 56,533, 104,661, 200,917, 393,429, 791,763,
    1,594,579, 3,196,898, 6,353,001, 9,826,409, 16,773,225, 30,666,857): the wide ids of the capped level make few pairs, ids
    ascend by first occurrence, and the lowest equal-halved id is named before
    any wide one exists; at 20 the parents permute all 65,534 sixteen-row
    subtables. Stisp's 739 at 20 (728 of pair pricing over three digit
    widths, 11 of own-id naming) is era-constant, not a patch: the same
    correction closes the whole n - 4 era, 20..36. 3x sits 20-28% below
    its F, and the gap is structural: F's head maximum and tree maximum
    are attained by incompatible tables (a complement copy collapses the
    subtree the recursion prices as a split), so no table reaches both;
    exact worsts at n = 2..4 run 72-76% of F.
- **Unformulated scaling** (2026-10-22): Polynomial is a lower bound.
- **S*bleq scaling past n = 25** is fenced by measurement, not
  derivation: the shipped generator attains P exactly at n = 26
  (25,817,068 characters, 61.5 s at a 5.55 GB peak; the packed
  build alone peaks at 3.18 GB) and, once the foreclosed tree
  build is skipped and the packed build streams its projection
  and render, at n = 27 (54,687,747 characters, 42.3 s at a
  1.68 GB peak; the packed build alone peaks at 0.72 GB) and
  n = 28 (105,463,455 characters, 88.3 s at a 3.30 GB peak) —
  one-off builds recorded here; the permanent harness generates
  the scaling arities to 25. Past n = 28 the bound is derived,
  not built: P's closed form evaluates at every n and its
  layout accounting supports attainment, but no program has
  been built there — the route's peak doubles per arity
  (0.87 GB at 26, 1.68 at 27, 3.30 at 28, some 6.5 GB projected
  at 29) against this machine's memory, so the built range
  ends at the route's memory, not the accounting.
- **What!? past n = 22** is fenced by measurement, not derivation: the
  witness builds at every arity to 26 (n = 22 in 2.47 s at 0.366 GB; the
  builder's fragment list is the wall at 27, 5.42 GB at 26), the harness
  generates the scaling claim's arities to 22 exactly, and sparse named
  rows are executed at 16, 17 and 22 — the last row attains E(22) =
  8,519,845 steps and W(22) = 587 bits exactly. The binding wall is the
  interpreter's token parse (one token object per token): a load at
  n = 22 takes 3.15 GB and 63 s and dies at 23, ≈6.3 GB projected — the
  6.4 GB once recorded at 22 was that parse one arity up. No executed
  evidence past 22 is claimed: last built 26, last loaded 22, and
  execution past 22 waits on a parse-cost change.
- **Open mathematics:** Whether some 17-input Malbolge table has no program
  is open; the Malbolge row above is the constructive side
  ([proofs](proofs/index.md#malbolge-bound)).

Keep the registry-wide scaling regressions in `tests/proofs/deep/linearity.py`.
An unresolved bound stays open; it does not authorize removing its regression
check or weakening a contract.

## Engineering

Dead-code leads, unmeasured against the
[10% size bar](CONTRIBUTING.md#what-makes-a-generator-optimization-worth-shipping).
A removal must leave the generated corpus byte-identical (tiled, constant and
ignored-input tables included).

- **Plain-rewrite audits are one-off:** Streetcode and LaserFuck were each
  audited once -- write the plain canonical construction, price every
  bespoke trick against it, and remove the ones whose saving is a fixed
  amount rather than a genuine percentage (see
  [CONTRIBUTING](CONTRIBUTING.md#what-makes-a-generator-optimization-worth-shipping)):
  Streetcode's lift and tail overlap, LaserFuck's sized leaf retirement and
  Dig's default banded tree came out this way, and four of SStack's six
  sharing routes (2026-10-21), 6-5's copy node and Minifuck's dead lookup
  threshold (2026-10-22), and BrainIf's leaf trampoline and odd-n loop step
  and ThisThat's DAG single-arm router (2026-10-27). Flowchart, Circlefuck
  and Circuit Diagram kept every trick and Ascenic has none. Line, Alight, Polynomial, Slow ACV
  Mammalian, APL, INTERCAL and Packlang are inventoried (2026-10-22): their
  unrecorded mechanisms are width/balance layout or core-construction
  constants, not default-path tricks. The audit is repeatable per generator.
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
