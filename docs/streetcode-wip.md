# Streetcode: lane merging (resolved) and remaining open questions

The interpreter (`src/esolangs/interpreters/grid_based/streetcode.py`) now
implements lane merging for genuine multi-cell-wide junction turns -- see
the "Lane merging" bullet in
[`streetcode-semantics.md`](streetcode-semantics.md) for the confirmed rule,
alongside the rest of the implemented interpretation. This file preserves
the hand-derived trace it was built from, plus the questions that trace does
*not* answer.

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
   `_junction_kind` detects it (a detected junction is not re-detected on
   subsequent steps -- the choice has to be latched).
   Instead keep driving straight (plain wall-following handles this for
   free, since the hugged wall is still there) until the car's position
   reaches the new road's right-hand lane relative to the chosen heading --
   derived directly from the mouth's own `+` pair (see `_road_mouth`), one
   step in from whichever `+` sits in the new heading's right-hand
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

## Toward a counting loop: what works, what leaks (probed 2026-08-22)

The text generator (`esolangs.tools.text.streetcode`) emits a straight
corridor whose size is `O(sum of |code point deltas|)` -- unary, unlike
the repo's other text generators, which compress with multiplication
loops (`_factor_triple` gets the brainfuck family to `O(sqrt(value))`).
Closing that gap needs `while (cell) { ... }`: a body the car
re-traverses under the control of a counter. The two halves of that
primitive were both demonstrated, but no ring composing
enter -> lap x N -> exit was found. This section records the traces so
the next attempt does not re-derive them.

### The conditional is real, and re-decides every lap

On the wiki infinite-loop example -- the ring the interpreter provably
laps (17 cells, pinned by
`test_infinite_loop_example_traces_its_17_cell_lap`) -- the junction at
`(2, 2)` approached heading East offers `roads=['E', 'S']`. With the
cell at 0 the car takes `E` (the plain lap, which is why the committed
example loops forever); with the cell nonzero it takes `S` instead, and
it re-decides on **every** lap, not once. So this is a genuine per-lap,
cell-keyed, two-way branch, and its polarity is the countdown one:
nonzero continues into the body, zero leaves.

### A counter on the lap does count down

With the seed placed on an entry corridor rather than on the lap, the
counter decrements once per lap as the car crosses a `~` on the ring
(observed 3 -> 2, then 6 -> 5 on the following lap). Neither latching
nor non-detection is an obstacle: `_junction_kind` fires on each
arrival and the cell is re-read each time.

### What could not be built: a ring you can enter and leave

Six hand-drawn geometries all leaked, each differently, and the
recurring mechanism is this: **cutting a wall for an entry or exit road
changes the lap**, so any travel direction measured on the uncut ring is
void afterwards. The right-hand hug then treats the cut as an open road
on the car's right and drives out through it. Concretely:

- An entry joined to a run the lap travels in the *opposite* direction
  is seen as open-to-the-right on the return leg, so the car escapes
  onto the entry corridor and re-crosses the seed, which re-raises the
  counter (3 -> 6 -> 9 ...) instead of letting it fall.
- Cutting the outer wall to admit that entry re-routed the lap so the
  gap was traversed *outward*, into the entry corridor's dead end, and
  the car bounced back across the seed twice per excursion.
- Seeding anywhere on the lap itself never terminates: every cell of the
  17-cell lap is re-crossed, so the seed's `^`s re-apply each lap and
  fight the body's `~` (a `+1` seed against a `-1` body oscillates 0/1
  forever).

The invariant these imply, for anyone picking this up: the lap must pass
the entry gap **travelling the entry's own direction** -- a mouth behind
the car is `back`, and `_junction_choices` never offers `back`, so a
tangential join is invisible while lapping. That has to be checked on
the *cut* grid, not the uncut one. A mechanical sweep over small ring
shapes, rather than hand-drawing, is the way to find such a geometry (or
to establish that none of the small ones work); one was started but not
completed.

So `O(value)` stands for the Streetcode text generator today, and the
straight corridor is what ships -- but on the evidence above the barrier
is the entry/exit plumbing, **not** the absence of a loop construct. The
boolean generator is consistent with this: its loops are driven by `I`
reading fresh input and each is traversed once per run, so it never
needs to solve the re-entry problem.

### Two pitfalls worth keeping

- A cell that reaches exactly 0 *inside* one of these hallways sends the
  car into an unterminated lap (no halt, no error).
- A parameterized drive-through hallway (the boolean generator's
  `_streetcode_hallway`, with the row count varied) lands a cell on
  exactly `2 * rows + 2`, confirmed to 100 rows, and hallways in series
  compose additively. That is unary rotated 90 degrees -- grid *height*
  proportional to the value -- so it compresses nothing on its own. Its
  conditional half does work: zero at the mouth skips the hallway,
  nonzero enters it.
