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
