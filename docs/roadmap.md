# Roadmap

Only live work belongs here. Completed findings and negative results go to
[limitations](limitations.md).

## New interpreters

The candidate list is empty.

## Conditional follow-up

- **Linear Boolean generators.**  Make build time and emitted size O(T), where
  T is the truth-table length, and add a registry-wide scaling contract.  The
  n=8 -> 9 parity sweep already exposes super-linear output in A Painter Ant
  (135016 -> 534124), 123 (222847 -> 750738), Circuit Diagram
  (632616 -> 1661008), COD (942692 -> 3668705), Eval
  (35611 -> 136735), Minifuck (57601 -> 203089), ROTFuck
  (83516 -> 200647), and Suffolk (34697 -> 105932); dense tables also expose
  Polynomial and Super SNUSP.  Treat every emitted character as build work,
  then remove the independent non-linear planners: the shared and bespoke
  factorial input-order scans (including CircleFuck, 6-5, LaserFuck,
  Streetcode, and Unsquare's `3**n` arrangements), Circuit Diagram's
  quadratic layout checks, and the greedy reorder's O(T log(T)^2) scoring.
  Do not replace them with BFS or DFS.  `%^2^-1`'s live breadth-first spelling
  catalogue must become a derived rule or a fixed-size direct construction;
  test-only oracle searches and prose about retired searches may remain.

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
