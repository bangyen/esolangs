# Streetcode: the implemented interpretation

The [wiki page](https://esolangs.org/wiki/Streetcode) never spells out the
concrete geometry behind "drive on the right-hand side" or its
leftmost/second-leftmost "ambiguous turn" rule.  This file records what
`src/esolangs/interpreters/grid_based/streetcode.py` implements and why.

## Language summary

A car drives along a 2D network of two-way, two-character-wide streets,
executing the instruction under it at every cell.  Memory is an unbounded
list of signed integer cells indexed by an unsigned, right-unbounded cell
pointer (CP), starting at 0.  `^`/`~` increment/decrement the CPth cell;
`=`/`_` move CP right/left; `I`/`O` read/write the CPth cell as a
character; `U` turns the car around; `;` halts; space is a no-op.  Any
other character (including the box-drawing characters the wiki's diagrams
use to illustrate street shape) is treated like space -- a no-op the car
simply drives over; only `+`, `-`, and `|` are walls.

## Movement, junctions, and runtime errors

The wiki describes the car as driving "on the right-hand side" and
resolving "ambiguous turns" (real intersections) leftmost when the CPth
cell is zero, otherwise second-leftmost, without spelling out the
geometry.  This interpreter models it as right-hand-rule wall-following,
with the leftmost/second-leftmost choice made only where the local wall
shape actually marks an intersection rather than a plain corner:

* **Default movement: hug the wall on the right.**  At each step the car
  checks the cell to its right (relative to heading): if open, it turns
  right onto it.  Otherwise it checks straight ahead: if blocked, it
  turns left; if nothing is open, it is a dead end and reverses 180
  degrees (halting only if that is also out of bounds).  Verified against
  the wiki's "infinite loop" example: hugging the right-hand wall from
  the start visits 17 distinct cells before the lap repeats (pinned by
  `test_infinite_loop_example_traces_its_17_cell_lap`), not the small
  4-cell loop a naive "leftmost open neighbor" rule falls into next to `C`.

* **Initial heading**: derived from the same right-hand-wall rule rather
  than a fixed compass direction -- the car starts heading whichever
  direction has a wall immediately to its right at `C` and open ground
  ahead.  All four wiki examples share identical local geometry at `C`
  (wall South, wall West, open North and East) and resolve to the same
  heading, *East*, reproducing the simple example (`CIO;`), both
  infinite-cat examples, and the infinite loop -- not a per-example
  special case.

* **Genuine ambiguous turns**: a real intersection, as opposed to a plain
  corner, is recognized by the local wall shape rather than by counting
  open neighbors (an open room can present two or three open orthogonal
  neighbors at an ordinary corner without being a drawn intersection).  A
  branch is a gap in the wall with a `+` marking each end (`_road_mouth`
  scans up to `_MOUTH_MAX_DIST` cells out, anchoring the near `+` at depth
  0/1/-1 so the junction fires as the car *arrives* at the mouth); the
  same intersection met head-on is `_crossing_mouth`. Only when one of
  these shapes is present does the car make the spec's real
  leftmost/second-leftmost choice among the open non-backward directions.
  Both the infinite-loop and infinite-cat examples contain a road mouth
  (at `(1,5)` and `(1,6)` heading West respectively), so two of the
  wiki's own four examples exercise this branch.

* **Lane merging**: when a mouth's two `+` are genuine wall arms (a wall
  one cell further, perpendicular to travel, past each `+`, as opposed to
  a bare `+` floating in an open room), the road being turned onto is
  itself multi-cell-wide, and "drive on the right-hand side" applies to
  *that* road too: the car keeps driving straight until it reaches the
  new road's right-hand lane, *then* turns, then keeps driving straight
  (suppressing the ordinary right-hand-hug re-turn) until the new road's
  own right-hand wall picks up.  This two-phase suppression
  (`_heading_leaving_merge` then `_heading_from_merge_target`, both
  reached from `_choose_heading`) is derived from a hand-drawn,
  user-confirmed ground-truth trace (see "The lane-merge rule and its
  ground-truth trace" below), and corroborated by the infinite-loop and
  infinite-cat examples above.  A bare, unbounded `+` (no wall arms) still
  turns immediately.

* **An early-sighted mouth defers its turn**: `_road_mouth` anchors the
  near `+` at depth 0, +1, or -1, so a junction can fire while the gap
  still opens *ahead* of the car.  When the turn is not a lane merge (no
  wall arms past the far `+`), the turn is deferred: wall-following
  carries the car forward, the same mouth re-detects each step, and the
  turn is made once the car is level with the gap.  Without this guard the
  car turned immediately, drove *inside* the wall, and wall-followed
  around its far side -- pinned by
  `test_early_sighted_mouth_defers_the_turn_to_the_gap`.

* **A road is two cells deep, and a turn keeps to the right.**  Streets
  are two characters wide, so a direction with one open cell before a
  wall is not a road: it is the street the car is already on -- the
  oncoming lane, or the last cell of a bend (`_road_deep`).  Nor is a turn
  a road when its destination would leave the wall on the car's left and
  open road on its right, the oncoming lane (`_lawful_turn`).  Together
  these let a ring hug an island: at the island's corner the wall simply
  ends, with no `+ ... +` mouth to detect.  A mouth met head-on
  (`_crossing_mouth`) is exempt from the depth test: the road being
  joined runs perpendicular, so probing two cells out crosses it and
  reads its far wall.

* **A junction reads the cell as the car arrives.**  The branch is taken
  on the CPth cell as it stood when the car reached the deciding square,
  before that square's own instruction runs (the `arrival_cell` argument
  to `_choose_heading`).  A square on a turning lane commonly prepares the
  road being taken with an `=`, and that preparation must not double as
  the decision of which road to take.

* **A `U` ends in the opposite lane.**  Streets are two-way and two wide,
  and the car drives on the right, so after turning around the lane it
  belongs in is the one now on its right: the U-turn ends in that cell,
  and every latch keyed to the old heading is dropped. (Turning in place
  instead leaves the car in the oncoming lane, and the right-hand hug
  then takes two right turns to land back on the original heading one
  lane over -- the U-turn would cancel itself, which a hand-drawn
  counting-loop program relying on `U` to transfer the hug onto an inner
  island exposed as wrong.) A one-wide corridor has no opposite lane, so
  a `U` there has nowhere legal to end; one-wide streets are rejected up
  front instead (`_validate_width`, `ValueError` at construction).
  `HaltError` remains the residual path for programs the up-front check
  exempts -- a grid with no walls at all, such as bare `CU`. The wiki's
  U-turn cat (`UOI ` / `CIOU`) is unaffected.

* **The larger "infinite cat for single characters" example** is a genuine
  cat under plain wall-following, but not via the inner `IO`/`OI` branch
  its diagram suggests: the outer ring's wall-hugging loops back through
  the same `I`/`O` pair each lap rather than turning into the
  `+-+IO++`/`|OI++` corridor, since that corridor's mouth is an ordinary
  corner, not a wall shape `_junction_kind` recognizes as an
  intersection.  It still echoes every input character in order, matching
  the wiki's own framing ("Why wouldn't this be a cat?").

* CP is unsigned and right-unbounded: decrementing it below 0 raises
  `esolangs.exceptions.HaltError`. Cells are unbounded signed integers
  (plain Python `int`, so `~` can drive a cell negative with no
  wraparound); there is no brainfuck-style byte wraparound on `O` either,
  so outputting a cell whose value is not a valid Unicode code point
  raises `HaltError` rather than a raw Python exception from `chr()`.

* "Nth register" for `I`/`O` is never defined anywhere else in the spec --
  no N-argument syntax appears in any example.  Read alongside `^`/`~`'s
  "CPth cell" phrasing, it is sloppy wording for "the current cell"
  (N = CP).

* Exactly one `C` (car start) must appear, per the spec; zero or more
  than one raises `ValueError`.

* Exhausted input on `I` raises `EOFError` (repo-wide convention; the
  wiki does not mention EOF).  An empty input *line* is different from
  exhausted input (`ScriptedIO` only raises `EOFError` once there are no
  more lines at all) and sets the cell to 0.

## Construction-time validation

The spec is explicit that "all streets are two-way, they are two
characters wide", so a malformed drawing is rejected at construction
rather than part-way through a run.  Four checks run in
`src/esolangs/interpreters/grid_based/streetcode.py`.

**Width.**  `_validate_width` walks the open cells reachable from `C` and
rejects a cell whose open neighbours are a single dead end, or an
opposite pair (N+S or E+W) with no perpendicular neighbour -- no second
lane.  A blank row or column counts as a lane, since space is a drivable
no-op.  A street wider than two lanes is also rejected.  Cross-section
runs cannot measure this -- a run through a legal crossing reports the
*length* of the crossing street, not any width -- so the rule is a fully
open three-by-three block, which a region wider than two in both
directions must contain and a two-wide network never does (a crossing is
a plus whose open centre is two-by-two, with walls at the diagonal
corners).  A three-by-two room passes: it is a two-wide street of length
three seen sideways.

One exemption remains: a grid with no walls is not a street network to
measure, so bare `CU` still constructs and reaches the residual
`HaltError` path.  There is deliberately no "no instruction characters"
exemption, which would be content sniffing rather than geometry.  The
wall-shape fixtures disable validation through a test-local helper,
keeping the escape hatch out of the interpreter.

**The street must be enclosed.**  A street is bounded by walls, so the
road the car can reach never touches the border of the grid:
`_validate_enclosed` rejects a program whose flood fill from `C` reaches
an edge.  This catches a hole two cells across.  A one-cell hole already
fails the width check, but a two-wide hole is a legal-width passage that
looks like ordinary road -- only its running off the grid marks it as a
gap.

**Wall structure: three neighbourhood forms.**  Street width does not
catch every malformed drawing: a wall with a one-cell hole punched
through it (`-- --`) leaves a gap too narrow to drive, yet the corridor
either side still measures two wide.  That shape is real: found in the
boolean generator's one-input CP-rewind strip, drawn one character wide.

`_validate_walls` requires every reachable cell's three-by-three
neighbourhood to match one of three forms, up to rotation:

```
corner: ?W?      wall: ?W?      intersection: W..
        W..            ...                    ...
        ?..            ...                    ...
```

`W` is any wall character, `.` is open ground, `?` is anything at all.
Writing the corner's cells as `W` rather than the literal glyphs means a
rotation need not swap `|` and `-`, and lets one form cover the outside
of a corner, the inside of one, and two boxes packed flush together --
why three forms suffice where a literal corner form would need a dozen.

The forms constrain where walls sit, never which glyph is used, so a
second pass (`_validate_glyphs`) rejects a `-` drawn beside a `|`: the
two mean walls running in different directions, and where they meet the
wall turns a corner, drawn `+`.

The forms also keep an uncapped road divider legal (see "Still open"
below): the `?` edges of the wall form, together with the intersection
form's plain `W`, leave a bare `-` at a divider's open end accepted while
still catching the interrupted wall.

**Everything drawn belongs to one street network.**  `_validate_connected`
grows the reachable road by one cell, taking in the walls along its
edges, and rejects whatever is still drawn: a detached second box, a
stray fragment of wall, an instruction sealed inside an island, or the
middle of a solid block.  A hollow island needs no special case, since
every cell of a one-thick wall is within one step of the road around it.
Two decisions here are worth recording:

* **Solid blocks are rejected.**  Permitting them would mean a second
  flood-fill pass to tell a hole enclosed by the region from the outside
  of the grid, a real implementation cost with no program in the repo
  needing it.
* **The check is strict about what counts as leftover** -- any non-blank
  character, not only walls.  Restricting it to walls would cost no
  detection but would let remaining text stand as comments, which the
  car would treat as no-ops anyway.  The wiki says nothing about
  comments; left unimplemented on the grounds that stray marks are more
  likely drawn wrong than annotated.

Coverage lives in `TestStreetcodeStreetWidth` in
`tests/interpreters/test_streetcode.py`, which pins both rejected and
accepted shapes, including the two shipped examples, verified against all
276 generated truth tables and the wiki's own worked examples.

## The lane-merge rule and its ground-truth trace

The two phases behind "Lane merging" above are `_heading_leaving_merge`
(approach: keep straight until the car reaches the new road's right-hand
lane, derived from the mouth's own `+` pair via `_road_mouth`, then turn)
and `_heading_from_merge_target` (merge-out: after turning, keep straight
until the new road's right-hand wall materializes).  Both are gated on
`_lane_bounded`; a bare `+` floating in an open room still turns
immediately.  The ground-truth trace is
`TestStreetcodeLaneMerge.test_merge_lands_in_the_right_hand_lane`; the
wiki's infinite-loop and infinite-cat examples each contain an
independent lane-bounded junction that also exercises it
(`test_infinite_loop_example_traces_its_17_cell_lap`).

The hand-drawn trace referenced in "Still open" below is a vertical 2-wide
corridor (columns 0=wall/1-2=lanes) with two branches peeling off East at
rows 1 and 4:

```
|  |
|  +--
|
|
|  +--
|  |
```

with the car starting at (row0, col1) heading South landing on
`(0,1) -> (1,1) -> (2,1) -> (3,1) -> (3,2) -> (3,3) -> (3,4)`.

## Still open

- **Must a road divider end in a `+`?** Undecided by the wiki.  The
  hello-world example draws dividers with a bare `-` at the open end
  (`+  --------`), uncapped; the boolean example and the generator cap
  theirs with a `+`.  Nothing in the driving rules keys on which it is,
  so the interpreter takes the permissive reading: an uncapped end is
  accepted.  A wall *interrupted* by a one-cell hole is a different shape
  and a real defect -- rejected by the wall-structure forms above,
  written to leave the uncapped end legal while catching the hole.
- **Does plain-corner wall-hugging (a single-cell step, not a detected
  junction) also need lane-landing?** No evidence demands it -- the
  hand-drawn trace above only exercises the junction-turn case, and the
  plain-corner path is confirmed against all four wiki examples as
  implemented (a single, unwidened step onto the one open neighbor).
- **What happens after `(3,4)` in the hand-drawn example?** The car
  continues East indefinitely -- the 6-column diagram has nothing
  further to its right, untested beyond that point.
- **Four-way junctions**: the approach/merge-out logic is written
  generally, but only a three-way junction has a worked trace behind it.
  It also only ever applies when the chosen turn is toward
  `_left(heading)`; a turn toward `_right(heading)` (reachable when
  straight-ahead is blocked and both left and right are open) falls back
  to the old immediate-turn behavior, unverified either way.

## The counting loop

`TestStreetcodeCountingLoop` (`tests/interpreters/test_streetcode.py`) is
an enterable ring: the car counts a cell up on the way in, laps an
island under that count's control, and leaves once it hits zero.  Building
one correctly depends on exactly three rules already stated above (a road
is two cells deep, a turn may not enter the oncoming lane, a junction
reads the cell as the car arrives); the test is the standing check that
they hold together.

A ring must also respect two invariants a future change must not violate:

- **A lap must pass any entry/exit gap travelling the entry's own
  direction.**  A mouth behind the car is `back`, and `_junction_choices`
  never offers `back`, so a gap joined tangentially to the lap is invisible
  while lapping -- cutting a wall for an entry or exit changes the lap
  itself, so this has to hold on the *cut* grid, not the uncut one.
- **A cell that reaches exactly 0 inside a hallway or ring body (not at a
  junction) sends the car into an unterminated lap** -- no halt, no error.
  A parameterized hallway lands a cell on exactly `2 * rows + 2`, and
  hallways in series compose additively; that is unary rotated 90 degrees,
  so it compresses nothing on its own, but its conditional half works:
  zero at the mouth skips the hallway, nonzero enters it.

## Invariants the ring and lift optimizations rely on

Both Streetcode generators are **total**: `esolangs.tools.text.streetcode`
prints any text and `esolangs.tools.boolean.streetcode` builds any table.
Nothing below is a capability limit.  The ring and lift shapes are *size*
optimizations that emit a shorter program when their geometry fits; when
it does not, the plain straight or serpentine walk is emitted instead,
which prints the same thing.  In `tools/text/streetcode.py` that is
`_streetcode_ring` and `_streetcode_ring_serpentine`, both returning
`None` to decline; in `tools/boolean/streetcode.py` it is
`_streetcode_ring`, `_streetcode_lift` and `_streetcode_shared_lap`.

These are the conditions under which the shorter shape is safe, and any
change to those optimizations must keep satisfying them.  They are
consequences of the movement rules above, not restatements of them.

* **Every gap crossing is a junction and reads the CPth cell.**  Wherever a
  ring or hallway's mouth is crossed, CP must name a cell whose zero/nonzero
  state at that exact point is known and intended -- an unplanned crossing
  can steer the car off the shape entirely.  A mirrored ring (accumulator
  below the counter rather than above) still has to satisfy this at both of
  its gaps independently.
* **A lap must pass any entry/exit gap travelling the entry's own
  direction**, and only ever on the *cut* grid (see "The counting loop"
  above) -- this applies equally to generator-built rings.
* **A shared-body loop's divergent paths must hand the body the same CP.**
  If one path around a lap drops CP by a cell relative to another, the
  body's own rewind (sized for one arrival CP) breaks on whichever path
  disagrees with it.
* **A prefix that reads every cell it seeds cannot be lifted onto a
  westbound leg that crosses other mouths.**  Lifting (driving a leg in
  reverse to save columns) is only safe where CP is known nonzero at every
  mouth the leg passes over -- in `_streetcode_lift` that guarantee is the
  leading `^`, which leaves cell 0 nonzero for the whole leg so every
  crossing passes straight over.  A prefix still filling those same cells
  does not yet have it, so it cannot be lifted.
