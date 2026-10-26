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

- **Malbolge:** generation at seventeen inputs is open (2026-10-21): a
  table cell cannot carry eight address-independent meanings (window
  conflict graph: independence number 8, twelve classes), lockstep
  adjacent-cell reads reach 110 of 512 triples a phase, and the
  seven-meaning build's 1,994 gotos have 2.77 cells each in the
  complement against a 3.6-cell annealed routing floor (certified
  at least 2.99)
  ([limitations](limitations.md)). Reopen only with a layout that needs a
  quarter fewer gotos at that floor, or a decoder whose per-cell meaning
  is not a function of the window cell.
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
    found), Codesick scaling past n = 69 (exact to 69: from n = 37 the
    transition level holds 2^32 - 2 ranks, ids of widths 5..10 from
    65,806, covering binds first and the spares stay inside the
    10-digit pairs at every arity; at 70 the capped level drops to
    n - 6, 2^64 - 2 ranks of widths 10..20, and there the spares
    outgrow the 20-digit pairs at n = 133, so that era is measured by
    counting, not ruled), 1 + i workspace past n = 27 (exact to 27:
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
    240 * 239 ordered pairs, so the shape ends).
  - Per-level bounds (2026-10-22): Stisp is exact to n = 19 (3,554 at n = 9,
    6,952 at n = 10, 13,478, 20,652, 35,879, 67,629, 131,123, 258,105, 532,028,
    1,089,090, 2,199,893), Quassaunt to n = 19 (31,842, 59,978, 114,994, 171,634, 285,380, 513,732, 970,436, 1,883,844, 3,723,970, 7,410,370, 14,780,586) and Bleh to n = 21
    (6,016, 11,582, 21,315, 32,899, 56,533, 104,661, 200,917, 393,429, 791,763,
    1,594,579, 3,196,898, 6,353,001, 9,826,409): the wide ids of the capped level make few pairs, ids
    ascend by first occurrence, and the lowest equal-halved id is named before
    any wide one exists; at 20 the parents permute all 65,534 sixteen-row
    subtables. Stisp stops at 19: at 20 its capped level drops to n - 4, its
    parents price three digit widths, and a measured 739 characters (728 of
    pair pricing, 11 of own-id naming) are not yet a rule. 3x sits 20-28%
    below its F.
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

## Language candidates

Unimplemented wiki pages shortlisted for the first-implementation route
(2026-10-22): their specs read whole once the standing conventions (EOF,
empty-stack pops, output framing, cell width) fill the gaps. None is
admitted yet. Each needs a prototype audit first: an interpreter matching
every example on its page, a linear generator executed over every table at
small n, and a re-spelling comparison with the nearest collected generators
([curation](limitations.md#curation)). BASICER, CARP and IEBEL jump by
line number, so a plain tree costs T log T; they need equal subtrees shared.

- **Ready for the audit:** Pilas (two lockstep stack lines; `{...}` runs
  while the top is zero), Aprknia (one stack; `*` pushes five results),
  lol waht i cant edit talk pages (while-equal blocks over variables),
  IEBEL (equality-branch OISC; its truth machine forces `b` as a register
  for the controls and a literal for the load) and BASICER (`GOTO` menus
  read the input and branch in one step).
- **Re-spelling risk:** CARP's decrement-and-branch tree is Decleq's
  without the input normalization, and CreativeScript v2's arithmetic
  (integer division, forced by its own `==` program) invites Blindfolded
  Arithmetic's shifted literal or APL's `x`/`!x` selection. Each needs a
  construction neither collected generator uses.
- **No linear construction yet:** NOR machine (reaching an operand rotates
  the queue), Balik (a 2D tree in O(T) area) and Tiangou (markers set as
  they run, so jumps go backward only).

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
  sharing routes (2026-10-21), and 6-5's copy node and Minifuck's dead lookup
  threshold (2026-10-22). Flowchart, Circlefuck and Circuit Diagram kept
  every trick and Ascenic has none. Line, Alight, Polynomial, Slow ACV
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
