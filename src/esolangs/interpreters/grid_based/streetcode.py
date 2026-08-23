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

The wiki page (https://esolangs.org/wiki/Streetcode) does not spell out the
concrete geometry behind "drive on the right-hand side" or its
leftmost/second-leftmost "ambiguous turn" rule, so this interpreter models
movement as right-hand-rule wall-following, making the spec's real choice
only where the local wall shape marks an actual intersection.  The full
interpretation -- the wall-following rule, initial heading, how a road mouth
and a crossing mouth are recognized, and the two-phase lane merge
(``_merge_target``/``_merging_heading`` in ``_choose_heading``) -- is
documented in ``docs/streetcode.md``, with the reasoning, the wiki examples
corroborating each rule, and the questions that remain open.

Runtime error contract:

* CP is unsigned and right-unbounded: decrementing it below 0 is an invalid
  runtime operation and raises :class:`~esolangs.exceptions.HaltError`.
  Cells are unbounded signed integers (plain Python ``int`` arithmetic, so
  ``~`` can drive a cell negative with no wraparound); there is no
  brainfuck-style byte wraparound on ``O`` either, so outputting a cell
  whose value is not a valid Unicode code point (negative, or absurdly
  large) is also an invalid runtime operation and raises ``HaltError``
  rather than a raw Python exception from ``chr()``.

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

# How far perpendicular to the direction of travel ``_road_mouth`` looks for
# the wall a side road opens through (a two-way street is two cells wide, so
# the far lane's wall can sit two cells out), and how far along the direction
# of travel it will look for the ``+`` closing that road's mouth.
_MOUTH_MAX_DIST = 3
_MOUTH_MAX_DEPTH = 7


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
    further using the wall-following/junction rules described in
    ``docs/streetcode.md``; ``halted`` is true once ``;`` runs or
    the car reaches a true dead end with nowhere left to go.  The VM and the
    state-cycle hang detector expose this object.
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
        # Steps of ordinary right-hand hugging still to be suppressed after a
        # junction chose to carry straight on past a side road.  The declined
        # road's mouth is open ground exactly where the hug looks, so without
        # this the car would be steered into the road it just chose against
        # on the very next step.  Counted down once per step and cleared by
        # any heading change.
        self._skip_hug = 0

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
            self._skip_hug,
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
        """Return the character at ``(row, col)``, or ``'?'`` if out of bounds.

        ``'?'`` matches no wall character, so wall-shape scans treat the
        grid's implicit edge as open ground (``_open`` is the only check
        that treats it as closed).
        """
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

    def _road_mouth(self, heading: str, side: str) -> tuple[int, int, int] | None:
        """Detect a road opening off ``side`` of the car, or ``None``.

        A branch is drawn as a gap in the wall running along ``side``, with a
        ``+`` marking each end of the gap: the wall arrives, stops at a ``+``,
        open floor spans the mouth of the side road, and a second ``+`` picks
        the wall up again.  Both ends must be ``+`` -- a gap between two plain
        ``-``/``|`` runs is where a room simply has no wall drawn, not a
        junction -- and the floor strictly between them must be open, which is
        what separates a real road mouth from a solid corner where two ``+``
        happen to sit near each other on the same wall.

        The near ``+`` is anchored at depth 0, 1, or -1 (level with the
        car, one cell ahead, or one cell behind -- the car may corner
        straight into a mouth it never met head-on), so the junction
        fires as the car *arrives* at the mouth rather than from anywhere
        within lookahead range.

        Returns ``(dist, near_depth, far_depth)`` for a detected mouth: the
        perpendicular distance to the wall carrying it, and the depths (along
        the direction of travel) of the two ``+`` bounding the gap.
        """
        d_row, d_col = _DELTA[heading]
        s_row, s_col = _DELTA[side]

        def pos(depth: int, dist: int) -> tuple[int, int]:
            """Locate a cell at an offset from the car.

            ``depth`` cells along ``heading``, ``dist`` along ``side``.
            """
            return (
                self.row + depth * d_row + dist * s_row,
                self.col + depth * d_col + dist * s_col,
            )

        for dist in range(1, _MOUTH_MAX_DIST + 1):
            # The two `+` bounding a mouth sit at the same perpendicular
            # distance.  The car must be level with the mouth's near edge --
            # the `+` immediately behind it, so the first open cell of the
            # side road is the one alongside -- for the road to be one it
            # could actually turn into.  Detecting the same mouth a cell
            # earlier, while the closing `+` is still alongside, would let the
            # car decline a turn it has not yet reached and then be dragged
            # into that very road by the ordinary right-hand hug a step later.
            # A mouth is still the car's to decide about while it has not yet
            # driven clear of the gap: ``near`` may sit one cell behind (it
            # cornered straight into the mouth without ever meeting the
            # junction head-on), level with the car, or one cell ahead.
            near = next(
                (
                    d
                    for d in (0, 1, -1)
                    if self._at(*pos(d, dist)) == "+" and self._open(*pos(d + 1, dist))
                ),
                None,
            )
            if near is not None:
                for far in range(near + 2, _MOUTH_MAX_DEPTH):
                    if self._at(*pos(far, dist)) != "+":
                        continue
                    if all(self._open(*pos(k, dist)) for k in range(near + 1, far)):
                        return dist, near, far
                    break
            if any(self._at(*pos(d, dist)) in _WALLS for d in (-1, 0, 1)):
                # This line is the wall the car is driving along, and it
                # carries no mouth it could turn into.  Anything further out
                # sits behind that wall, not on a road reachable from here, so
                # stop looking: a `+` pair sighted through solid wall is some
                # other corridor's geometry, and treating it as a junction
                # would fire in the middle of an ordinary bend.
                return None
        return None

    def _plus_dist(self, side: str) -> int | None:
        """Return the distance to the nearest ``+`` on ``side``, or ``None``.

        Scans ``1.._MOUTH_MAX_DIST`` cells out from the car
        (``_crossing_mouth`` uses this to find the two ``+`` bounding a
        mouth it is driving through).
        """
        s_row, s_col = _DELTA[side]
        return next(
            (
                dist
                for dist in range(1, _MOUTH_MAX_DIST + 1)
                if self._at(self.row + dist * s_row, self.col + dist * s_col) == "+"
            ),
            None,
        )

    def _crossing_mouth(self, heading: str) -> bool:
        """Whether the car is driving *out through* a side road's mouth.

        The same drawn junction presents two different shapes depending on
        the approach.  Driving along the main road, a branch appears as a gap
        in the wall to one side (:meth:`_road_mouth`).  Driving up the branch
        itself, the car passes *between* the two ``+`` that bound that gap --
        one to either side, at the same depth -- with the road continuing
        ahead.  That is the same intersection, met head-on rather than
        side-on, and it is equally a decision point.

        Detected as a ``+`` on each side at a matching depth, the two sitting
        at different perpendicular distances (they bound a road wider than the
        lane the car occupies), with open ground straight ahead.
        """
        if not self._open(*self._ahead(self.row, self.col, heading)):
            return False
        # Level with both `+` -- one step further and they are behind the car,
        # one step earlier and it has not reached the intersection yet.
        left, right = self._plus_dist(_left(heading)), self._plus_dist(_right(heading))
        return left is not None and right is not None and left != right

    def _junction_kind(self, heading: str) -> int:
        """Detect a real intersection ahead, returning the open-option count.

        A junction is a road mouth (see :meth:`_road_mouth`) opening off
        either side of the car, counted alongside straight-ahead travel.  All
        three orientations of a T-junction are recognized symmetrically: a
        branch to the left with wall on the right, a branch to the right with
        wall on the left, and a branch to both sides at once (a four-way, or a
        T whose crossbar the car is driving into when straight ahead is
        blocked).  Returns 3, 4, or 0 (no junction -- an ordinary corner or a
        straight stretch).

        The earlier rule looked only at a 4x4 window built on the wall the car
        was hugging and required a ``+`` pair on that window's *far* side,
        which made a branch peeling off toward the hugged wall structurally
        invisible: its ``+`` pair landed on the near side and was classified
        as an ordinary L-bend.  That asymmetry was an artifact of anchoring
        the window on one wall, not something the spec calls for -- the wiki
        describes the leftmost/second-leftmost choice without restricting
        which side of the road a branch may open on.  Both of the wiki's own
        junction-bearing examples still detect under this rule (the
        infinite-loop example at ``(1,5)`` heading West, and the larger
        infinite-cat example at ``(1,6)`` heading West).
        """
        ahead_open = self._open(*self._ahead(self.row, self.col, heading))
        left_mouth = self._road_mouth(heading, _left(heading)) is not None
        right_mouth = self._road_mouth(heading, _right(heading)) is not None
        # Counting the road behind the car, which is always drivable, a branch
        # to one side with open road ahead is a three-way; branches to both
        # sides make it a four-way when the car can also continue straight,
        # and a three-way T whose crossbar it is driving into when it cannot.
        if left_mouth and right_mouth:
            return 4 if ahead_open else 3
        if left_mouth or right_mouth:
            return 3 if ahead_open else 0
        # Met head-on -- the car is driving out through the mouth itself
        # rather than past it (see :meth:`_crossing_mouth`).
        return 3 if self._crossing_mouth(heading) else 0

    def _lane_bounded(self, heading: str, side: str) -> bool:
        """Whether the mouth on ``side`` bounds a genuinely multi-lane road.

        A mouth's two ``+`` mark where the side road's own bounding walls
        meet the wall the car is driving along.  When those ``+`` continue
        into real wall arms -- a wall one cell further out, perpendicular to
        the direction of travel, past each of them -- the side road is a
        drawn corridor with lanes of its own, and the spec's "drive on the
        right-hand side" applies to it too, so the car must merge into its
        right-hand lane rather than turning the instant it is detected.  A
        bare ``+`` floating with nothing beyond it (as in an open room)
        bounds no such corridor and turns immediately.
        """
        mouth = self._road_mouth(heading, side)
        if mouth is None:  # pragma: no cover - guarded by the caller
            return False
        dist, near, far = mouth
        d_row, d_col = _DELTA[heading]
        s_row, s_col = _DELTA[side]
        return all(
            self._at(
                self.row + depth * d_row + (dist + 1) * s_row,
                self.col + depth * d_col + (dist + 1) * s_col,
            )
            in _WALLS
            for depth in (near, far)
        )

    def _lane_merge_target(
        self, heading: str, new_heading: str, side: str
    ) -> tuple[int, int]:
        """Return the cell the car must reach before turning to ``new_heading``.

        The mouth's two ``+`` (see :meth:`_road_mouth`) mark where the side
        road's own bounding walls meet the road the car is on; the side
        road's lane cells lie strictly between them, at depths
        ``near + 1 .. far - 1`` along the direction of travel.  The car must
        reach the lane adjacent to that road's right-hand wall relative to
        ``new_heading`` before turning -- one step in from whichever bound
        sits in the ``_right(new_heading)`` direction -- rather than turning
        the moment the junction is detected.  The car does not change lane
        during this approach, so the target keeps its perpendicular
        coordinate fixed and only advances along the travel axis.
        """
        mouth = self._road_mouth(heading, side)
        if mouth is None:  # pragma: no cover - guarded by the caller
            return self.row, self.col
        _, near, far = mouth
        d_row, d_col = _DELTA[heading]
        depth = far - 1 if _right(new_heading) == heading else near + 1
        # d_row/d_col is a unit vector with exactly one nonzero component;
        # that component picks out the travel-axis coordinate to advance,
        # while the perpendicular coordinate stays fixed at the car's own.
        if d_row:
            return self.row + depth * d_row, self.col
        return self.row, self.col + depth * d_col

    def _junction_choices(self, heading: str) -> list[str]:
        """Return the roads a junction offers, in the spec's choice order.

        Only a detected side road (:meth:`_road_mouth`) counts as a turn the
        car can take, plus straight ahead when the road continues.  An open
        cell in a direction with no drawn mouth -- the blank margin above a
        corridor, say -- is not a road, and must not consume a slot.

        The roads are ordered left to right as the driver sees them: a branch
        opening to the left, then straight on, then a branch opening to the
        right.  Which slot a given turn lands in therefore depends on the
        car's heading, not on the compass direction of the road it is turning
        onto -- the same drawn corner is the "leftmost" road approached one
        way and the "second-leftmost" approached the other.
        """
        roads = []
        crossing = self._crossing_mouth(heading)
        for side in (_left(heading), heading, _right(heading)):
            if side == heading:
                if self._open(*self._ahead(self.row, self.col, heading)):
                    roads.append(heading)
            elif self._road_mouth(heading, side) is not None or (
                # Driving out through a mouth head-on, the roads to either
                # side are the main road the branch joins; they have no mouth
                # of their own to find, so take whichever way is open.
                crossing
                and self._open(*self._ahead(self.row, self.col, side))
            ):
                roads.append(side)
        return roads

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
        ``_merge_target``/``_merging_heading`` and
        ``docs/streetcode.md``).
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
                # Re-read the branch condition here rather than trusting the
                # value the latch was taken under: the approach drives over
                # real cells, and an ``I`` or ``=`` along the way can change
                # what the CPth cell holds between detecting the junction and
                # arriving at the lane where the turn is actually made.  The
                # spec's choice is about the cell as the car takes the turn,
                # so a stale latch would branch on the wrong bit.  The roads
                # were established at detection time (the mouth now lies
                # alongside or behind the car, so it no longer re-detects):
                # the choice is between the latched turn and carrying
                # straight on, ordered as they were then.
                # Rank the latched turn against carrying straight on in the
                # same left-to-right order the junction was read in, so the
                # re-read cannot silently disagree with the original choice
                # about which road is "leftmost".  The latch is only ever set
                # under a turn away from ``latched_heading``, so the two roads
                # are always distinct.
                choices = (
                    [new_heading, latched_heading]
                    if new_heading == _left(latched_heading)
                    else [latched_heading, new_heading]
                )
                new_heading = choices[0] if self._cell() == 0 else choices[1]
                ahead_row, ahead_col = self._ahead(self.row, self.col, new_heading)
                if new_heading == heading:
                    self._merging_heading = None
                elif self._open(ahead_row, ahead_col):
                    self._merging_heading = new_heading
                    return new_heading
            else:
                # Still approaching the lane where the turn will be made.
                # Hold the latched heading rather than letting an ordinary
                # right-hand hug peel the car away mid-approach -- the road
                # being joined is open on that side by definition, so the hug
                # would otherwise turn early and never reach the target.
                ahead_row, ahead_col = self._ahead(self.row, self.col, heading)
                if self._open(ahead_row, ahead_col):
                    return heading
                self._merge_target = None

        if (
            self._merge_target is None
            and len(options) >= 2
            and self._junction_kind(heading)
        ):
            roads = self._junction_choices(heading)
            # A junction that fired (see ``_junction_kind``) always offers
            # at least two roads: a mouth on either side counts alongside
            # straight ahead, and a crossing mouth counts the open sides.
            new_heading = roads[0] if self._cell() == 0 else roads[1]
            # Lane merging applies only to a turn onto a detected side road:
            # continuing straight is not a turn at all, and a road whose
            # mouth is not bounded by real wall arms has no lanes to land in.
            if new_heading != heading and self._crossing_mouth(heading):
                # Emerging head-on from a branch onto the road it joins: the
                # car has to cross that road to its far lane before turning,
                # for the same reason a side-on turn merges -- "drive on the
                # right-hand side" applies to the road being joined too.  Run
                # on until the wall ahead stops it, then turn.
                target = self.row, self.col
                d_row, d_col = _DELTA[heading]
                while self._open(target[0] + d_row, target[1] + d_col):
                    target = target[0] + d_row, target[1] + d_col
                # ``_crossing_mouth`` guarantees the cell straight ahead is
                # open, so the loop above always advances at least one cell.
                self._merge_target = (*target, new_heading, heading)
            elif new_heading != heading and self._lane_bounded(heading, new_heading):
                target = self._lane_merge_target(heading, new_heading, new_heading)
                if target != (self.row, self.col):
                    self._merge_target = (*target, new_heading, heading)
                else:
                    return new_heading
            else:
                declined = [h for h in roads if h != heading]
                if new_heading == heading:
                    # Carrying straight on past a side road: suppress the hug
                    # for exactly as many cells as that road's mouth is wide,
                    # so the car drives past the branch it just declined
                    # instead of being steered into it a step later -- and no
                    # further, so the turn immediately after the mouth (which
                    # is an ordinary corner, not the declined road) still
                    # happens.  The same mouth can be detected from more than
                    # one cell as the car approaches, so the countdown is only
                    # ever extended, never restarted shorter.
                    mouth = self._road_mouth(heading, declined[0])
                    if mouth is not None and mouth[1] <= 0:
                        # Suppress the hug across the mouth, but only when the
                        # gap opens immediately beside the car (``near <= 0``)
                        # -- those are the cells where the fallen-away wall
                        # would otherwise steer it into the road it just
                        # declined.  When the gap starts further ahead,
                        # ordinary wall-following still holds the car against
                        # the wall until it arrives, and by then the junction
                        # is behind it, so nothing needs suppressing.
                        _, near, far = mouth
                        self._skip_hug = max(self._skip_hug, far - near - 1)
                return new_heading

        right_row, right_col = self._ahead(self.row, self.col, _right(heading))
        if self._skip_hug > 0:
            # Drive past the declined branch: keep going straight rather than
            # hugging the wall that has fallen away beside the car.  A wall
            # straight ahead still turns the car -- rounding a corner is not
            # the same as being pulled into the road it chose against -- but
            # the countdown carries on so the rest of the mouth stays skipped.
            self._skip_hug -= 1
            ahead_row, ahead_col = self._ahead(self.row, self.col, heading)
            if self._open(ahead_row, ahead_col):
                return heading
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
