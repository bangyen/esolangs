# Roadmap

Only live work belongs here. Completed findings and negative results go to
[limitations](limitations.md).

## New interpreters

The candidate list is empty.

## Conditional follow-up

- **Linear Boolean generators.**  Make build time and emitted size O(T), where
  T is the truth-table length, and add a registry-wide scaling contract.  The
  n=8 -> 9 parity sweep already exposes super-linear output in A Painter Ant
  (135016 -> 534124), 123 (94579 -> 230034), Circuit Diagram
  (145216 -> 322504), COD (942692 -> 3668705), Minifuck
  (57601 -> 203089), and Factor (24113 -> 50090); dense tables also expose
  Polynomial.  A construction audit adds AddSubJump, ArrowQueue, Back,
  B-tapemark, Bitdeque, BrainIf, Clockwise, Container, Dig, Flowchart, Forþ,
  Inject, Jaune, LaserFuck, RAM0, S*bleq,
  SLOW ACV MAMMALIAN, Streetcode, and Vandevelo.  Their quiet factors
  are minterms, rectangular tree layouts, widening labels or addresses, and
  per-depth padding; an n=8 -> 9 ratio near 2 is not evidence of O(T).
  Factor's Brainfuck tree has O(T) characters but Theta(T)
  command runs; assigning each run the next prime makes its numeral
  Theta(T log T) digits.  It needs a run-compressed Brainfuck lookup.
  Circuit Diagram now uses a linear one-pass Shannon fold and
  indexed layout guards, but its persistent selector rails leave the ASCII
  area O(T log T); route each selector only across its mux level.  Treat every
  emitted character as build work.  Input reordering is
  an optional optimization around a generator, not part of its construction,
  so its search cost does not enter this criterion.  No generator construction
  may use BFS or DFS; test-only oracle searches and prose about retired searches
  may remain.  Circuit Diagram's H-layout temporarily uses a bounded local
  dogleg scan with cell-indexed collision checks; derive its first-free lanes
  into a direct routing rule without changing the emitted programs.

- **A Painter Ant shared-head proof.**  The depth-first head cuts dense n=9
  from 517348 to 19684 characters and executes every n=3 program plus sampled
  programs through n=8, but invalidates the uniform proof check's independent
  per-leaf rest-point and motif decomposition.  Rewrite those lemmas around
  shared prefix entry/exit states, then restore `just apa-proof` to green and
  rescreen input order now that the construction is tree-shaped.

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
