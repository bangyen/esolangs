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
- **Scale Line boolean drawings.** The standalone Line generator reaches
  eleven inputs end to end, with all 2048 parity leaves correct. Its
  29920x16800 canvas completes the optimized round trip in under 80 seconds.
  Measure 12 inputs next: its projected 33600x29920 canvas is about one
  billion pixels, expected to take 2-5 minutes and 4-8GiB RAM on this 16GiB
  host. Only pursue subtree sharing or a denser layout if that measurement
  finds a real resource limit.
- **Extend Interprogck8's boolean tree.** `DownAccLines` routes the current
  tree without using the current-function slot, but its 255-line hop and
  nine-line branch window stop n=4: the bit-0 arm must cross 456 lines. Build
  and execute a relay rung inside that subtree to lift both bounds.
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
