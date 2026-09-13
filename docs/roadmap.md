# Roadmap

Only live work belongs here. Completed findings and negative results go to
[limitations](limitations.md).

## New interpreters

Implement the surveyed candidates in this order:

- **[Qwhy](https://esolangs.org/wiki/Qwhy).**  Its diagonal queue machine has a
  deterministic subset when `x` is absent, character input/output, two value
  branches, wrapping and self-modification.  Admission is conditional on a
  loop-less boolean construction: build 48 before `{`, subtract the input
  character, and route `X`'s zero/nonzero diagonals into a decision tree.
- **[Sir. Cut](https://esolangs.org/wiki/Sir._Cut).**  Its prioritized circuit
  scheduler, bit input memory and logic gates can express a minterm network,
  with seven fixed output bits and the result bit spelling ASCII `0`/`1`.
  Derive a planar wire-and-bridge layout and execute the generator before
  implementing the full interpreter.

## Curation: the prune to 60

65 languages now.  The prune to 65 removed the four ordinary imperative
languages in costume (DINAC, MyScript, Basicfuck, Nevermind); the
criterion, the bands below it, and the floor are in
[limitations](limitations.md#curation).

The second band reached 60: Suptiftam, Lamfunc, `function x(y)`, Between,
and Point Break were ordinary imperative or functional languages with shared
decision-tree shims and no downstream consumer.

Do not take the band below it (60 -> 55) on this criterion: it cuts family
duplicates rather than costume, which is a different argument and is
recorded as such.

## Conditional follow-up

- **Reorder EGL inputs.**  EGL hoists every read into addressable one-hot cells,
  so a tree can test cell `perm[depth]` while the `x` commands remain in stream
  order.  Exhaustive n=3 measurement over all 256 tables gives 61304 -> 53592
  total characters (12.6%); all 2048 rows of the shortest candidates execute
  correctly.  Generalize that prototype through `best_input_order` and keep
  the identity on ties.

- **ArrowQueue reusable drain.**  Ship the verified deep-fold drain only if
  a proof makes folding meaningfully testable at `n >= 5`; current coverage
  does not reach its crossover.

- **Reorder ArrowQueue inputs.**  The three-input screen leaves 12.4%
  headroom, but its queued inputs cannot be renamed in place.  Find a
  re-enqueue and grid-routing construction, then compare emitted, executed
  programs against the current template; abandon it if the routing spends
  the apparent gain.

- **`%^2^-1` fourteen inputs.**  The staged fold's endgame strands its last
  duplicated cofactor pairs.  Rank order is steerable (pulsed doubling), but
  a merge needs the pair's value gap `d` inside a wipe window, and diving
  the partner maps `d -> amount - d` with the amount free in the window --
  a derived, unbuilt alignment controller.  Build it only if a ~20x
  thirteen-input build cost (~430k plan ops, ~8MB templates, ~226 ops per
  merge) is acceptable.
