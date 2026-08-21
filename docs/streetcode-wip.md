# Streetcode: lane merging (resolved) and remaining open questions

The interpreter (`src/esolangs/interpreters/grid_based/streetcode.py`) now
implements lane merging for genuine multi-cell-wide junction turns -- see
the module docstring's "Lane merging" bullet for the confirmed rule. This
file preserves the hand-derived trace it was built from, plus the
questions that trace does *not* answer.

## The hand-drawn example (now the regression test)

A vertical 2-wide corridor, columns 0=wall/1-2=lanes, with two branches
peeling off to the right at different rows:

```
|  |
|  +--
|
|
|  +--
|  |
```

(columns 0-5; branches' `+` at (row1,col3) and (row4,col3); rows 2-3 are
blank between the two branches.)

The user's confirmed ground-truth trace, car starting at (row0, col1)
heading South:

```
(0,1) -> (1,1) -> (2,1) -> (3,1) -> (3,2) -> (3,3) -> (3,4)
```

This is now encoded as
`TestStreetcodeLaneMerge.test_merge_lands_in_the_right_hand_lane` in
`tests/interpreters/test_streetcode.py`.

## The rule that was derived and implemented

**"The car turns so that it's in the right lane of the road it's turning
onto, like in real life"** turned out to have two parts, both gated on the
junction's far-side `+` corners being genuine wall arms (a wall one cell
further, perpendicular to the direction of travel, past each corner --
`_lane_bounded` -- as opposed to a bare `+` floating in an open room, which
still turns immediately, same as before this rule existed):

1. **Approach (`_merge_target`)**: don't act on the junction the moment
   `_junction_kind` detects it (which, thanks to the window's fixed 4-deep
   lookahead, is always one step before the window itself starts, and is
   *not* re-detected on subsequent steps -- the choice has to be latched).
   Instead keep driving straight (plain wall-following handles this for
   free, since the hugged wall is still there) until the car's position
   reaches the new road's right-hand lane relative to the chosen heading --
   derived directly from the junction window's own far-side corners, one
   step in from whichever corner sits in the new heading's right-hand
   direction. Only then turn.
2. **Merge-out (`_merging_heading`)**: after turning, the new road's own
   right-hand wall has not necessarily picked up yet (in the hand-drawn
   example, turning East at (3,1) lands on (3,2), where South is still
   open). Keep driving straight, suppressing the ordinary right-hand-hug
   re-turn, until the new road's right-hand wall actually materializes.

Both phases were corroborated independently: the wiki's infinite-loop
example turns out to contain a genuine lane-bounded junction at (1,5)
heading West, and applying this rule there makes the car visit the `C`
cell once, then trace the full 20-cell drawn ring, before it starts
repeating -- 21 distinct cells altogether (the module docstring
previously claimed 22 cells without this rule ever having produced that
trace; measuring it directly once the rule existed gave 20 cells in the
ring itself, and the docstring has been corrected to match, pinned by
`test_infinite_loop_example_traces_the_full_21_cell_ring`) -- instead of
the small 4-cell loop a turn-immediately rule falls into right next to
the junction. The larger infinite-cat example has an analogous junction
at (1,6) heading West and still echoes every character correctly under
the rule.

## Still open

- **Does plain-corner wall-hugging (the single-cell step case, not a
  detected junction) also need lane-landing?** No evidence demands it --
  the hand-drawn trace above only exercises the junction-turn case, and
  the plain-corner path is confirmed against all four wiki examples as
  currently implemented (a single, unwidened step onto the one open
  neighbor). Left alone pending a trace that actually needs it.
- **What happens after `(3,4)` in the hand-drawn example?** Under the
  implemented rule the car simply continues East indefinitely (or until
  it hits more drawn structure) -- the 6-column diagram as given has
  nothing further to its right, so this is untested beyond that point.
- **Four-way junctions**: the implemented rule's approach/merge-out logic
  is written generally (any `_junction_kind` return value with lane-bounded
  far corners), but only a three-way junction has an actual worked trace
  behind it. It also only ever applies when the chosen turn is toward
  `_left(heading)` -- the detection window is built on that side, so a
  turn toward `_right(heading)` (reachable when straight-ahead is blocked
  and both the left and right options are open) still falls back to the
  old immediate-turn behavior, unverified either way. A four-way example,
  or one exercising a right-hand turn at a genuine junction, if either
  ever surfaces, is worth checking against the same rule before trusting
  it there too.
