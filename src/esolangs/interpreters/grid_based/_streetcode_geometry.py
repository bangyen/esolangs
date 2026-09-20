"""Streetcode road geometry and pure driving rules."""

import functools
from collections.abc import Callable, Iterator
from typing import Literal, NamedTuple, NewType, cast

# Wall-form alphabet: ``?`` any, ``W`` wall, ``.`` non-wall.  Naming it makes
# :func:`_matches` exhaustiveness visible.
_Pattern = Literal["?", "W", "."]

# The four compass headings.  Named so a heading stays distinct from the
# cell characters and form patterns that are also plain strings.
_Heading = Literal["N", "E", "S", "W"]

# Road count including entry, or 0: only 0, 3 and 4 are reachable.  A two-way
# is a corridor; a five-way needs another direction.  Kept int for truth tests.
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


# A flood-reached open cell.  Enclosure makes its unchecked 3x3 read safe;
# mypy rejects an ordinary coordinate.  Further reads use ``_at``'s sentinel.
_ReachableCell = NewType("_ReachableCell", tuple[int, int])
# Intentional ``;`` stop, distinct from a probe's ``None``.  Construction
# rejects the latter, so a survivor is a validator bug rather than a halt.
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

# Off-grid sentinel: neither wall nor source glyph, so scans see no phantom.
# ``_Grid.open_at`` checks bounds separately because it is not drivable.
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

# Longitudinal mouth scan: the tested floor is 5; 7 adds slack.  Larger is not
# safer because scanning past the box can pair unrelated ``+`` cells.
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
        # Shared geometry memo: the hello fixture makes 3242/12734/5864 calls
        # from 727/1235/702 states.  Redrawing clears it.
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
        # Coordinate reads are hottest, hence the first exact-type test.  Grid
        # bounds, not row length, make a short row blank on its right.
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
            # A solid nearer wall hides any farther mouth; sighting ``+``
            # through it would mistake another corridor for this bend.
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
            # Head-on from a mouth, the sides are the joined road.  Its extent
            # cannot be probed inside the mouth, so take whichever is open.
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
    # Every road passed ``_road_deep`` or ``_open_toward``; merging applies
    # only to turns onto a detected side road.
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


def _drive[StateT: _State](
    grid: _Grid, state: StateT, arrival_cell: int, current_cell: int
) -> "StateT | _Halt | None":
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
        return type(state)(*lane, reversed_car.heading, _NO_LATCHES)

    steer = _choose_heading(grid, car, state.latches, arrival_cell, current_cell)
    if steer is None:
        return None
    return type(state)(*car.ahead(steer.heading), steer.heading, steer.latches)
