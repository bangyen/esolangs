"""Interpreter for Streetcode.

A car drives a 2D network of two-way, two-character-wide streets, running
the instruction under it at every cell; memory is an unbounded list of
signed integer cells under an unsigned cell pointer (CP).

``the implementation`` is the spec of record for this interpreter and is
not repeated here: it carries the language summary, and -- since the
`wiki page <https://esolangs.org/wiki/Streetcode>`_ never spells out the
geometry behind "drive on the right-hand side" or its
leftmost/second-leftmost "ambiguous turn" rule -- the full movement
interpretation (right-hand-rule wall-following, initial heading, road and
crossing mouths, and the two-phase lane merge), with the wiki examples
corroborating each rule and the questions that remain open.

How this module is laid out
---------------------------

Movement is pure and lives at module level; the run is mutable and lives
in :class:`_Machine`.  That line is exactly the line between what steers
and what does not.  The types come first, then the rules as functions of a
:class:`_Grid` and a :class:`_Car`, then :func:`_drive`, which is the whole
of movement in one signature::

    _drive(grid, state, arrival_cell, current_cell) -> _State | "halt" | None

A drawing, a state, and the only two tape values movement may read.  None of
the rules can consult a machine, because none is given one -- which is what
lets :meth:`_Machine._drive_states` enumerate the reachable state space by
calling :func:`_drive`, and lets a rule be asked about a hypothetical car.

Runtime error contract:

* The program is validated at construction and a malformed one raises
  :class:`ValueError` before the car moves (``_validate``): streets exactly
  two characters wide, road enclosed by walls, each cell's wall structure
  matching one of three neighbourhood forms, no ``-`` beside ``|``,
  everything on the grid part of the one street network, and exactly one
  ``C``.  ``U`` ends the turn in the opposite lane, so a ``U`` with no such
  lane is the late-detected width violation and raises
  :class:`~esolangs.exceptions.HaltError`.

* CP is unsigned and right-unbounded, so ``_`` at cell 0 **clamps** and the
  car drives on -- the wiki bounds CP on the left but never says what a
  below-zero ``_`` does, and the rest of this package saturates (brainfuck
  clamps ``<``).  Cells are unbounded signed ints, so ``O`` on a value that
  is not a valid code point raises ``HaltError`` rather than letting
  ``chr()`` throw.

* Exhausted input on ``I`` raises :class:`EOFError`, the repo-wide
  convention.  An empty input *line* is not exhausted input and is not an
  error: it sets the cell to 0.
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

    Three bare ints meaning three different things, two of them
    interchangeable to the checker: named fields keep ``near`` and ``far``
    from being read in the wrong order.
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

    The latch holds *which way it turns* rather than the heading it turns
    to, so the two direction fields are different types and cannot be built
    swapped; :attr:`new_heading` recovers the destination.  ``None`` rather
    than an instance means no merge is in progress.
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

    One record because they travel together everywhere -- the machine's
    field, :meth:`_Machine.snapshot`, and the successor states the
    drive-state search builds -- so there is one field order rather than
    several lists to keep in step.  It also makes the steering phases
    functions rather than mutations: each takes the latches it was handed
    and returns the ones the next phase should see (see :class:`_Steer`).
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

    Where the car is, which way it points, and the latches it carries.
    The tape, CP and I/O are deliberately absent -- they do not steer, and
    leaving them out makes the state space finite and small enough to
    enumerate (see ``_Machine._drive_states``).  A NamedTuple so the graph's
    keys, :func:`_drive`'s successors and ``step``'s lookup all name their
    fields while staying hashable.  :class:`_Machine` holds one as the whole
    of its steering state, so a step looks up the machine's own value rather
    than rebuilding one to match.
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


# Legal 3x3 wall forms around a drivable cell, up to rotation
# (``_Machine._validate_walls``); ``W`` any wall, ``.`` open, ``?`` anything.
#
#     corner: ?W?      wall: ?W?      intersection: W..   The corner is ``W``,
#             W..            ...                    ...   not ``+-|``, so one
#             ?..            ...                    ...   form covers outer,
#                                                        inner and flush corners.
_WALL_FORMS = [
    *_rotations("?W?W..?.."),
    *_rotations("?W?......"),
    *_rotations("W........"),
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

    Distinct from the validators' ``ValueError``, which says the *program*
    is malformed: a failure here says the *interpreter* is wrong, and a
    caller cannot provoke it with a bad program.

    Not an ``assert``: bandit rejects those in ``src`` (B101), and an
    invariant that disappears under ``python -O`` is not one to lean on.
    Keyword-only so a call reads as a statement of what must be true.
    """
    if not condition:
        raise AssertionError(message)


class _Grid:
    """The program's characters, addressable at any coordinate at all.

    Reads are total: ``grid[row, col]`` off the drawing returns
    :data:`_VOID`, so a scan can walk off the edge and get a definite
    answer, and the bounds test lives here rather than at six call sites.

    ``_VOID`` is its own character rather than a border of ``+`` because
    off the grid has two meanings no real character serves:
    :meth:`open_at` must treat it as *closed*, while the wall forms, the
    glyph rule and the mouth scans must treat it as matching *nothing* --
    a ``+`` border would have the mouth scans sight junctions never drawn.

    Rows stay strings and stay assignable, because the interpreter's own
    tests redraw a row to build a fixture (``grid[1] = "|C   |"``).
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

        Exposed rather than reached into, since the rules are module-level
        functions by design (see :class:`_Machine`) and so cannot touch a
        private attribute without tripping the linter.
        """
        return self._geometry

    def __getitem__(self, where: int | tuple[int, int]) -> str:
        """Return a whole row by index, or one character by coordinate.

        The coordinate read is total, so the mouth scans and
        ``_validate_glyphs`` need no bounds test of their own; what they
        find off the drawing is nothing rather than a phantom wall.
        :meth:`open_at` is the one read treating off the grid as closed.
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

        A redrawn row is a different drawing, so the geometry memo is
        dropped rather than left answering for geometry no longer there.
        """
        self._rows[row] = "".join(value).ljust(self.width)
        self._geometry.clear()

    def __iter__(self) -> Iterator[str]:
        """Iterate the rows, so the drawing can be scanned as text."""
        return iter(self._rows)

    def open_at(self, row: int, col: int) -> bool:
        """Whether ``(row, col)`` is drivable: on the grid and not a wall.

        The off-grid test is explicit rather than riding on the character:
        outside the drawing there is no road, the opposite of what a
        non-wall character means anywhere else.
        """
        if not (0 <= row < self.height and 0 <= col < self.width):
            return False
        return self._rows[row][col] not in _WALLS

    def op_at(self, row: int, col: int) -> _Op:
        """Return what the square at ``(row, col)`` does when the car runs it.

        A wall and the void both answer ``"NOP"``: the car never stands on
        either, so a caller asking anyway gets the harmless answer.
        Anything the spec does not define -- ``C``, space, a stray ``#`` --
        folds to ``"NOP"`` too; see ``_Op`` for why the fold is here.
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

    Streets are two-way and two cells wide and the car drives on the
    right, so a lane is the car's own only when the wall it hugs is on its
    *right*.  Wall on the left is the oncoming lane travelled backwards:
    geometry the drive-state search can name but the car cannot occupy.

    That search probes each state under both branch conditions, so it
    reaches wrong-side successors a real run never does.  Those have no
    successor of their own and looked like the wedged streets
    :meth:`_Machine._validate_total` rejects, which made the check refuse
    correct programs whose lanes are drawn tightly enough.

    Walls on both sides or neither is not a violation: the first is a
    one-wide corridor the width check already rejected, the second open
    road where the hug has nothing to follow yet.
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

    Only the two are representable, because only the two can be latched
    (see :data:`_Turn`).  A caller that has not ruled out straight ahead
    and the reverse is asking a question with no answer, so this raises: a
    silent "right" would latch a turn the junction never offered and steer
    into a wall several steps later, where the cause is invisible.
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

    The geometry rules all ask their questions *from* a car, so passing
    this record is what lets one be called on a hypothetical car -- the
    successor a probe is considering, a position a test asks about --
    without moving the real one there and back.

    Position and heading travel together because no rule wants one
    without the other: a mouth scan is anchored at the car and swept along
    its heading.
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

    The rules answer questions about the *drawing* from a grid, a
    :class:`_Car` and plain values.  None reads the tape, CP, a latch or
    the I/O, and the drawing is fixed for a run, so recurring arguments
    have a recurring answer -- and they recur constantly, since the four
    steering phases each re-derive the shape from scratch (see
    :class:`_Grid` for the counts).

    Caching here keeps the rules written as the plain geometric predicates
    they are and keeps invalidation in one place: the grid owns the memo,
    so a redrawn row drops it.  The key includes the rule's name, so two
    rules with the same argument tuple do not collide.
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

    The car starts as if it had just arrived driving on the right, so
    its initial heading is whichever direction has a wall immediately
    to its right (and open ground straight ahead) at the ``C`` cell.
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
    d_row, d_col = _DELTA[car.heading]
    s_row, s_col = _DELTA[side]

    def pos(depth: int, dist: int) -> tuple[int, int]:
        """Locate a cell at an offset from the car.

        ``depth`` cells along the car's heading, ``dist`` along ``side``.
        """
        return (
            car.row + depth * d_row + dist * s_row,
            car.col + depth * d_col + dist * s_col,
        )

    for dist in range(1, _MOUTH_MAX_DIST + 1):
        # The car must be level with the mouth's near edge, or it declines
        # a turn it has not reached and the hug drags it in a step later.
        # ``near`` may be one behind (cornered into the mouth), level, or one ahead.
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

    Scans ``1.._MOUTH_MAX_DIST`` cells out from the car
    (:func:`_crossing_mouth` uses this to find the two ``+`` bounding a
    mouth it is driving through).
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

    The same drawn junction has two shapes depending on the approach:
    along the main road it is a gap in the wall to one side
    (:func:`_road_mouth`), while up the branch itself the car passes
    *between* the two ``+`` bounding that gap.  Equally a decision point.

    Detected as a ``+`` on each side at a matching depth, at different
    perpendicular distances (they bound a road wider than the car's lane),
    with open ground straight ahead.
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

    A junction is a road mouth (see :func:`_road_mouth`) opening off
    either side of the car, counted alongside straight-ahead travel.  All
    three orientations of a T are recognized symmetrically, including a
    branch to both sides at once (a four-way, or a T whose crossbar the
    car drives into when straight ahead is blocked).  Returns 3 or 4
    roads, or 0 for an ordinary corner or a straight stretch.

    Both of the wiki's junction-bearing examples detect under this rule --
    the infinite-loop example first at ``(1,3)`` heading West and the
    infinite-cat example at ``(1,4)`` heading West, ten firing states each
    -- and every one of those twenty is a **three**-way.  Scanning both
    grids at every cell and heading answers 4 nowhere, so the four-way arm
    is a convention rather than a sourced rule; see ``docs/limitations.md``.
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

    A mouth's two ``+`` mark where the side road's bounding walls meet the
    wall the car drives along.  When those ``+`` continue into real wall
    arms one cell further out, the side road is a corridor with lanes of
    its own, so "drive on the right-hand side" applies to it too and the
    car merges rather than turning the instant it is detected.  A bare
    ``+`` with nothing beyond it bounds no corridor and turns immediately.
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

    The side road's lane cells lie strictly between the mouth's two ``+``,
    at depths ``near + 1 .. far - 1`` along the direction of travel.  The
    car must reach the lane adjacent to that road's right-hand wall
    relative to ``new_heading`` -- one step in from whichever bound sits in
    the ``_right(new_heading)`` direction -- before turning.  It does not
    change lane on the approach, so the target keeps its perpendicular
    coordinate and only advances along the travel axis.
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

    Only a detected side road (:func:`_road_mouth`) counts as a turn, plus
    straight ahead when the road continues; an open cell with no drawn
    mouth is not a road and must not consume a slot.

    Ordered left to right as the driver sees them, so which slot a turn
    lands in depends on the car's heading rather than on the compass
    direction of the road -- the same drawn corner is the "leftmost" road
    approached one way and the "second-leftmost" approached the other.
    """
    heading = car.heading
    roads = []
    crossing = _crossing_mouth(grid, car)
    # "Whichever way is open" is sound only once the open sides are the
    # road being joined; a side road not yet drivable would fill its slot
    # with the oncoming lane.  Defer: the hug brings the car level, and it re-detects.
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

    Streets are two characters wide, so a direction with a single open
    cell before a wall is the street the car is already on -- the oncoming
    lane, or the last cell of a bend.  Requiring two drivable cells is what
    distinguishes a road from the width of the road.
    """
    d_row, d_col = _DELTA[heading]
    return grid.open_at(car.row + d_row, car.col + d_col) and grid.open_at(
        car.row + 2 * d_row, car.col + 2 * d_col
    )


def _lawful_turn(grid: _Grid, car: _Car, heading: _Heading) -> bool:
    """Whether entering ``heading`` leaves the car driving on the right.

    The lane a car belongs in has that road's wall on its right, so a turn
    whose destination has open ground right and a wall left would put it in
    the oncoming lane -- not a road the junction may offer, however open it
    looks.  A destination with walls on neither side is not yet inside a
    lane and is left to the ordinary rules.
    """
    row, col = car.ahead(heading)
    wrong_side = grid.open_at(*_ahead(row, col, _right(heading))) and not grid.open_at(
        *_ahead(row, col, _left(heading))
    )
    return not wrong_side


class _Steer(NamedTuple):
    """What a steering phase decided: a heading, and the latches after it.

    Returning both makes the whole decision the value: a phase is a
    function from latches to latches, so a test can assert on what it did
    without a machine in between.

    ``None`` in place of a heading is a phase declining to decide, falling
    through to the next phase.  A declining phase can still change the
    latches -- an abandoned merge is exactly that -- which is why it
    reports ``(None, latches)`` rather than a bare ``None`` that would
    lose the update.
    """

    heading: _Heading
    latches: _Latches


# What one phase answers before ``_choose_heading`` sorts it out.  Not a
# ``_Steer | None`` because a declining phase may still have written a latch
# off (a merge abandoned mid-approach), and that write must survive.
_Phase = tuple["_Heading | None", _Latches]


def _heading_leaving_merge(grid: _Grid, car: _Car, latches: _Latches) -> _Phase:
    """Phase 2 of a merge: hold straight until the new wall picks up.

    After turning onto the new road the car is not yet against that road's
    right-hand wall, so an ordinary hug would turn it straight back.  Keep
    going while both right and ahead are open; the moment either closes,
    the wall has picked up and the latch is done.
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

    Returns a heading while the approach is still running or when the
    turn is made, and ``None`` once the latch is spent or abandoned.
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
    # Re-read the condition (an ``I``/``=`` on the approach can change the
    # CPth cell), from ``arrival_cell`` so a turning square's own setup is
    # not the decision.  Side mouths only: a crossing was decided at the
    # mouth, and a ``^`` on the run out must not overturn it.
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

    Returns the heading to take, or ``None`` when no junction fires or
    when the turn has to be deferred until the car is level with the
    road's mouth.

    ``current_cell`` is the CPth cell *after* this square's instruction
    ran, unlike the arrival read phase 1 uses, and is passed rather than
    fetched so this rule needs no tape to answer.
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

    Ordinary movement hugs the wall on the right; a detected intersection
    applies the spec's leftmost/second-leftmost rule among the open
    non-backward directions -- except where the chosen road has its own
    lanes, in which case the car drives to that road's right-hand lane
    before turning and holds straight afterwards until the new wall picks
    up (see :class:`_Merge`, :class:`_Latches` and ``the implementation``).
    Both latches are abandoned the moment the approach stops matching what
    was latched: a heading change during it, or a wall at the cell the
    latch would step onto.

    The tape enters as two ints.  ``arrival_cell`` is the CPth cell as the
    car arrived, before this square's instruction ran; ``current_cell`` is
    that cell after it ran.  The merge re-read branches on the first and
    the junction rule on the second, and they are the only tape reads
    movement makes -- which is why the drive-state graph can enumerate it
    by trying both bits.

    Four phases, each answering a heading or ``None`` to fall through and
    each threading the latches on: leaving a merge, approaching a latched
    target, deciding a junction, and ordinary hugging.  ``None`` only when
    every phase declines, which means the car has run out of road.
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

    The whole movement semantics in one function.  Nothing else is
    consulted and nothing written, so the same arguments always give the
    same answer -- which lets :meth:`_Machine._drive_states` enumerate the
    reachable space by calling it and :meth:`_Machine.step` replay it.

    ``;`` and ``U`` are movement too: ``;`` stops the car (``"halt"``) and
    ``U`` reverses it into the lane now on its right, clearing every latch
    keyed to the old heading.  ``None`` is the car running out of road,
    which :meth:`_Machine._validate_total` rejects a street for, and is
    deliberately not ``"halt"`` -- a wedged street and a legal stop are
    different facts.

    Only movement is modelled: the value-dependent halts (``_`` at CP 0,
    ``O`` on a non-code-point, ``I`` at end of input) stay with the tape
    and the I/O in :meth:`_Machine.step`.
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

    ``step()`` executes the cell under the car, then drives it one cell
    further using the wall-following/junction rules described in
    ``the implementation``; ``halted`` is true once ``;`` runs or
    the car reaches a true dead end with nowhere left to go.  The VM and the
    state-cycle hang detector expose this object.

    Deliberately the *only* mutable thing in the module.  The movement
    rules are module-level functions of the drawing, a :class:`_Car` and
    the two tape bits movement may read, returning a new :class:`_State`
    rather than moving anything.  What is left here is the run -- tape, CP,
    I/O and the car's position -- which ``step`` advances by handing the
    current state to those functions and storing what comes back.
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
        """The car's ``(row, col, heading)``.

        The heading is spelled ``"N"``/``"E"``/``"S"``/``"W"`` internally and
        reported as its index into that order, so ``ip`` stays all-integer
        like every other 2D language's.
        """
        return (self.row, self.col, "NESW".index(self.heading))

    @property
    def memory(self) -> list[int]:
        """The tape's cells, densified.

        The tape is a sparse dict keyed by CP, which never goes negative --
        ``LEFT`` at zero halts -- so this is the dense prefix up to the
        highest cell touched.
        """
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

        For a caller that needs to drive from somewhere other than the
        square its ``C`` is on; the interpreter's own fixtures do this to
        reach a geometry a whole program would take many steps to arrive
        at.  One call rather than three assignments, because the three
        coordinates only mean anything together.

        The latches are deliberately left alone: a test that places a car
        *and* sets up a merge wants both.
        """
        self._state = self._state._replace(row=row, col=col, heading=heading)

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection.

        Every attribute carried between steps appears here, so two equal
        snapshots have equal futures.  Everything that steers enters as
        the single :class:`_State` record, so a latch added later is
        carried without touching this method.

        ``_done`` matters even though a halted machine takes no further
        steps: ``;`` halts without moving the car, so without the flag the
        halt looks like a repeat of the step before it.
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

        Unlike an ordinary ``grid[row, col]`` the eight reads are not
        bounds-checked.  :meth:`_validate_enclosed` has already rejected
        any street whose road touches the border, so a cell reaching here
        has all eight neighbours on the grid; the precondition below
        states that property and fails if the fill ever breaks it.
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

        Two static checks over the open cells reachable from ``C``:
        :meth:`_validate_width` measures the streets and
        :meth:`_validate_walls` checks the wall structure around them.
        Both raise :class:`ValueError`.  This is the single hook the
        interpreter's own wall-shape fixtures disable, so that skeletal
        test geometry need not be a legal street.
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

        Built once at construction and kept as ``_graph``, where it
        serves two callers: :meth:`_validate_total` reads it to reject a
        street the car cannot drive out of, and :meth:`step` looks up
        each move in it rather than re-running the mouth scans.

        A driving state is a position, a heading and the three latches --
        the movement half of :meth:`snapshot`, minus the tape, CP and I/O.
        The geometry is static, so a state's successors depend on nothing
        else, and the breadth-first search terminates because positions,
        headings and latch values are all finite.

        Each state maps to its successors keyed by the branch bits that
        produce them.  Movement reads the tape at exactly two places, both
        testing ``== 0`` -- :func:`_heading_from_merge_target` on the
        arrival cell and :func:`_heading_from_junction` on the current one
        -- and a step can consume both, so each state is probed with all
        four combinations.  Testing only zero-ness is what makes those two
        bits cover every tape the car could hold, so the map is exhaustive
        rather than a sample.  A ``None`` successor is a state the car
        cannot drive out of.

        The search calls :func:`_drive` on each state directly rather than
        *becoming* it: with movement a function of its arguments there is
        no machine to save and restore, and the probe cannot disturb a car
        it was never given.
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

        Only ``;`` halts a well-formed program, so a reachable state
        with no successor is a street the movement rules have run out
        of road on.  :meth:`step` would meet that as a silent halt
        partway through a run, with nothing to say about where the
        street went wrong; the search finds it before the car moves and
        names the square.

        What it catches is narrower than "dead ends".
        :meth:`_heading_from_hug` falls back through all four directions
        including the reverse, and a validated street is connected with at
        least two cells, so ordinary wall-following is total by
        construction rather than by this search.  That leaves one class of
        program it rejects today -- a reachable ``U`` whose opposite lane
        is walled, promoting the documented runtime ``HaltError`` to a
        construction-time :class:`ValueError` -- plus a regression net
        over the movement phases.  A brute force over 137472 small walled
        grids found none that only this check rejects.

        It is still stronger than running the program, covering every
        reachable state under both branch conditions.  It does not cover
        the value-dependent halts (see :func:`_drive`), which are runtime
        semantics rather than geometry.
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

        The movement rules were reverse-engineered from the wiki's
        examples and several remain judgement calls (see the module
        docstring).  These are not: a car inside a wall, or one that
        teleports rather than driving a cell at a time, is wrong under
        every reading.  A junction firing while its gap still opened a
        cell ahead once drove the car *inside* the wall the mouth opens
        through; here that is a construction-time failure naming the
        square.

        :class:`AssertionError` rather than :class:`ValueError` because
        they do not describe a malformed program: a breach means the
        movement rules disagree with the grid they are driving on.
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

        The spec requires streets to be two-way and two characters wide; a
        one-wide street has no opposite lane for ``U`` to end in.  Static
        and run before the car moves, so a malformed program fails with
        :class:`ValueError` rather than a late
        :class:`~esolangs.exceptions.HaltError` at the first ``U``.

        Width reads off the grid: a corridor cell with open neighbours
        directly opposite (N+S or E+W) must have an open neighbour on at
        least one perpendicular side, and a dead-end cell with a single
        open neighbour must too.  Isolated cells and wall-free grids are
        not streets and are exempt.  A blank row or column is a lane:
        space is a drivable no-op.

        The upper bound is a fully open three-by-three block rather than a
        cross-section run, which cannot measure it -- where two legal
        streets cross, a run through the intersection reports the crossing
        street's *length*.  A region wider than two in both directions
        must contain such a block; a two-wide network never does, since a
        crossing is a plus whose open centre is two-by-two with walls at
        the diagonal corners.  A three-by-two room therefore passes, which
        is the deliberate boundary of the rule.
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

        The rule :meth:`_validate_width` enforces, as a value rather than
        a raise, so it can be asked as a question without a second
        implementation free to drift.  The message is the one the
        validator raises with.
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

        Width alone misses a wall with a one-cell hole punched through it
        (``-- --``): the gap is too narrow to drive, yet the corridor
        either side still measures two wide.  So each reachable cell's
        three-by-three neighbourhood must match one of ``_WALL_FORMS`` up
        to rotation.  A wall-free neighbourhood is open road and legal.

        The forms are deliberately permissive at their edges -- a wall may
        simply stop, and a corner admits any wall character rather than
        only ``+`` -- which leaves open a question the wiki does not
        settle, whether a road divider must terminate in a ``+``.  The
        ring program in ``tests/fixtures/streetcode_hello.txt`` leaves its
        divider ends bare and runs correctly.  What the forms do reject is
        the hole, whose cell has wall on two opposite sides and open
        ground on the other two.

        :meth:`_block` does not bounds-check, which is sound only because
        :meth:`_validate` runs :meth:`_validate_enclosed` first -- moving
        this check ahead of the enclosure one would break the read.

        Only cells reachable from ``C`` are checked: the ``ljust`` padding
        around a program and the background around an L-shaped layout are
        drawing, not street.
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

        A street is bounded by walls, so the road the car can reach never
        touches the border.  A flood fill from ``C`` that reaches it has
        escaped through a hole, or through a wall that was never drawn.

        This is what catches a hole two cells across: a one-cell hole
        leaves a one-wide stub the width check already rejects, but a
        two-wide hole is a legal-width passage that looks like ordinary
        road, and only leading off the grid marks it as a gap.
        """
        violation = self._enclosure_violation(reachable)
        if violation is not None:
            raise ValueError(violation)

    def _enclosure_violation(self, reachable: set[_ReachableCell]) -> str | None:
        """Name a road cell on the grid's border, or ``None`` if none is.

        The property :meth:`_block` depends on, stated once so the read's
        precondition and this check cannot disagree about the border.
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

        ``-`` runs horizontally and ``|`` vertically; where they meet the
        wall turns a corner, drawn ``+``.  So a ``-`` beside a ``|``, or a
        ``|`` above or below a ``-``, is a wall changing direction without
        the corner that marks it.

        This is about which glyph is used rather than where walls are, so
        the forms in :meth:`_validate_walls` cannot see it -- they match
        any wall character alike.
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

        A program is a single street network: everything drawn is either
        road the car can reach or a wall bounding it.  Grow the reachable
        open cells by one in every direction so the region takes in the
        walls along its edges, and whatever is still drawn belongs to no
        street -- a detached box, a stray fragment, an instruction sealed
        inside an island, or the middle of a solid block, which is ink
        bounding nothing.

        A hollow island needs no special case: every cell of a one-thick
        wall is within one step of the road outside it, so the growth
        takes the whole island in.  Only a block thick enough to have an
        interior falls outside, and permitting that would cost a second
        flood fill to tell an enclosed hole from the outside.

        Only non-blank cells count, so the ``ljust`` padding and the
        background around an L-shaped layout are ignored -- which is what
        lets the boolean example's wide blank margins pass.

        The rule is strict: any character off the street is rejected, not
        only walls.  Restricting it to walls would catch the same
        drawings and let the rest stand as comments, which the wiki says
        nothing about either way; stray marks are likelier a drawing slip
        than an annotation.
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
