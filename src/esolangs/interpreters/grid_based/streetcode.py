"""Interpreter for Streetcode.

A car drives a 2D network of two-way, two-character-wide streets, running
the instruction under it at every cell; memory is an unbounded list of
signed integer cells under an unsigned cell pointer (CP).

``the implementation`` is the spec of record: the `wiki page
<https://esolangs.org/wiki/Streetcode>`_ never spells out "drive on the
right-hand side" or its leftmost/second-leftmost "ambiguous turn" rule, so
the movement interpretation lives there with the wiki examples
corroborating each rule.

Movement is pure and module-level; the run is mutable and lives in
:class:`_Machine`.  :func:`_drive` is the whole of movement in one
signature, ``_drive(grid, state, arrival_cell, current_cell)``, which is
what lets :meth:`_Machine._drive_states` enumerate the state space.

Errors: a malformed program raises :class:`ValueError` at construction
(streets two wide, road enclosed, wall forms, no ``-`` beside ``|``, one
network, exactly one ``C``); a ``U`` with no opposite lane raises
:class:`~esolangs.exceptions.HaltError`.  ``_`` at cell 0 clamps (the wiki
says nothing; brainfuck clamps ``<``); ``O`` on a non-code-point raises
``HaltError``.  ``I`` on exhausted input raises :class:`EOFError`; an
empty line sets the cell to 0.
"""

import functools
import sys
from collections.abc import Callable, Iterator, Mapping
from typing import Literal, NamedTuple, NewType, assert_never, cast

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import IO

# The alphabet a wall form is written in: ``?`` matches any cell, ``W`` a
# wall character, ``.`` a non-wall.  Naming the three lets the checker see
# :func:`_matches` handles every one.
_Pattern = Literal["?", "W", "."]

# The four compass headings.  Named so a heading stays distinct from the
# cell characters and form patterns that are also plain strings.
_Heading = Literal["N", "E", "S", "W"]

# How many roads the drawn shape offers, counting the one the car came in
# on, or 0 for no junction.  Only 0, 3 and 4 are reachable -- a "two-way
# junction" is a corridor, a five-way needs a fifth direction.  Plain ints
# rather than an enum: ``_junction_kind`` is used as a truth value.
_Junction = Literal[0, 3, 4]

# Which way a merge latch turns, relative to the heading it was taken
# under.  Straight and reverse are unreachable, not merely unobserved --
# see ``the implementation``.
_Turn = Literal["left", "right"]


class _Mouth(NamedTuple):
    """A road mouth as :func:`_road_mouth` measured it.

    Named fields keep ``near`` and ``far`` from being read in the wrong order.
    """

    # Perpendicular distance from the car to the wall carrying the mouth.
    dist: int
    # Depth along the direction of travel of the ``+`` nearer the car.
    near: int
    # Depth along the direction of travel of the ``+`` further along.
    far: int

    @property
    def width(self) -> int:
        """How many open cells the gap between the two ``+`` spans."""
        return self.far - self.near - 1


class _Merge(NamedTuple):
    """An in-progress lane merge, latched until the car reaches ``target``.

    Holds *which way* it turns, not the heading, so the two direction
    fields cannot be built swapped; :attr:`new_heading` recovers it.
    """

    # The cell the car must reach before the turn is made.
    target_row: int
    target_col: int
    # Which way it turns there, relative to ``latched_heading``.
    turn: _Turn
    # The heading the latch was taken under; a turn in between voids it.
    latched_heading: _Heading
    # Whether the latch came from a crossing mouth, which decides whether
    # the branch condition is re-read on arrival.
    crossing: bool

    @property
    def target(self) -> tuple[int, int]:
        """The cell the car is driving to, as a coordinate pair."""
        return self.target_row, self.target_col

    @property
    def new_heading(self) -> _Heading:
        """The heading the car will take at ``target``."""
        return (
            _left(self.latched_heading)
            if self.turn == "left"
            else _right(self.latched_heading)
        )


class _Latches(NamedTuple):
    """The three values :func:`_choose_heading` carries between steps.

    One record so the machine, :meth:`_Machine.snapshot` and the drive-state
    search share one field order, and each steering phase is a function
    from latches to latches (see :class:`_Steer`).
    """

    # Set when a junction turn is detected but not yet reached (phase 1).
    merge: "_Merge | None"
    # Set after that turn, while the new road's right-hand wall has not
    # yet picked up (phase 2).
    merging_heading: _Heading | None
    # Steps of ordinary right-hand hugging still to be suppressed.
    skip_hug: int


class _State(NamedTuple):
    """The movement half of a machine's state.

    Tape, CP and I/O are absent: they do not steer, and leaving them out
    makes the state space finite (see ``_Machine._drive_states``).  A
    NamedTuple so graph keys and successors are hashable and named.
    """

    row: int
    col: int
    heading: _Heading
    latches: _Latches

    @property
    def car(self) -> "_Car":
        """Return the car half of the state, for the rules that only steer."""
        return _Car(self.row, self.col, self.heading)


# An open cell ``_validate_width``'s flood fill reached; ``_validate_enclosed``
# proves none is on the border, so ``_block``'s unchecked 3x3 read is
# reachable only from cells carrying that proof (mypy refuses a plain
# coordinate).  Reads further out go through ``_at``'s ``'?'`` sentinel.
_ReachableCell = NewType("_ReachableCell", tuple[int, int])
# The car stops here on purpose: the square is ``;``.  Distinct from the
# ``None`` a probe returns when the rules run out of road, which is a
# malformed street ``_validate_total`` rejects at construction -- keeping
# them apart lets :meth:`_Machine.step` treat a surviving ``None`` as the
# validator bug it would have to be rather than halting quietly.
_Halt = Literal["halt"]
# A state's successors, keyed by the two branch bits movement can read in
# one step: the arrival cell and the post-instruction cell, in that order.
_Edges = dict[tuple[int, int], "_State | _Halt | None"]

# No merge in progress and nothing to suppress: the latches a car starts
# with and is reset to when a ``U`` clears them, named so the reset is one
# value rather than three assignments that have to agree.
_NO_LATCHES = _Latches(merge=None, merging_heading=None, skip_hug=0)

_HEADINGS: tuple[_Heading, ...] = ("N", "E", "S", "W")
_DELTA: dict[_Heading, tuple[int, int]] = {
    "N": (-1, 0),
    "E": (0, 1),
    "S": (1, 0),
    "W": (0, -1),
}
_WALLS = frozenset("+-|")

# What a read off the edge of the drawing returns: not a wall, so the form,
# glyph and mouth scans see nothing rather than a phantom one, and not any
# glyph a program can contain.  ``_Grid.open_at`` tests the bounds itself,
# since off the grid is not drivable either.
_VOID = "?"

# Closed set: every glyph maps here or to ``NOP``, so :meth:`_Machine.step`
# is exhaustive.  Cells keep the glyph as drawn (``_validate_connected``
# names stray ink): ``#`` on the street is a no-op, beside it malformed.
_Op = Literal["NOP", "INC", "DEC", "RIGHT", "LEFT", "IN", "OUT", "TURN", "HALT"]

# The spec's instruction glyphs, keyed by the glyph.  Anything absent is
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

# How far perpendicular to travel ``_road_mouth`` looks for the wall a side
# road opens through: a two-way street is two cells wide, so the far lane's
# wall can sit two cells out, and 3 covers that with a cell to spare.
_MOUTH_MAX_DIST = 3

# How far along travel ``_road_mouth`` looks for the ``+`` closing a road's
# mouth.  Swept against the suite, the floor is 5 (at 4 the wider junctions'
# mouths stop being seen); 7 is that plus slack.  Raising it is not
# conservatively safer -- the bound is two-sided, since too high a scan runs
# past the box and pairs up two ``+`` that bound nothing.
_MOUTH_MAX_DEPTH = 7


def _rotate(form: tuple[_Pattern, ...]) -> tuple[_Pattern, ...]:
    """Rotate a three-by-three form a quarter turn clockwise."""
    return tuple(form[i] for i in (6, 3, 0, 7, 4, 1, 8, 5, 2))


# The pattern alphabet keyed by its own spelling, so a written form is
# validated into _Pattern characters rather than asserted to be them.
_PATTERNS: dict[str, _Pattern] = {"?": "?", "W": "W", ".": "."}


def _rotations(form: str) -> list[tuple[_Pattern, ...]]:
    """Return the four rotations of a nine-character form."""
    out, cur = [], tuple(_PATTERNS[c] for c in form)
    for _ in range(4):
        cur = _rotate(cur)
        out.append(cur)
    return out


# Legal 3x3 forms (row-major) around a drivable cell, up to rotation:
# ``W`` any wall, ``.`` open, ``?`` anything.  The corner is ``W``, not
# ``+-|``, so one form covers outer, inner and flush corners.
_WALL_FORMS = [
    *_rotations("?W?W..?.."),  # corner
    *_rotations("?W?......"),  # wall
    *_rotations("W........"),  # intersection
]


def _matches(block: tuple[str, ...], form: tuple[_Pattern, ...]) -> bool:
    """Whether a three-by-three neighbourhood matches one form."""
    for actual, want in zip(block, form, strict=True):
        if want == "?":
            continue
        if want == "W":
            if actual not in _WALLS:
                return False
        # ``want`` is "." here: the alphabet has no fourth character, so
        # there is nothing left to fall through to.
        elif actual in _WALLS:
            return False
    return True


def _require(*, condition: bool, message: str) -> None:
    """Raise when an invariant this module relies on does not hold.

    A failure here says the *interpreter* is wrong, unlike the validators'
    ``ValueError``.  Not an ``assert``: bandit rejects those in ``src``
    (B101), and ``python -O`` would drop it.
    """
    if not condition:
        raise AssertionError(message)


class _Grid:
    """The program's characters, addressable at any coordinate at all.

    Reads are total: off the drawing returns :data:`_VOID`, its own
    character because off-grid has two meanings no real one serves --
    :meth:`open_at` treats it as *closed*, the wall forms and mouth scans
    as matching *nothing* (a ``+`` border would sight junctions never
    drawn).  Rows stay assignable for fixtures (``grid[1] = "|C   |"``).
    """

    __slots__ = ("_geometry", "_rows", "height", "width")

    def __init__(self, rows: list[str]) -> None:
        """Square the drawing off, so every row is ``width`` characters."""
        self.width = max(len(row) for row in rows)
        self._rows = [row.ljust(self.width) for row in rows]
        self.height = len(self._rows)
        # Memo shared by the geometry rules (see :func:`_geometric`).  The
        # drawing is fixed for a run, and the rules are asked a lot: over
        # ``tests/fixtures/streetcode_hello.txt`` they run 3242/12734/5864
        # times from only 727/1235/702 distinct states.  ``__setitem__``
        # clears it, since a redrawn row is a different drawing.
        self._geometry: dict[tuple[str, tuple[object, ...]], object] = {}

    @property
    def geometry(self) -> dict[tuple[str, tuple[object, ...]], object]:
        """The memo :func:`_geometric` keeps for the rules about this grid.

        Exposed because the rules are module-level and cannot touch a
        private attribute without tripping the linter.
        """
        return self._geometry

    def __getitem__(self, where: int | tuple[int, int]) -> str:
        """Return a whole row by index, or one character by coordinate.

        The coordinate read is total; :meth:`open_at` is the one read
        treating off-grid as closed.
        """
        # The coordinate read is the hottest call in loading a drawing, so
        # it is tested first and with ``type`` rather than ``isinstance``.
        # The bounds are the grid's ``height``/``width``, not the row's
        # length: a short row reads as blank to its right.
        if type(where) is tuple:
            row, col = where
            if not (0 <= row < self.height and 0 <= col < self.width):
                return _VOID
            return self._rows[row][col]
        return self._rows[cast("int", where)]

    def __setitem__(self, row: int, value: str) -> None:
        """Redraw one row, for the fixtures that build geometry by hand.

        Drops the geometry memo: a redrawn row is a different drawing.
        """
        self._rows[row] = "".join(value).ljust(self.width)
        self._geometry.clear()

    def __iter__(self) -> Iterator[str]:
        """Iterate the rows, so the drawing can be scanned as text."""
        return iter(self._rows)

    def open_at(self, row: int, col: int) -> bool:
        """Whether ``(row, col)`` is drivable: on the grid and not a wall.

        Off-grid is explicitly closed, the opposite of a non-wall character.
        """
        if not (0 <= row < self.height and 0 <= col < self.width):
            return False
        return self._rows[row][col] not in _WALLS

    def op_at(self, row: int, col: int) -> _Op:
        """Return what the square at ``(row, col)`` does when the car runs it.

        Walls, the void and anything the spec does not define fold to
        ``"NOP"``; see ``_Op``.
        """
        char = self[row, col]
        if char in _WALLS or char == _VOID:
            return "NOP"
        return _OPS.get(char, "NOP")


def _right(heading: _Heading) -> _Heading:
    """Return the heading 90 degrees clockwise from ``heading``."""
    return _HEADINGS[(_HEADINGS.index(heading) + 1) % 4]


def _left(heading: _Heading) -> _Heading:
    """Return the heading 90 degrees counter-clockwise from ``heading``."""
    return _HEADINGS[(_HEADINGS.index(heading) - 1) % 4]


def _drives_on_the_right(grid: _Grid, state: _State) -> bool:
    """Whether a car in ``state`` is on the right-hand side of its street.

    A lane is the car's own when the wall it hugs is on its *right*.  The
    drive-state search probes both branch conditions, so it reaches
    wrong-side successors a real run never does; those have no successor
    and looked like the wedged streets :meth:`_Machine._validate_total`
    rejects, refusing correct programs with tightly drawn lanes.  Walls on
    both sides or neither is not a violation.
    """
    car = _Car(state.row, state.col, state.heading)
    open_right = _open_toward(grid, car, _right(state.heading))
    open_left = _open_toward(grid, car, _left(state.heading))
    return not (open_right and not open_left)


def _opposite(heading: _Heading) -> _Heading:
    """Return the heading 180 degrees from ``heading``."""
    return _HEADINGS[(_HEADINGS.index(heading) + 2) % 4]


def _turn_of(heading: _Heading, new_heading: _Heading) -> _Turn:
    """Classify ``heading`` -> ``new_heading`` as a left or a right turn.

    Raises on straight or reverse: only the two turns can be latched (see
    :data:`_Turn`), and a silent "right" would steer into a wall later.
    """
    if new_heading == _left(heading):
        return "left"
    if new_heading == _right(heading):
        return "right"
    raise AssertionError(
        f"{heading} -> {new_heading} is neither a left nor a right turn:"
        " a merge latch is only ever set for a turn onto a side road"
    )


class _Car(NamedTuple):
    """Where the car is and which way it points.

    The rules ask their questions *from* a car, so one can be called on a
    hypothetical car without moving the real one.
    """

    row: int
    col: int
    heading: _Heading

    @property
    def at(self) -> tuple[int, int]:
        """The cell the car occupies, as a coordinate pair."""
        return self.row, self.col

    def ahead(self, heading: _Heading | None = None) -> tuple[int, int]:
        """Return the cell one step along ``heading``, or the car's own way."""
        d_row, d_col = _DELTA[self.heading if heading is None else heading]
        return self.row + d_row, self.col + d_col

    def facing(self, heading: _Heading) -> "_Car":
        """Return the same position under a new heading."""
        return _Car(self.row, self.col, heading)


def _ahead(row: int, col: int, heading: _Heading) -> tuple[int, int]:
    """Return the cell one step from ``(row, col)`` along ``heading``."""
    d_row, d_col = _DELTA[heading]
    return row + d_row, col + d_col


def _geometric[Answer](rule: Callable[..., Answer]) -> Callable[..., Answer]:
    """Memoize a geometry ``rule`` on the grid it is asked about.

    The rules read only the drawing, a :class:`_Car` and plain values, and
    the four steering phases re-derive the shape from scratch each step.
    The grid owns the memo, so a redrawn row drops it; the key includes
    the rule's name.
    """
    # Bound once at decoration: reading it off the function per call was an
    # attribute lookup per memo probe, and these are probed hundreds of
    # thousands of times per load.
    name = rule.__name__

    @functools.wraps(rule)
    def cached(grid: _Grid, *args: object) -> Answer:
        key = (name, args)
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
    """Whether the cell one step from ``car`` along ``heading`` is open."""
    return grid.open_at(*car.ahead(heading))


def _initial_heading(grid: _Grid, start: tuple[int, int]) -> _Heading:
    """Pick the heading consistent with hugging the wall at ``C``.

    Whichever direction has a wall to its right and open ground ahead.
    """
    row, col = start
    for heading in _HEADINGS:
        if grid.open_at(*_ahead(row, col, _right(heading))):
            continue
        if grid.open_at(*_ahead(row, col, heading)):
            return heading
    # No heading has both a wall on the right and open ground ahead
    # (e.g. an isolated cell): fall back to South, matching the halt
    # this program will hit on its very first movement attempt anyway.
    return "S"


@_geometric
def _road_mouth(grid: _Grid, car: _Car, side: _Heading) -> _Mouth | None:
    """Detect a road opening off ``side`` of ``car``, or ``None``.

    A branch is a gap in the wall along ``side`` with a ``+`` at each end
    and open floor strictly between them; a gap between plain ``-``/``|``
    runs is an undrawn wall, not a junction.  The near ``+`` is anchored at
    depth 0, 1 or -1 (the car may corner straight into a mouth), so the
    junction fires as the car *arrives*.  Returns ``(dist, near_depth,
    far_depth)``.
    """
    d_row, d_col = _DELTA[car.heading]
    s_row, s_col = _DELTA[side]

    def pos(depth: int, dist: int) -> tuple[int, int]:
        """Locate a cell ``depth`` along the heading and ``dist`` along ``side``."""
        return (
            car.row + depth * d_row + dist * s_row,
            car.col + depth * d_col + dist * s_col,
        )

    for dist in range(1, _MOUTH_MAX_DIST + 1):
        # Level with the near edge, or the hug drags the car into a turn
        # it declined; ``near`` may be one behind, level, or one ahead.
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
            # The wall the car drives along, carrying no mouth it could
            # turn into.  Anything further out sits behind it, so a `+`
            # pair sighted through solid wall is another corridor's
            # geometry and would fire in the middle of an ordinary bend.
            return None
    return None


@_geometric
def _plus_dist(grid: _Grid, car: _Car, side: _Heading) -> int | None:
    """Return the distance to the nearest ``+`` on ``side``, or ``None``.

    Scans ``1.._MOUTH_MAX_DIST`` cells out; :func:`_crossing_mouth` uses it.
    """
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
    """Whether the car is driving *out through* a side road's mouth.

    The junction :func:`_road_mouth` sees as a gap to one side is, up the
    branch, a pass *between* the two ``+``: detected as a ``+`` on each
    side at matching depth and different distances, with open ground ahead.
    """
    if not _open_toward(grid, car, car.heading):
        return False
    # Level with both `+` -- one step further and they are behind the car,
    # one step earlier and it has not reached the intersection yet.
    left = _plus_dist(grid, car, _left(car.heading))
    right = _plus_dist(grid, car, _right(car.heading))
    return left is not None and right is not None and left != right


@_geometric
def _junction_kind(grid: _Grid, car: _Car) -> _Junction:
    """Detect a real intersection ahead, returning the open-option count.

    A road mouth off either side, counted with straight ahead: 3 or 4
    roads, or 0 for a corner or straight stretch.  Both wiki junction
    examples detect (infinite-loop at ``(1,3)`` W, infinite-cat at
    ``(1,4)`` W, ten firing states each) and every one is a three-way;
    no cell of either grid answers 4, so the four-way arm is a convention
    (``docs/limitations.md``).
    """
    kind = _junction_shape(grid, car)
    # A drawn junction is only a choice when at least two of its roads are
    # ones the car could drive down (see :func:`_road_deep`); otherwise the
    # shape is a bend or a lane boundary, and wall-following handles it.
    return kind if len(_junction_choices(grid, car)) >= 2 else 0


@_geometric
def _junction_shape(grid: _Grid, car: _Car) -> _Junction:
    """Classify the wall shape alone, before the roads are counted."""
    heading = car.heading
    ahead_open = _open_toward(grid, car, heading)
    left_mouth = _road_mouth(grid, car, _left(heading)) is not None
    right_mouth = _road_mouth(grid, car, _right(heading)) is not None
    # Counting the road behind the car, a branch to one side with open
    # road ahead is a three-way; branches to both sides make a four-way
    # when it can also continue straight, and a T's crossbar when not.
    if left_mouth and right_mouth:
        return 4 if ahead_open else 3
    if left_mouth or right_mouth:
        return 3 if ahead_open else 0
    # Met head-on -- the car is driving out through the mouth itself
    # rather than past it (see :func:`_crossing_mouth`).
    return 3 if _crossing_mouth(grid, car) else 0


def _lane_bounded(grid: _Grid, car: _Car, side: _Heading, mouth: _Mouth) -> bool:
    """Whether ``mouth`` bounds a genuinely multi-lane road.

    When the mouth's ``+`` continue into wall arms one cell further out,
    the side road has lanes and the car merges instead of turning at once.
    """
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
    """Return the cell the car must reach before turning to ``new_heading``.

    The lane adjacent to the side road's right-hand wall relative to
    ``new_heading``, at depths ``near + 1 .. far - 1``; the car does not
    change lane on the approach.
    """
    near, far = mouth.near, mouth.far
    d_row, d_col = _DELTA[car.heading]
    depth = far - 1 if _right(new_heading) == car.heading else near + 1
    # d_row/d_col is a unit vector with exactly one nonzero component;
    # that component picks out the travel-axis coordinate to advance,
    # while the perpendicular coordinate stays fixed at the car's own.
    if d_row:
        return car.row + depth * d_row, car.col
    return car.row, car.col + depth * d_col


@_geometric
def _junction_choices(grid: _Grid, car: _Car) -> list[_Heading]:
    """Return the roads a junction offers, in the spec's choice order.

    Only a detected mouth counts as a turn (an open cell with no drawn
    mouth consumes no slot), ordered left to right as the driver sees them.
    """
    heading = car.heading
    roads = []
    crossing = _crossing_mouth(grid, car)
    # Defer until the open sides are the road being joined, or a side road
    # not yet drivable fills its slot with the oncoming lane.
    if crossing:
        for side in (_left(heading), _right(heading)):
            if _road_mouth(grid, car, side) is not None and not _open_toward(
                grid, car, side
            ):
                return []
    for side in (_left(heading), heading, _right(heading)):
        if crossing:
            # Driving out through a mouth head-on, the sides are the main
            # road the branch joins.  It runs perpendicular, so its extent
            # cannot be probed from inside the mouth (two cells out hits
            # its far wall): take whichever way is open.
            if _open_toward(grid, car, side):
                roads.append(side)
        elif _road_deep(grid, car, side) and _lawful_turn(grid, car, side):
            roads.append(side)
    return roads


def _road_deep(grid: _Grid, car: _Car, heading: _Heading) -> bool:
    """Whether ``heading`` leads onto a road, rather than across one.

    Two drivable cells are required: a single open cell before a wall is
    the street the car is already on.
    """
    d_row, d_col = _DELTA[heading]
    return grid.open_at(car.row + d_row, car.col + d_col) and grid.open_at(
        car.row + 2 * d_row, car.col + 2 * d_col
    )


def _lawful_turn(grid: _Grid, car: _Car, heading: _Heading) -> bool:
    """Whether entering ``heading`` leaves the car driving on the right.

    Open ground right and a wall left is the oncoming lane, not a road the
    junction may offer; walls on neither side is left to the ordinary rules.
    """
    row, col = car.ahead(heading)
    wrong_side = grid.open_at(*_ahead(row, col, _right(heading))) and not grid.open_at(
        *_ahead(row, col, _left(heading))
    )
    return not wrong_side


class _Steer(NamedTuple):
    """What a steering phase decided: a heading, and the latches after it.

    ``None`` for the heading is a phase declining; it may still change the
    latches (an abandoned merge), hence ``(None, latches)``.
    """

    heading: _Heading
    latches: _Latches


# What one phase answers before ``_choose_heading`` sorts it out.  Not a
# ``_Steer | None`` because a declining phase may still have written a latch
# off (a merge abandoned mid-approach), and that write must survive.
_Phase = tuple["_Heading | None", _Latches]


def _heading_leaving_merge(grid: _Grid, car: _Car, latches: _Latches) -> _Phase:
    """Phase 2 of a merge: hold straight until the new wall picks up.

    Keep going while right and ahead are open; either closing ends the latch.
    """
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
    """Phase 1 of a merge: drive to the latched lane, then turn.

    ``None`` once the latch is spent or abandoned.
    """
    merge = latches.merge
    if merge is None:
        return None, latches
    new_heading = merge.new_heading
    heading = car.heading
    # A 'U' during the approach turns the car around, so the latch must not
    # wait forever for a cell it no longer visits -- that would disable
    # junction detection for the rest of the run.
    if heading != merge.latched_heading:
        return None, latches._replace(merge=None)
    if car.at != merge.target:
        # Still approaching the lane where the turn will be made.  Hold
        # the latched heading: the road being joined is open on that side
        # by definition, so an ordinary hug would turn early and never
        # reach the target.
        if _open_toward(grid, car, heading):
            return heading, latches
        return None, latches._replace(merge=None)

    latches = latches._replace(merge=None)
    # Re-read from ``arrival_cell`` (an ``I``/``=`` on the approach changes
    # the CPth cell; a turning square's own setup is not the decision).
    # Side mouths only: a ``^`` on a crossing's run out must not overturn it.
    if not merge.crossing:
        # Left-to-right as the driver sees it: a left turn before carrying
        # straight on, a right turn after.  Read off the latch rather than
        # recomputed from the headings, so the re-read cannot disagree with
        # the original choice about which road is "leftmost".
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
    """Apply the spec's ambiguous-turn rule at a detected intersection.

    ``None`` when no junction fires or the turn is deferred until level with
    the mouth.  ``current_cell`` is the CPth cell *after* this square's
    instruction, unlike phase 1's arrival read.
    """
    heading = car.heading
    order = [_left(heading), heading, _right(heading)]
    options = [h for h in order if _open_toward(grid, car, h)]
    if len(options) < 2 or not _junction_kind(grid, car):
        return None, latches

    roads = _junction_choices(grid, car)
    # A junction that fired always offers at least two roads.
    new_heading = roads[0] if current_cell == 0 else roads[1]
    turning = new_heading != heading
    # Nothing deferred: every offered road passed ``_road_deep`` (whose
    # first test is the destination cell -- keep it, or a junction fires
    # early into the wall) or ``_open_toward``.  Lane merging is for turns
    # onto a detected side road only.
    if turning and _crossing_mouth(grid, car):
        # Emerging head-on from a branch onto the road it joins: cross to
        # the far lane before turning, since "drive on the right-hand
        # side" applies to the road being joined too.
        target = car.at
        d_row, d_col = _DELTA[heading]
        while grid.open_at(target[0] + d_row, target[1] + d_col):
            target = target[0] + d_row, target[1] + d_col
        # ``_crossing_mouth`` guarantees the cell ahead is open, so the
        # loop always advances at least one cell.
        return None, latches._replace(
            merge=_Merge(
                target_row=target[0],
                target_col=target[1],
                turn=_turn_of(heading, new_heading),
                latched_heading=heading,
                crossing=True,
            )
        )
    # Looked up once and handed to both helpers, rather than each
    # re-finding it and guarding against a miss the other ruled out.
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
        # Suppress the hug for exactly the mouth's width past a declined
        # side road (no further: the next corner must still happen).  Only
        # ever extended; one mouth is detected from several cells.
        declined = [h for h in roads if h != heading]
        mouth = _road_mouth(grid, car, declined[0])
        if mouth is not None and mouth.near <= 0:
            # Only when the gap opens immediately beside the car
            # (``near <= 0``), where the fallen-away wall would otherwise
            # steer it into the declined road.  A gap further ahead needs
            # no suppression: wall-following holds the car until it
            # arrives, by which point the junction is behind it.
            latches = latches._replace(skip_hug=max(latches.skip_hug, mouth.width))
    return new_heading, latches


def _heading_from_hug(grid: _Grid, car: _Car, latches: _Latches) -> _Phase:
    """Ordinary right-hand wall-following, the default movement rule."""
    heading = car.heading
    if latches.skip_hug > 0:
        # Drive past the declined branch rather than hugging the wall that
        # has fallen away.  A wall straight ahead still turns the car --
        # rounding a corner is not being pulled into the declined road --
        # but the countdown carries on so the rest of the mouth is skipped.
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
    """Pick the car's next heading, and the latches it carries onward.

    Four phases, each a heading or ``None``: leaving a merge, approaching
    a latched target, deciding a junction, hugging the wall.  Latches are
    abandoned when the approach stops matching.  ``arrival_cell`` (the
    merge re-read) and ``current_cell`` (the junction rule) are the only
    tape reads movement makes, so the drive-state graph tries both bits.
    ``None`` overall means the car ran out of road.
    """
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
    """Return the state one step on from ``state``, or why there is none.

    The whole movement semantics; pure, so :meth:`_Machine._drive_states`
    can enumerate it and :meth:`_Machine.step` replay it.  ``;`` is
    ``"halt"``; ``U`` reverses into the lane now on the right and clears
    every latch.  ``None`` is running out of road (a wedged street, which
    :meth:`_Machine._validate_total` rejects), deliberately not ``"halt"``.
    Value-dependent halts stay in :meth:`_Machine.step`.
    """
    car = state.car
    op = grid.op_at(car.row, car.col)
    if op == "HALT":
        return "halt"
    if op == "TURN":
        reversed_car = car.facing(_opposite(car.heading))
        lane = reversed_car.ahead(_right(reversed_car.heading))
        # A street with no opposite lane is the late-detected width
        # violation ``step`` raises ``HaltError`` for.
        if not grid.open_at(*lane):
            return None
        # A 'U' clears the latches, the same reset ``step`` applies.
        return _State(*lane, reversed_car.heading, _NO_LATCHES)

    steer = _choose_heading(grid, car, state.latches, arrival_cell, current_cell)
    if steer is None:
        return None
    return _State(*car.ahead(steer.heading), steer.heading, steer.latches)


class _Machine:
    """Per-run Streetcode state: the car, its heading, and the cell list.

    ``step()`` runs the cell under the car, then drives one cell by the
    rules in ``the implementation``; ``halted`` once ``;`` runs or the car
    has nowhere to go.  The only mutable thing in the module: the rules
    return a new :class:`_State`, and ``step`` stores what comes back.
    """

    def __init__(self, code: list[str], io: IO) -> None:
        """Locate the single ``C`` and derive the car's initial heading."""
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
        # The whole of the machine's steering state, in the one record the
        # movement rules speak in.  ``step`` hands it to :func:`_drive` and
        # stores back what comes out, so the value looked up in the
        # drive-state graph is the machine's own.  See :class:`_Latches`
        # for what the three latches carry.
        self._state = _State(
            *starts[0], _initial_heading(self.grid, starts[0]), _NO_LATCHES
        )
        self.cp = 0
        # The tape, as a value: an instruction returns the cells that
        # follow rather than writing into a dict.  It is bounded by how far
        # CP has travelled, which grows one cell at a time, so rebuilding
        # it per write is a constant.
        self.cells: Mapping[int, int] = {}
        self._done = False
        # The enumerated drive-state graph, or ``None`` for a program whose
        # geometry is not a street or whose validation a fixture patched
        # out.  ``step`` then calls :func:`_drive` directly -- the same
        # function that filled the graph, so the answer is the same.
        self._graph: dict[_State, _Edges] | None = None
        # Last, because ``_validate_total`` drives the real movement rules
        # over the grid and so needs every field they touch to exist.
        self._validate(starts[0])

    @property
    def halted(self) -> bool:
        """Whether the car has halted."""
        return self._done

    # The VM's language-shaped view.

    #: The first two parts of ``ip`` are a row and a column, the rest a
    #: heading.  Without this a caller cannot tell the pair from a call
    #: depth or a frame stack, which look identical.
    ip_shape = "grid"

    @property
    def ip(self) -> tuple[int, ...]:
        """The car's ``(row, col, heading)``, heading as its index in ``NESW``."""
        return (self.row, self.col, "NESW".index(self.heading))

    @property
    def memory(self) -> list[int]:
        """The tape's cells, densified up to the highest cell touched."""
        cells = self.cells
        if not cells:
            return []
        return [cells.get(i, 0) for i in range(max(cells) + 1)]

    @property
    def stack(self) -> list[object]:
        """No stack in this language."""
        return []

    # Read-only views onto the one record that holds the car: a caller
    # that wants to *move* it states the whole position at once through
    # :meth:`place`, so the three coordinates cannot come from two places.

    @property
    def row(self) -> int:
        """The row the car occupies."""
        return self._state.row

    @property
    def col(self) -> int:
        """The column the car occupies."""
        return self._state.col

    @property
    def heading(self) -> _Heading:
        """The direction the car points."""
        return self._state.heading

    def place(self, row: int, col: int, heading: _Heading) -> None:
        """Put the car at ``(row, col)`` pointing ``heading``.

        For fixtures that drive from somewhere other than ``C``.  Latches
        are left alone: a test placing a car *and* setting up a merge wants both.
        """
        self._state = self._state._replace(row=row, col=col, heading=heading)

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection.

        ``_done`` matters: ``;`` halts without moving, so without it the
        halt looks like a repeat of the step before.
        """
        return (
            self._state,
            self.cp,
            tuple(sorted(self.cells.items())),
            self.io.position(),
            self._done,
        )

    def _cell(self) -> int:
        """Return the CPth cell's value, defaulting to 0 if untouched."""
        return self.cells.get(self.cp, 0)

    def _set_cell(self, value: int) -> None:
        """Write the CPth cell, replacing the tape rather than editing it."""
        self.cells = {**self.cells, self.cp: value}

    def _block(self, cell: _ReachableCell) -> tuple[str, ...]:
        """Return the three-by-three neighbourhood around a reachable cell.

        Not bounds-checked: :meth:`_validate_enclosed` has rejected any
        road touching the border, and the precondition states that.
        """
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
        """Reject a malformed street network before the car moves.

        :meth:`_validate_width` and :meth:`_validate_walls` over the cells
        reachable from ``C``; the one hook the wall-shape fixtures disable.
        """
        reachable = self._validate_width(start)
        if reachable is not None:
            self._validate_enclosed(reachable)
            self._validate_walls(reachable)
            self._validate_glyphs()
            self._validate_connected(reachable)
            self._validate_total(start)

    def _drive_states(self, start: tuple[int, int]) -> dict[_State, _Edges]:
        """Explore every driving state the car can reach from ``start``.

        Kept as ``_graph`` for :meth:`_validate_total` and :meth:`step`.
        A state is position, heading and latches; geometry is static, so
        the BFS terminates.  Movement reads the tape at exactly two places,
        both testing ``== 0`` (:func:`_heading_from_merge_target` on the
        arrival cell, :func:`_heading_from_junction` on the current one),
        so probing all four bit combinations is exhaustive, not a sample.
        A ``None`` successor is a state the car cannot leave.
        """
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
        """Reject a street the car can drive into and not out of.

        Only ``;`` halts a well-formed program, so a reachable state with
        no successor is a wedged street, named here.  Hugging is total by
        construction, so today this rejects only a reachable ``U`` with a
        walled opposite lane (``HaltError`` promoted to ``ValueError``);
        137472 small walled grids found none only this check rejects.
        """
        self._graph = self._drive_states(start)
        for state, edges in self._graph.items():
            # ``;`` reports ``"halt"`` rather than ``None``, so ``None``
            # means only the one thing.
            if any(successor is None for successor in edges.values()):
                raise ValueError(
                    f"the car cannot drive out of {(state.row, state.col)} heading"
                    f" {state.heading}: the street is a dead end with no ';'"
                )
            self._check_state_invariants(state, edges)

    def _check_state_invariants(self, state: _State, edges: _Edges) -> None:
        """Assert what must hold of a drive state under any reading of the spec.

        A car inside a wall, or one that teleports, is wrong under every
        reading (a junction firing a cell early once drove the car inside
        the wall).  :class:`AssertionError`, not ``ValueError``: a breach is
        the movement rules disagreeing with the grid.
        """
        if not self.grid.open_at(state.row, state.col):
            raise AssertionError(
                f"the car occupies {(state.row, state.col)}, which is not"
                f" open floor: {self.grid[state.row, state.col]!r}"
            )
        for successor in edges.values():
            if successor is None or successor == "halt":
                continue
            # A step drives one cell along one axis.  Anything else is the
            # car teleporting, which no movement rule is allowed to do.
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
        # A latch whose heading no longer matches is abandoned on the next
        # step, so its target is stale and describes no geometry.
        if merge is None or state.heading != merge.latched_heading:
            return
        if not self.grid.open_at(merge.target_row, merge.target_col):
            raise AssertionError(
                f"the merge latched at {(state.row, state.col)} is driving to"
                f" {merge.target}, which is not open floor:"
                f" {self.grid[merge.target_row, merge.target_col]!r}"
            )
        # The approach does not change lane, so the target sits straight
        # ahead along the latched heading -- never to one side, never
        # behind a car that can only drive forwards onto it.
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
        """Validate that every street is two characters wide.

        A corridor cell with open neighbours directly opposite, or a dead
        end, must have an open perpendicular neighbour; isolated cells and
        wall-free grids are exempt, and a blank row is a lane.  The upper
        bound is a fully open 3x3 block, which a two-wide network never
        contains (a cross-section run through a crossing reports the other
        street's length).  A 3x2 room passes, deliberately.
        """
        # No walls → not a street network (e.g. ["C","U"] or ["C"])
        if not any(ch in _WALLS for row in self.grid for ch in row):
            return None
        # BFS reachable open cells from C (open = not a wall)
        from collections import deque

        sr, sc = start
        visited: set[_ReachableCell] = set()
        q: deque[_ReachableCell] = deque([_ReachableCell((sr, sc))])
        visited.add(_ReachableCell((sr, sc)))
        while q:
            r, c = q.popleft()
            for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                nr, nc = r + dr, c + dc
                # No bounds test: off the grid is not open, so the fill
                # cannot walk out of the drawing.
                if self.grid.open_at(nr, nc) and (nr, nc) not in visited:
                    visited.add(_ReachableCell((nr, nc)))
                    q.append(_ReachableCell((nr, nc)))
        # Isolated single cell is not a street
        if len(visited) <= 1:
            return None
        violation = self._width_violation(visited)
        if violation is not None:
            raise ValueError(violation)
        return visited

    def _width_violation(self, reachable: set[_ReachableCell]) -> str | None:
        """Name a cell breaking the two-wide rule, or ``None`` if none does.

        The rule as a value, so it can be asked without a second implementation.
        """
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
        """Validate the wall structure around every drivable cell.

        Width misses a one-cell hole (``-- --``); each reachable cell's 3x3
        must match ``_WALL_FORMS`` up to rotation.  The forms let a wall
        simply stop and admit any wall character at a corner -- whether a
        divider must end in ``+`` is unsettled, and
        ``tests/fixtures/streetcode_hello.txt`` leaves its ends bare.
        Must run after :meth:`_validate_enclosed`: :meth:`_block` does not
        bounds-check.
        """
        for cell in reachable:
            r, c = cell
            block = self._block(cell)
            # A street is two cells wide, so every reachable cell has a
            # wall within one; a wall-free neighbourhood is an interior
            # wider than two, already rejected by the width check.
            if not any(ch in _WALLS for ch in block):  # pragma: no cover
                continue
            # The two-wide check runs first and rejects every malformed
            # shape found so far; this stands as the independent check the
            # forms were written to be.
            if not any(  # pragma: no cover - the width check rejects these first
                _matches(block, form) for form in _WALL_FORMS
            ):
                shape = " ".join(
                    "".join("." if ch not in _WALLS else ch for ch in block[i : i + 3])
                    for i in (0, 3, 6)
                )
                raise ValueError(f"malformed wall at {(r, c)} ({shape})")

    def _validate_enclosed(self, reachable: set[_ReachableCell]) -> None:
        """Reject a street that runs off the edge of the grid.

        A flood fill from ``C`` reaching the border has escaped through a
        hole.  This is what catches a two-wide hole, which is legal-width
        passage the width check cannot see.
        """
        violation = self._enclosure_violation(reachable)
        if violation is not None:
            raise ValueError(violation)

    def _enclosure_violation(self, reachable: set[_ReachableCell]) -> str | None:
        """Name a road cell on the grid's border, or ``None`` if none is.

        The property :meth:`_block` depends on, stated once.
        """
        for r, c in reachable:
            if r in (0, self.grid.height - 1) or c in (0, self.grid.width - 1):
                return (
                    f"street reaches the edge of the grid at {(r, c)}:"
                    " the road is not enclosed by walls"
                )
        return None

    def _validate_glyphs(self) -> None:
        """Reject a ``-`` and a ``|`` drawn side by side.

        A wall changing direction without its ``+``.  About glyph choice,
        not wall placement, so the forms in :meth:`_validate_walls` cannot see it.
        """
        violation = self._glyph_violation()
        if violation is not None:
            raise ValueError(violation)

    def _glyph_violation(self) -> str | None:
        """Name a ``-`` drawn beside a ``|``, or ``None`` if none is."""
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
        """Reject geometry that is not part of the one street network.

        Grow the reachable open cells by one so the region takes in its
        walls; anything still drawn belongs to no street.  A one-thick
        island is taken in whole; only a block with an interior falls
        outside.  Blank cells are ignored (``ljust`` padding, the boolean
        example's margins).  Strict: any character off the street, not
        only walls -- stray marks are likelier a slip than a comment.
        """
        violation = self._connection_violation(reachable)
        if violation is not None:
            raise ValueError(violation)

    def _connection_violation(self, reachable: set[_ReachableCell]) -> str | None:
        """Name drawn geometry off the street, or ``None`` if none is."""
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
        """Execute the cell under the car, then drive it one cell further."""
        if self._done:
            return
        op = self.grid.op_at(self.row, self.col)
        if op == "HALT":
            self._done = True
            return

        # The driving state as the car arrives, for the graph lookup
        # below.  An instruction moves CP and the tape but never the car,
        # its heading or the latches, and ``U`` returns before the lookup.
        state = self._state

        # The cell on arrival, before this square's instruction, so a
        # turning square's ``=`` sets up the road ahead without deciding it.
        # Passed, not kept: it would look like snapshot state.
        arrival_cell = self._cell()

        if op == "INC":
            self._set_cell(self._cell() + 1)
        elif op == "DEC":
            self._set_cell(self._cell() - 1)
        elif op == "RIGHT":
            self.cp += 1
        elif op == "LEFT":
            # Clamped, not an error: an unsigned quantity that cannot go
            # lower saturates.  See the module docstring.
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
            # The U-turn ends in the lane now on the right; turning in
            # place leaves the car in the oncoming lane, where the hug's
            # two right turns cancel it.  Old-heading latches are void.
            # Via :func:`_drive` so the run and the graph agree; ``None``
            # (no opposite lane) is a malformed street.
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
            # ``C``, space and every undefined character fold to NOP (see
            # ``_Op``).  Spelled out rather than fallen through, so the
            # ``else`` below is the checker's exhaustiveness proof.
            pass
        else:
            # Unreachable, and checked to be: a glyph added to ``_Op``
            # without an arm here fails the type check rather than
            # silently behaving as a no-op.
            assert_never(op)

        # A memo of :func:`_drive` over every reachable state, keyed on the
        # two reads' zero-ness; a miss (non-street geometry, or a state the
        # search never enumerated) falls through to :func:`_drive` itself.
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
                # No graph vouched for this state, so running out of road
                # is the car's ordinary dead end: stop.
                self._done = True
                return
            # ``_validate_total`` rejects a wedged state, so reaching one
            # here means the graph and the validator disagree -- a bug in
            # this module.  Halting quietly would hand back a truncated
            # run as though it were the answer.
            raise AssertionError(
                f"no successor for {(self.row, self.col)} heading"
                f" {self.heading}: the drive-state graph outlived"
                " the totality check"
            )
        self._state = successor


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
