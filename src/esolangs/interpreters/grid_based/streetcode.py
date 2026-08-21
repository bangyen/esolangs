"""Interpreter for Streetcode.

A car drives along a 2D network of two-way, two-character-wide streets,
executing the instruction under it at every cell.  Memory is an unbounded
list of signed integer cells indexed by an unsigned, right-unbounded cell
pointer (CP), starting at 0.  ``^``/``~`` increment/decrement the CPth cell;
``=``/``_`` move CP right/left; ``I``/``O`` read/write the CPth cell as a
character; ``U`` turns the car around; ``;`` halts; space is a no-op.  Any
other character (including the box-drawing characters the wiki's diagrams
use to illustrate street shape) is treated like space -- a no-op the car
simply drives over; only ``+``, ``-``, and ``|`` are walls.

The wiki page (https://esolangs.org/wiki/Streetcode) describes the car as
always driving "on the right-hand side" of a two-way street and resolving
"ambiguous turns" (real intersections) by taking the leftmost road when the
CPth cell is zero, otherwise the second-leftmost.  It does not spell out the
concrete geometry, so this interpreter models it as ordinary right-hand-rule
wall-following, with a genuine ambiguous-turn choice made only where the
local wall shape actually marks an intersection rather than a plain corner:

* **Default movement: hug the wall on the right.**  At each step (once off
  the ``C`` starting cell), the car checks the cell to its right (relative
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
  start visits the ``C`` cell once, then the full 20-cell drawn ring,
  before the ring starts repeating -- 21 distinct cells altogether --
  rather than the small 4-cell loop a naive "leftmost open neighbor" rule
  falls into right next to ``C``).

* **Initial heading**: derived from the same right-hand-wall rule rather
  than a fixed compass direction.  The car starts heading whichever
  direction has a wall immediately to its right at the ``C`` cell (and open
  ground straight ahead) -- i.e., the heading consistent with having just
  arrived hugging that wall.  All four of the wiki's worked examples share
  identical local geometry at ``C`` (wall South, wall West, open North and
  East), and this rule resolves all four to the same heading, *East*, which
  reproduces the "simple example" (``CIO;`` echoes one character and
  halts), both infinite-cat examples (echo input character-by-character
  with no spurious leading byte -- see below on the larger of the two), and
  the infinite loop (traces the full ring) simultaneously -- so it is not a
  per-example special case.

* **Genuine ambiguous turns**: a real intersection, as opposed to a plain
  corner, is recognized by the local wall shape rather than by simply
  counting open neighbors (an open room can present two or three open
  orthogonal neighbors at a perfectly ordinary corner, as the "infinite
  loop" example's turns do, without being a drawn intersection at all).
  Looking at a 4x4 window immediately ahead of the car -- aligned to the
  wall it is hugging, one cell further in than that wall, four cells deep
  in the direction of travel -- a **three-way** junction is a wall on one
  side of the window with ``+`` at the two corners of the opposite side
  (two separate corners, not one ordinary L-shaped corner's adjacent pair);
  a **four-way** junction is ``+`` at all four corners of the window.
  Only then does the car make the spec's actual leftmost/second-leftmost
  choice among the open non-backward directions (ordered left to right
  relative to its heading): leftmost when the CPth cell is zero, otherwise
  second-leftmost.  Both the infinite-loop example and the larger
  infinite-cat example actually do contain this shape (at ``(1,5)`` heading
  West and ``(1,6)`` heading West respectively), so this branch is
  exercised by two of the wiki's own four examples, not just by programs
  that draw a real intersection for its own sake.

* **Lane merging**: when the junction's far-side ``+`` corners are genuine
  wall arms (a wall one cell further, perpendicular to the direction of
  travel, past each corner -- as opposed to a bare ``+`` floating in an
  open room with nothing beyond it, which does not bound a real road) the
  road being turned onto is itself multi-cell-wide, and the spec's "drive
  on the right-hand side" applies to *that* road too: the car does not
  turn the instant the junction is detected, but keeps driving straight
  (plain wall-following) until it reaches the right-hand lane of the new
  road relative to the chosen heading, *then* turns; after turning it
  keeps driving straight, suppressing the ordinary right-hand-hug re-turn,
  until the new road's own right-hand wall actually picks up.  This two-
  phase suppression (``_merge_target`` then ``_merging_heading`` in
  ``_choose_heading``) is derived from a single hand-drawn, user-confirmed
  ground-truth trace (see ``docs/streetcode-wip.md``) rather than
  anything the wiki page spells out explicitly, but it is corroborated by
  both examples above: under this rule the infinite-loop example traces
  the full 20-cell drawn ring before repeating (matching the "hug the
  wall" description above) rather than the small 4-cell loop a
  turn-immediately rule falls into right next to the junction, and the
  infinite-cat example still echoes every character with nothing dropped.
  A bare, unbounded ``+`` shape (no wall arms) still turns immediately,
  the same as before this rule existed.

* **The larger "infinite cat for single characters" example** is a genuine
  cat under plain wall-following, but not via the inner ``IO``/``OI``
  branch its diagram suggests: the outer ring's wall-hugging loops back
  through the same ``I``/``O`` pair on each lap rather than turning off
  into the ``+-+IO++``/``|OI++`` corridor, since that corridor's mouth is
  an ordinary corner rather than a wall shape ``_junction_kind`` recognizes
  as a real intersection.  It still echoes every input character in order
  with nothing dropped, matching the wiki's own framing of the example
  ("Why wouldn't this be a cat?") rather than the inner branch being load-
  bearing for cat-ness.

* CP is unsigned and right-unbounded: decrementing it below 0 is an invalid
  runtime operation and raises :class:`~esolangs.exceptions.HaltError`.
  Cells are unbounded signed integers (plain Python ``int`` arithmetic, so
  ``~`` can drive a cell negative with no wraparound); there is no
  brainfuck-style byte wraparound on ``O`` either, so outputting a cell
  whose value is not a valid Unicode code point (negative, or absurdly
  large) is also an invalid runtime operation and raises ``HaltError``
  rather than a raw Python exception from ``chr()``.

* "Nth register" for ``I``/``O`` is never defined anywhere else in the
  spec -- no N-argument syntax appears in any example; ``I``/``O`` always
  appear bare.  Read literally alongside ``^``/``~``'s "CPth cell"
  phrasing, "Nth register" is sloppy wording for "the current cell"
  (N = CP).

* Exactly one ``C`` (car start) must appear, per the spec; zero or more
  than one is a malformed program and raises :class:`ValueError`.

* Exhausted input on ``I`` raises :class:`EOFError` (the repo-wide
  convention; the wiki does not mention EOF at all).  An empty input
  *line* is different from exhausted input (``ScriptedIO`` only raises
  ``EOFError`` once there are no more lines at all) and is not an error:
  it sets the cell to 0.
"""

import sys

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import IO

_HEADINGS = ("N", "E", "S", "W")
_DELTA = {"N": (-1, 0), "E": (0, 1), "S": (1, 0), "W": (0, -1)}
_WALLS = frozenset("+-|")


def _right(heading: str) -> str:
    """Return the heading 90 degrees clockwise from ``heading``."""
    return _HEADINGS[(_HEADINGS.index(heading) + 1) % 4]


def _left(heading: str) -> str:
    """Return the heading 90 degrees counter-clockwise from ``heading``."""
    return _HEADINGS[(_HEADINGS.index(heading) - 1) % 4]


def _opposite(heading: str) -> str:
    """Return the heading 180 degrees from ``heading``."""
    return _HEADINGS[(_HEADINGS.index(heading) + 2) % 4]


class _Machine:
    """Per-run Streetcode state: the car, its heading, and the cell list.

    ``step()`` executes the cell under the car, then drives it one cell
    further using the wall-following/junction rules described in the
    module docstring; ``halted`` is true once ``;`` runs or the car reaches
    a true dead end with nowhere left to go.  The VM and the state-cycle
    hang detector expose this object.
    """

    def __init__(self, code: list[str], io: IO) -> None:
        """Locate the single ``C`` and derive the car's initial heading."""
        if not code or not any(line.strip() for line in code):
            raise ValueError("Streetcode program cannot be empty")
        self.io = io
        self.width = max(len(line) for line in code)
        self.grid = [line.ljust(self.width) for line in code]
        self.height = len(self.grid)

        starts = [
            (r, c)
            for r, row in enumerate(self.grid)
            for c, ch in enumerate(row)
            if ch == "C"
        ]
        if len(starts) != 1:
            raise ValueError(
                f"Streetcode program must have exactly one C, found {len(starts)}"
            )
        self.row, self.col = starts[0]
        self.cp = 0
        self.cells: dict[int, int] = {}
        self._done = False
        self.heading = self._initial_heading()
        # Lane-merge latches (see ``_choose_heading``): ``_merge_target`` is
        # set when a junction turn is detected but not yet reached (phase 1,
        # driving to the new road's lane before turning); ``_merging_heading``
        # is set after that turn while the new road's right-hand wall has not
        # yet picked up (phase 2, suppressing the immediate right-hand-hug
        # re-turn).  Both are ``None`` outside an in-progress merge.
        # ``_merge_target``'s fourth element is the heading it was latched
        # under, so any change of heading before the target is reached (a
        # 'U', or a corner forcing a turn) invalidates the latch instead of
        # silently misapplying a stale turn.
        self._merge_target: tuple[int, int, str, str] | None = None
        self._merging_heading: str | None = None

    @property
    def halted(self) -> bool:
        """Whether the car has halted."""
        return self._done

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        return (
            self.row,
            self.col,
            self.heading,
            self.cp,
            tuple(sorted(self.cells.items())),
            self.io.position(),
            self._merge_target,
            self._merging_heading,
        )

    def _cell(self) -> int:
        """Return the CPth cell's value, defaulting to 0 if untouched."""
        return self.cells.get(self.cp, 0)

    def _set_cell(self, value: int) -> None:
        self.cells[self.cp] = value

    def _open(self, row: int, col: int) -> bool:
        """Whether ``(row, col)`` is in bounds and not a wall character."""
        if not (0 <= row < self.height and 0 <= col < self.width):
            return False
        return self.grid[row][col] not in _WALLS

    def _at(self, row: int, col: int) -> str:
        """Return the character at ``(row, col)``, or a wall if out of bounds."""
        if not (0 <= row < self.height and 0 <= col < self.width):
            return "?"
        return self.grid[row][col]

    def _ahead(self, row: int, col: int, heading: str) -> tuple[int, int]:
        d_row, d_col = _DELTA[heading]
        return row + d_row, col + d_col

    def _initial_heading(self) -> str:
        """Pick the heading consistent with hugging the wall at ``C``.

        The car starts as if it had just arrived driving on the right, so
        its initial heading is whichever direction has a wall immediately
        to its right (and open ground straight ahead) at the ``C`` cell.
        """
        for heading in _HEADINGS:
            right_row, right_col = self._ahead(self.row, self.col, _right(heading))
            if self._open(right_row, right_col):
                continue
            ahead_row, ahead_col = self._ahead(self.row, self.col, heading)
            if self._open(ahead_row, ahead_col):
                return heading
        # No heading has both a wall on the right and open ground ahead
        # (e.g. an isolated cell): fall back to South, matching the halt
        # this program will hit on its very first movement attempt anyway.
        return "S"

    def _junction_corners(self, heading: str) -> list[tuple[int, int]]:
        """Return the 4x4 detection window's four corners for ``heading``.

        The window starts one cell ahead of the car (in the direction of
        travel), at the wall it is hugging (one step to its right), and
        extends 3 more cells both further ahead and away from that wall.
        Returned as ``[near-wall-near, near-wall-far, far-near, far-far]``
        along (direction-of-travel, perpendicular): index 0/1 sit against
        the hugged wall, 2/3 sit on the far side of the window.
        """
        d_row, d_col = _DELTA[heading]
        wall_row, wall_col = self._ahead(self.row, self.col, _right(heading))
        base_row, base_col = wall_row + d_row, wall_col + d_col
        perp_row, perp_col = _DELTA[_left(heading)]
        return [
            (base_row, base_col),
            (base_row + 3 * d_row, base_col + 3 * d_col),
            (base_row + 3 * perp_row, base_col + 3 * perp_col),
            (
                base_row + 3 * d_row + 3 * perp_row,
                base_col + 3 * d_col + 3 * perp_col,
            ),
        ]

    def _junction_kind(self, heading: str) -> int:
        """Detect a real intersection ahead, returning the open-option count.

        Two ``+`` characters at two *different* corners of the detection
        window (with a wall completing the third side) mark a three-way
        junction; ``+`` at all four corners marks a four-way junction.
        Returns 3, 4, or 0 (no junction detected -- an ordinary corner or
        straight stretch).
        """
        corner_positions = self._junction_corners(heading)
        plus_corners = [self._at(r, c) == "+" for r, c in corner_positions]
        plus_count = sum(plus_corners)
        if plus_count == 4:
            return 4
        if plus_count == 2:
            # A three-way junction is `+` at both far-side corners (a branch
            # peeling away on the far side, with the hugged wall's near-side
            # corners staying plain wall) -- not two adjacent `+`s forming
            # one ordinary L-bend corner.
            near_side = plus_corners[0] and plus_corners[1]
            far_side = plus_corners[2] and plus_corners[3]
            if far_side and not near_side:
                return 3
        return 0

    def _lane_bounded(self, heading: str) -> bool:
        """Whether the junction's far-side corners are genuine wall arms.

        ``_junction_kind`` fires on any two ``+`` at the window's far side,
        but a bare ``+`` with nothing beyond it (as in an open room) does
        not bound a real multi-cell-wide road worth landing a lane in --
        only a ``+`` that continues into an actual wall one cell further,
        perpendicular to the direction of travel, does.  Gates lane-merging
        so it does not fire on such a false-positive junction shape.  Only
        meaningful
        (and only ever called) when the chosen turn is toward
        ``_left(heading)``: the detection window itself is built on that
        side, so it says nothing about a turn toward ``_right(heading)``.
        """
        perp_row, perp_col = _DELTA[_left(heading)]
        _, _, far_near, far_far = self._junction_corners(heading)
        near_wall = self._at(far_near[0] + perp_row, far_near[1] + perp_col) in _WALLS
        far_wall = self._at(far_far[0] + perp_row, far_far[1] + perp_col) in _WALLS
        return near_wall and far_wall

    def _lane_merge_target(self, heading: str, new_heading: str) -> tuple[int, int]:
        """Return the cell the car must reach before turning to ``new_heading``.

        A three-way junction's far-side corners (``_junction_corners``'
        indices 2 and 3) mark where the new road's two bounding walls sit,
        ``3 * _DELTA[heading]`` apart along the direction of travel; the new
        road's lane cells are strictly between them.  The car must reach the
        lane adjacent to the new road's right-hand wall relative to
        ``new_heading`` -- i.e. the one step in from whichever far-side
        corner sits in the ``_right(new_heading)`` direction -- before
        turning, rather than turning the moment the junction is detected.
        The car does not change lane during this approach, so the target
        keeps the car's current row/col fixed along the direction
        perpendicular to travel, only advancing the travel-axis coordinate.
        """
        d_row, d_col = _DELTA[heading]
        _, _, far_near, far_far = self._junction_corners(heading)
        from_far = _right(new_heading) == heading
        # d_row/d_col is a unit vector with exactly one nonzero component;
        # that component picks out the travel-axis coordinate to advance,
        # while the perpendicular coordinate stays fixed at the car's own.
        if d_row:
            corner_row = far_far[0] - d_row if from_far else far_near[0] + d_row
            return corner_row, self.col
        corner_col = far_far[1] - d_col if from_far else far_near[1] + d_col
        return self.row, corner_col

    def _choose_heading(self) -> str | None:
        """Pick the car's next heading.

        Ordinary movement hugs the wall on the right; a detected
        intersection instead applies the spec's leftmost/second-leftmost
        rule among the open non-backward directions -- except when the
        junction is wide enough that the chosen road has its own lanes, in
        which case the car first drives (via plain wall-following) to the
        right-hand lane of the road it is turning onto, and after turning
        keeps driving straight until that new road's right-hand wall
        actually picks up, before resuming ordinary wall-following (see
        ``_merge_target``/``_merging_heading`` and the module docstring).
        Both latches are abandoned -- falling back to plain wall-following
        -- the moment anything about the approach stops matching what was
        latched: a heading change (e.g. a 'U') during the approach, or a
        wall exactly at the cell the latch would otherwise step onto.
        """
        heading = self.heading
        back = _opposite(heading)
        order = [_left(heading), heading, _right(heading)]
        options = [h for h in order if self._open(*self._ahead(self.row, self.col, h))]

        if self._merging_heading is not None:
            if self._merging_heading == heading:
                right_row, right_col = self._ahead(self.row, self.col, _right(heading))
                ahead_row, ahead_col = self._ahead(self.row, self.col, heading)
                if self._open(right_row, right_col) and self._open(
                    ahead_row, ahead_col
                ):
                    return heading
            self._merging_heading = None

        if self._merge_target is not None:
            target_row, target_col, new_heading, latched_heading = self._merge_target
            if heading != latched_heading:
                self._merge_target = None
            elif (self.row, self.col) == (target_row, target_col):
                self._merge_target = None
                ahead_row, ahead_col = self._ahead(self.row, self.col, new_heading)
                if self._open(ahead_row, ahead_col):
                    self._merging_heading = new_heading
                    return new_heading

        if (
            self._merge_target is None
            and len(options) >= 2
            and self._junction_kind(heading)
        ):
            new_heading = options[0] if self._cell() == 0 else options[1]
            # The junction window (and everything derived from it) only
            # describes the _left(heading) side; a turn onto _right(heading)
            # is geometrically unrelated to what it measured, so lane-merge
            # logic cannot apply there.
            merge_side = new_heading == _left(heading)
            if merge_side and self._lane_bounded(heading):
                target = self._lane_merge_target(heading, new_heading)
                if target != (self.row, self.col):
                    self._merge_target = (*target, new_heading, heading)
                else:
                    ahead_row, ahead_col = self._ahead(self.row, self.col, new_heading)
                    if self._open(ahead_row, ahead_col):
                        self._merging_heading = new_heading
                        return new_heading
            else:
                return new_heading

        right_row, right_col = self._ahead(self.row, self.col, _right(heading))
        if self._open(right_row, right_col):
            return _right(heading)
        ahead_row, ahead_col = self._ahead(self.row, self.col, heading)
        if self._open(ahead_row, ahead_col):
            return heading
        left_row, left_col = self._ahead(self.row, self.col, _left(heading))
        if self._open(left_row, left_col):
            return _left(heading)
        back_row, back_col = self._ahead(self.row, self.col, back)
        return back if self._open(back_row, back_col) else None

    def step(self) -> None:
        """Execute the cell under the car, then drive it one cell further."""
        if self._done:
            return
        char = self.grid[self.row][self.col]
        if char == ";":
            self._done = True
            return

        if char == "^":
            self._set_cell(self._cell() + 1)
        elif char == "~":
            self._set_cell(self._cell() - 1)
        elif char == "=":
            self.cp += 1
        elif char == "_":
            if self.cp == 0:
                raise HaltError
            self.cp -= 1
        elif char == "I":
            value = self.io.input_str()
            self._set_cell(ord(value[0]) if value else 0)
        elif char == "O":
            try:
                self.io.print_char(chr(self._cell()))
            except ValueError:
                raise HaltError from None
        elif char == "U":
            self.heading = _opposite(self.heading)
        # 'C' and space (and any other undefined character) are no-ops.

        heading = self._choose_heading()
        if heading is None:
            self._done = True
            return
        self.heading = heading
        d_row, d_col = _DELTA[heading]
        self.row += d_row
        self.col += d_col


def run(code: list[str], io: IO) -> None:
    """Drive a Streetcode car over ``code`` until it halts."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.readlines()
            run(data, IO())
