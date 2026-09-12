r"""Interpreter for Streetcode."""

import functools
import sys
from collections.abc import Callable, Iterator, Mapping
from typing import Literal, NamedTuple, NewType, assert_never, cast

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import IO

# The alphabet a wall form is.
# wall character, and ``.`` a.
# see that :func:`_matches`.
# pattern character that no.
_Pattern = Literal["?", "W", "."]

# The four compass headings the.
# heading distinct from the.
# plain strings, so a mix-up is.
# the wrong alphabet.
_Heading = Literal["N", "E", "S", "W"]

# What a junction detector.
# offers, counting the one the.
# all.
# corridor and a five-way needs.
# lets the checker reject an.
# ``_Pattern`` does for the.
# rather than an enum:.
# (``not.
_Junction = Literal[0, 3, 4]

# Which way a merge latch.
# under.
# unreachable, not merely.
_Turn = Literal["left", "right"]


class _Mouth(NamedTuple):
    r"""A road mouth as :func:`_road_mouth` measured it."""

    # Perpendicular distance from.
    dist: int
    # Depth along the direction of.
    near: int
    # Depth along the direction of.
    far: int

    @property
    def width(self) -> int:
        r"""How many open cells the gap between the two ``+`` spans."""
        return self.far - self.near - 1


class _Merge(NamedTuple):
    r"""An in-progress lane merge, latched until the car reaches ``target``."""

    # The cell the car must reach.
    target_row: int
    target_col: int
    # Which way it turns there,.
    turn: _Turn
    # The heading the latch was.
    latched_heading: _Heading
    # Whether the latch came from a.
    # the branch condition is.
    crossing: bool

    @property
    def target(self) -> tuple[int, int]:
        r"""The cell the car is driving to, as a coordinate pair."""
        return self.target_row, self.target_col

    @property
    def new_heading(self) -> _Heading:
        r"""The heading the car will take at ``target``."""
        return (
            _left(self.latched_heading)
            if self.turn == "left"
            else _right(self.latched_heading)
        )


class _Latches(NamedTuple):
    r"""The three values :func:`_choose_heading` carries between steps."""

    # Set when a junction turn is.
    merge: "_Merge | None"
    # Set after that turn, while.
    # yet picked up (phase 2).
    merging_heading: _Heading | None
    # Steps of ordinary right-hand.
    skip_hug: int


class _State(NamedTuple):
    r"""The movement half of a machine's state."""

    row: int
    col: int
    heading: _Heading
    latches: _Latches

    @property
    def car(self) -> "_Car":
        r"""Return the car half of the state, for the rules that only steer."""
        return _Car(self.row, self.col, self.heading)


# An open cell the flood fill.
# Only that fill mints these,.
# of them sits on the border of.
# are all on the grid, and a.
# The distinction is.
# coordinate where one of these.
# unchecked read in ``_block``.
# proof.
# up to ``_MOUTH_MAX_DEPTH``.
# which is what ``_at`` and its.
_ReachableCell = NewType("_ReachableCell", tuple[int, int])
# The car stops here on.
# ``None`` a probe returns when.
# is a malformed street.
# two were once spelled alike,.
# were indistinguishable.
# :meth:`_Machine.step` treat a.
# would have to be, rather than.
_Halt = Literal["halt"]
# A state's successors, keyed.
# one step: the arrival cell.
_Edges = dict[tuple[int, int], "_State | _Halt | None"]

# No merge in progress and.
# with, and the ones it is.
# the reset is one value rather.
_NO_LATCHES = _Latches(merge=None, merging_heading=None, skip_hug=0)

_HEADINGS: tuple[_Heading, ...] = ("N", "E", "S", "W")
_DELTA: dict[_Heading, tuple[int, int]] = {
    "N": (-1, 0),
    "E": (0, 1),
    "S": (1, 0),
    "W": (0, -1),
}
_WALLS = frozenset("+-|")

# What a read off the edge of.
# form, glyph and mouth scans.
# wall) and not any glyph a.
# ``_Grid.open_at`` tests the.
# this is a wall, because off.
_VOID = "?"

# What a drivable square does.
# the spec defines maps to one.
# space, and any character the.
# which is what makes the set.
# undefined characters here.
# lets :meth:`_Machine.step` be.
# chain of comparisons with a.
# .
# The fold is of the *meaning*,.
# as drawn (see.
# stray ink off the street and.
# street is a no-op; the same.
# program, and the two are told.
_Op = Literal["NOP", "INC", "DEC", "RIGHT", "LEFT", "IN", "OUT", "TURN", "HALT"]

# The spec's instruction.
# a no-op; see ``_Op``.
_OPS: dict[str, _Op] = {
    "^": "INC",
    "~": "DEC",
    "=": "RIGHT",
    "_": "LEFT",
    "I": "IN",
    "O": "OUT",
    "U": "TURN",
    ";": "HALT",
}

# How far perpendicular to the.
# the wall a side road opens.
# the far lane's wall can sit.
# spare.
_MOUTH_MAX_DIST = 3

# How far along the direction.
# ``+`` closing a road's mouth.
# puts the floor at 5 -- at 4.
# being seen and three tests.
# 7 is that floor plus slack.
# Raising it is not.
# high a scan runs past the box.
# bound nothing.
_MOUTH_MAX_DEPTH = 7


def _rotate(form: tuple[_Pattern, ...]) -> tuple[_Pattern, ...]:
    r"""Rotate a three-by-three form a quarter turn clockwise."""
    return tuple(form[i] for i in (6, 3, 0, 7, 4, 1, 8, 5, 2))


# The pattern alphabet keyed by.
# validated into _Pattern.
_PATTERNS: dict[str, _Pattern] = {"?": "?", "W": "W", ".": "."}


def _rotations(form: str) -> list[tuple[_Pattern, ...]]:
    r"""Return the four rotations of a nine-character form."""
    out, cur = [], tuple(_PATTERNS[c] for c in form)
    for _ in range(4):
        cur = _rotate(cur)
        out.append(cur)
    return out


# The legal wall structure.
# matched up to rotation; see.
# wall character, ``.`` is open.
# .
# corner: ?W.
# W.
# .
# .
# The corner's cells are ``W``.
# rotation does not have to.
# covers the outside of a.
# to the outer wall and the.
# boxes packed flush against.
_WALL_FORMS = [
    *_rotations("?W?W..?.."),
    *_rotations("?W?......"),
    *_rotations("W........"),
]


def _matches(block: tuple[str, ...], form: tuple[_Pattern, ...]) -> bool:
    r"""Whether a three-by-three neighbourhood matches one form."""
    for actual, want in zip(block, form, strict=True):
        if want == "?":
            continue
        if want == "W":
            if actual not in _WALLS:
                return False
        # ``want`` is "." here: the.
        # there is nothing left to fall.
        elif actual in _WALLS:
            return False
    return True


def _require(*, condition: bool, message: str) -> None:
    r"""Raise when an invariant this module relies on does not hold."""
    if not condition:
        raise AssertionError(message)


class _Grid:
    r"""The program's characters, addressable at any coordinate at all."""

    __slots__ = ("_geometry", "_rows", "height", "width")

    def __init__(self, rows: list[str]) -> None:
        r"""Square the drawing off, so every row is ``width`` characters."""
        self.width = max(len(row) for row in rows)
        self._rows = [row.ljust(self.width) for row in rows]
        self.height = len(self._rows)
        # Memo shared by the geometry.
        # drawing never changes during.
        # the drawing* from a given car.
        # time it is asked.
        # re-derive the shape, the.
        # the car revisits squares, so.
        # ``tests/fixtures/streetcode_he.
        # rules run 3242/12734/5864.
        # states -- between 4.5 and.
        # ``__setitem__`` clears it,.
        # drawing.
        self._geometry: dict[tuple[str, tuple[object, ...]], object] = {}

    @property
    def geometry(self) -> dict[tuple[str, tuple[object, ...]], object]:
        r"""The memo :func:`_geometric` keeps for the rules about this grid."""
        return self._geometry

    def __getitem__(self, where: int | tuple[int, int]) -> str:
        r"""Return a whole row by index, or one character by coordinate."""
        if isinstance(where, int):
            return self._rows[where]
        row, col = where
        if not (0 <= row < self.height and 0 <= col < self.width):
            return _VOID
        return self._rows[row][col]

    def __setitem__(self, row: int, value: str) -> None:
        r"""Redraw one row, for the fixtures that build geometry by hand."""
        self._rows[row] = "".join(value).ljust(self.width)
        self._geometry.clear()

    def __iter__(self) -> Iterator[str]:
        r"""Iterate the rows, so the drawing can be scanned as text."""
        return iter(self._rows)

    def open_at(self, row: int, col: int) -> bool:
        r"""Whether ``(row, col)`` is drivable: on the grid and not a wall."""
        if not (0 <= row < self.height and 0 <= col < self.width):
            return False
        return self._rows[row][col] not in _WALLS

    def op_at(self, row: int, col: int) -> _Op:
        r"""Return what the square at ``(row, col)`` does when the car runs it."""
        char = self[row, col]
        if char in _WALLS or char == _VOID:
            return "NOP"
        return _OPS.get(char, "NOP")


def _right(heading: _Heading) -> _Heading:
    r"""Return the heading 90 degrees clockwise from ``heading``."""
    return _HEADINGS[(_HEADINGS.index(heading) + 1) % 4]


def _left(heading: _Heading) -> _Heading:
    r"""Return the heading 90 degrees counter-clockwise from ``heading``."""
    return _HEADINGS[(_HEADINGS.index(heading) - 1) % 4]


def _drives_on_the_right(grid: _Grid, state: _State) -> bool:
    r"""Whether a car in ``state`` is on the right-hand side of its street."""
    car = _Car(state.row, state.col, state.heading)
    open_right = _open_toward(grid, car, _right(state.heading))
    open_left = _open_toward(grid, car, _left(state.heading))
    return not (open_right and not open_left)


def _opposite(heading: _Heading) -> _Heading:
    r"""Return the heading 180 degrees from ``heading``."""
    return _HEADINGS[(_HEADINGS.index(heading) + 2) % 4]


def _turn_of(heading: _Heading, new_heading: _Heading) -> _Turn:
    r"""Classify ``heading`` -> ``new_heading`` as a left or a right turn."""
    if new_heading == _left(heading):
        return "left"
    if new_heading == _right(heading):
        return "right"
    raise AssertionError(
        f"{heading} -> {new_heading} is neither a left nor a right turn:"
        " a merge latch is only ever set for a turn onto a side road"
    )


class _Car(NamedTuple):
    r"""Where the car is and which way it points."""

    row: int
    col: int
    heading: _Heading

    @property
    def at(self) -> tuple[int, int]:
        r"""The cell the car occupies, as a coordinate pair."""
        return self.row, self.col

    def ahead(self, heading: _Heading | None = None) -> tuple[int, int]:
        r"""Return the cell one step along ``heading``, or the car's own way."""
        d_row, d_col = _DELTA[self.heading if heading is None else heading]
        return self.row + d_row, self.col + d_col

    def facing(self, heading: _Heading) -> "_Car":
        r"""Return the same position under a new heading."""
        return _Car(self.row, self.col, heading)


def _ahead(row: int, col: int, heading: _Heading) -> tuple[int, int]:
    r"""Return the cell one step from ``(row, col)`` along ``heading``."""
    d_row, d_col = _DELTA[heading]
    return row + d_row, col + d_col


def _geometric[Answer](rule: Callable[..., Answer]) -> Callable[..., Answer]:
    r"""Memoize a geometry ``rule`` on the grid it is asked about."""

    @functools.wraps(rule)
    def cached(grid: _Grid, *args: object) -> Answer:
        key = (rule.__name__, args)
        memo = grid.geometry
        try:
            return cast("Answer", memo[key])
        except KeyError:
            answer = rule(grid, *args)
            memo[key] = answer
            return answer

    return cached


@_geometric
def _open_toward(grid: _Grid, car: _Car, heading: _Heading) -> bool:
    r"""Whether the cell one step from ``car`` along ``heading`` is open."""
    return grid.open_at(*car.ahead(heading))


def _initial_heading(grid: _Grid, start: tuple[int, int]) -> _Heading:
    r"""Pick the heading consistent with hugging the wall at ``C``."""
    row, col = start
    for heading in _HEADINGS:
        if grid.open_at(*_ahead(row, col, _right(heading))):
            continue
        if grid.open_at(*_ahead(row, col, heading)):
            return heading
    # No heading has both a wall on.
    # (e.g.
    # this program will hit on its.
    return "S"


@_geometric
def _road_mouth(grid: _Grid, car: _Car, side: _Heading) -> _Mouth | None:
    r"""Detect a road opening off ``side`` of ``car``, or ``None``."""
    d_row, d_col = _DELTA[car.heading]
    s_row, s_col = _DELTA[side]

    def pos(depth: int, dist: int) -> tuple[int, int]:
        r"""Locate a cell at an offset from the car."""
        return (
            car.row + depth * d_row + dist * s_row,
            car.col + depth * d_col + dist * s_col,
        )

    for dist in range(1, _MOUTH_MAX_DIST + 1):
        # The two `+` bounding a mouth.
        # distance.
        # the `+` immediately behind.
        # side road is the one.
        # could actually turn into.
        # earlier, while the closing.
        # car decline a turn it has not.
        # into that very road by the.
        # A mouth is still the car's to.
        # driven clear of the gap:.
        # cornered straight into the.
        # junction head-on), level with.
        near = next(
            (
                d
                for d in (0, 1, -1)
                if grid[pos(d, dist)] == "+" and grid.open_at(*pos(d + 1, dist))
            ),
            None,
        )
        if near is not None:
            for far in range(near + 2, _MOUTH_MAX_DEPTH):
                if grid[pos(far, dist)] != "+":
                    continue
                if all(grid.open_at(*pos(k, dist)) for k in range(near + 1, far)):
                    return _Mouth(dist=dist, near=near, far=far)
                break
        if any(grid[pos(d, dist)] in _WALLS for d in (-1, 0, 1)):
            # This line is the wall the car.
            # carries no mouth it could.
            # sits behind that wall, not on.
            # stop looking: a `+` pair.
            # other corridor's geometry,.
            # would fire in the middle of.
            return None
    return None


@_geometric
def _plus_dist(grid: _Grid, car: _Car, side: _Heading) -> int | None:
    r"""Return the distance to the nearest ``+`` on ``side``, or ``None``."""
    s_row, s_col = _DELTA[side]
    return next(
        (
            dist
            for dist in range(1, _MOUTH_MAX_DIST + 1)
            if grid[car.row + dist * s_row, car.col + dist * s_col] == "+"
        ),
        None,
    )


@_geometric
def _crossing_mouth(grid: _Grid, car: _Car) -> bool:
    r"""Whether the car is driving *out through* a side road's mouth."""
    if not _open_toward(grid, car, car.heading):
        return False
    # Level with both `+` -- one.
    # one step earlier and it has.
    left = _plus_dist(grid, car, _left(car.heading))
    right = _plus_dist(grid, car, _right(car.heading))
    return left is not None and right is not None and left != right


@_geometric
def _junction_kind(grid: _Grid, car: _Car) -> _Junction:
    r"""Detect a real intersection ahead, returning the open-option count."""
    kind = _junction_shape(grid, car)
    # A drawn junction is only a.
    # it offers are roads the car.
    # :func:`_road_deep`);.
    # boundary, and ordinary.
    return kind if len(_junction_choices(grid, car)) >= 2 else 0


@_geometric
def _junction_shape(grid: _Grid, car: _Car) -> _Junction:
    r"""Classify the wall shape alone, before the roads are counted."""
    heading = car.heading
    ahead_open = _open_toward(grid, car, heading)
    left_mouth = _road_mouth(grid, car, _left(heading)) is not None
    right_mouth = _road_mouth(grid, car, _right(heading)) is not None
    # Counting the road behind the.
    # to one side with open road.
    # sides make it a four-way when.
    # and a three-way T whose.
    if left_mouth and right_mouth:
        return 4 if ahead_open else 3
    if left_mouth or right_mouth:
        return 3 if ahead_open else 0
    # Met head-on -- the car is.
    # rather than past it (see.
    return 3 if _crossing_mouth(grid, car) else 0


def _lane_bounded(grid: _Grid, car: _Car, side: _Heading, mouth: _Mouth) -> bool:
    r"""Whether ``mouth`` bounds a genuinely multi-lane road."""
    dist, near, far = mouth.dist, mouth.near, mouth.far
    d_row, d_col = _DELTA[car.heading]
    s_row, s_col = _DELTA[side]
    return all(
        grid[
            car.row + depth * d_row + (dist + 1) * s_row,
            car.col + depth * d_col + (dist + 1) * s_col,
        ]
        in _WALLS
        for depth in (near, far)
    )


def _lane_merge_target(
    car: _Car, new_heading: _Heading, mouth: _Mouth
) -> tuple[int, int]:
    r"""Return the cell the car must reach before turning to."""
    near, far = mouth.near, mouth.far
    d_row, d_col = _DELTA[car.heading]
    depth = far - 1 if _right(new_heading) == car.heading else near + 1
    # d_row/d_col is a unit vector.
    # that component picks out the.
    # while the perpendicular.
    if d_row:
        return car.row + depth * d_row, car.col
    return car.row, car.col + depth * d_col


@_geometric
def _junction_choices(grid: _Grid, car: _Car) -> list[_Heading]:
    r"""Return the roads a junction offers, in the spec's choice order."""
    heading = car.heading
    roads = []
    crossing = _crossing_mouth(grid, car)
    # Crossing a mouth head-on, the.
    # is open", because a.
    # from inside the mouth.
    # *are* the road being joined.
    # not yet drivable --.
    # ahead, so a junction fires as.
    # is open instead fills that.
    # the two-wide street the car.
    # junction the drawing never.
    # wall-following brings it.
    # re-detects and the cell is.
    if crossing:
        for side in (_left(heading), _right(heading)):
            if _road_mouth(grid, car, side) is not None and not _open_toward(
                grid, car, side
            ):
                return []
    for side in (_left(heading), heading, _right(heading)):
        if crossing:
            # Driving out through a mouth.
            # side are the main road the.
            # perpendicular to the car, so.
            # from inside the mouth (two.
            # its far wall): take whichever.
            if _open_toward(grid, car, side):
                roads.append(side)
        elif _road_deep(grid, car, side) and _lawful_turn(grid, car, side):
            roads.append(side)
    return roads


def _road_deep(grid: _Grid, car: _Car, heading: _Heading) -> bool:
    r"""Whether ``heading`` leads onto a road, rather than across one."""
    d_row, d_col = _DELTA[heading]
    return grid.open_at(car.row + d_row, car.col + d_col) and grid.open_at(
        car.row + 2 * d_row, car.col + 2 * d_col
    )


def _lawful_turn(grid: _Grid, car: _Car, heading: _Heading) -> bool:
    r"""Whether entering ``heading`` leaves the car driving on the right."""
    row, col = car.ahead(heading)
    wrong_side = grid.open_at(*_ahead(row, col, _right(heading))) and not grid.open_at(
        *_ahead(row, col, _left(heading))
    )
    return not wrong_side


class _Steer(NamedTuple):
    r"""What a steering phase decided: a heading, and the latches after it."""

    heading: _Heading
    latches: _Latches


# What one phase answers before.
# decision if it made one, and.
# ``_Steer | None`` because a.
# a latch off (a merge.
# survive into the next phase.
_Phase = tuple["_Heading | None", _Latches]


def _heading_leaving_merge(grid: _Grid, car: _Car, latches: _Latches) -> _Phase:
    r"""Phase 2 of a merge: hold straight until the new wall picks up."""
    if latches.merging_heading is None:
        return None, latches
    heading = car.heading
    if latches.merging_heading == heading and (
        _open_toward(grid, car, _right(heading)) and _open_toward(grid, car, heading)
    ):
        return heading, latches
    return None, latches._replace(merging_heading=None)


def _heading_from_merge_target(
    grid: _Grid, car: _Car, latches: _Latches, arrival_cell: int
) -> _Phase:
    r"""Phase 1 of a merge: drive to the latched lane, then turn."""
    merge = latches.merge
    if merge is None:
        return None, latches
    new_heading = merge.new_heading
    heading = car.heading
    # A 'U' during the approach.
    # not wait forever for a cell.
    # is what keeps a divert from.
    # rest of the run (see.
    # ``test_diverting_before_the_ta.
    if heading != merge.latched_heading:
        return None, latches._replace(merge=None)
    if car.at != merge.target:
        # Still approaching the lane.
        # Hold the latched heading.
        # right-hand hug peel the car.
        # being joined is open on that.
        # would otherwise turn early.
        if _open_toward(grid, car, heading):
            return heading, latches
        return None, latches._replace(merge=None)

    latches = latches._replace(merge=None)
    # Re-read the branch condition.
    # value the latch was taken.
    # real cells, and an ``I`` or.
    # what the CPth cell holds.
    # arriving at the lane where.
    # spec's choice is about the.
    # turn (``arrival_cell``), not.
    # instruction has run: a square.
    # sets CP up for the road being.
    # must not double as the.
    # The roads were established at.
    # lies alongside or behind the.
    # re-detects): the choice is.
    # carrying straight on, ordered.
    # Rank the latched turn against.
    # same left-to-right order the.
    # re-read cannot silently.
    # about which road is.
    # under a turn away from.
    # are always distinct.
    # A *side* mouth is re-read at.
    # drove the approach as.
    # there is the one the spec's.
    # mouth was decided at the.
    # with both ``+`` when it chose.
    # lane is only lane positioning.
    # Re-reading there lets an.
    # (a ``^`` on the way to the.
    # already made, which is the.
    # as the decision" the arrival.
    if not merge.crossing:
        # Left-to-right as the driver.
        # before carrying straight on,.
        # latch stores which of the two.
        # read off the record rather.
        # headings -- the comparison.
        # second spelling of the same.
        choices = (
            [new_heading, merge.latched_heading]
            if merge.turn == "left"
            else [merge.latched_heading, new_heading]
        )
        new_heading = choices[0] if arrival_cell == 0 else choices[1]
    if new_heading == heading:
        return None, latches._replace(merging_heading=None)
    if _open_toward(grid, car, new_heading):
        return new_heading, latches._replace(merging_heading=new_heading)
    return None, latches


def _heading_from_junction(
    grid: _Grid, car: _Car, latches: _Latches, current_cell: int
) -> _Phase:
    r"""Apply the spec's ambiguous-turn rule at a detected intersection."""
    heading = car.heading
    order = [_left(heading), heading, _right(heading)]
    options = [h for h in order if _open_toward(grid, car, h)]
    if len(options) < 2 or not _junction_kind(grid, car):
        return None, latches

    roads = _junction_choices(grid, car)
    # A junction that fired (see.
    # at least two roads: a mouth.
    # straight ahead, and a.
    new_heading = roads[0] if current_cell == 0 else roads[1]
    turning = new_heading != heading
    # A turn's destination is open.
    # "sighted too early" case left.
    # mouth anchors its near ``+``.
    # fire before the car is level.
    # stepped into the wall the.
    # a guard at this point).
    # (fc58258): every road.
    # either ``_road_deep``, whose.
    # on the crossing branch --.
    # condition became.
    # ``no cover`` pragma and why.
    # over the corpus.
    # in 857 corpus programs.
    # 3.6M brute-forced (grid, car).
    # is enforced; keep the.
    # .
    # Lane merging applies only to.
    # continuing straight is not a.
    # mouth is not bounded by real.
    if turning and _crossing_mouth(grid, car):
        # Emerging head-on from a.
        # car has to cross that road to.
        # for the same reason a side-on.
        # right-hand side" applies to.
        # on until the wall ahead stops.
        target = car.at
        d_row, d_col = _DELTA[heading]
        while grid.open_at(target[0] + d_row, target[1] + d_col):
            target = target[0] + d_row, target[1] + d_col
        # ``_crossing_mouth``.
        # open, so the loop above.
        return None, latches._replace(
            merge=_Merge(
                target_row=target[0],
                target_col=target[1],
                turn=_turn_of(heading, new_heading),
                latched_heading=heading,
                crossing=True,
            )
        )
    # The mouth is looked up once.
    # to re-find it and guard.
    # out, so the lookup and the.
    mouth = _road_mouth(grid, car, new_heading)
    if turning and mouth is not None and _lane_bounded(grid, car, new_heading, mouth):
        target = _lane_merge_target(car, new_heading, mouth)
        if target != car.at:
            return None, latches._replace(
                merge=_Merge(
                    target_row=target[0],
                    target_col=target[1],
                    turn=_turn_of(heading, new_heading),
                    latched_heading=heading,
                    crossing=False,
                )
            )
        return new_heading, latches

    if not turning:
        # Carrying straight on past a.
        # for exactly as many cells as.
        # so the car drives past the.
        # instead of being steered into.
        # further, so the turn.
        # is an ordinary corner, not.
        # happens.
        # one cell as the car.
        # ever extended, never.
        declined = [h for h in roads if h != heading]
        mouth = _road_mouth(grid, car, declined[0])
        if mouth is not None and mouth.near <= 0:
            # Suppress the hug across the.
            # gap opens immediately beside.
            # -- those are the cells where.
            # would otherwise steer it into.
            # declined.
            # ordinary wall-following still.
            # the wall until it arrives,.
            # is behind it, so nothing.
            latches = latches._replace(skip_hug=max(latches.skip_hug, mouth.width))
    return new_heading, latches


def _heading_from_hug(grid: _Grid, car: _Car, latches: _Latches) -> _Phase:
    r"""Ordinary right-hand wall-following, the default movement rule."""
    heading = car.heading
    if latches.skip_hug > 0:
        # Drive past the declined.
        # hugging the wall that has.
        # straight ahead still turns.
        # the same as being pulled into.
        # the countdown carries on so.
        latches = latches._replace(skip_hug=latches.skip_hug - 1)
        if _open_toward(grid, car, heading):
            return heading, latches
    for candidate in (_right(heading), heading, _left(heading), _opposite(heading)):
        if _open_toward(grid, car, candidate):
            return candidate, latches
    return None, latches


def _choose_heading(
    grid: _Grid, car: _Car, latches: _Latches, arrival_cell: int, current_cell: int
) -> _Steer | None:
    r"""Pick the car's next heading, and the latches it carries onward."""
    phases: tuple[Callable[[_Latches], _Phase], ...] = (
        lambda ls: _heading_leaving_merge(grid, car, ls),
        lambda ls: _heading_from_merge_target(grid, car, ls, arrival_cell),
        lambda ls: _heading_from_junction(grid, car, ls, current_cell),
        lambda ls: _heading_from_hug(grid, car, ls),
    )
    for phase in phases:
        heading, latches = phase(latches)
        if heading is not None:
            return _Steer(heading, latches)
    return None


def _drive(
    grid: _Grid, state: _State, arrival_cell: int, current_cell: int
) -> "_State | _Halt | None":
    r"""Return the state one step on from ``state``, or why there is none."""
    car = state.car
    op = grid.op_at(car.row, car.col)
    if op == "HALT":
        return "halt"
    if op == "TURN":
        reversed_car = car.facing(_opposite(car.heading))
        lane = reversed_car.ahead(_right(reversed_car.heading))
        # A street with no opposite.
        # violation ``step`` raises.
        # state the car drives on to.
        if not grid.open_at(*lane):
            return None
        # A 'U' clears the latches, the.
        return _State(*lane, reversed_car.heading, _NO_LATCHES)

    steer = _choose_heading(grid, car, state.latches, arrival_cell, current_cell)
    if steer is None:
        return None
    return _State(*car.ahead(steer.heading), steer.heading, steer.latches)


class _Machine:
    r"""Per-run Streetcode state: the car, its heading, and the cell list."""

    def __init__(self, code: list[str], io: IO) -> None:
        r"""Locate the single ``C`` and derive the car's initial heading."""
        if not code or not any(line.strip() for line in code):
            raise ValueError("Streetcode program cannot be empty")
        self.io = io
        self.grid = _Grid(code)

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
        # The whole of the machine's.
        # movement rules speak in:.
        # and the three latches the.
        # ``step`` hands this to.
        # out, so the value looked up.
        # machine's own rather than one.
        # .
        # The latches (see.
        # ``merge`` is set when a.
        # reached (phase 1, driving to.
        # turning); ``merging_heading``.
        # new road's right-hand wall.
        # suppressing the immediate.
        # ``None`` outside an.
        # steps of ordinary right-hand.
        # after a junction chose to.
        # the declined road's mouth is.
        # looks, so without it the car.
        # just chose against on the.
        self._state = _State(
            *starts[0], _initial_heading(self.grid, starts[0]), _NO_LATCHES
        )
        self.cp = 0
        # The tape, as a value: an.
        # follow rather than writing.
        # far CP has travelled, which a.
        # so rebuilding it per write is.
        # quadratic a growable stack.
        self.cells: Mapping[int, int] = {}
        self._done = False
        # The enumerated drive-state.
        # graph to consult: a program.
        # (``_validate_width`` exempts.
        # interpreter's own fixtures.
        # :func:`_drive` directly in.
        # filled the graph, so the.
        # was reached.
        self._graph: dict[_State, _Edges] | None = None
        # Last, because.
        # over the grid and so needs.
        self._validate(starts[0])

    @property
    def halted(self) -> bool:
        r"""Whether the car has halted."""
        return self._done

    # The VM's language-shaped view.

    # : ``ip`` is a cell of the.
    # : parts are a row and a.
    # : this a caller cannot tell.
    # : stack, which look identical.
    ip_shape = "grid"

    @property
    def ip(self) -> tuple[int, ...]:
        r"""The car's ``(row, col, heading)``."""
        return (self.row, self.col, "NESW".index(self.heading))

    @property
    def memory(self) -> list[int]:
        r"""The tape's cells, densified."""
        cells = self.cells
        if not cells:
            return []
        return [cells.get(i, 0) for i in range(max(cells) + 1)]

    @property
    def stack(self) -> list[object]:
        r"""No stack in this language."""
        return []

    # Where the car is, as.
    # it.
    # to *move* the car states the.
    # :meth:`place`, so a machine.
    # three coordinates from one.

    @property
    def row(self) -> int:
        r"""The row the car occupies."""
        return self._state.row

    @property
    def col(self) -> int:
        r"""The column the car occupies."""
        return self._state.col

    @property
    def heading(self) -> _Heading:
        r"""The direction the car points."""
        return self._state.heading

    def place(self, row: int, col: int, heading: _Heading) -> None:
        r"""Put the car at ``(row, col)`` pointing ``heading``."""
        self._state = self._state._replace(row=row, col=col, heading=heading)

    def snapshot(self) -> tuple[object, ...]:
        r"""Return the complete internal state, hashable for cycle detection."""
        return (
            self._state,
            self.cp,
            tuple(sorted(self.cells.items())),
            self.io.position(),
            self._done,
        )

    def _cell(self) -> int:
        r"""Return the CPth cell's value, defaulting to 0 if untouched."""
        return self.cells.get(self.cp, 0)

    def _set_cell(self, value: int) -> None:
        r"""Write the CPth cell, replacing the tape rather than editing it."""
        self.cells = {**self.cells, self.cp: value}

    def _block(self, cell: _ReachableCell) -> tuple[str, ...]:
        r"""Return the three-by-three neighbourhood around a reachable cell."""
        row, col = cell
        _require(
            condition=0 < row < self.grid.height - 1 and 0 < col < self.grid.width - 1,
            message=(
                f"{cell} is on the border of the grid, so its neighbourhood"
                " runs off it: the enclosure check did not establish what"
                " this read depends on"
            ),
        )
        return tuple(
            self.grid[row + d_row, col + d_col]
            for d_row in (-1, 0, 1)
            for d_col in (-1, 0, 1)
        )

    def _validate(self, start: tuple[int, int]) -> None:
        r"""Reject a malformed street network before the car moves."""
        reachable = self._validate_width(start)
        if reachable is not None:
            self._validate_enclosed(reachable)
            self._validate_walls(reachable)
            self._validate_glyphs()
            self._validate_connected(reachable)
            self._validate_total(start)

    def _drive_states(self, start: tuple[int, int]) -> dict[_State, _Edges]:
        r"""Explore every driving state the car can reach from ``start``."""
        origin = _State(*start, _initial_heading(self.grid, start), _NO_LATCHES)
        graph: dict[_State, _Edges] = {origin: {}}
        pending = [origin]
        while pending:
            state = pending.pop()
            edges = graph[state]
            for arrival in (0, 1):
                for current in (0, 1):
                    successor = _drive(self.grid, state, arrival, current)
                    edges[arrival, current] = successor
                    if (
                        successor is not None
                        and successor != "halt"
                        and successor not in graph
                        and _drives_on_the_right(self.grid, successor)
                    ):
                        graph[successor] = {}
                        pending.append(successor)
        return graph

    def _validate_total(self, start: tuple[int, int]) -> None:
        r"""Reject a street the car can drive into and not out of."""
        self._graph = self._drive_states(start)
        for state, edges in self._graph.items():
            # ``;`` reports itself as.
            # deliberate stop no longer has.
            # re-reading the square:.
            if any(successor is None for successor in edges.values()):
                raise ValueError(
                    f"the car cannot drive out of {(state.row, state.col)} heading"
                    f" {state.heading}: the street is a dead end with no ';'"
                )
            self._check_state_invariants(state, edges)

    def _check_state_invariants(self, state: _State, edges: _Edges) -> None:
        r"""Assert what must hold of a drive state under any reading of the."""
        if not self.grid.open_at(state.row, state.col):
            raise AssertionError(
                f"the car occupies {(state.row, state.col)}, which is not"
                f" open floor: {self.grid[state.row, state.col]!r}"
            )
        for successor in edges.values():
            if successor is None or successor == "halt":
                continue
            # A step drives one cell along.
            # car teleporting, which no.
            steps = abs(successor.row - state.row) + abs(successor.col - state.col)
            if steps != 1:
                raise AssertionError(
                    f"the car moved from {(state.row, state.col)} to"
                    f" {(successor.row, successor.col)}, which is not one"
                    " orthogonal step"
                )
            if not self.grid.open_at(successor.row, successor.col):
                raise AssertionError(
                    f"the car drove from {(state.row, state.col)} into"
                    f" {(successor.row, successor.col)}, which is not open"
                    f" floor: {self.grid[successor.row, successor.col]!r}"
                )
        merge = state.latches.merge
        # A latch whose heading no.
        # step (see.
        # stale by construction and.
        if merge is None or state.heading != merge.latched_heading:
            return
        if not self.grid.open_at(merge.target_row, merge.target_col):
            raise AssertionError(
                f"the merge latched at {(state.row, state.col)} is driving to"
                f" {merge.target}, which is not open floor:"
                f" {self.grid[merge.target_row, merge.target_col]!r}"
            )
        # The approach does not change.
        # ahead along the latched.
        # never behind a car that can.
        d_row, d_col = _DELTA[merge.latched_heading]
        off_row, off_col = merge.target_row - state.row, merge.target_col - state.col
        if off_row * d_col - off_col * d_row != 0:
            raise AssertionError(
                f"the merge latched at {(state.row, state.col)} heading"
                f" {merge.latched_heading} is driving to {merge.target}, which"
                " is off the axis it is travelling along"
            )
        if off_row * d_row + off_col * d_col < 0:
            raise AssertionError(
                f"the merge latched at {(state.row, state.col)} heading"
                f" {merge.latched_heading} is driving to {merge.target}, which"
                " is behind it"
            )

    def _validate_width(self, start: tuple[int, int]) -> set[_ReachableCell] | None:
        r"""Validate that every street is two characters wide."""
        # No walls → not a street.
        if not any(ch in _WALLS for row in self.grid for ch in row):
            return None
        # BFS reachable open cells from.
        from collections import deque

        sr, sc = start
        visited: set[_ReachableCell] = set()
        q: deque[_ReachableCell] = deque([_ReachableCell((sr, sc))])
        visited.add(_ReachableCell((sr, sc)))
        while q:
            r, c = q.popleft()
            for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                nr, nc = r + dr, c + dc
                # No bounds test: off the grid.
                # so the fill cannot walk out.
                if self.grid.open_at(nr, nc) and (nr, nc) not in visited:
                    visited.add(_ReachableCell((nr, nc)))
                    q.append(_ReachableCell((nr, nc)))
        # Isolated single cell is not a.
        if len(visited) <= 1:
            return None
        violation = self._width_violation(visited)
        if violation is not None:
            raise ValueError(violation)
        return visited

    def _width_violation(self, reachable: set[_ReachableCell]) -> str | None:
        r"""Name a cell breaking the two-wide rule, or ``None`` if none does."""
        for r, c in reachable:
            n = self.grid.open_at(r - 1, c)
            s = self.grid.open_at(r + 1, c)
            e = self.grid.open_at(r, c + 1)
            w2 = self.grid.open_at(r, c - 1)
            cnt = sum((n, s, e, w2))
            if cnt == 1:
                return f"not two-wide at {(r, c)} (dead end)"
            if n and s and not (e or w2):
                return f"not two-wide at {(r, c)} (vertical)"
            if e and w2 and not (n or s):
                return f"not two-wide at {(r, c)} (horizontal)"
            if all(
                self.grid.open_at(r + dr, c + dc)
                for dr in (0, 1, 2)
                for dc in (0, 1, 2)
            ):
                return f"not two-wide at {(r, c)} (wider than two)"
        return None

    def _validate_walls(self, reachable: set[_ReachableCell]) -> None:
        r"""Validate the wall structure around every drivable cell."""
        for cell in reachable:
            r, c = cell
            block = self._block(cell)
            # A street is two cells wide,.
            # within one of it; a wall-free.
            # wider than two, which the.
            if not any(ch in _WALLS for ch in block):  # pragma: no cover
                continue
            # The two-wide check runs first.
            # shape found so far -- a wall.
            # one-wide stub, which it.
            # as the independent check the.
            if not any(  # pragma: no cover - the width check rejects these first
                _matches(block, form) for form in _WALL_FORMS
            ):
                shape = " ".join(
                    "".join("." if ch not in _WALLS else ch for ch in block[i : i + 3])
                    for i in (0, 3, 6)
                )
                raise ValueError(f"malformed wall at {(r, c)} ({shape})")

    def _validate_enclosed(self, reachable: set[_ReachableCell]) -> None:
        r"""Reject a street that runs off the edge of the grid."""
        violation = self._enclosure_violation(reachable)
        if violation is not None:
            raise ValueError(violation)

    def _enclosure_violation(self, reachable: set[_ReachableCell]) -> str | None:
        r"""Name a road cell on the grid's border, or ``None`` if none is."""
        for r, c in reachable:
            if r in (0, self.grid.height - 1) or c in (0, self.grid.width - 1):
                return (
                    f"street reaches the edge of the grid at {(r, c)}:"
                    " the road is not enclosed by walls"
                )
        return None

    def _validate_glyphs(self) -> None:
        r"""Reject a ``-`` and a ``|`` drawn side by side."""
        violation = self._glyph_violation()
        if violation is not None:
            raise ValueError(violation)

    def _glyph_violation(self) -> str | None:
        r"""Name a ``-`` drawn beside a ``|``, or ``None`` if none is."""
        for r in range(self.grid.height):
            for c in range(self.grid.width):
                char = self.grid[r, c]
                if char == "-":
                    neighbours = ((r, c - 1), (r, c + 1))
                    other = "|"
                elif char == "|":
                    neighbours = ((r - 1, c), (r + 1, c))
                    other = "-"
                else:
                    continue
                for nr, nc in neighbours:
                    if self.grid[nr, nc] == other:
                        return (
                            f"wall turns without a corner at {(r, c)}:"
                            f" {char!r} beside {other!r} at {(nr, nc)}"
                        )
        return None

    def _validate_connected(self, reachable: set[_ReachableCell]) -> None:
        r"""Reject geometry that is not part of the one street network."""
        violation = self._connection_violation(reachable)
        if violation is not None:
            raise ValueError(violation)

    def _connection_violation(self, reachable: set[_ReachableCell]) -> str | None:
        r"""Name drawn geometry off the street, or ``None`` if none is."""
        grown = {
            (r + dr, c + dc)
            for r, c in reachable
            for dr in (-1, 0, 1)
            for dc in (-1, 0, 1)
        }
        for r in range(self.grid.height):
            for c in range(self.grid.width):
                char = self.grid[r, c]
                if char == " " or (r, c) in grown:
                    continue
                return f"geometry not connected to the street at {(r, c)} ({char!r})"
        return None

    def step(self) -> None:
        r"""Execute the cell under the car, then drive it one cell further."""
        if self._done:
            return
        op = self.grid.op_at(self.row, self.col)
        if op == "HALT":
            self._done = True
            return

        # The driving state as the car.
        # Read into a local because an.
        # but never the car, its.
        # before the lookup; so this is.
        # happens.
        # separate fields to match what.
        state = self._state

        # The cell as the car arrives,.
        # A junction decision is about.
        # branches on this rather than.
        # the tape: the ``=`` painted.
        # the road ahead, and must not.
        # a per-step value, so it is.
        # kept on the machine, where it.
        # cycle detector snapshots.
        arrival_cell = self._cell()

        if op == "INC":
            self._set_cell(self._cell() + 1)
        elif op == "DEC":
            self._set_cell(self._cell() - 1)
        elif op == "RIGHT":
            self.cp += 1
        elif op == "LEFT":
            # Clamped, not an error: CP is.
            # quantity that cannot go lower.
            # docstring for why this fills.
            # of the package does.
            self.cp = max(0, self.cp - 1)
        elif op == "IN":
            value = self.io.input_str()
            self._set_cell(ord(value[0]) if value else 0)
        elif op == "OUT":
            try:
                self.io.print_char(chr(self._cell()))
            except ValueError:
                raise HaltError from None
        elif op == "TURN":
            # Streets are two-way and two.
            # right: after turning around,.
            # one now on its right, so the.
            # is this step's movement, and.
            # step like any cell the car.
            # would leave the car in the.
            # left, and the right-hand hug.
            # right turns -- back onto the.
            # cancelling the U-turn.
            # keyed to the old one is void.
            # .
            # The manoeuvre itself is.
            # because the drive-state.
            # through it here is what keeps.
            # about where a U-turn ends,.
            # drift.
            # spec allows, so there is.
            # rule answers ``None``, and.
            # runtime rather than a.
            turned = _drive(self.grid, state, arrival_cell, arrival_cell)
            if turned is None or turned == "halt":
                raise HaltError(
                    f"a U-turn at {arrival_cell} has nowhere to end: the "
                    f"street has no opposite lane, which is narrower than "
                    f"the spec allows"
                )
            self._state = turned
            return
        elif op == "NOP":
            # ``C``, space, and every.
            # fold to NOP (see ``_Op``), so.
            # it out rather than falling.
            # the type checker's.
            pass
        else:
            # Unreachable, and checked to.
            # arms exhaust the rest of.
            # ``Never``.
            # the type check rather than.
            assert_never(op)

        # Where the car goes next was.
        # at construction, so the.
        # rather than a re-run of the.
        # two branch bits are the same.
        # makes -- the arrival cell and.
        # and only their zero-ness is.
        # only tests movement applies.
        # .
        # A miss falls through to.
        # graph in the first place: a.
        # street has no graph to.
        # a latch by hand and reach a.
        # Cached or computed, the.
        # arguments -- the lookup is a.
        # second implementation that.
        current_cell = self._cell()
        edges = None if self._graph is None else self._graph.get(state)
        successor = (
            _drive(self.grid, state, arrival_cell, current_cell)
            if edges is None
            else edges[int(arrival_cell != 0), int(current_cell != 0)]
        )

        if successor == "halt":
            self._done = True
            return
        if successor is None:
            if edges is None:
                # No graph vouched for this.
                # is the car's ordinary dead.
                self._done = True
                return
            # ``_validate_total`` rejects a.
            # so reaching one here means.
            # disagree -- a bug in this.
            # that stops.
            # a truncated run as though it.
            raise AssertionError(
                f"no successor for {(self.row, self.col)} heading"
                f" {self.heading}: the drive-state graph outlived"
                " the totality check"
            )
        self._state = successor


def run(code: list[str], io: IO) -> None:
    r"""Drive a Streetcode car over ``code`` until it halts."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.readlines()
            run(data, IO())
