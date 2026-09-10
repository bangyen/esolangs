# Roadmap

Only live work belongs here. Completed findings, negative results, and
conditional ideas stay in [`docs/walls.md`](walls.md) and
[`docs/limitations.md`](limitations.md).

## New interpreters

The candidate list is empty: DINAC, Alight, function x(y), Packlang and
Interprogck8 are implemented, and Pinyin is rejected. Both outcomes are
recorded in [`docs/limitations.md`](limitations.md) — Pinyin's routing
pinned and its two-input program priced at 4 characters, but its triples
did not: the page's own selection rule reroutes 8 of 23 Hello, world!
characters, and its truth machine on input 1 is unreachable under all 384
readings.

The list refills by survey rather than by waiting — APL arrived that way and
is now implemented, with its own boolean generator.

## Research

- **Measure Interprogck8's repair budget at n=11.** Dense n=11 exhausts
  `_REPAIRS = 256` about 30s in, and the refusal names its stranded window;
  whether more budget closes it is the ledger's one explicit unmeasured
  claim. n=10 spends 95-126 repairs across four dense seeds, so there is
  headroom, but nothing bounds the gap. Raise the budget and record
  build-or-refuse with its cost. Do not assume it builds: WII2D's analogous
  "raise the 256 guard" question was measured *false*, and that guard's own
  message asserting otherwise was wrong. Needs a wall-clock alarm — an
  unbounded run here reads as acceptance.
- **Price Polynomial's instruction guard at n=11.** The guard is 1934, the
  analytic worst case over n=10 tables, so every n=10 table builds; dense
  n=11 needs 2910 and is refused. It guards the *interpreter*, not the
  generator, so the question is what 2910 instructions cost to run, not
  whether the generator can spell them. Anchor against dense n=10 (1638
  instructions, all 1024 rows in 44s) before moving the constant. The cap is
  an instruction count and not an arity — a table that collapses already
  renders far past n=10.
- **Source the empty-input `0`.** `io.input_char` answers `0` on an empty
  line, pinned across the registry by
  `tests/interpreters/test_input_convention.py`. Open: whether any language's
  `0` was ever taken from its own specification rather than chosen — the
  docstrings citing "the original" are the same author's earlier readings, so
  they corroborate nothing. Finish condition: every such docstring checked
  against its wiki page, each `0` ending either sourced or marked chosen.
- **Settle Streetcode's four-way junction.** `_junction_kind` reports 3 or 4
  roads, and the four-way arm is pinned only to what the implementation does:
  `test_four_way_junction_also_merges` says so in its own docstring — no
  hand-drawn, user-confirmed trace exists for it, unlike the three-way case.
  The wiki cannot settle it either; it never spells out the geometry behind
  "drive on the right-hand side" or the leftmost/second-leftmost ambiguous
  turn rule, which is why `docs/streetcode.md` is the spec of record. Two
  exits: find a wiki example that forces a four-way choice, making it ground
  truth, or accept the current behavior as a documented convention and move it
  to `limitations.md` beside the other interpreter conventions.

  *Post-corner is not part of this.* The `near == -1` arm of `_road_mouth` —
  the car cornering into a mouth it never met head-on — is the most exercised
  of the three depths, firing 1808 times across the interpreter's 174 tests
  against 802 for depth 0 and 672 for depth 1.

  **The lowering half of this entry is retired.** It asked for a compiler from
  Streetcode grids and printed-leaf decision trees; `7c440f9e` then deleted
  `src/esolangs/transpilers/` entire — the total brainfuck -> Streetcode
  transpiler included — because 2069 lines and 47s of suite time served
  nothing in the repo, following `58427732` on the compilers. Rebuilding a
  larger version of what was just removed needs a consumer first. The
  construction is recoverable at `7c440f9e^` if one appears.
- **Re-screen input reordering, then take what the screen still names.** The
  59-generator screen (`46a32c85`) measured, at n=3 over all 256 tables, the
  shortest program any of the six orders emits against the identity's. It
  lived in `docs/generator-optimizations.md`, which `f1e4ab68` trimmed to a
  policy page and `920760c3` deleted; the roadmap pointed into it for each
  reorder verdict, and the ArrowQueue entry below is the only one that
  survived. **Re-run the screen before citing any figure from it — its
  verdicts are falsified, not merely stale.** Four of its seven exclusions
  reorder at HEAD (six_five 17.9%, addsubjump 16.7%, jaune 16.3%, unsquare
  15.7%), as do three it left unattempted (streetcode 16.8% in `816fb13d`,
  laserfuck 16.3%, forth 14.5%): seventeen generators call
  `best_input_order` and five more run their own capped order search. What
  it named and nothing since has touched is polynomial 25.1%, dig 19.8%,
  flowchart 17.1%, modulous 16.4% and sophie 16.4%, each verified orderless
  at HEAD. Its under-15% tail was not re-verified here, and sbleq and
  three_x from it already reorder.

  *The trap to carry forward.* A generator that validates its own output
  during construction needs that check frame-mapped, or it rejects every
  correct placement and reports a clean 0.00% — indistinguishable from
  "reordering does not help here". ZTOALC L is where that happened; wii2d's
  budget and requirement-set machinery is the next likely instance. A 0% on
  a generator the screen gives upside is a diagnosis, not a verdict.
- **Scale Line boolean drawings.** Twelve inputs is *measured, and it fits*:
  a 33760x29920 canvas (1.01Gpx, within a rounding of the 33600x29920
  projection) completes the round trip in 289s at 2.60GiB peak, all sampled
  parity rows correct. That is inside the 2-5 minute projection and *below*
  the 4-8GiB one, so there is no resource wall and **subtree sharing and a
  denser layout stay unpursued** -- the condition this entry set for them
  was not met. The n=11 control in the same conditions is 85.5s at 2.68GiB,
  which reproduces this entry's earlier "under 80 seconds".

  **Measure one arity per process.** The first attempt ran n=11 and n=12 in
  one process and got 268s and 642s -- 3.1x and 2.2x the true figures, with
  `compile` inflated 10x at n=11 (105s against 10.1s). Nothing is cached
  between calls, so this is not warm-up: a repeated `compile_program` on one
  stroke is flat to the millisecond, and repeated `extract` likewise. It is
  the billion-pixel canvas still resident while the next arity is measured.
  A per-arity process is what makes these numbers reproducible.

  The cost is in the reader, and specifically in `extract`: 70.4s of 85.5s
  at n=11 and 237.6s of 288.8s at n=12, a steady 82% at both arities, while
  drawing and saving the canvas is 4% and `compile` 12-13%. `compile` scales
  cleanly at 4x per arity (0.16 / 0.62 / 2.48 / 10.1 / 38.0s for n=8..12),
  so it is predictable and small; `extract` is the stage any future work
  belongs in.

  Line's open work that is not about arity — extraction from anti-aliased
  input, the lattice probe length, ambiguous arrowheads — lives in
  `extra/line/WIP.md`, the separate suite's own ledger.

## Conditional follow-up

- **WII2D's exactly-once embed convention.** Dense n=10 is a wall of the
  convention, not the machine: a per-node re-embed does dense n=10 in 14432
  characters and dense n=13 in 146540, every row executed. Re-examine the
  convention only if the arity ever matters — it is fenced by the invariant
  in `tests/tools/test_boolean_parameterized.py`, and Dotlang and 2dFish were
  removed rather than exempted from it. The audit is in
  [`docs/walls.md`](walls.md).
- **Minifuck's mux round loop.** The rest of the sculpt closed (pool code in
  `5b35c66b`, the named accumulator from nine); the round loop did not, and is
  *measured* not to. Over 36864 round transitions at exhaustive n=3 no round
  moved a row above the frontier, but 27656 moved one below it, so the
  post-fix column is not predictable without walking. Reopen only with a rule
  for the `_mux_probe` cascade — now 69% of the build — not a wider search.
- **ArrowQueue reusable drain.** Ship the verified deep-fold drain only if a
  proof makes folding meaningfully testable at `n >= 5`; current coverage does
  not reach its crossover.
- **Reorder ArrowQueue inputs.** A three-input screen leaves 12.4% headroom,
  but its queued inputs cannot be renamed in place. Find a re-enqueue and
  grid-routing construction, then compare emitted, executed programs against
  the current template; abandon it if the routing spends the apparent gain.
- **`%^2^-1` fourteen inputs.** The staged fold's endgame strands its last
  duplicated cofactor pairs: rank order is steerable (pulsed doubling), but a
  merge needs the pair's value gap `d` inside a wipe window, and diving the
  partner maps `d -> amount - d` with the amount free in the window -- a
  derived, unbuilt alignment controller. Build it only if a ~20x-thirteen
  build cost (~430k plan ops, ~8MB templates, ~226 ops per merge) is
  acceptable; the walls around it are recorded in
  [`docs/walls.md`](walls.md).
