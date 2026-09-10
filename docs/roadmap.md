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

## Research

- **Lower drawn control flow.** Lower arbitrary Streetcode programs and the
  boolean generator's printed-leaf decision trees. This is a compiler or
  source-machine emulator, not command transliteration. It needs a constructed
  Streetcode-program corpus/fuzzer and resolution of the reference
  interpreter's junction and post-corner gaps.
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
- **Extend Interprogck8's boolean tree.** *Done twice over.* `77025aa7`
  built the relay rung asked for here and lifted the ceiling from 3 to 7
  at a cost that refused n=8 (2031s of rung interference).  The express
  rewrite then replaced the iterative router: `DownAccLines` keeps the
  accumulator, so a chain spells its stride once and rides one-line rungs
  parked in meadows, routed once against frozen coordinates.  Ceiling is
  now 10 — every row of dense and parity executed at n=8..10, n=10 built
  in ~10s — and n=7 fell from 3.5s to 0.05s.  `docs/limitations.md`
  carries the measured edge: n=11 dense exhausts the meadow repair
  budget.
- **Close Minifuck's mux sculpt.** The pool-code half is *done*: `5b35c66b`
  replaced the per-round interpreter scan with `_SCULPT_POOL_CODE`, proved
  structurally (the probe clamps to one canonical state, so the fifth code
  answers every arity, accumulator and round) and checked at 169628 probes
  with the scan kept as the oracle. The 14.5-of-17.9-seconds figure this
  entry used to carry is stale: `_pool_reaches` now profiles at 0.0% of a
  ~0.41s five-input build. What remains is the round loop, and it is not
  merely unfinished but *measured not to close* -- over 36864 round
  transitions at exhaustive n=3, no round moved a row above the frontier
  (the monotonicity that bounds the loop) but 27656 moved one below it, so
  the post-fix column is not predictable without walking. The live cost is
  now `_mux_probe` at 69% of the build; reopen only with a rule for that
  cascade, not a wider search.
## Conditional follow-up

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
