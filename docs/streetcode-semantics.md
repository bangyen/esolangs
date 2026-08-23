# Streetcode: the implemented interpretation

This file records the interpretation that
`src/esolangs/interpreters/grid_based/streetcode.py` actually implements, and
why each rule was chosen.  Open questions and the hand-drawn ground-truth
lane-merge trace live in [`streetcode-wip.md`](streetcode-wip.md).

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
  ground-truth trace (see `docs/streetcode-wip.md`) rather than
  anything the wiki page spells out explicitly, but it is corroborated by
  both examples above: under this rule the infinite-loop example traces
  the full 20-cell drawn ring before repeating (matching the "hug the
  wall" description above) rather than the small 4-cell loop a
  turn-immediately rule falls into right next to the junction, and the
  infinite-cat example still echoes every character with nothing dropped.
  A bare, unbounded `+` shape (no wall arms) still turns immediately,
  the same as before this rule existed.

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
