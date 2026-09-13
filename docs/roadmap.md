# Roadmap

Only live work belongs here. Completed findings and negative results go to
[limitations](limitations.md).

## New interpreters

The candidate list is empty.

## Line

Boolean generation has no resource wall: twelve inputs round-trip within the
projected time and memory budget. Future performance work belongs in extraction,
not subtree sharing or a denser layout.

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

- **WII2D's exactly-once embed convention.**  Dense n=10 is a wall of the
  convention, not the machine: a per-node re-embed does dense n=10 in 14432
  characters and dense n=13 in 146540, every row executed.  Re-examine the
  convention only if the arity ever matters -- it is fenced by the invariant
  in `tests/tools/test_boolean_parameterized.py`, and Dotlang and 2dFish
  were removed rather than exempted from it.

- **Minifuck's mux round loop.**  The rest of the sculpt closed (pool code
  in `5b35c66b`, the named accumulator from nine); the round loop did not,
  and is *measured* not to.  Over 36864 round transitions at exhaustive n=3
  no round moved a row above the frontier, but 27656 moved one below it, so
  the post-fix column is not predictable without walking.  Reopen only with
  a rule for the `_mux_probe` cascade -- now 69% of the build -- not a wider
  search.

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
