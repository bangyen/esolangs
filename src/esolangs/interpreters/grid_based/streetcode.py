"""Interpreter for Streetcode.

A car drives a 2D network of two-way, two-character-wide streets, running
the instruction under it at every cell; memory is an unbounded list of
signed integer cells under an unsigned cell pointer (CP).

``docs/streetcode.md`` is the spec of record for this interpreter and is
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
in :class:`_Machine`.  The line between them is exactly the line between
what steers and what does not.

* The types come first: :class:`_Car` (where the car is and which way it
  points), :class:`_Latches` (what the steering phases carry between
  steps), :class:`_State` (a car and its latches -- the whole movement
  half of the machine), and the records the rules answer in
  (:class:`_Mouth`, :class:`_Merge`, :class:`_Steer`).

* Then the rules, as functions of a :class:`_Grid` and a :class:`_Car`:
  the mouth and junction detectors (:func:`_road_mouth`,
  :func:`_crossing_mouth`, :func:`_junction_kind`,
  :func:`_junction_choices`), the four steering phases
  (:func:`_heading_leaving_merge`, :func:`_heading_from_merge_target`,
  :func:`_heading_from_junction`, :func:`_heading_from_hug`), and
  :func:`_choose_heading`, which runs the phases in order, threading the
  latches through.

* :func:`_drive` is the whole of movement in one signature::

      _drive(grid, state, arrival_cell, current_cell) -> _State | "halt" | None

  A drawing, a state, and the only two tape values movement is allowed to
  read -- and that is everything a step depends on.  The intersection
  logic in particular can be reasoned about by reading these functions:
  none of them can consult a machine, because none of them is given one.

* :class:`_Machine` holds what is genuinely a run rather than a rule --
  the tape, CP, the I/O, whether the car has stopped, and where it
  currently is.  :meth:`_Machine.step` runs the square's instruction
  (that is where every effect happens) and then applies :func:`_drive` to
  find the next state.

Two things fall out of the split.  :meth:`_Machine._drive_states` can
enumerate the entire reachable state space by *calling* :func:`_drive`,
where it used to have to move the machine onto each state, run the rules
for their side effects, and restore every field afterwards.  And a rule
can be asked about a hypothetical car -- in a test, or in the search --
without a car being driven there and back.

Runtime error contract:

* The program is validated at construction and a malformed one raises
   :class:`ValueError` before the car moves (``_validate``).  Streets
   must be exactly two characters wide, the road must be enclosed by
   walls rather than running off the grid, each cell's wall structure
   must match one of three neighbourhood forms, ``-`` and ``|`` may not
   be drawn side by side, and everything on the grid must belong to the
   one street network.  ``U`` ends the turn in the opposite lane (the
   spec's streets are two-way and two wide), so a ``U`` with no such
   lane is the late-detected case of the width violation and raises
   :class:`~esolangs.exceptions.HaltError` when the street has no walls
   to validate against.

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
from collections.abc import Callable, Iterator
from typing import Literal, NamedTuple, NewType, assert_never

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import IO

# The alphabet a wall form is written in: ``?`` matches any cell, ``W`` a
# wall character, and ``.`` a non-wall.  Naming the three lets the checker
# see that :func:`_matches` handles every one, so it needs no arm for a
# pattern character that no form contains.
_Pattern = Literal["?", "W", "."]

# The four compass headings the car drives under.  Naming them keeps a
# heading distinct from the cell characters and form patterns that are also
# plain strings, so a mix-up is a type error rather than a silent lookup
# against the wrong alphabet.
_Heading = Literal["N", "E", "S", "W"]

# What a junction detector reports: the number of roads the drawn shape
# offers, counting the one the car came in on, or 0 for no junction at
# all.  Only 0, 3 and 4 are reachable -- a "two-way junction" is a
# corridor and a five-way needs a fifth direction -- so naming the three
# lets the checker reject an arm for a count that cannot occur, the same
# way ``_Pattern`` does for the form alphabet.  The values stay plain
# ints rather than an enum: ``_junction_kind`` is used as a truth value
# (``not self._junction_kind(...)``) and 0 has to keep meaning false.
_Junction = Literal[0, 3, 4]

# Which way a merge latch turns, relative to the heading it was taken
# under.  A latch is only ever set for a turn onto a detected side road:
# ``_junction_choices`` offers nothing but ``_left(heading)``, ``heading``
# and ``_right(heading)``, and ``turning`` in
# :func:`_heading_from_junction` rules out the straight-ahead
# case, so these two are the whole space -- straight and reverse are not
# merely unobserved, they are unreachable.  Storing the turn rather than
# the destination heading is what makes a merge's two direction fields
# different types, so :class:`_Merge` cannot be built with them swapped.
_Turn = Literal["left", "right"]


class _Mouth(NamedTuple):
    """A road mouth as :func:`_road_mouth` measured it.

    Three bare ints that mean three different things, and the two depths
    are interchangeable to the checker: named fields are what keep
    ``near`` and ``far`` from being read in the wrong order by the
    helpers that consume a mouth (:func:`_lane_bounded`,
    :func:`_lane_merge_target`, and the hug suppression in
    :func:`_heading_from_junction`).
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
    to.  Both were once a :data:`_Heading`, and a NamedTuple cannot make
    its fields keyword-only, so nothing but argument order stopped the
    two from being swapped in a positional call -- a mistake the checker
    could not see and the drive-state graph would faithfully reproduce.
    A :data:`_Turn` beside a :data:`_Heading` is two different types, so
    the swap no longer typechecks; it is ruled out by the record's shape
    rather than by a convention the next construction site has to follow.

    Storing the turn also keeps one fact in one place.  The destination
    is recovered by :attr:`new_heading`, and the "was this a left turn?"
    question :func:`_heading_from_merge_target` asks when it
    re-reads the branch is now the stored field rather than a comparison
    that reconstructs it -- the two spellings could previously disagree.

    ``None`` (rather than an instance) means no merge is in progress.
    See ``_Machine.__init__``.
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

    Grouped into one record because they travel together everywhere: the
    machine's field, :meth:`_Machine.snapshot`, and the successor states
    the drive-state search builds all used to spell the same three
    fields out independently, so adding or reordering a latch meant
    editing several lists in step and silently corrupting the drive-state
    graph on missing one.  One record means one field order.

    The record is also what makes the steering phases functions rather
    than mutations.  Each takes the latches it was handed and returns the
    ones the next phase and the next step should see (see
    :class:`_Steer`); a phase used to write them back onto the machine
    one field at a time, which is why its effect on the following step
    could not be read off its signature.
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
    The tape, CP and I/O are deliberately absent -- they do not steer,
    and leaving them out is what makes the state space finite and small
    enough to enumerate (see ``_Machine._drive_states``).  A NamedTuple
    rather than a plain tuple so that the graph's keys, the successors
    :func:`_drive` returns and ``step``'s lookup all name their fields;
    it stays hashable and tuple-compatible, which is what the graph dict
    and :meth:`_Machine.snapshot` need.

    :class:`_Machine` holds one of these as the whole of its steering
    state, so the value a step looks up in the graph is the machine's own
    rather than one rebuilt from separate fields to match.  Those were
    once separate -- a ``_Car`` beside a ``_Latches`` -- and ``step`` had
    to assemble a state on the way in and take one apart on the way out,
    which is two conversions that existed only because the same four
    values were written down twice.
    """

    row: int
    col: int
    heading: _Heading
    latches: _Latches

    @property
    def car(self) -> "_Car":
        """Return the car half of the state, for the rules that only steer."""
        return _Car(self.row, self.col, self.heading)


# An open cell the flood fill in ``_validate_width`` reached from ``C``.
# Only that fill mints these, and ``_validate_enclosed`` then proves none
# of them sits on the border of the grid -- so the eight neighbours of one
# are all on the grid, and a read anchored on it needs no bounds test.
# The distinction is provenance, not shape: mypy will not accept a plain
# coordinate where one of these is asked for, which is what keeps the
# unchecked read in ``_block`` reachable only from cells carrying that
# proof.  It says nothing about reads further out -- the mouth scans look
# up to ``_MOUTH_MAX_DEPTH`` cells away and legitimately run off the grid,
# which is what ``_at`` and its ``'?'`` sentinel remain for.
_ReachableCell = NewType("_ReachableCell", tuple[int, int])
# The car stops here on purpose: the square is ``;``.  Distinct from the
# ``None`` a probe returns when the movement rules run out of road, which
# is a malformed street ``_validate_total`` rejects at construction.  The
# two were once spelled alike, so a wedged street and a deliberate stop
# were indistinguishable downstream; keeping them apart is what lets
# :meth:`_Machine.step` treat a surviving ``None`` as the validator bug it
# would have to be, rather than halting quietly on it.
_Halt = Literal["halt"]
# A state's successors, keyed by the two branch bits movement can read in
# one step: the arrival cell and the post-instruction cell, in that order.
_Edges = dict[tuple[int, int], "_State | _Halt | None"]

# No merge in progress and nothing to suppress: the latches a car starts
# with, and the ones it is reset to whenever a 'U' clears them.  Named so
# the reset is one value rather than three assignments that have to agree.
_NO_LATCHES = _Latches(merge=None, merging_heading=None, skip_hug=0)

_HEADINGS: tuple[_Heading, ...] = ("N", "E", "S", "W")
_DELTA: dict[_Heading, tuple[int, int]] = {
    "N": (-1, 0),
    "E": (0, 1),
    "S": (1, 0),
    "W": (0, -1),
}
_WALLS = frozenset("+-|")

# What a read off the edge of the drawing returns.  Not a wall (so the
# form, glyph and mouth scans see nothing there rather than a phantom
# wall) and not any glyph a program can contain, so it matches no rule.
# ``_Grid.open_at`` tests the bounds itself rather than asking whether
# this is a wall, because off the grid is not drivable either.
_VOID = "?"

# What a drivable square does when the car runs it.  Closed: every glyph
# the spec defines maps to one of these, and everything else -- ``C``,
# space, and any character the language does not use -- maps to ``NOP``,
# which is what makes the set closed rather than open-ended.  Folding the
# undefined characters here rather than at the point of dispatch is what
# lets :meth:`_Machine.step` be exhaustive over a finite set instead of a
# chain of comparisons with a silent fallthrough at the end.
#
# The fold is of the *meaning*, not the character: a cell keeps the glyph
# as drawn (see :class:`_Open`), because ``_validate_connected`` rejects
# stray ink off the street and names the glyph it found.  A ``#`` on the
# street is a no-op; the same ``#`` beside the street is a malformed
# program, and the two are told apart by where it is, not by what it does.
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

# How far perpendicular to the direction of travel ``_road_mouth`` looks for
# the wall a side road opens through: a two-way street is two cells wide, so
# the far lane's wall can sit two cells out, and 3 covers that with a cell to
# spare.
_MOUTH_MAX_DIST = 3
# How far along the direction of travel ``_road_mouth`` will look for the
# ``+`` closing a road's mouth.  Sweeping the value against the test suite
# puts the floor at 5 -- at 4 the mouths of the wider drawn junctions stop
# being seen and three tests fail -- while 5 and up are indistinguishable.
# 7 is that floor plus slack for mouths wider than anything drawn so far.
#
# Raising it is not conservatively safer, which is why the slack is small.
# The bound is two-sided: too low and a real mouth is truncated, too high
# and the scan runs past the box it is reading and pairs up two ``+`` that
# bound nothing.  The 1-arity boolean programs are the worked example --
# from ``(9, 6)`` heading East, a generous bound finds a "mouth" spanning
# the blank margin between two drawn boxes, which 7 correctly does not
# see.  Behaviour is unaffected there only because ``_junction_choices``
# offers one road and the junction does not fire.  So what is checked is
# the driving, not the scan: ``tests`` compares the whole drive-state
# graph at this bound against a generous one over the corpus, and the
# graphs agree.  Nothing depends on the exact value in that sense.
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


# The legal wall structure around a drivable cell, as three-by-three forms
# matched up to rotation; see ``_Machine._validate_walls``.  ``W`` is any
# wall character, ``.`` is open ground, and ``?`` is anything at all.
#
#     corner: ?W?      wall: ?W?      intersection: W..
#             W..            ...                    ...
#             ?..            ...                    ...
#
# The corner's cells are ``W`` rather than ``+``, ``-`` and ``|`` so that a
# rotation does not have to swap the two wall glyphs, and so that one form
# covers the outside of a corner, the inside of one (where the arms belong
# to the outer wall and the corner to an island), and the corners of two
# boxes packed flush against each other.
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

    Distinct from the ``ValueError`` the validators raise.  That one says
    the *program* is malformed, and is part of the documented contract; a
    failure here says the *interpreter* is wrong -- some code depended on
    a property that an earlier check was supposed to have established and
    no longer does.  A caller cannot provoke it with a bad program.

    Not written as ``assert``: bandit rejects those in ``src`` (B101), and
    an invariant that disappears under ``python -O`` is not one the code
    can lean on.  The condition is keyword-only so a call reads as a
    statement of what must be true rather than a bare boolean argument.
    """
    if not condition:
        raise AssertionError(message)


class _Grid:
    """The program's characters, addressable at any coordinate at all.

    Reads are total: ``grid[row, col]`` off the drawing returns
    :data:`_VOID` rather than raising or needing the caller to have
    range-checked first.  The bounds test does not disappear -- it moves
    here, to one place, from the six or so call sites that each used to
    make it -- so a scan can walk off the edge and get a definite answer
    instead of a special case.

    ``_VOID`` is deliberately not a wall glyph, and this is the whole
    reason the off-grid value is its own character rather than padding
    the drawing with ``+``.  Off the grid has two meanings here that no
    single real character serves: :meth:`_Grid.open_at` must treat it as
    *closed* (there is no road out there to drive onto), while the wall
    forms, the glyph rule and the mouth scans must treat it as matching
    *nothing* -- a border of ``+`` would have the mouth scans sight
    junctions that were never drawn.  ``_VOID`` satisfies both: it is not
    in ``_WALLS``, and it equals no glyph.

    Rows stay strings and stay assignable, because the interpreter's own
    tests redraw a row to build a fixture (``grid[1] = "|C   |"``).
    """

    __slots__ = ("_rows", "height", "width")

    def __init__(self, rows: list[str]) -> None:
        """Square the drawing off, so every row is ``width`` characters."""
        self.width = max(len(row) for row in rows)
        self._rows = [row.ljust(self.width) for row in rows]
        self.height = len(self._rows)

    def __getitem__(self, where: int | tuple[int, int]) -> str:
        """Return a whole row by index, or one character by coordinate.

        The coordinate read is total, so the scans that come through here
        -- the mouth scans, which look several cells out and can
        legitimately run off the drawing, and ``_validate_glyphs`` --
        need no bounds test of their own.  ``_VOID`` matches no glyph and
        is not a wall, so what they find out there is nothing rather than
        a phantom wall; :meth:`open_at` is the one read that treats off
        the grid as closed instead.
        """
        if isinstance(where, int):
            return self._rows[where]
        row, col = where
        if not (0 <= row < self.height and 0 <= col < self.width):
            return _VOID
        return self._rows[row][col]

    def __setitem__(self, row: int, value: str) -> None:
        """Redraw one row, for the fixtures that build geometry by hand."""
        self._rows[row] = "".join(value).ljust(self.width)

    def __iter__(self) -> Iterator[str]:
        """Iterate the rows, so the drawing can be scanned as text."""
        return iter(self._rows)

    def open_at(self, row: int, col: int) -> bool:
        """Whether ``(row, col)`` is drivable: on the grid and not a wall.

        ``_VOID`` is not in ``_WALLS``, so the off-grid test is explicit
        here rather than riding on the character: outside the drawing
        there is no road, which is the opposite of what a non-wall
        character means anywhere else.
        """
        if not (0 <= row < self.height and 0 <= col < self.width):
            return False
        return self._rows[row][col] not in _WALLS

    def op_at(self, row: int, col: int) -> _Op:
        """Return what the square at ``(row, col)`` does when the car runs it.

        A wall has no instruction and neither does the void, so both
        answer ``"NOP"``: the car never stands on either, and a caller
        asking anyway gets the harmless answer rather than an error.
        Every other character is looked up, with anything the spec does
        not define -- ``C``, space, a stray ``#`` -- folding to ``"NOP"``
        as well.  See ``_Op`` for why the fold happens here.
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


def _opposite(heading: _Heading) -> _Heading:
    """Return the heading 180 degrees from ``heading``."""
    return _HEADINGS[(_HEADINGS.index(heading) + 2) % 4]


def _turn_of(heading: _Heading, new_heading: _Heading) -> _Turn:
    """Classify ``heading`` -> ``new_heading`` as a left or a right turn.

    Only the two are representable, because only the two can be latched:
    see :data:`_Turn`.  A caller that has not already ruled out straight
    ahead and the reverse is asking a question with no answer, so this
    raises rather than picking one -- a silent "right" there would latch
    a turn the junction never offered and steer the car into a wall
    several steps later, where the cause is no longer visible.
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

    The geometry rules below all ask their questions *from* a car: is
    there a mouth off this side, is that direction a road, is this a
    junction.  Every one of them used to read ``self.row``, ``self.col``
    and ``self.heading`` off the machine, which made "the car" an
    implicit argument that could not be seen in a signature and could
    not be supplied without a machine to mutate.  Passing this record
    instead is what lets a rule be called on a hypothetical car -- the
    successor a probe is considering, a position a test wants to ask
    about -- without moving the real one there and back.

    Position and heading travel together because no rule wants one
    without the other: a mouth scan is anchored at the car and swept
    along its heading, and splitting the two would only mean two
    parameters that must agree.
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
            # This line is the wall the car is driving along, and it
            # carries no mouth it could turn into.  Anything further out
            # sits behind that wall, not on a road reachable from here, so
            # stop looking: a `+` pair sighted through solid wall is some
            # other corridor's geometry, and treating it as a junction
            # would fire in the middle of an ordinary bend.
            return None
    return None


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


def _crossing_mouth(grid: _Grid, car: _Car) -> bool:
    """Whether the car is driving *out through* a side road's mouth.

    The same drawn junction presents two different shapes depending on
    the approach.  Driving along the main road, a branch appears as a gap
    in the wall to one side (:func:`_road_mouth`).  Driving up the branch
    itself, the car passes *between* the two ``+`` that bound that gap --
    one to either side, at the same depth -- with the road continuing
    ahead.  That is the same intersection, met head-on rather than
    side-on, and it is equally a decision point.

    Detected as a ``+`` on each side at a matching depth, the two sitting
    at different perpendicular distances (they bound a road wider than the
    lane the car occupies), with open ground straight ahead.
    """
    if not _open_toward(grid, car, car.heading):
        return False
    # Level with both `+` -- one step further and they are behind the car,
    # one step earlier and it has not reached the intersection yet.
    left = _plus_dist(grid, car, _left(car.heading))
    right = _plus_dist(grid, car, _right(car.heading))
    return left is not None and right is not None and left != right


def _junction_kind(grid: _Grid, car: _Car) -> _Junction:
    """Detect a real intersection ahead, returning the open-option count.

    A junction is a road mouth (see :func:`_road_mouth`) opening off
    either side of the car, counted alongside straight-ahead travel.  All
    three orientations of a T-junction are recognized symmetrically: a
    branch to the left with wall on the right, a branch to the right with
    wall on the left, and a branch to both sides at once (a four-way, or a
    T whose crossbar the car is driving into when straight ahead is
    blocked).  Returns a :data:`_Junction`: 3 or 4 roads, or 0
    for no junction -- an ordinary corner or a straight stretch.

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
    kind = _junction_shape(grid, car)
    # A drawn junction is only a choice when at least two of the roads
    # it offers are roads the car could actually drive down (see
    # :func:`_road_deep`); otherwise the shape is a bend or a lane
    # boundary, and ordinary wall-following handles it.
    return kind if len(_junction_choices(grid, car)) >= 2 else 0


def _junction_shape(grid: _Grid, car: _Car) -> _Junction:
    """Classify the wall shape alone, before the roads are counted."""
    heading = car.heading
    ahead_open = _open_toward(grid, car, heading)
    left_mouth = _road_mouth(grid, car, _left(heading)) is not None
    right_mouth = _road_mouth(grid, car, _right(heading)) is not None
    # Counting the road behind the car, which is always drivable, a branch
    # to one side with open road ahead is a three-way; branches to both
    # sides make it a four-way when the car can also continue straight,
    # and a three-way T whose crossbar it is driving into when it cannot.
    if left_mouth and right_mouth:
        return 4 if ahead_open else 3
    if left_mouth or right_mouth:
        return 3 if ahead_open else 0
    # Met head-on -- the car is driving out through the mouth itself
    # rather than past it (see :func:`_crossing_mouth`).
    return 3 if _crossing_mouth(grid, car) else 0


def _lane_bounded(grid: _Grid, car: _Car, side: _Heading, mouth: _Mouth) -> bool:
    """Whether ``mouth`` bounds a genuinely multi-lane road.

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

    The mouth's two ``+`` (see :func:`_road_mouth`) mark where the side
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
    near, far = mouth.near, mouth.far
    d_row, d_col = _DELTA[car.heading]
    depth = far - 1 if _right(new_heading) == car.heading else near + 1
    # d_row/d_col is a unit vector with exactly one nonzero component;
    # that component picks out the travel-axis coordinate to advance,
    # while the perpendicular coordinate stays fixed at the car's own.
    if d_row:
        return car.row + depth * d_row, car.col
    return car.row, car.col + depth * d_col


def _junction_choices(grid: _Grid, car: _Car) -> list[_Heading]:
    """Return the roads a junction offers, in the spec's choice order.

    Only a detected side road (:func:`_road_mouth`) counts as a turn the
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
    heading = car.heading
    roads = []
    crossing = _crossing_mouth(grid, car)
    # Crossing a mouth head-on, the branch below takes "whichever way
    # is open", because a perpendicular road's extent cannot be probed
    # from inside the mouth.  That is sound only while the open sides
    # *are* the road being joined.  When a side road is detected but
    # not yet drivable -- _road_mouth anchors a mouth up to one cell
    # ahead, so a junction fires as the car arrives -- taking whatever
    # is open instead fills that road's slot with the oncoming lane of
    # the two-wide street the car is already on, and the car decides a
    # junction the drawing never offered.  Defer: ordinary
    # wall-following brings it level with the gap, where the same mouth
    # re-detects and the cell is read there.
    if crossing:
        for side in (_left(heading), _right(heading)):
            if _road_mouth(grid, car, side) is not None and not _open_toward(
                grid, car, side
            ):
                return []
    for side in (_left(heading), heading, _right(heading)):
        if crossing:
            # Driving out through a mouth head-on, the roads to either
            # side are the main road the branch joins.  That road runs
            # perpendicular to the car, so its extent cannot be probed
            # from inside the mouth (two cells out crosses it and hits
            # its far wall): take whichever way is open.
            if _open_toward(grid, car, side):
                roads.append(side)
        elif _road_deep(grid, car, side) and _lawful_turn(grid, car, side):
            roads.append(side)
    return roads


def _road_deep(grid: _Grid, car: _Car, heading: _Heading) -> bool:
    """Whether ``heading`` leads onto a road, rather than across one.

    Streets are two characters wide, so a direction with a single open
    cell before a wall is not a road the car can drive down: it is the
    street it is already on -- the oncoming lane alongside it, or the
    last cell of a bend before the wall turns.  Requiring two drivable
    cells is what distinguishes a road from the width of the road.
    """
    d_row, d_col = _DELTA[heading]
    return grid.open_at(car.row + d_row, car.col + d_col) and grid.open_at(
        car.row + 2 * d_row, car.col + 2 * d_col
    )


def _lawful_turn(grid: _Grid, car: _Car, heading: _Heading) -> bool:
    """Whether entering ``heading`` leaves the car driving on the right.

    The lane a car belongs in has that road's wall on its right, so a
    turn whose destination has open ground to the right and a wall to
    the left would put the car in the lane oncoming traffic uses.  Such
    a turn is not a road the junction may offer, however open it looks:
    the spec's cars drive on the right-hand side.  A destination with
    walls on neither side is not yet inside a lane (an open room, or a
    junction's own floor) and is left to the ordinary rules.
    """
    row, col = car.ahead(heading)
    wrong_side = grid.open_at(*_ahead(row, col, _right(heading))) and not grid.open_at(
        *_ahead(row, col, _left(heading))
    )
    return not wrong_side


class _Steer(NamedTuple):
    """What a steering phase decided: a heading, and the latches after it.

    A phase used to answer only the heading and write any latch change
    back through ``self._merge = ...`` on the way out, so its effect on
    the next step was invisible in its signature and could only be found
    by reading the body.  Returning both makes the whole decision the
    value: a phase is a function from latches to latches, and the caller
    can see -- and a test can assert on -- what it did without a machine
    in between.

    ``None`` in place of an instance is a phase declining to decide (see
    :func:`_choose_heading`), which is different from a phase that
    commits to a heading and happens to clear a latch: the first falls
    through to the next phase carrying the latches it was given, the
    second ends the search.  A phase that declines can still change the
    latches -- an abandoned merge is exactly that -- which is why
    declining is reported as ``(None, latches)`` from the helpers below
    rather than as a bare ``None`` that would lose the update.
    """

    heading: _Heading
    latches: _Latches


# What one phase answers before ``_choose_heading`` sorts it out: the
# decision if it made one, and the latches either way.  The pair is not a
# ``_Steer | None`` because a phase that declines may still have written
# a latch off (a merge abandoned mid-approach), and that write has to
# survive into the next phase.
_Phase = tuple["_Heading | None", _Latches]


def _heading_leaving_merge(grid: _Grid, car: _Car, latches: _Latches) -> _Phase:
    """Phase 2 of a merge: hold straight until the new wall picks up.

    After turning onto the new road the car is not yet against that
    road's right-hand wall, so an ordinary hug would turn it straight
    back.  Keep going while both the right and ahead are open; the
    moment either closes, the wall has picked up and the latch is
    done.
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
    # A 'U' during the approach turns the car around, and the latch must
    # not wait forever for a cell it no longer visits: abandoning it here
    # is what keeps a divert from disabling junction detection for the
    # rest of the run (see
    # ``test_diverting_before_the_target_abandons_the_merge_latch``).
    if heading != merge.latched_heading:
        return None, latches._replace(merge=None)
    if car.at != merge.target:
        # Still approaching the lane where the turn will be made.
        # Hold the latched heading rather than letting an ordinary
        # right-hand hug peel the car away mid-approach -- the road
        # being joined is open on that side by definition, so the hug
        # would otherwise turn early and never reach the target.
        if _open_toward(grid, car, heading):
            return heading, latches
        return None, latches._replace(merge=None)

    latches = latches._replace(merge=None)
    # Re-read the branch condition here rather than trusting the
    # value the latch was taken under: the approach drives over
    # real cells, and an ``I`` or ``=`` along the way can change
    # what the CPth cell holds between detecting the junction and
    # arriving at the lane where the turn is actually made.  The
    # spec's choice is about the cell as the car *arrives* at the
    # turn (``arrival_cell``), not after this square's own
    # instruction has run: a square on the turning lane commonly
    # sets CP up for the road being taken, and that preparation
    # must not double as the decision of which road to take.
    # The roads were established at detection time (the mouth now
    # lies alongside or behind the car, so it no longer
    # re-detects): the choice is between the latched turn and
    # carrying straight on, ordered as they were then.
    # Rank the latched turn against carrying straight on in the
    # same left-to-right order the junction was read in, so the
    # re-read cannot silently disagree with the original choice
    # about which road is "leftmost".  The latch is only ever set
    # under a turn away from ``latched_heading``, so the two roads
    # are always distinct.
    # A *side* mouth is re-read at the turning square: the car
    # drove the approach as ordinary road, so the cell it finds
    # there is the one the spec's choice is about.  A *crossing*
    # mouth was decided at the mouth itself -- the car was level
    # with both ``+`` when it chose -- and the run out to the far
    # lane is only lane positioning for a road already taken.
    # Re-reading there lets an instruction on the positioning run
    # (a ``^`` on the way to the lane) overturn a choice that was
    # already made, which is the same "preparation must not double
    # as the decision" the arrival read exists to prevent.
    if not merge.crossing:
        # Left-to-right as the driver sees it: a left turn comes
        # before carrying straight on, a right turn after.  The
        # latch stores which of the two it is, so this ordering is
        # read off the record rather than recomputed from the
        # headings -- the comparison that used to stand here was a
        # second spelling of the same fact, free to disagree.
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
    ran, which is the read the spec's choice is about here (unlike the
    arrival read phase 1 uses); it is passed rather than fetched so this
    rule needs no tape to answer.
    """
    heading = car.heading
    order = [_left(heading), heading, _right(heading)]
    options = [h for h in order if _open_toward(grid, car, h)]
    if len(options) < 2 or not _junction_kind(grid, car):
        return None, latches

    roads = _junction_choices(grid, car)
    # A junction that fired (see ``_junction_kind``) always offers
    # at least two roads: a mouth on either side counts alongside
    # straight ahead, and a crossing mouth counts the open sides.
    new_heading = roads[0] if current_cell == 0 else roads[1]
    turning = new_heading != heading
    # A turn's destination is open by construction, so there is no
    # "sighted too early" case left to defer here.  There was one: a
    # mouth anchors its near ``+`` up to a cell ahead, so a junction can
    # fire before the car is level with the gap, and the turn then
    # stepped into the wall the mouth opens through (fixed in 701de45 by
    # a guard at this point).  What retired the guard was ``_road_deep``
    # (fc58258): every road ``_junction_choices`` offers now passes
    # either ``_road_deep``, whose first test is that very cell, or --
    # on the crossing branch -- ``_open_toward`` directly.  The guard's
    # condition became unsatisfiable, which is why it carried a
    # ``no cover`` pragma and why deleting it moves no drive-state graph
    # over the corpus.  Searched for a witness before removing it: none
    # in 857 corpus programs (including 701de45's own fixture) nor in
    # 3.6M brute-forced (grid, car) states.  ``_road_deep`` is where this
    # is enforced; keep the first-cell test in it.
    #
    # Lane merging applies only to a turn onto a detected side road:
    # continuing straight is not a turn at all, and a road whose
    # mouth is not bounded by real wall arms has no lanes to land in.
    if turning and _crossing_mouth(grid, car):
        # Emerging head-on from a branch onto the road it joins: the
        # car has to cross that road to its far lane before turning,
        # for the same reason a side-on turn merges -- "drive on the
        # right-hand side" applies to the road being joined too.  Run
        # on until the wall ahead stops it, then turn.
        target = car.at
        d_row, d_col = _DELTA[heading]
        while grid.open_at(target[0] + d_row, target[1] + d_col):
            target = target[0] + d_row, target[1] + d_col
        # ``_crossing_mouth`` guarantees the cell straight ahead is
        # open, so the loop above always advances at least one cell.
        return None, latches._replace(
            merge=_Merge(
                target_row=target[0],
                target_col=target[1],
                turn=_turn_of(heading, new_heading),
                latched_heading=heading,
                crossing=True,
            )
        )
    # The mouth is looked up once and handed to both helpers: each used
    # to re-find it and guard against a miss the other had already ruled
    # out, so the lookup and the guard were both duplicated.
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
        # Carrying straight on past a side road: suppress the hug
        # for exactly as many cells as that road's mouth is wide,
        # so the car drives past the branch it just declined
        # instead of being steered into it a step later -- and no
        # further, so the turn immediately after the mouth (which
        # is an ordinary corner, not the declined road) still
        # happens.  The same mouth can be detected from more than
        # one cell as the car approaches, so the countdown is only
        # ever extended, never restarted shorter.
        declined = [h for h in roads if h != heading]
        mouth = _road_mouth(grid, car, declined[0])
        if mouth is not None and mouth.near <= 0:
            # Suppress the hug across the mouth, but only when the
            # gap opens immediately beside the car (``near <= 0``)
            # -- those are the cells where the fallen-away wall
            # would otherwise steer it into the road it just
            # declined.  When the gap starts further ahead,
            # ordinary wall-following still holds the car against
            # the wall until it arrives, and by then the junction
            # is behind it, so nothing needs suppressing.
            latches = latches._replace(skip_hug=max(latches.skip_hug, mouth.width))
    return new_heading, latches


def _heading_from_hug(grid: _Grid, car: _Car, latches: _Latches) -> _Phase:
    """Ordinary right-hand wall-following, the default movement rule."""
    heading = car.heading
    if latches.skip_hug > 0:
        # Drive past the declined branch: keep going straight rather than
        # hugging the wall that has fallen away beside the car.  A wall
        # straight ahead still turns the car -- rounding a corner is not
        # the same as being pulled into the road it chose against -- but
        # the countdown carries on so the rest of the mouth stays skipped.
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

    Ordinary movement hugs the wall on the right; a detected
    intersection instead applies the spec's leftmost/second-leftmost
    rule among the open non-backward directions -- except when the
    junction is wide enough that the chosen road has its own lanes, in
    which case the car first drives (via plain wall-following) to the
    right-hand lane of the road it is turning onto, and after turning
    keeps driving straight until that new road's right-hand wall
    actually picks up, before resuming ordinary wall-following (see
    :class:`_Merge`, :class:`_Latches` and ``docs/streetcode.md``).
    Both latches are abandoned -- falling back to plain wall-following
    -- the moment anything about the approach stops matching what was
    latched: a heading change (e.g. a 'U') during the approach, or a
    wall exactly at the cell the latch would otherwise step onto.

    The tape enters as two ints and nothing more.  ``arrival_cell`` is
    the CPth cell as the car arrived at this square, before the square's
    own instruction ran, and ``current_cell`` is that cell after it ran;
    the merge re-read branches on the first and the junction rule on the
    second (an ``=`` on a turning square moves CP between them).  Those
    are the only two tape reads movement makes, which is why the whole
    rule can be a function of the grid, the car and two integers -- and
    why the drive-state graph can enumerate it by trying both bits.

    The work is four phases, each answering a heading to commit to or
    ``None`` to fall through to the next, and each threading the latches
    on: leaving a merge, arriving at or approaching a latched merge
    target, deciding a junction, and finally ordinary right-hand hugging.
    Returns ``None`` only when every phase declines, which means the car
    has run out of road.
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

    The whole movement semantics in one function: given the drawing, a
    driving state and the two tape bits movement is allowed to read, this
    says where the car ends up.  Nothing else is consulted and nothing is
    written, so the same arguments always give the same answer -- which
    is what lets :meth:`_Machine._drive_states` enumerate the entire
    reachable space by calling it, and :meth:`_Machine.step` replay the
    result.

    ``;`` and ``U`` are movement too, and are handled here rather than
    left to the caller: ``;`` stops the car deliberately (``"halt"``),
    and ``U`` reverses it and slides it into the lane now on its right,
    clearing every latch keyed to the old heading.  ``None`` is the car
    running out of road, which :meth:`_Machine._validate_total` rejects a
    street for; it is deliberately not the same answer as ``"halt"``,
    because a wedged street and a legal stop are different facts.

    Only movement is modelled.  The instruction on the square is not run,
    so the value-dependent halts -- ``_`` at CP 0, ``O`` on a cell that is
    not a code point, ``I`` at end of input -- are runtime semantics this
    deliberately does not predict; they stay with the tape and the I/O in
    :meth:`_Machine.step`.
    """
    car = state.car
    op = grid.op_at(car.row, car.col)
    if op == "HALT":
        return "halt"
    if op == "TURN":
        reversed_car = car.facing(_opposite(car.heading))
        lane = reversed_car.ahead(_right(reversed_car.heading))
        # A street with no opposite lane is the late-detected width
        # violation ``step`` raises ``HaltError`` for; it is not a
        # state the car drives on to.
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
    ``docs/streetcode.md``; ``halted`` is true once ``;`` runs or
    the car reaches a true dead end with nowhere left to go.  The VM and the
    state-cycle hang detector expose this object.

    This class is deliberately the *only* mutable thing in the module.
    The movement rules -- the mouth and junction detectors, the four
    steering phases, and the :func:`_drive` transition that composes them
    -- are module-level functions of the drawing, a :class:`_Car` and the
    two tape bits movement may read; they return a new :class:`_State`
    rather than moving anything.  What is left here is the run: the tape,
    CP, the I/O, and the car's current position, which ``step`` advances
    by handing the current state to those functions and storing what
    comes back.  Effects and geometry no longer share a body, so a
    question about the junction rules can be answered by reading
    functions that have no machine to consult.
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
        # The whole of the machine's steering state, as the one record the
        # movement rules speak in: where the car is, which way it points,
        # and the three latches the steering phases carry between steps.
        # ``step`` hands this to :func:`_drive` and stores back what comes
        # out, so the value looked up in the drive-state graph is the
        # machine's own rather than one assembled to match it.
        #
        # The latches (see :func:`_choose_heading` and :class:`_Latches`):
        # ``merge`` is set when a junction turn is detected but not yet
        # reached (phase 1, driving to the new road's lane before
        # turning); ``merging_heading`` is set after that turn while the
        # new road's right-hand wall has not yet picked up (phase 2,
        # suppressing the immediate right-hand-hug re-turn).  Both are
        # ``None`` outside an in-progress merge.  ``skip_hug`` counts
        # steps of ordinary right-hand hugging still to be suppressed
        # after a junction chose to carry straight on past a side road:
        # the declined road's mouth is open ground exactly where the hug
        # looks, so without it the car would be steered into the road it
        # just chose against on the very next step.
        self._state = _State(
            *starts[0], _initial_heading(self.grid, starts[0]), _NO_LATCHES
        )
        self.cp = 0
        self.cells: dict[int, int] = {}
        self._done = False
        # The enumerated drive-state graph, or ``None`` when there is no
        # graph to consult: a program whose geometry is not a street
        # (``_validate_width`` exempts those) or one whose validation the
        # interpreter's own fixtures have patched out.  ``step`` calls
        # :func:`_drive` directly in that case -- the same function that
        # filled the graph, so the answer does not depend on which way it
        # was reached.
        self._graph: dict[_State, _Edges] | None = None
        # Last, because ``_validate_total`` drives the real movement rules
        # over the grid and so needs every field they touch to exist.
        self._validate(starts[0])

    @property
    def halted(self) -> bool:
        """Whether the car has halted."""
        return self._done

    # Where the car is, as read-only views onto the one record that holds
    # it.  They are reads and not writes on purpose: a caller that wants
    # to *move* the car states the whole position at once through
    # :meth:`place`, so a machine can never be left holding two of the
    # three coordinates from one place and the third from another.

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

        For a caller that needs to drive a machine from somewhere other
        than the square its ``C`` is on: the interpreter's own fixtures
        do this to reach a geometry that a whole program would take many
        steps to arrive at.  It is one call rather than three assignments
        because the three coordinates only mean anything together --
        assigning them separately left the machine briefly holding a
        position that was half of one place and half of another, and
        nothing but ordering stopped a caller from forgetting the third.

        The latches are deliberately left alone: a test that places a car
        *and* sets up a merge wants both, and clearing them here would
        silently undo half of what it asked for.
        """
        self._state = self._state._replace(row=row, col=col, heading=heading)

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection.

        Every attribute the machine carries between steps appears here, so
        two equal snapshots really do have equal futures.  Per-step values
        are deliberately not attributes at all -- the arrival cell is
        passed to :func:`_choose_heading` as a parameter -- and everything
        that steers enters as the single :class:`_State` record, so a
        latch added later is carried here without this method being
        touched, rather than drifting out of the snapshot the way a
        separate attribute could.

        ``_done`` matters even though a halted machine takes no further
        steps: ``;`` halts without moving the car, so the states either
        side of it agree on every other field, and leaving the flag out
        made the halt look like a repeat of the step before it.
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
        self.cells[self.cp] = value

    def _block(self, cell: _ReachableCell) -> tuple[str, ...]:
        """Return the three-by-three neighbourhood around a reachable cell.

        Unlike an ordinary ``grid[row, col]`` this does not bounds-check
        the eight reads.
        What makes that sound is :meth:`_validate_enclosed`, which has
        already rejected any street whose road touches the border, so a
        cell reaching here has all eight neighbours on the grid.  The
        ``_ReachableCell`` type records where the cell came from; the
        precondition below states the property that actually matters,
        and is what fails if the fill ever yields a border cell.
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

        A driving state is a position, a heading and the three latches
        the steering phases carry between steps -- exactly the movement
        half of :meth:`snapshot`, minus the tape, CP and I/O, which do not
        steer.  The geometry is static, so the successors of a state
        depend on nothing else: the search enumerates the whole space by
        breadth-first search from the car's start, and it terminates
        because positions, headings and latch values are all finite.

        Each state maps to its successors keyed by the pair of branch
        bits that produce them.  Movement reads the tape at exactly two
        places, both testing ``== 0`` -- :func:`_heading_from_merge_target`
        on the arrival cell (as the car arrived, before this square ran)
        and :func:`_heading_from_junction` on the current one (after it
        ran, since an ``=`` on a turning square moves CP between the two
        reads).  A step can consume both, so each state is probed with
        all four combinations; because both sites test only zero-ness,
        the two bits cover every tape the car could hold, and the map is
        exhaustive rather than a sample.  A ``None`` successor is a state
        the car cannot drive out of.

        The search calls :func:`_drive` on each state directly.  It used
        to have to *become* each state instead -- saving the car, CP,
        tape and latches, moving the machine to the state being probed,
        running the rules for their side effects, and putting everything
        back afterwards -- because the rules only knew how to read the
        machine they were attached to.  With movement a function of its
        arguments there is nothing to save: the probe cannot disturb a
        car it was never given.
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

        What this can actually catch is narrower than "dead ends", and
        worth stating plainly.  :meth:`_heading_from_hug` falls back
        through all four directions including the reverse, and a
        validated street is connected with at least two cells, so every
        reachable cell has an open neighbour and the hug cannot return
        ``None``.  Ordinary wall-following is therefore total by
        construction, not by this search.  That leaves exactly one
        class of program for the check to reject today -- a reachable
        ``U`` whose opposite lane is walled, which promotes the runtime
        ``HaltError`` the module contract documents to a construction-
        time :class:`ValueError` -- and a regression net over the
        movement phases, which is the rest of its value.  A brute force
        over 137472 small walled grids found none that only this check
        rejects, which is consistent with that: those grids are plain
        corridors, where totality is the theorem above rather than
        something a search discovers.

        It is still stronger than running the program: it covers every
        reachable state under both branch conditions, including the
        arms a particular input never takes.  What it does not cover is
        the value-dependent halts (see :func:`_drive`), which are
        runtime semantics rather than geometry.
        """
        self._graph = self._drive_states(start)
        for state, edges in self._graph.items():
            # ``;`` reports itself as ``"halt"`` rather than ``None``, so a
            # deliberate stop no longer has to be told from a wedge by
            # re-reading the square: ``None`` now means only the one thing.
            if any(successor is None for successor in edges.values()):
                raise ValueError(
                    f"the car cannot drive out of {(state.row, state.col)} heading"
                    f" {state.heading}: the street is a dead end with no ';'"
                )
            self._check_state_invariants(state, edges)

    def _check_state_invariants(self, state: _State, edges: _Edges) -> None:
        """Assert what must hold of a drive state under any reading of the spec.

        The movement rules were reverse-engineered from the wiki's
        examples and several of them remain judgement calls (see the
        module docstring).  These are not: a car inside a wall, or one
        that teleports rather than driving a cell at a time, is wrong
        under every reading, so they can be checked outright rather than
        interpreted.  Keeping them apart from the geometry rules is the
        point -- a rule that might be misread should not be asserted,
        and one that cannot be misread should not be left to a test.

        The bug ``701de45`` fixed is the worked example: a junction fired
        while its gap still opened a cell ahead, and the turn drove the
        car *inside* the wall the mouth opens through, after which it
        wall-followed along the wall's far side.  That was found by
        hand-drawing a program and watching the car misbehave; here it is
        a construction-time failure naming the square.

        These are :class:`AssertionError` rather than :class:`ValueError`
        because they do not describe a malformed program.  The validators
        around them reject bad *drawings*; a breach here means the
        movement rules disagree with the grid they are driving on, which
        is a bug in this module -- the same distinction :meth:`step`
        draws when a ``None`` edge survives the totality check.
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
        # step (see :meth:`_heading_from_merge_target`), so its target is
        # stale by construction and describes no geometry to check.
        if merge is None or state.heading != merge.latched_heading:
            return
        if not self.grid.open_at(merge.target_row, merge.target_col):
            raise AssertionError(
                f"the merge latched at {(state.row, state.col)} is driving to"
                f" {merge.target}, which is not open floor:"
                f" {self.grid[merge.target_row, merge.target_col]!r}"
            )
        # The approach does not change lane, so the target sits straight
        # ahead along the latched heading -- never off to one side, and
        # never behind a car that can only drive forwards onto it.
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

        The spec requires streets to be two-way, two characters wide; a street
        that is only one cell wide has no opposite lane for ``U`` to end in.
        The check is static and runs before the car moves, so a malformed
        program fails fast with :class:`ValueError` rather than a late
        :class:`~esolangs.exceptions.HaltError` at the first ``U``.

        The geometry is static, so width can be read off the grid: a corridor
        cell that has open neighbours directly opposite (N+S or E+W) must have
        an open neighbour on at least one perpendicular side (the second lane);
        a dead-end cell with a single open neighbour must also have a
        perpendicular open neighbour. Isolated single cells and grids with no
        walls are not streets and are exempt.

        Note that a blank row or column is a lane: space is a drivable no-op,
        so an instruction row paired with a blank row is a legal two-wide
        street.

        The upper bound is enforced too: a street wider than two lanes is
        rejected.  Cross-section runs cannot measure this -- where two legal
        two-wide streets cross, a run through the intersection reports the
        *length* of the crossing street, not any width -- so the rule is a
        fully open three-by-three block instead.  A region wider than two in
        both directions must contain one; a two-wide network never does,
        because a crossing is a plus whose open centre is two-by-two with
        walls at the diagonal corners.  A three-by-two room therefore passes:
        it is a two-wide street of length three seen sideways, which is the
        deliberate boundary of the rule.
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
                # No bounds test: off the grid is not open (see ``_Grid``),
                # so the fill cannot walk out of the drawing.
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
        a raise, so the same statement of it can be asked as a question --
        after the fact, or of a grid the validator has not seen -- without
        a second implementation free to drift from this one.  The message
        is the one the validator raises with.
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

        Width alone does not catch every malformed drawing: a wall with a
        one-cell hole punched through it (``-- --``) leaves a gap too narrow
        to drive, yet the corridor either side of it still measures two
        wide.  So each reachable cell's three-by-three neighbourhood must
        match one of the forms in ``_WALL_FORMS`` -- a corner, a wall
        running alongside, or a lone wall character at a corner -- up to
        rotation.  A neighbourhood with no wall in it is open road and is
        trivially legal.

        The forms are deliberately permissive at their edges.  The ``?``
        ends of the wall form let a wall simply stop, and the intersection
        form admits any wall character at the corner rather than only
        ``+``: together these leave open a question the wiki does not
        settle, whether a road divider must terminate in a ``+``.  The
        hello-world example leaves its divider ends bare and runs
        correctly, and nothing in the driving rules keys on the
        difference, so the shape is accepted.  What the forms do reject is
        the hole, whose cell has wall on two opposite sides and open
        ground on the other two, matching no form.

        The neighbourhood is read by :meth:`_block`, which does not
        bounds-check.  That is sound only because :meth:`_validate`
        runs :meth:`_validate_enclosed` first, so a road touching the
        border has already been rejected and every cell here has all
        eight neighbours on the grid.  The ``_ReachableCell`` argument
        type carries that provenance; the ordering in :meth:`_validate`
        is what establishes it, and moving this check ahead of the
        enclosure one would break the read.

        Only the cells reachable from ``C`` are checked, as in
        :meth:`_validate_width`.  Walls do not move and the car cannot
        teleport, so a cell the search does not reach is one the car can
        never drive: the ``ljust`` padding around a program, and the
        background around an L-shaped layout, are drawing, not street.
        Whether a program should consist of one connected block at all is
        a separate question this check does not try to answer.
        """
        for cell in reachable:
            r, c = cell
            block = self._block(cell)
            # A street is two cells wide, so every reachable cell has a wall
            # within one of it; a wall-free neighbourhood means an interior
            # wider than two, which the width check has already rejected.
            if not any(ch in _WALLS for ch in block):  # pragma: no cover
                continue
            # The two-wide check runs first and rejects every malformed
            # shape found so far -- a wall that stops short leaves a
            # one-wide stub, which it catches as a dead end.  This stands
            # as the independent check the forms were written to be.
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
        touches the border of the grid: there is always a wall between it
        and the outside.  If the flood fill from ``C`` reaches the border,
        the road has escaped -- through a hole in a wall, or because a
        wall was never drawn at all -- and what lies beyond is the blank
        padding around the program rather than street.

        This is what catches a hole two cells across.  A one-cell hole is
        already caught by width, since squeezing through it leaves a
        one-wide stub, but a two-wide hole is a legal-width passage and
        looks like an ordinary road: only the fact that it leads off the
        grid marks it as a gap rather than a street.
        """
        violation = self._enclosure_violation(reachable)
        if violation is not None:
            raise ValueError(violation)

    def _enclosure_violation(self, reachable: set[_ReachableCell]) -> str | None:
        """Name a road cell on the grid's border, or ``None`` if none is.

        The property :meth:`_block` depends on, stated once so that the
        read's precondition and this check cannot disagree about where the
        border is.
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

        The two wall glyphs mean different things: ``-`` is a wall running
        horizontally, ``|`` one running vertically.  Where they meet, the
        wall turns a corner, and a corner is drawn ``+``.  So a ``-``
        immediately left or right of a ``|``, or a ``|`` immediately above
        or below a ``-``, is a wall changing direction without the corner
        that marks it -- a drawing slip rather than a shape.

        This is about which glyph is used, not where walls are, so the
        neighbourhood forms in :meth:`_validate_walls` cannot see it: they
        match any wall character alike.  Neither example, neither wiki
        diagram, nor any of the generated programs draws such a pair.
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
        road the car can reach or a wall bounding that road.  Take the
        reachable open cells, grow the region by one cell in every
        direction so that it takes in the walls along its edges, and
        remove it from the grid.  Whatever is still drawn belongs to no
        street, and the program is malformed -- a detached second box, a
        stray fragment of wall, an instruction sealed inside an island
        where the car can never drive it, or the middle of a solid block
        of wall, which is ink bounding nothing.

        A hollow island is still legal, and needs no special case: the
        car drives around the block, and every cell of a one-thick wall
        is within one step of the road outside it, so the growth takes
        the whole island in.  Only a block thick enough to have an
        interior falls outside, which is the case being rejected.
        Whether such a block should be legal is a question the wiki does
        not settle; unlike an uncapped divider end, permitting it would
        cost a second flood-fill pass to tell an enclosed hole from the
        outside, and no program the repo draws needs it.

        Only non-blank cells count.  The blank padding ``ljust`` adds to
        square off a ragged program, and the background around an
        L-shaped layout, are not drawn geometry and are ignored -- which
        is what lets the boolean example, whose hallways leave large
        blank margins, pass while a detached wall does not.

        The rule is strict: any character off the street is rejected, not
        only walls.  Restricting it to walls would cost no detection --
        a detached box and a stray fragment are both drawn out of walls
        -- and would let the remaining text stand as comments, since the
        car treats anything that is not ``+``, ``-`` or ``|`` as a no-op
        and off the street it can never execute anyway.  The wiki says
        nothing about comments either way.  That alternative is left
        unimplemented: a program that contains stray marks is more likely
        drawn wrong than annotated, and nothing in the repo needs them.
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

        # The driving state as the car arrives, for the graph lookup below.
        # Read into a local because an instruction moves CP and the tape
        # but never the car, its heading or the latches, and ``U`` returns
        # before the lookup; so this is still the state when the lookup
        # happens.  It is the machine's own record, not one rebuilt from
        # separate fields to match what the graph is keyed by.
        state = self._state

        # The cell as the car arrives, before this square's instruction runs.
        # A junction decision is about the road the car is arriving at, so it
        # branches on this rather than on whatever the square itself does to
        # the tape: the ``=`` painted on a turning square moves CP to set up
        # the road ahead, and must not also decide which road that is.  It is
        # a per-step value, so it is passed to ``_choose_heading`` rather than
        # kept on the machine, where it would look like part of the state the
        # cycle detector snapshots.
        arrival_cell = self._cell()

        if op == "INC":
            self._set_cell(self._cell() + 1)
        elif op == "DEC":
            self._set_cell(self._cell() - 1)
        elif op == "RIGHT":
            self.cp += 1
        elif op == "LEFT":
            if self.cp == 0:
                raise HaltError
            self.cp -= 1
        elif op == "IN":
            value = self.io.input_str()
            self._set_cell(ord(value[0]) if value else 0)
        elif op == "OUT":
            try:
                self.io.print_char(chr(self._cell()))
            except ValueError:
                raise HaltError from None
        elif op == "TURN":
            # Streets are two-way and two wide, and the car drives on the
            # right: after turning around, the lane it belongs in is the
            # one now on its right, so the U-turn ends there -- that slide
            # is this step's movement, and the lane cell is executed next
            # step like any cell the car drives onto.  Turning in place
            # would leave the car in the oncoming lane, driving on the
            # left, and the right-hand hug then "corrects" that with two
            # right turns -- back onto the original heading one lane over,
            # cancelling the U-turn.  The heading changed, so every latch
            # keyed to the old one is void.
            #
            # The manoeuvre itself is :func:`_drive`, which models ``U``
            # because the drive-state search has to predict it too; going
            # through it here is what keeps the run and the graph agreeing
            # about where a U-turn ends, rather than two spellings free to
            # drift.  A street with no opposite lane is narrower than the
            # spec allows, so there is nowhere legal to end the turn: the
            # rule answers ``None``, and that is a malformed street met at
            # runtime rather than a manoeuvre with a sensible fallback.
            turned = _drive(self.grid, state, arrival_cell, arrival_cell)
            if turned is None or turned == "halt":
                raise HaltError
            self._state = turned
            return
        elif op == "NOP":
            # ``C``, space, and every character the spec does not define all
            # fold to NOP (see ``_Op``), so there is nothing to do.  Spelling
            # it out rather than falling through lets the ``else`` below be
            # the type checker's exhaustiveness proof.
            pass
        else:
            # Unreachable, and checked to be: ``HALT`` returned above and the
            # arms exhaust the rest of ``_Op``, so mypy narrows this to
            # ``Never``.  A glyph added to ``_Op`` without an arm here fails
            # the type check rather than silently behaving as a no-op.
            assert_never(op)

        # Where the car goes next was worked out for every reachable state
        # at construction, so the ordinary case is a dictionary lookup
        # rather than a re-run of the mouth scans and junction rules.  The
        # two branch bits are the same two reads :func:`_choose_heading`
        # makes -- the arrival cell and the cell after this square ran --
        # and only their zero-ness is asked for, because those are the
        # only tests movement applies to them (see :meth:`_drive_states`).
        #
        # A miss falls through to :func:`_drive`, which is what filled the
        # graph in the first place: a machine whose geometry is not a
        # street has no graph to consult, and a test can set a heading or
        # a latch by hand and reach a state the search never enumerated.
        # Cached or computed, the answer is the same function of the same
        # arguments -- the lookup is a memo of :func:`_drive`, not a
        # second implementation that could drift from it.
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
            # ``_validate_total`` rejects a street with a wedged state,
            # so reaching one here means the graph and the validator
            # disagree -- a bug in this module rather than a program
            # that stops.  Halting quietly would hide it and hand back
            # a truncated run as though it were the answer.
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
