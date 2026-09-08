"""Lower brainfuck to Streetcode, drawn as roads.

Streetcode is a 2D language: a car drives a network of two-wide streets and
runs the glyph under it at each cell (``^``/``~`` are cell +/-1, ``=``/``_``
move the pointer right/left, ``I``/``O`` are I/O, ``;`` halts), and a *gap*
in a wall is a junction that reads the cell under the pointer -- zero takes
one road, nonzero the other.  That junction read is the only branch the
language offers, and it is exactly brainfuck's ``[``/``]`` test, so a
brainfuck loop draws as a *room* the car laps until the tested cell is zero.
There is no wraparound and no left clamp built in: cells are unbounded
signed integers and ``_`` at cell 0 saturates.

Two facts make the lowering total rather than partial, and both are handled
in :func:`_lower` -- a pure brainfuck-to-brainfuck rewrite -- so the
geometry pass never has to reason about them:

* **Streetcode cells do not wrap.**  brainfuck's do (0-255).  A ``+`` past
  255, a ``-`` below 0, or a ``,`` of a code point above U+00FF would leave
  Streetcode holding a value brainfuck never would, and ``O`` on a negative
  or huge value is a runtime error where brainfuck would print a byte.  So
  every maximal ``+``/``-`` run and every ``,`` is followed by a
  *canonicalizer*: a fixed brainfuck fragment that reduces the cell mod 256.

* **The canonicalizer must stay non-negative and use no wraparound of its
  own**, because it is itself lowered to geometry and Streetcode has neither
  a wrap nor a native ``if``.  It is the standard brainfuck divmod idiom,
  whose loops park the pointer on a cell they have just driven to zero -- a
  loop that runs at most once is an ``if`` -- so it needs only the room the
  geometry already draws.  It keeps every cell ``>= 0`` throughout.

The rewrite widens the tape to **stride 8** (brainfuck cell ``i`` becomes
cell ``8i``; ``>``/``<`` become ``>``*8/``<``*8) so each canonicalizer's
four scratch cells sit in the gap ``8i+1 .. 8i+4`` and can never collide
with the next data cell ``8(i+1)``.  The geometry pass
(:func:`_build`) then doubles again -- brainfuck cell ``j`` to Streetcode
cell ``2j`` -- for its own steering scratch, so a source cell lands at
Streetcode cell ``16 i``.  Widening a disjoint scratch region is what makes
the two passes compose without an ordering constraint between gadgets.

The result is total over brainfuck and linear in program size: the
canonicalizer is a *fixed* fragment per arithmetic run, independent of the
run's magnitude, so a ``+``*49 costs the same three-loop fragment a single
``-`` does.  Verified by a seeded differential fuzz against the brainfuck
interpreter in ``tests/tools/test_transpilers.py``.
"""

from __future__ import annotations

from esolangs.interpreters.brackets import match_brackets as _match_brackets

# -- the brainfuck-to-brainfuck rewrite -----------------------------------

#: Stride of the widened tape.  The canonicalizer needs four scratch cells
#: past the one it reduces; ``8`` leaves room and keeps the arithmetic on
#: byte-aligned boundaries.
_STRIDE = 8

#: The divmod-by-256 core, operating on ``x n 0 0 0`` from the pointer:
#: it leaves ``0  (n - r)  r  q`` where ``r = x % n`` and ``q = x // n``.
#: Every loop it runs exits with the pointer parked on a cell it has just
#: zeroed, so no loop iterates on a cell whose sign is unknown, and no cell
#: is ever driven below zero.
_DIVMOD = "[->-[>+>>]>[+[-<+>]>+>>]<<<<<]"

#: Reduce the cell under the pointer mod 256, leaving every scratch cell at
#: zero and the pointer where it started.  ``n = 256`` is set in ``x+1``,
#: the divmod runs, the remainder is moved back over ``x``, and the two
#: leftover scratch cells (``n - r`` and ``q``) are cleared.
_CANON = (
    ">"
    + "+" * 256
    + "<"  # x+1 = 256
    + _DIVMOD  # x -> 0 ; x+2 = x % 256 ; x+3 = x // 256
    + ">>[-<<+>>]<<"  # move the remainder from x+2 back to x
    + ">[-]<"  # clear x+1 ( = 256 - remainder)
    + ">>>[-]<<<"  # clear x+3 ( = quotient)
)


def _lower(program: str) -> str:
    """Rewrite ``program`` as stride-8 brainfuck that never leaves 0-255.

    Non-command characters are brainfuck comments and are dropped -- the
    same convention the ``brainfuck -> 3D Brainfuck`` and ``-> Painfuck``
    transpilers use, and required here because a later pass reads the
    result as pure commands.  Unbalanced brackets are malformed in
    brainfuck too, so they raise :class:`ValueError` before anything is
    emitted, exactly where the source interpreter raises.
    """
    _match_brackets(program)
    code = "".join(c for c in program if c in "+-<>.,[]")
    out: list[str] = []
    i, n = 0, len(code)
    while i < n:
        char = code[i]
        if char in "+-":
            delta = 0
            while i < n and code[i] in "+-":
                delta += 1 if code[i] == "+" else -1
                i += 1
            residue = delta % 256
            if residue:
                out.append("+" * residue)
                out.append(_CANON)
            continue
        if char == ">":
            out.append(">" * _STRIDE)
        elif char == "<":
            out.append("<" * _STRIDE)
        elif char == ".":
            out.append(".")
        elif char == ",":
            out.append(",")
            out.append(_CANON)
        else:  # '[' or ']'
            out.append(char)
        i += 1
    return "".join(out)


# -- the geometry: brainfuck (no wrap concerns) -> a Streetcode grid ------
#
# From here the input is the stride-8 rewrite: pure brainfuck whose cells
# provably stay in 0-255, so the drawing never has to model wraparound.
# brainfuck cell ``j`` is drawn at Streetcode cell ``2j`` (odd cells are
# steering scratch no program can name), which is why ``>`` draws as ``==``
# and ``<`` as ``__``.

#: brainfuck command -> its Streetcode glyphs on the doubled tape.
_GLYPH = {">": "==", "<": "__", "+": "^", "-": "~", ".": "O", ",": "I"}

#: A childless room's rows below its own body run: the island's north wall,
#: two hollow rows, its south wall, the ``U`` turn, a blank row and the
#: closer, plus the shaft row above the run.
_FLAT_ROOM_ROWS = 8

#: Rows between a room's body run and its children's: the island's north
#: wall (which carries their mouths) and their exit shafts.
_CHILD_DROP = 3

#: How far a sub-room's west wall must clear its parent's island wall so the
#: two ``+`` do not abut and leave the mouth no gap.
_CHILD_CLEAR = 1


# A parsed program is a tree: each node is a command character or a nested
# body (a loop), so the type is recursive.
type _Tree = list["str | _Tree"]


def _parse(program: str) -> _Tree:
    """Brainfuck source -> a tree of command characters and nested lists."""
    tree: _Tree = []
    stack: list[_Tree] = [tree]
    for char in program:
        if char == "[":
            node: _Tree = []
            stack[-1].append(node)
            stack.append(node)
        elif char == "]":
            if len(stack) == 1:
                raise ValueError("unbalanced ]")
            stack.pop()
        elif char in _GLYPH:
            stack[-1].append(char)
    if len(stack) != 1:
        raise ValueError("unbalanced [")
    return tree


def _split(nodes: _Tree) -> tuple[list[str], list[_Tree]]:
    """Split a body into plain glyph segments and the loops between them.

    ``len(segments) == len(loops) + 1``: ``segments[i]`` runs before
    ``loops[i]`` and ``segments[-1]`` is the tail.
    """
    segments: list[str] = []
    loops: list[_Tree] = []
    cur: list[str] = []
    for node in nodes:
        if isinstance(node, list):
            segments.append("".join(_GLYPH[x] for x in cur))
            cur = []
            loops.append(node)
        else:
            cur.append(node)
    segments.append("".join(_GLYPH[x] for x in cur))
    return segments, loops


class _Room:
    """One loop's footprint: its columns, its height and its children.

    Columns, west to east (the same arithmetic at every nesting level)::

        m - 1               the west wall
        m, m + 1            the entry mouth
        b = m + 2           the island's west wall
        b + 1 ..            the body run: plain glyphs and sub-room mouths
        isl_e               the island's east wall
        isl_e + 1, + 2      the exit mouth (exit_a, exit_b)
        east                the east wall
        rest                the conditional restore shaft, east of the room
    """

    #: Column of the east wall and total row height, read by an enclosing
    #: room off each child; annotated here so a forward read type-checks.
    east: int
    height: int

    def __init__(self, nodes: _Tree, col: int) -> None:
        self.segments, self.loops = _split(nodes)
        self.m = col + 1
        self.b = self.m + 2
        self.children: list[_Room] = []
        self.slots: list[tuple[int, str]] = []
        self.rest: tuple[int, int, int, int] = (0, 0, 0, 0)

        c = self.b + 1
        for i, sub in enumerate(self.loops):
            for ch in self.segments[i]:
                self.slots.append((c, ch))
                c += 1
            c = max(c, self.b + _CHILD_CLEAR)
            child = _Room(sub, c)
            self.children.append(child)
            # The child's exit shaft runs a ``^`` on the way out, which
            # steers the returning car; a conditional restore shaft east of
            # the rejoin cancels it on the taken path only, so a skipped
            # child leaves its cell alone.
            rest_l = child.east + 2
            child.rest = (rest_l, rest_l + 1, rest_l + 2, rest_l + 3)
            c = rest_l + 5
        for ch in self.segments[-1]:
            self.slots.append((c, ch))
            c += 1

        self.isl_e = max(c + 1, self.b + 5)
        self.exit_a, self.exit_b = self.isl_e + 1, self.isl_e + 2
        self.east = self.exit_b + 1
        inner = max((ch.height for ch in self.children), default=0)
        self.height = _FLAT_ROOM_ROWS + inner


def _restore_shaft(
    grid: list[list[str]], wall: int, rest: tuple[int, int, int, int]
) -> None:
    """Draw a conditional restore shaft hanging below row ``wall``."""
    rl, ra, rb, rr = rest
    grid[wall][rl] = "+"
    grid[wall][ra] = grid[wall][rb] = " "
    grid[wall][rr] = "+"
    for r in (wall + 1, wall + 2, wall + 3):
        grid[r][rl] = "|"
        grid[r][rr] = "|"
    grid[wall + 2][rb] = "~"
    grid[wall + 4][rl] = "+"
    grid[wall + 4][rr] = "+"
    for c in range(rl + 1, rr):
        grid[wall + 4][c] = "-"


def _draw(room: _Room, grid: list[list[str]], run: int) -> None:
    """Stamp ``room`` into ``grid`` with its body run on row ``run``.

    Rows, relative to ``run``::

        run - 2   the wall this room's own mouths are cut into
        run - 1   the exit shaft (carries the '^')
        run       the body run: plain glyphs and sub-room mouth approaches
        run + 1   the island's north wall, carrying the sub-room mouths
        run + 2   the sub-rooms' exit shafts
        run + 3   the sub-rooms' body runs (recursively)
        bot - 3   the island's south wall
        bot - 2   the 'U' that flips the car onto the island lap
        bot       the closer
    """
    m, b, isl_e = room.m, room.b, room.isl_e
    exit_a, exit_b, east = room.exit_a, room.exit_b, room.east
    top = run - 2
    bot = run + room.height - 1

    grid[top][m - 1] = "+"
    grid[top][m] = grid[top][m + 1] = " "
    grid[top][b] = "+"
    for c in range(b + 1, isl_e):
        if grid[top][c] == " ":
            grid[top][c] = "-"
    grid[top][isl_e] = "+"
    grid[top][exit_a] = grid[top][exit_b] = " "
    grid[top][east] = "+"

    for r in range(top + 1, bot):
        grid[r][m - 1] = "|"
        grid[r][east] = "|"
    grid[run - 1][exit_b] = "^"

    isl_bot = bot - 3
    for r in (run + 1, isl_bot):
        grid[r][b] = "+"
        grid[r][isl_e] = "+"
        for c in range(b + 1, isl_e):
            if grid[r][c] == " ":
                grid[r][c] = "-"
    for r in range(run + 2, isl_bot):
        grid[r][b] = "|"
        grid[r][isl_e] = "|"

    grid[bot - 2][exit_b] = "U"
    grid[bot][m - 1] = "+"
    grid[bot][east] = "+"
    for c in range(m, east):
        grid[bot][c] = "-"

    for c, ch in room.slots:
        grid[run][c] = ch

    for child in room.children:
        _draw(child, grid, run + _CHILD_DROP)
        _restore_shaft(grid, run + 1, child.rest)


def _build(program: str) -> list[str]:
    """Draw a Streetcode grid for stride-8 brainfuck, at any nesting depth."""
    tree = _parse(program)
    segments, loops = _split(tree)

    col = 2
    rooms: list[_Room] = []
    street: list[tuple[int, str]] = []
    for i, node in enumerate(loops):
        for ch in segments[i]:
            street.append((col, ch))
            col += 1
        room = _Room(node, col)
        rooms.append(room)
        rest_l = room.east + 2
        room.rest = (rest_l, rest_l + 1, rest_l + 2, rest_l + 3)
        col = rest_l + 5
    for ch in segments[-1]:
        street.append((col, ch))
        col += 1
    street.append((col, ";"))
    col += 1

    width = max(col + 2, max((r.east + 3 for r in rooms), default=0))
    height = max((r.height + 5 for r in rooms), default=4)

    grid = [[" "] * width for _ in range(height)]
    # The street's frame is rows 0-3 only.  Rooms hang below row 3 carrying
    # their own side walls, so a full-height border would duplicate them and
    # the grid would fail "geometry not connected".
    for c in range(width):
        grid[0][c] = "-"
        grid[3][c] = "-"
    grid[0][0] = grid[0][width - 1] = "+"
    grid[3][0] = grid[3][width - 1] = "+"
    grid[1][0] = grid[1][width - 1] = "|"
    grid[2][0] = grid[2][width - 1] = "|"

    grid[2][1] = "C"
    for c, ch in street:
        grid[2][c] = ch

    for room in rooms:
        _draw(room, grid, 5)
        _restore_shaft(grid, 3, room.rest)

    return ["".join(x).rstrip() for x in grid]


def bf_to_streetcode(program: str) -> str:
    """Rewrite a brainfuck program as an equivalent Streetcode program.

    The lowering is two passes.  :func:`_lower` rewrites brainfuck to
    brainfuck that provably stays in 0-255 (canonicalizing every arithmetic
    run and every ``,`` mod 256, on a stride-8 tape whose scratch cells no
    source cell can reach), so the second pass need not model Streetcode's
    non-wrapping unbounded cells at all.  :func:`_build` then draws that
    brainfuck as roads: a ``[``/``]`` loop is a room the car laps until its
    tested cell is zero, plain glyphs run on the street, and rooms nest to
    any depth by recursion.

    Total over brainfuck: every well-formed program translates, and the two
    raise sites (unbalanced brackets) are exactly the ones the brainfuck
    interpreter rejects on the same input.  The output runs to identical
    output through the Streetcode interpreter -- underflow, overflow, and a
    ``,`` of a code point above U+00FF all reproduced by the canonicalizer,
    and end-of-input raising :class:`EOFError` in both.
    """
    return "\n".join(_build(_lower(program)))
