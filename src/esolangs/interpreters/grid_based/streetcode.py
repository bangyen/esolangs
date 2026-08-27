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
from typing import Literal

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

# An in-progress lane merge: the cell the car must reach, the heading it
# will turn to there, the heading the latch was taken under (so a turn in
# between voids it), and whether it came from a crossing mouth.  ``None``
# outside a merge.  See ``_Machine.__init__``.
_Merge = tuple[int, int, _Heading, _Heading, bool] | None

# The movement half of a machine's state: where the car is, which way it
# points, and the three latches ``_choose_heading`` carries between steps.
# The tape, CP and I/O are deliberately absent -- they do not steer, and
# leaving them out is what makes the state space finite and small enough
# to enumerate (see ``_Machine._drive_states``).
_State = tuple[int, int, _Heading, _Merge, _Heading | None, int]
# A state's successors, keyed by the two branch bits movement can read in
# one step: the arrival cell and the post-instruction cell, in that order.
_Edges = dict[tuple[int, int], "_State | None"]

_HEADINGS: tuple[_Heading, ...] = ("N", "E", "S", "W")
_DELTA: dict[_Heading, tuple[int, int]] = {
    "N": (-1, 0),
    "E": (0, 1),
    "S": (1, 0),
    "W": (0, -1),
}
_WALLS = frozenset("+-|")

# How far perpendicular to the direction of travel ``_road_mouth`` looks for
# the wall a side road opens through: a two-way street is two cells wide, so
# the far lane's wall can sit two cells out, and 3 covers that with a cell to
# spare.
_MOUTH_MAX_DIST = 3
# How far along the direction of travel ``_road_mouth`` will look for the
# ``+`` closing a road's mouth.  Sweeping the value against the test suite
# puts the floor at 5 -- at 4 the mouths of the wider drawn junctions stop
# being seen and three tests fail -- while 5 and up are indistinguishable.
# 7 is that floor plus slack for mouths wider than anything drawn so far;
# nothing depends on the exact value above 5.
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


def _right(heading: _Heading) -> _Heading:
    """Return the heading 90 degrees clockwise from ``heading``."""
    return _HEADINGS[(_HEADINGS.index(heading) + 1) % 4]


def _left(heading: _Heading) -> _Heading:
    """Return the heading 90 degrees counter-clockwise from ``heading``."""
    return _HEADINGS[(_HEADINGS.index(heading) - 1) % 4]


def _opposite(heading: _Heading) -> _Heading:
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
        # silently misapplying a stale turn.  The fifth records whether the
        # latch came from a crossing mouth, which decides whether the branch
        # condition is re-read on arrival; carrying it inside the latch keeps
        # the two from drifting apart and keeps ``snapshot`` complete.
        self._merge_target: _Merge = None
        self._merging_heading: _Heading | None = None
        # Steps of ordinary right-hand hugging still to be suppressed after a
        # junction chose to carry straight on past a side road.  The declined
        # road's mouth is open ground exactly where the hug looks, so without
        # this the car would be steered into the road it just chose against
        # on the very next step.  Counted down once per step and cleared by
        # any heading change.
        self._skip_hug = 0
        # Last, because ``_validate_total`` drives the real movement rules
        # over the grid and so needs every field they touch to exist.
        self._validate(starts[0])

    @property
    def halted(self) -> bool:
        """Whether the car has halted."""
        return self._done

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection.

        Every attribute the machine carries between steps appears here, so
        two equal snapshots really do have equal futures.  Per-step values
        are deliberately not attributes at all -- the arrival cell is passed
        to ``_choose_heading`` as a parameter -- and the merge latch carries
        its crossing flag inside the tuple, so neither can drift out of the
        snapshot the way a separate attribute could.

        ``_done`` matters even though a halted machine takes no further
        steps: ``;`` halts without moving the car, so the states either
        side of it agree on every other field, and leaving the flag out
        made the halt look like a repeat of the step before it.
        """
        return (
            self.row,
            self.col,
            self.heading,
            self.cp,
            tuple(sorted(self.cells.items())),
            self.io.position(),
            self._done,
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

    def _ahead(self, row: int, col: int, heading: _Heading) -> tuple[int, int]:
        d_row, d_col = _DELTA[heading]
        return row + d_row, col + d_col

    def _step_to(self, heading: _Heading) -> tuple[int, int]:
        """Return the cell one step from the car along ``heading``."""
        return self._ahead(self.row, self.col, heading)

    def _open_toward(self, heading: _Heading) -> bool:
        """Whether the cell one step from the car along ``heading`` is open."""
        return self._open(*self._step_to(heading))

    def _initial_heading(self) -> _Heading:
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

        A driving state is a position, a heading and the three latches
        ``_choose_heading`` carries between steps -- exactly the movement
        half of :meth:`snapshot`, minus the tape, CP and I/O, which do not
        steer.  The geometry is static, so the successors of a state
        depend on nothing else: the search enumerates the whole space by
        breadth-first search from the car's start, and it terminates
        because positions, headings and latch values are all finite.

        Each state maps to its successors keyed by the pair of branch
        bits that produce them.  Movement reads the tape at exactly two
        places, both testing ``== 0`` -- ``_heading_from_merge_target``
        on the ``arrival_cell`` parameter (the cell as the car arrived,
        before this square ran) and ``_heading_from_junction`` on
        ``_cell()`` (after it ran, since an ``=`` on a turning square
        moves CP between the two reads).  A step can consume both, so
        each state is probed with all four combinations; because both
        sites test only zero-ness, the two bits cover every tape the car
        could hold, and the map is exhaustive rather than a sample.
        A ``None`` successor is a state the car cannot drive out of.

        The probe runs on this machine, so it saves and restores every
        field it disturbs: ``__init__`` calls this before it has set the
        real heading, and the car must be left exactly where the search
        found it.
        """
        saved = (
            self.row,
            self.col,
            self.heading,
            self.cp,
            self.cells,
            self._merge_target,
            self._merging_heading,
            self._skip_hug,
        )
        graph: dict[_State, _Edges] = {}
        # ``_initial_heading`` reads only the grid and the start, so it is
        # safe to call here, before ``__init__`` assigns ``self.heading``.
        self.row, self.col = start
        origin: _State = (*start, self._initial_heading(), None, None, 0)
        pending = [origin]
        graph[origin] = {}
        while pending:
            state = pending.pop()
            edges = graph[state]
            for arrival in (0, 1):
                for current in (0, 1):
                    successor = self._probe(state, arrival, current)
                    edges[arrival, current] = successor
                    if successor is not None and successor not in graph:
                        graph[successor] = {}
                        pending.append(successor)
        (
            self.row,
            self.col,
            self.heading,
            self.cp,
            self.cells,
            self._merge_target,
            self._merging_heading,
            self._skip_hug,
        ) = saved
        return graph

    def _probe(self, state: _State, arrival: int, current: int) -> _State | None:
        """Return the state one step on from ``state`` under two branch bits.

        Drives the real movement rules rather than a second copy of them:
        the geometry was reverse-engineered from the wiki's examples and
        has open questions (see the module docstring), so a re-derivation
        here would be a second interpretation free to disagree with the
        one that runs.  ``;`` and ``U`` are handled by :meth:`step`
        rather than :meth:`_choose_heading`, so they are modelled here
        too: ``;`` halts deliberately and has no successor, and ``U``
        reverses and slides into the lane now on the right.

        Only movement is modelled.  The instruction on the square is not
        run, so the value-dependent halts -- ``_`` at CP 0, ``O`` on a
        cell that is not a code point, ``I`` at end of input -- are
        runtime semantics this search deliberately does not predict.
        """
        row, col, heading, merge_target, merging, skip = state
        char = self.grid[row][col]
        if char == ";":
            return None
        if char == "U":
            reversed_heading = _opposite(heading)
            lane = self._ahead(row, col, _right(reversed_heading))
            # A street with no opposite lane is the late-detected width
            # violation ``step`` raises ``HaltError`` for; it is not a
            # state the car drives on to.
            if not self._open(*lane):
                return None
            return (*lane, reversed_heading, None, None, 0)

        self.row, self.col = row, col
        self.heading = heading
        self._merge_target = merge_target
        self._merging_heading = merging
        self._skip_hug = skip
        self.cp = 0
        self.cells = {0: current}
        new_heading = self._choose_heading(arrival)
        if new_heading is None:
            return None
        d_row, d_col = _DELTA[new_heading]
        # The latches the phases just wrote are part of the successor:
        # they are what the next step reads.
        return (
            row + d_row,
            col + d_col,
            new_heading,
            self._merge_target,
            self._merging_heading,
            self._skip_hug,
        )

    def _validate_total(self, start: tuple[int, int]) -> None:
        """Reject a street the car can drive into and not out of.

        Ordinary wall-following always finds somewhere to go -- a dead
        end reverses the car rather than stopping it -- so a state with
        no successor means the movement rules have run out of road
        somewhere the car can actually reach.  Only ``;`` halts a
        well-formed program.  :meth:`step` would meet this as a silent
        halt partway through a run, with nothing to say about where the
        street went wrong; the search finds it before the car moves and
        names the square.

        This is stronger than running the program: it covers every
        reachable state under both branch conditions, including the
        arms a particular input never takes.  What it does not cover is
        the value-dependent halts (see :meth:`_probe`), which are
        runtime semantics rather than geometry.
        """
        for state, edges in self._drive_states(start).items():
            row, col, heading = state[0], state[1], state[2]
            if self.grid[row][col] == ";":
                continue
            if any(successor is None for successor in edges.values()):
                raise ValueError(
                    f"the car cannot drive out of {(row, col)} heading"
                    f" {heading}: the street is a dead end with no ';'"
                )

    def _validate_width(self, start: tuple[int, int]) -> set[tuple[int, int]] | None:
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

        h, w = self.height, self.width
        sr, sc = start
        visited: set[tuple[int, int]] = set()
        q: deque[tuple[int, int]] = deque([(sr, sc)])
        visited.add((sr, sc))
        while q:
            r, c = q.popleft()
            for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                nr, nc = r + dr, c + dc
                if (
                    0 <= nr < h
                    and 0 <= nc < w
                    and self._open(nr, nc)
                    and (nr, nc) not in visited
                ):
                    visited.add((nr, nc))
                    q.append((nr, nc))
        # Isolated single cell is not a street
        if len(visited) <= 1:
            return None
        for r, c in visited:
            n = self._open(r - 1, c)
            s = self._open(r + 1, c)
            e = self._open(r, c + 1)
            w2 = self._open(r, c - 1)
            cnt = sum((n, s, e, w2))
            if cnt == 1:
                raise ValueError(f"not two-wide at {(r, c)} (dead end)")
            if n and s and not (e or w2):
                raise ValueError(f"not two-wide at {(r, c)} (vertical)")
            if e and w2 and not (n or s):
                raise ValueError(f"not two-wide at {(r, c)} (horizontal)")
            if all(self._open(r + dr, c + dc) for dr in (0, 1, 2) for dc in (0, 1, 2)):
                raise ValueError(f"not two-wide at {(r, c)} (wider than two)")
        return visited

    def _validate_walls(self, reachable: set[tuple[int, int]]) -> None:
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

        Only the cells reachable from ``C`` are checked, as in
        :meth:`_validate_width`.  Walls do not move and the car cannot
        teleport, so a cell the search does not reach is one the car can
        never drive: the ``ljust`` padding around a program, and the
        background around an L-shaped layout, are drawing, not street.
        Whether a program should consist of one connected block at all is
        a separate question this check does not try to answer.
        """
        for r, c in reachable:
            block = tuple(
                self._at(r + dr, c + dc) for dr in (-1, 0, 1) for dc in (-1, 0, 1)
            )
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

    def _validate_enclosed(self, reachable: set[tuple[int, int]]) -> None:
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
        for r, c in reachable:
            if r in (0, self.height - 1) or c in (0, self.width - 1):
                raise ValueError(
                    f"street reaches the edge of the grid at {(r, c)}:"
                    " the road is not enclosed by walls"
                )

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
        for r in range(self.height):
            for c in range(self.width):
                char = self.grid[r][c]
                if char == "-":
                    neighbours = ((r, c - 1), (r, c + 1))
                    other = "|"
                elif char == "|":
                    neighbours = ((r - 1, c), (r + 1, c))
                    other = "-"
                else:
                    continue
                for nr, nc in neighbours:
                    if self._at(nr, nc) == other:
                        raise ValueError(
                            f"wall turns without a corner at {(r, c)}:"
                            f" {char!r} beside {other!r} at {(nr, nc)}"
                        )

    def _validate_connected(self, reachable: set[tuple[int, int]]) -> None:
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
        grown = {
            (r + dr, c + dc)
            for r, c in reachable
            for dr in (-1, 0, 1)
            for dc in (-1, 0, 1)
        }
        for r in range(self.height):
            for c in range(self.width):
                char = self.grid[r][c]
                if char == " " or (r, c) in grown:
                    continue
                raise ValueError(
                    f"geometry not connected to the street at {(r, c)} ({char!r})"
                )

    def _road_mouth(
        self, heading: _Heading, side: _Heading
    ) -> tuple[int, int, int] | None:
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

    def _plus_dist(self, side: _Heading) -> int | None:
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

    def _crossing_mouth(self, heading: _Heading) -> bool:
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
        if not self._open_toward(heading):
            return False
        # Level with both `+` -- one step further and they are behind the car,
        # one step earlier and it has not reached the intersection yet.
        left, right = self._plus_dist(_left(heading)), self._plus_dist(_right(heading))
        return left is not None and right is not None and left != right

    def _junction_kind(self, heading: _Heading) -> _Junction:
        """Detect a real intersection ahead, returning the open-option count.

        A junction is a road mouth (see :meth:`_road_mouth`) opening off
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
        kind = self._junction_shape(heading)
        # A drawn junction is only a choice when at least two of the roads
        # it offers are roads the car could actually drive down (see
        # :meth:`_road_deep`); otherwise the shape is a bend or a lane
        # boundary, and ordinary wall-following handles it.
        return kind if len(self._junction_choices(heading)) >= 2 else 0

    def _junction_shape(self, heading: _Heading) -> _Junction:
        """Classify the wall shape alone, before the roads are counted."""
        ahead_open = self._open_toward(heading)
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

    def _lane_bounded(
        self, heading: _Heading, side: _Heading, mouth: tuple[int, int, int]
    ) -> bool:
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
        self, heading: _Heading, new_heading: _Heading, mouth: tuple[int, int, int]
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
        _, near, far = mouth
        d_row, d_col = _DELTA[heading]
        depth = far - 1 if _right(new_heading) == heading else near + 1
        # d_row/d_col is a unit vector with exactly one nonzero component;
        # that component picks out the travel-axis coordinate to advance,
        # while the perpendicular coordinate stays fixed at the car's own.
        if d_row:
            return self.row + depth * d_row, self.col
        return self.row, self.col + depth * d_col

    def _junction_choices(self, heading: _Heading) -> list[_Heading]:
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
            if crossing:
                # Driving out through a mouth head-on, the roads to either
                # side are the main road the branch joins.  That road runs
                # perpendicular to the car, so its extent cannot be probed
                # from inside the mouth (two cells out crosses it and hits
                # its far wall): take whichever way is open.
                if self._open_toward(side):
                    roads.append(side)
            elif self._road_deep(side) and self._lawful_turn(side):
                roads.append(side)
        return roads

    def _road_deep(self, heading: _Heading) -> bool:
        """Whether ``heading`` leads onto a road, rather than across one.

        Streets are two characters wide, so a direction with a single open
        cell before a wall is not a road the car can drive down: it is the
        street it is already on -- the oncoming lane alongside it, or the
        last cell of a bend before the wall turns.  Requiring two drivable
        cells is what distinguishes a road from the width of the road.
        """
        d_row, d_col = _DELTA[heading]
        return self._open(self.row + d_row, self.col + d_col) and self._open(
            self.row + 2 * d_row, self.col + 2 * d_col
        )

    def _lawful_turn(self, heading: _Heading) -> bool:
        """Whether entering ``heading`` leaves the car driving on the right.

        The lane a car belongs in has that road's wall on its right, so a
        turn whose destination has open ground to the right and a wall to
        the left would put the car in the lane oncoming traffic uses.  Such
        a turn is not a road the junction may offer, however open it looks:
        the spec's cars drive on the right-hand side.  A destination with
        walls on neither side is not yet inside a lane (an open room, or a
        junction's own floor) and is left to the ordinary rules.
        """
        d_row, d_col = _DELTA[heading]
        row, col = self.row + d_row, self.col + d_col
        right_row, right_col = self._ahead(row, col, _right(heading))
        left_row, left_col = self._ahead(row, col, _left(heading))
        wrong_side = self._open(right_row, right_col) and not self._open(
            left_row, left_col
        )
        return not wrong_side

    def _choose_heading(self, arrival_cell: int) -> _Heading | None:
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

        ``arrival_cell`` is the CPth cell as the car arrived at this
        square, before the square's own instruction ran; junction
        decisions branch on it rather than on the current value.

        The work is four phases, each returning a heading to commit to or
        ``None`` to fall through to the next: leaving a merge, arriving at
        or approaching a latched merge target, deciding a junction, and
        finally ordinary right-hand hugging.
        """
        for phase in (
            self._heading_leaving_merge,
            lambda: self._heading_from_merge_target(arrival_cell),
            self._heading_from_junction,
            self._heading_from_hug,
        ):
            heading = phase()
            if heading is not None:
                return heading
        return None

    def _heading_leaving_merge(self) -> _Heading | None:
        """Phase 2 of a merge: hold straight until the new wall picks up.

        After turning onto the new road the car is not yet against that
        road's right-hand wall, so an ordinary hug would turn it straight
        back.  Keep going while both the right and ahead are open; the
        moment either closes, the wall has picked up and the latch is
        done.
        """
        if self._merging_heading is None:
            return None
        heading = self.heading
        if self._merging_heading == heading and (
            self._open_toward(_right(heading)) and self._open_toward(heading)
        ):
            return heading
        self._merging_heading = None
        return None

    def _heading_from_merge_target(self, arrival_cell: int) -> _Heading | None:
        """Phase 1 of a merge: drive to the latched lane, then turn.

        Returns a heading while the approach is still running or when the
        turn is made, and ``None`` once the latch is spent or abandoned.
        """
        if self._merge_target is None:
            return None
        target_row, target_col, new_heading, latched_heading, crossing = (
            self._merge_target
        )
        heading = self.heading
        # Nothing between latching and the turn changes the heading -- the
        # car holds it precisely so the turn is made from the lane it was
        # latched in -- so the latch is never abandoned this way in
        # practice; it keeps a stale target from firing if that changes.
        if heading != latched_heading:  # pragma: no cover - the heading is held
            self._merge_target = None
            return None
        if (self.row, self.col) != (target_row, target_col):
            # Still approaching the lane where the turn will be made.
            # Hold the latched heading rather than letting an ordinary
            # right-hand hug peel the car away mid-approach -- the road
            # being joined is open on that side by definition, so the hug
            # would otherwise turn early and never reach the target.
            if self._open_toward(heading):
                return heading
            self._merge_target = None
            return None

        self._merge_target = None
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
        if not crossing:
            choices = (
                [new_heading, latched_heading]
                if new_heading == _left(latched_heading)
                else [latched_heading, new_heading]
            )
            new_heading = choices[0] if arrival_cell == 0 else choices[1]
        if new_heading == heading:
            self._merging_heading = None
            return None
        if self._open_toward(new_heading):
            self._merging_heading = new_heading
            return new_heading
        return None

    def _heading_from_junction(self) -> _Heading | None:
        """Apply the spec's ambiguous-turn rule at a detected intersection.

        Returns the heading to take, or ``None`` when no junction fires or
        when the turn has to be deferred until the car is level with the
        road's mouth.
        """
        heading = self.heading
        order = [_left(heading), heading, _right(heading)]
        options = [h for h in order if self._open_toward(h)]
        if len(options) < 2 or not self._junction_kind(heading):
            return None

        roads = self._junction_choices(heading)
        # A junction that fired (see ``_junction_kind``) always offers
        # at least two roads: a mouth on either side counts alongside
        # straight ahead, and a crossing mouth counts the open sides.
        new_heading = roads[0] if self._cell() == 0 else roads[1]
        turning = new_heading != heading
        # Lane merging applies only to a turn onto a detected side road:
        # continuing straight is not a turn at all, and a road whose
        # mouth is not bounded by real wall arms has no lanes to land in.
        # No committed or generated program sights a road this early, so
        # the deferral is a correctness guard rather than a path taken.
        if turning and not self._open_toward(  # pragma: no cover
            new_heading
        ):
            # The chosen road was sighted before the car is level with
            # its gap: ``_road_mouth`` anchors the near ``+`` up to one
            # cell ahead, so the cell this turn would step onto can
            # still be the wall the mouth opens through.  Turning now
            # would drive the car inside that wall.  Defer instead:
            # ordinary wall-following carries the car forward, the same
            # mouth re-detects on arrival (``near`` only shrinks as the
            # car advances), and the cell is re-read where the turn is
            # actually made, which is what the spec's choice is about.
            return None
        if turning and self._crossing_mouth(heading):
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
            self._merge_target = (*target, new_heading, heading, True)
            return None
        # The mouth is looked up once and handed to both helpers: each used
        # to re-find it and guard against a miss the other had already ruled
        # out, so the lookup and the guard were both duplicated.
        mouth = self._road_mouth(heading, new_heading)
        if (
            turning
            and mouth is not None
            and self._lane_bounded(heading, new_heading, mouth)
        ):
            target = self._lane_merge_target(heading, new_heading, mouth)
            if target != (self.row, self.col):
                self._merge_target = (*target, new_heading, heading, False)
                return None
            return new_heading

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

    def _heading_from_hug(self) -> _Heading | None:
        """Ordinary right-hand wall-following, the default movement rule."""
        heading = self.heading
        if self._skip_hug > 0:
            # Drive past the declined branch: keep going straight rather than
            # hugging the wall that has fallen away beside the car.  A wall
            # straight ahead still turns the car -- rounding a corner is not
            # the same as being pulled into the road it chose against -- but
            # the countdown carries on so the rest of the mouth stays skipped.
            self._skip_hug -= 1
            if self._open_toward(heading):
                return heading
        for candidate in (_right(heading), heading, _left(heading), _opposite(heading)):
            if self._open_toward(candidate):
                return candidate
        return None

    def step(self) -> None:
        """Execute the cell under the car, then drive it one cell further."""
        if self._done:
            return
        char = self.grid[self.row][self.col]
        if char == ";":
            self._done = True
            return

        # The cell as the car arrives, before this square's instruction runs.
        # A junction decision is about the road the car is arriving at, so it
        # branches on this rather than on whatever the square itself does to
        # the tape: the ``=`` painted on a turning square moves CP to set up
        # the road ahead, and must not also decide which road that is.  It is
        # a per-step value, so it is passed to ``_choose_heading`` rather than
        # kept on the machine, where it would look like part of the state the
        # cycle detector snapshots.
        arrival_cell = self._cell()

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
            # A street with no opposite lane is narrower than the spec
            # allows, so there is nowhere legal to end the turn: that is a
            # malformed street met at runtime, not a manoeuvre with a
            # sensible fallback.
            lane_row, lane_col = self._ahead(self.row, self.col, _right(self.heading))
            if not self._open(lane_row, lane_col):
                raise HaltError
            self._merge_target = None
            self._merging_heading = None
            self._skip_hug = 0
            self.row, self.col = lane_row, lane_col
            return
        # 'C' and space (and any other undefined character) are no-ops.

        heading = self._choose_heading(arrival_cell)
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
