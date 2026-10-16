"""Alight grid geometry: headings, word scanning and function lookup."""

from __future__ import annotations

from esolangs.languages.alight.interpreter._hints import Hint
from esolangs.languages.alight.interpreter._parse import _Parser, _valid_name


def _grid(code: list[str]) -> list[str]:
    """Pad ragged source to a rectangle for in-bounds indexing."""
    width = max((len(line) for line in code), default=0)
    return [line.ljust(width) for line in code]


#: Headings as ``(drow, dcol)`` in screen coordinates -- row grows downward,
#: so a *left* turn (counter-clockwise on the page) takes east to north.
type _Heading = tuple[int, int]


_EAST: _Heading = (0, 1)


_WEST: _Heading = (0, -1)


_NORTH: _Heading = (-1, 0)


_SOUTH: _Heading = (1, 0)


# Turning is a rotation of this cycle: the next entry is a right turn, the
# previous a left one.  Written as a cycle rather than two dicts so the two
# directions cannot disagree.
_CLOCKWISE: tuple[_Heading, ...] = (_NORTH, _EAST, _SOUTH, _WEST)


def _find(grid: list[str], word: str) -> tuple[int, int, _Heading] | None:
    """Return where ``word`` is spelled on the grid, and the heading it runs in.

    Row-major over start cells, and for each cell the four headings in a
    fixed order, so a grid spelling the word twice picks the first
    deterministically.  The cell returned is the word's *first* character;
    the walk continues from just past its last.
    """
    for row, line in enumerate(grid):
        for col in range(len(line)):
            for heading in (_EAST, _SOUTH, _WEST, _NORTH):
                if _read_word(grid, row, col, heading) == word:
                    return row, col, heading
    return None


def _read_word(grid: list[str], row: int, col: int, heading: _Heading) -> str:
    """Return ``len(word)`` characters from ``(row, col)`` along ``heading``.

    Returns ``""`` when the run would leave the grid, so a word cannot be
    matched half off the edge.
    """
    drow, dcol = heading
    out: list[str] = []
    for _ in range(5):  # ``begin`` is the longest word this is asked for
        if not (0 <= row < len(grid) and 0 <= col < len(grid[0])):
            return "".join(out)
        out.append(grid[row][col])
        row += drow
        col += dcol
    return "".join(out)


def _scan(
    grid: list[str], row: int, col: int, heading: _Heading
) -> tuple[str, int, int]:
    """Read one command from ``(row, col)`` along ``heading``.

    Returns the command's text and the cell its terminating ``;`` sat on --
    the *pivot*: a ``turn`` turns as if the semicolon were the command, and
    the next command starts one cell beyond it.  This closes the wiki's cat
    loop: the ``;`` ending ``var c`` is the cell the vertical ``turn right``
    ends on, read from the other direction.

    A run reaching the grid edge without a ``;`` ends there, last cell as
    pivot (both cat examples finish on an edge-terminated ``end``); whether
    *walking on* from there is legal is the caller's, and only ``end``
    survives it.

    A ``;`` inside ``"..."`` is a string character (the wiki says so), and
    ``'`` shields the next character, so ``';`` is a semicolon literal.
    """
    drow, dcol = heading
    height, width = len(grid), len(grid[0])
    text: list[str] = []
    quoted = False
    escape = False
    while 0 <= row < height and 0 <= col < width:
        c = grid[row][col]
        if escape:
            escape = False
        elif c == "'" and not quoted:
            escape = True
        elif c == '"':
            quoted = not quoted
        elif c == ";" and not quoted:
            return "".join(text), row, col
        text.append(c)
        row += drow
        col += dcol
    if quoted or escape:
        raise Hint.SCANNED_LITERAL.error("unterminated string literal")
    # Stepped off the grid: back up onto the last in-bounds cell, which is
    # the pivot an edge-terminated command ends on.
    return "".join(text), row - drow, col - dcol


def _find_func(
    grid: list[str], name: str
) -> tuple[int, int, _Heading, list[str]] | None:
    """Locate ``func <name>{...}`` on the grid; return its entry and parameters.

    Returns the cell and heading the body starts at -- just past the ``}`` --
    with the parameter names, or ``None`` when no such function is written.
    """
    for row, line in enumerate(grid):
        for col in range(len(line)):
            for heading in (_EAST, _SOUTH, _WEST, _NORTH):
                if _read_word(grid, row, col, heading)[:4] != "func":
                    continue
                drow, dcol = heading
                text, srow, scol = _scan(grid, row, col, heading)
                p = _Parser(text)
                if p.word() != "func" or p.word() != name or p.peek() != "{":
                    continue
                p.pos += 1
                params = _func_params(p)
                if params is None:
                    continue
                # The body begins one cell past the ``func`` command's
                # semicolon, exactly as a ``turn``'s next command does.
                return srow + drow, scol + dcol, heading, params
    return None


def _func_params(p: _Parser) -> list[str] | None:
    """Read a ``func`` header's parameter names, or ``None`` if malformed."""
    params: list[str] = []
    if p.peek() == "}":
        p.pos += 1
        return params if p.at_end() else None
    while True:
        name = p.word()
        if not _valid_name(name):
            return None
        params.append(name)
        c = p.peek()
        p.pos += 1
        if c == "}":
            return params if p.at_end() else None
        if c != ",":
            return None


def _turned(heading: _Heading, *, left: bool) -> _Heading:
    """Return the heading after a quarter turn.

    ``left`` is counter-clockwise on the page.  The wiki's cat pins this:
    the true branch of ``turn c = eof`` travelling east reads ``end``
    *upward*, so a left turn from east is north.
    """
    i = _CLOCKWISE.index(heading)
    return _CLOCKWISE[(i - 1) % 4] if left else _CLOCKWISE[(i + 1) % 4]
