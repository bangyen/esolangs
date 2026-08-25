# Streetcode: the implemented interpretation

The [wiki page](https://esolangs.org/wiki/Streetcode) never spells out the
concrete geometry behind "drive on the right-hand side" or its
leftmost/second-leftmost "ambiguous turn" rule.  This file records what
`src/esolangs/interpreters/grid_based/streetcode.py` actually implements and
why: the settled rules first, then the hand-derived trace the lane-merge rule
was built from, then the questions that trace does *not* answer.

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

The wiki page (https://esolangs.org/wiki/Streetcode) describes the car as
always driving "on the right-hand side" of a two-way street and resolving
"ambiguous turns" (real intersections) by taking the leftmost road when the
CPth cell is zero, otherwise the second-leftmost.  It does not spell out the
concrete geometry, so this interpreter models it as ordinary right-hand-rule
wall-following, with a genuine ambiguous-turn choice made only where the
local wall shape actually marks an intersection rather than a plain corner:

* **Default movement: hug the wall on the right.**  At each step (once off
  the `C` starting cell), the car checks the cell to its right (relative
  to its current heading): if that cell is open, the wall it was hugging
  has fallen away, so it turns right and drives onto it.  Otherwise it
  checks straight ahead: if that is blocked, it turns left; if neither
  right nor left nor straight is open, it is a true dead end and reverses
  180 degrees (halting only if even that is out of bounds).  This is the
  standard right-hand maze-wall-following rule, and it is what "drive on
  the right-hand side" cashes out to concretely: it makes an ordinary
  corridor bend or corner resolve on its own, with no ambiguity, while
  still tracing out the full shape of a drawn loop (verified against the
  wiki's "infinite loop" example: hugging the right-hand wall from the
  start visits the `C` cell once, then the full 20-cell drawn ring,
  before the ring starts repeating -- 21 distinct cells altogether --
  rather than the small 4-cell loop a naive "leftmost open neighbor" rule
  falls into right next to `C`).

* **Initial heading**: derived from the same right-hand-wall rule rather
  than a fixed compass direction.  The car starts heading whichever
  direction has a wall immediately to its right at the `C` cell (and open
  ground straight ahead) -- i.e., the heading consistent with having just
  arrived hugging that wall.  All four of the wiki's worked examples share
  identical local geometry at `C` (wall South, wall West, open North and
  East), and this rule resolves all four to the same heading, *East*, which
  reproduces the "simple example" (`CIO;` echoes one character and
  halts), both infinite-cat examples (echo input character-by-character
  with no spurious leading byte -- see below on the larger of the two), and
  the infinite loop (traces the full ring) simultaneously -- so it is not a
  per-example special case.

* **Genuine ambiguous turns**: a real intersection, as opposed to a plain
  corner, is recognized by the local wall shape rather than by simply
  counting open neighbors (an open room can present two or three open
  orthogonal neighbors at a perfectly ordinary corner, as the "infinite
  loop" example's turns do, without being a drawn intersection at all).
  A branch is a gap in the wall the car is driving along, with a `+`
  marking each end of the gap (`_road_mouth` scans up to
  `_MOUTH_MAX_DIST` cells out, anchoring the near `+` at depth
  0/1/-1 so the junction fires as the car *arrives* at the mouth rather
  than from within lookahead range); the same intersection met head-on --
  driving up the branch itself, out through the gap between the two
  `+` -- is `_crossing_mouth`.  Only when one of these shapes is
  actually present does the car make the spec's real
  leftmost/second-leftmost choice among the open non-backward directions
  (ordered left to right relative to its heading): leftmost when the
  CPth cell is zero, otherwise second-leftmost.  Both the infinite-loop
  example and the larger infinite-cat example actually do contain a road
  mouth (at `(1,5)` heading West and `(1,6)` heading West
  respectively), so this branch is exercised by two of the wiki's own
  four examples, not just by programs that draw a real intersection for
  its own sake.

* **Lane merging**: when a mouth's two `+` are genuine wall arms (a wall
  one cell further, perpendicular to the direction of travel, past each
  `+` -- as opposed to a bare `+` floating in an open room with
  nothing beyond it, which does not bound a real road) the
  road being turned onto is itself multi-cell-wide, and the spec's "drive
  on the right-hand side" applies to *that* road too: the car does not
  turn the instant the junction is detected, but keeps driving straight
  (plain wall-following) until it reaches the right-hand lane of the new
  road relative to the chosen heading, *then* turns; after turning it
  keeps driving straight, suppressing the ordinary right-hand-hug re-turn,
  until the new road's own right-hand wall actually picks up.  This two-
  phase suppression (`_merge_target` then `_merging_heading` in
  `_choose_heading`) is derived from a single hand-drawn, user-confirmed
  ground-truth trace (see "How the lane-merge rule was derived" below)
  rather than
  anything the wiki page spells out explicitly, but it is corroborated by
  both examples above: under this rule the infinite-loop example traces
  the full 20-cell drawn ring before repeating (matching the "hug the
  wall" description above) rather than the small 4-cell loop a
  turn-immediately rule falls into right next to the junction, and the
  infinite-cat example still echoes every character with nothing dropped.
  A bare, unbounded `+` shape (no wall arms) still turns immediately,
  the same as before this rule existed.

* **An early-sighted mouth defers its turn**: `_road_mouth` anchors the
  near `+` at depth 0, +1, or -1, so a junction can fire while the gap
  still opens *ahead* of the car -- the cell the chosen turn would step
  onto is then the wall the mouth opens through.  When the turn is not
  a lane merge (no wall arms past the far `+`, so no merge latch is
  taken), the turn is deferred: ordinary wall-following carries the car
  forward, the same mouth re-detects each step (`near` only shrinks as
  the car advances), and the turn is made once the car is level with
  the gap, re-reading the cell there.  Without this guard the car
  turned immediately, drove *inside* the wall (wall cells only block
  entry via `_open`; nothing re-checks the cell being stepped onto),
  and then wall-followed around the far side of that wall -- pinned by
  `test_early_sighted_mouth_defers_the_turn_to_the_gap`, found via a
  hand-drawn loop attempt whose entry mouth sat two cells ahead of the
  junction's firing point.

* **A road is two cells deep, and a turn keeps to the right.**  The
  roads a junction offers are the directions the car could actually
  drive down.  Streets are two characters wide, so a direction with one
  open cell before a wall is not a road: it is the street the car is
  already on -- the oncoming lane beside it, or the last cell of a bend
  (`_road_deep`).  Nor is a turn a road when its destination would leave
  the car with the wall on its left and open road on its right, which is
  the lane oncoming traffic uses (`_lawful_turn`).  Together these are
  what let a ring hug an island: at the island's corner the wall simply
  ends, with no `+ ... +` mouth to detect, and the old rule offered the
  direction the car was already travelling while missing the one the
  road bends into.  A mouth met head-on (`_crossing_mouth`) is exempt
  from the depth test: the road being joined runs perpendicular, so
  probing two cells out from inside the mouth crosses it and reads its
  far wall.

* **A junction reads the cell as the car arrives.**  The branch is taken
  on the CPth cell as it stood when the car reached the deciding square,
  before that square's own instruction runs (`_arrival_cell`).  A square
  on a turning lane commonly prepares the road being taken -- an `=`
  moving CP onto the value the road will print -- and that preparation
  must not double as the decision of which road to take.

* **A `U` ends in the opposite lane.**  Streets are two-way and two
  wide, and the car drives on the right, so after turning around the
  lane it belongs in is the one now on its right: the U-turn ends in
  that cell (the slide is the step's movement; the lane cell is executed
  on the next step, as any cell the car drives onto is), and every
  latch keyed to the old heading is dropped.  Turning in place instead
  leaves the car in the oncoming lane -- driving on the left -- and the
  right-hand hug then takes two right turns to get out of it, which
  puts the car back on its *original* heading one lane over: the U-turn
  cancels itself.  That was the implemented behavior until a hand-drawn
  counting-loop program relied on a `U` to transfer the hug from the
  outer wall onto an inner island, and the car came out of the turn
  northbound again instead of orbiting.  A one-wide corridor is
  narrower than the spec's streets and has no opposite lane, so a `U`
  there has nowhere legal to end its turn and raises `HaltError`.
  One-wide streets are now rejected up front instead: `_validate_width`
  reads the geometry off the grid at construction and raises
  `ValueError`, so a malformed program does not begin running.  The
  `HaltError` remains as the residual path, reached only by programs the
  up-front check exempts -- a grid with no walls at all, such as the
  bare `CU`, is not a street network to measure.
  The wiki's U-turn cat (`UOI ` / `CIOU`) is unaffected:
  the slide lands on exactly the cell the old in-place turn reached one
  hug-turn later, so its visited sequence and echo order are unchanged.

* **The larger "infinite cat for single characters" example** is a genuine
  cat under plain wall-following, but not via the inner `IO`/`OI`
  branch its diagram suggests: the outer ring's wall-hugging loops back
  through the same `I`/`O` pair on each lap rather than turning off
  into the `+-+IO++`/`|OI++` corridor, since that corridor's mouth is
  an ordinary corner rather than a wall shape `_junction_kind` recognizes
  as a real intersection.  It still echoes every input character in order
  with nothing dropped, matching the wiki's own framing of the example
  ("Why wouldn't this be a cat?") rather than the inner branch being load-
  bearing for cat-ness.

* CP is unsigned and right-unbounded: decrementing it below 0 is an invalid
  runtime operation and raises `esolangs.exceptions.HaltError`.
  Cells are unbounded signed integers (plain Python `int` arithmetic, so
  `~` can drive a cell negative with no wraparound); there is no
  brainfuck-style byte wraparound on `O` either, so outputting a cell
  whose value is not a valid Unicode code point (negative, or absurdly
  large) is also an invalid runtime operation and raises `HaltError`
  rather than a raw Python exception from `chr()`.

* "Nth register" for `I`/`O` is never defined anywhere else in the
  spec -- no N-argument syntax appears in any example; `I`/`O` always
  appear bare.  Read literally alongside `^`/`~`'s "CPth cell"
  phrasing, "Nth register" is sloppy wording for "the current cell"
  (N = CP).

* Exactly one `C` (car start) must appear, per the spec; zero or more
  than one is a malformed program and raises `ValueError`.

* Exhausted input on `I` raises `EOFError` (the repo-wide
  convention; the wiki does not mention EOF at all).  An empty input
  *line* is different from exhausted input (`ScriptedIO` only raises
  `EOFError` once there are no more lines at all) and is not an error:
  it sets the cell to 0.

## Construction-time validation

The spec is explicit that "all streets are two-way, they are two
characters wide", so a malformed drawing is rejected at construction
rather than part-way through a run.  Four checks run in
`src/esolangs/interpreters/grid_based/streetcode.py`.

**Width.**  `_validate_width` walks the open cells reachable from `C` and
rejects a cell whose open neighbours are a single dead end, or an
opposite pair (N+S or E+W) with no perpendicular neighbour -- in each
case there is no second lane.  A blank row or column counts as a lane,
since space is a drivable no-op.  The upper bound is enforced too: a
street wider than two lanes is rejected.  Cross-section runs cannot
measure this -- where two legal two-wide streets cross, a run through the
intersection reports the *length* of the crossing street, not any width
-- so the rule is a fully open three-by-three block, which a region wider
than two in both directions must contain and a two-wide network never
does (a crossing is a plus whose open centre is two-by-two, with walls at
the diagonal corners).  A three-by-two room passes, the deliberate
boundary of the rule: it is a two-wide street of length three seen
sideways.

One exemption remains: a grid with no walls is not a street network to
measure, so the bare `CU` still constructs and reaches the residual
`HaltError` path.  The earlier "no instruction characters" exemption is
gone -- it was content sniffing rather than geometry.  The wall-shape
fixtures that relied on it disable validation explicitly through a
test-local helper, keeping the escape hatch out of the interpreter.

**The street must be enclosed.**  A street is bounded by walls, so the
road the car can reach never touches the border of the grid:
`_validate_enclosed` rejects a program whose flood fill from `C` reaches
an edge.  This is what catches a hole two cells across.  A one-cell hole
already fails the width check, since squeezing through it leaves a
one-wide stub, but a two-wide hole is a legal-width passage that looks
like ordinary road -- only its running off the grid marks it as a gap.

**Wall structure: three neighbourhood forms.**  Street width does not
catch every malformed drawing.  A wall with a one-cell hole punched
through it (`-- --`) leaves a gap too narrow to drive, yet the corridor
either side of it still measures two wide.  That shape is real: it is how
the boolean generator's one-input CP-rewind strip was found to be drawn
one character wide.

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
which is why three forms suffice where an earlier, more literal corner
form appeared to need a dozen.

The forms constrain where walls sit, never which glyph is used, so a
second pass (`_validate_glyphs`) rejects a `-` drawn beside a `|`: the
two mean walls running in different directions, and where they meet the
wall turns a corner, which is drawn `+`.

The forms are also what keep an uncapped road divider legal (see "Still
open" below): the `?` edges of the wall form, together with the
intersection form's plain `W`, leave a bare `-` at a divider's open end
accepted while still catching the interrupted wall.

**Everything drawn belongs to one street network.**  `_validate_connected`
takes the reachable road, grows it by one cell so the growth takes in the
walls along its edges, and rejects whatever is still drawn: a detached
second box, a stray fragment of wall, an instruction sealed inside an
island, or the middle of a solid block.  A hollow island needs no special
case, since every cell of a one-thick wall is within one step of the road
around it.  Two decisions inside this check are worth recording:

* **Solid blocks are rejected.**  Permitting them would mean a second
  flood-fill pass to tell a hole enclosed by the region from the outside
  of the grid.  Unlike the divider question, where permissiveness is
  free, this one has a real implementation cost and no program in the
  repo needs it.
* **The check is strict about what counts as leftover** -- any non-blank
  character, not only walls.  Restricting it to walls would cost no
  detection (a detached box and a stray fragment are both drawn out of
  walls) and would let the remaining text stand as comments, which the
  car would treat as no-ops anyway.  The wiki says nothing about
  comments.  That alternative is left unimplemented on the grounds that a
  program containing stray marks is more likely drawn wrong than
  annotated.

Coverage lives in `TestStreetcodeStreetWidth` in
`tests/interpreters/test_streetcode.py`, which pins both the rejected
shapes and the accepted ones, including the two shipped examples, and the
checks are verified against all 276 generated truth tables and the wiki's
own worked examples.

## How the lane-merge rule was derived

The "Lane merging" bullet above states the rule; this section preserves the
single hand-drawn, user-confirmed trace it was built from, and the
independent corroboration, since neither is recoverable from the wiki.

### The hand-drawn example (now the regression test)

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


### Naming, and independent corroboration

The two phases are `_merge_target` (approach: keep driving straight until
the car reaches the new road's right-hand lane, derived from the mouth's own
`+` pair via `_road_mouth`, then turn) and `_merging_heading` (merge-out:
after turning, keep driving straight until the new road's right-hand wall
materializes -- in the trace above, turning East at (3,1) lands on (3,2),
where South is still open).  Both are gated on `_lane_bounded`; a bare `+`
floating in an open room still turns immediately.

Both phases were corroborated independently of the hand-drawn trace: the
wiki's infinite-loop example turns out to contain a genuine lane-bounded
junction at (1,5) heading West, and applying this rule there makes the car
visit the `C` cell once, then trace the full 20-cell drawn ring, before it
starts repeating -- 21 distinct cells altogether -- instead of the small
4-cell loop a turn-immediately rule falls into right next to the junction.
(An earlier version of this note claimed 22 cells without the rule ever
having produced that trace; measuring directly once the rule existed gave 20
cells in the ring itself, now pinned by
`test_infinite_loop_example_traces_the_full_21_cell_ring`.)  The larger
infinite-cat example has an analogous junction at (1,6) heading West and
still echoes every character correctly under the rule.

## Still open

- **Must a road divider end in a `+`?** Undecided by the wiki, and
  deliberately not decided here.  The hello-world example draws its
  dividers with a bare `-` at the open end (`+  --------`), uncapped;
  the boolean example and the generator cap theirs with a `+`.  Nothing
  in the driving rules keys on which it is, and hello-world runs
  correctly either way, so there is no concrete reason to reject the
  uncapped shape.  The interpreter takes the permissive reading: an
  uncapped end is accepted, and no validation rejects it.  A wall
  *interrupted* by a one-cell hole is a different shape and a real
  defect -- one was found in the boolean generator -- and is rejected
  by the wall-structure forms described above under "Construction-time
  validation", which are written to leave the uncapped end legal while
  catching the hole.
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

## The counting loop (found 2026-08-23)

A counting loop exists.  `TestStreetcodeCountingLoop` runs it: the car
counts cell 0 up to nine on the way in, U-turns onto a `++` island, and
laps it nine times, each lap adding eight to cell 1 and taking one off
cell 0, then leaves through a gap in the outer wall and prints `H`.

```
+------------+
|            |
|C^        O;|
+--+  ++  +--+
   |      |
   | ^_~ =|
   | ^++= |
   |^^++^U|
   |^^^^^=|
   |^^^^^^|
   +------+
```

The ring is an ordinary wall-hug around the island; the decision is at
the island's top-right corner, where the roads are north (out through
the gap) and south (on around the island), so the countdown steers the
loop -- nonzero laps again, zero leaves.  Three rules had to be right
before it would run, and each was wrong in a way that only a program of
this shape exposes:

* **A road is two cells deep.**  The corner offered *east* -- one open
  cell before the outer wall, which is the width of the road rather than
  a road -- and did not offer *south*, which has no `+ ... +` mouth to
  detect because the island's wall simply ends.  Both are fixed by
  requiring two drivable cells (`_road_deep`).

* **A turn may not enter the oncoming lane.**  From the corner cell the
  south turn lands with the outer wall on the car's *left*, which is the
  lane oncoming traffic uses; "the car always drives on the right-hand
  side" rules it out however open it looks (`_lawful_turn`).

* **A junction reads the cell as the car arrives**, before the square's
  own instruction runs (`_arrival_cell`).  The turning square carries an
  `=` that moves CP onto the accumulator so the `O` prints it; reading
  after that instruction, the junction branched on the accumulator (72,
  nonzero) instead of the counter (0), and the loop never exited.

The section below records the earlier probing, which concluded no such
ring existed.  Its two halves were right -- the conditional does
re-decide every lap, and a counter on the lap does count down -- but its
conclusion was an artifact of the interpreter's road detection, not of
the language.

## Earlier probing: what worked, what leaked (2026-08-22)

The text generator (`esolangs.tools.text.streetcode`) emits a straight
corridor whose size is `O(sum of |code point deltas|)` -- unary, unlike
the repo's other text generators, which compress with multiplication
loops (`_factor_triple` gets the brainfuck family to `O(sqrt(value))`).
Closing that gap needs `while (cell) { ... }`: a body the car
re-traverses under the control of a counter. The two halves of that
primitive were both demonstrated, but no ring composing
enter -> lap x N -> exit was found *at the time*. This section records the
traces so the next attempt does not re-derive them.

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

**Superseded.** The barrier was narrower still: the plumbing works, and
the leaks recorded here were the interpreter offering roads that are not
roads.  See "The counting loop" above.  The generator now uses the ring
for its first character (`_streetcode_ring`): the hand-written loop's
nine-by-eight is not a minimum, since blanking cells shortens a factor
and widening the island lengthens one, so the ring makes any
`counter * per_lap` and a remainder walked on the street covers the
rest.  Later characters keep the straight corridor of increments --
their deltas are the gaps between adjacent code points, and a gap that
small is cheaper walked than ringed.

Chaining rings on one street also works (a second ring's descent gap
placed after the first ring's `O`, with `_` resetting CP and a fresh
`^` run seeding the next counter), so the entry/exit plumbing composes;
the generator does not use it yet, because only the first character has
a delta large enough to be worth a ring.

**The ring survives a width (2026-08-24).**  It was at first built only
on the unfolded path, so any caller passing a `width` -- which
`scripts/write_examples.py` does for every example -- got the plain
serpentine and no loop at all, which is why the committed hello-world
example used to be loopless.  Folding does not make the first
character's walk cheaper, though; it packs the same unary run into more
rows.  The two layouts compose (`_streetcode_ring_serpentine`): the fold
fills its lane pairs bottom-up and starts the car in the lowest
eastbound lane, which is exactly where the ring prefix belongs, and the
block hangs below the grid's southern wall, where the fold has built
nothing.  `Hello, World!` at width 80 goes 809 -> 650 bytes.  A ring
whose prefix will not fit one lane leaves the plain fold standing -- a
CJK plan wants a remainder of 18453 -- rather than being re-planned to
suit the width: what a ring costs is what it costs, and the two finished
programs are compared as they are.

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
