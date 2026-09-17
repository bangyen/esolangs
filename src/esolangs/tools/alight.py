"""Boolean-function generator for Alight.

Derived, not transliterated (the page is unimplemented).  Alight's
``at{list, index}`` takes the index as an expression, so the table is a
string literal and the input bits fold into its row by Horner's rule,
``row = ((b0 * 2 + b1) * 2 + b2)...``, minus their ASCII offset: O(n)
commands over an O(2**n) literal, no branching.  That is why ``alight``
sits in the contract test's ``_UNSHAPED`` list: a 0%
fold is the construction working.  The reads are unconditional and first.
"""

from esolangs.tools.helpers import _ASCII_ZERO, _validate_truth_table

__all__ = ["alight"]


#: The two turns a fold spends.  ``turn`` pivots *at its own semicolon's
#: cell* and the next command begins one cell beyond it in the new heading,
#: so a fold is two of them: one along the row to face south, one written
#: downward to face along the next row.  Which one depends on the heading --
#: right of east is south and right of south is west, while it takes two
#: lefts to get from west back to east.
_ALIGHT_EAST_TURN = "turn right;"
_ALIGHT_WEST_TURN = "turn left;"


def _alight_chunk(rows: int, width: int) -> int:
    """How many table entries one lookup may carry, inside ``width``.

    A chunk's guard, lookup and turn share a row; the index text is bounded
    by the largest row number, so this is a formula.
    """
    index = len(f"{rows - 0.5}")
    # ``skip i < I;`` is 10 + I, ``set r at{"", i-I};`` is 18 + I.
    overhead = 28 + 2 * index
    chunk = max(1, width - overhead - len(_ALIGHT_EAST_TURN))
    # Chunking is not free: it buys a shorter literal with a guard, and for
    # a short table the guard costs more than the literal saves.  Keeping
    # the whole table in one lookup whenever splitting would not actually
    # make the widest unit narrower is also what keeps this monotone --
    # otherwise asking for 1 came back *wider* than asking for 40, which is
    # not what "the narrowest it can build" should mean.
    if len('set r at{"", i+0.5};') + rows <= overhead + chunk:
        return rows
    return chunk


def _alight_units(truth_table: str, n: int, chunk: int) -> list[list[str]]:
    """Build the commands, grouped into pieces a fold may not split.

    A ``skip`` guards the next command along the heading, so the pair stays
    on one row.  The literal is one token, so it is chunked to make the floor
    the chunk size; each chunk is guarded only from below, so every chunk up
    to the index's runs and the last overwrites (reading past a chunk's end
    is ``nil``, per the wiki).
    """
    units: list[list[str]] = [["begin"], ["var a"], ["var i"], ["var r"]]
    for k in range(n):
        units.append(["inp a"])
        units.append(
            [f"set i a-{_ASCII_ZERO}" if k == 0 else f"set i i*2+a-{_ASCII_ZERO}"]
        )
    rows = len(truth_table)
    if chunk >= rows:
        # Indices run 0.5, 1.5, ... so the row number is offset by a half.
        units.append([f'set r at{{"{truth_table}", i+0.5}}'])
    else:
        for start in range(0, rows, chunk):
            piece = truth_table[start : start + chunk]
            if start == 0:
                units.append(
                    [
                        f"skip i > {start + len(piece) - 0.5}",
                        f'set r at{{"{piece}", i+0.5}}',
                    ]
                )
            else:
                low = start - 0.5
                units.append([f"skip i < {low}", f'set r at{{"{piece}", i-{low}}}'])
    units.append(["out r"])
    units.append(["end"])
    return units


def _alight_flat_compact(truth_table: str, n: int) -> str:
    """Return the shorter straight lookup, with the index in ``at`` itself."""
    names = [chr(code) for code in range(ord("a"), ord("z") + 1) if code != ord("r")]
    names.extend(f"a{index}" for index in range(n - len(names)))
    expr = names[0]
    for name in names[1:n]:
        expr += f"*2+{name}"
    # Every input is its character code.  The final half selects Alight's
    # half-integer list slot; omitting its leading zero saves one column.
    offset = _ASCII_ZERO * ((1 << n) - 1) - 0.5
    expr += f"-{offset:g}"
    return ";".join(
        ["begin", *(f"var {name}" for name in names[:n]), "var r"]
        + [f"inp {name}" for name in names[:n]]
        + [f'set r at{{"{truth_table}",{expr}}}', "out r", "end", ""]
    )


def _alight_folded(units: list[list[str]], width: int) -> str:
    """Lay ``commands`` out as a boustrophedon inside ``width`` columns.

    A command is a word walked cell by cell, so a row end cuts it; the
    heading is steered with two ``turn right`` then two ``turn left``, the
    second of each written downward from the cell beyond.  Westward rows
    read right to left (``end;`` is ``;dne``).  The turn sits at the far
    edge with bare semicolons (a nop) filling the gap, so every row is full
    width.  The floor is the longest command plus its turn.
    """
    longest = max(len(";".join(unit)) for unit in units) + 1
    # Every row runs the full span, so one command plus its turn is what a
    # row has to hold; a narrower request cannot be met by folding.
    limit = max(width, longest + len(_ALIGHT_EAST_TURN) + 1)
    cells: dict[tuple[int, int], str] = {}
    row, col, step = 0, 0, 1
    pending = list(units)
    # Every pass places at least one command and the pass that empties
    # ``pending`` leaves through the break below, so the loop has no other
    # way out and says so.
    while True:
        turn = _ALIGHT_EAST_TURN if step == 1 else _ALIGHT_WEST_TURN
        edge = limit - 1 if step == 1 else 0
        turn_start = edge - step * (len(turn) - 1)
        room = abs(turn_start - col)
        taken: list[str] = []
        used = 0
        while pending:
            piece = ";".join(pending[0]) + ";"
            if taken and used + len(piece) > room:
                break
            taken.append(piece)
            used += len(piece)
            pending.pop(0)
        for i, char in enumerate("".join(taken)):
            cells[row, col + i * step] = char
        col += step * used
        if not pending:
            break
        while col != turn_start:
            cells[row, col] = ";"
            col += step
        for i, char in enumerate(turn):
            cells[row, col + i * step] = char
        col = edge
        for i, char in enumerate(turn):
            cells[row + 1 + i, col] = char
        row += len(turn)
        step = -step
        col += step
    if min(c for _, c in cells) < 0:
        raise AssertionError("a run walked off the left edge")
    height = max(r for r, _ in cells) + 1
    ends: dict[int, int] = {}
    for r, c in cells:
        ends[r] = max(ends.get(r, 0), c)
    # The interpreter pads ragged rows back to this grid's widest line, so
    # trailing blank cells need not be serialized.  Empty interior rows stay
    # present as the newlines around them.
    return "\n".join(
        "".join(cells.get((r, c), " ") for c in range(ends.get(r, -1) + 1)).rstrip()
        for r in range(height)
    )


def _dimensions(program: str) -> tuple[int, int]:
    """Return the rendered width and height of an Alight program."""
    rows = program.splitlines()
    return max(map(len, rows)), len(rows)


def _alight_balanced(truth_table: str, n: int, width: int) -> str:
    """Return the permitted layout with the smallest longer dimension.

    Straight, one-column rotation, or any legal boustrophedon within
    ``width``; ties prefer less area, then fewer characters.
    """
    if width < 1:
        raise ValueError("width must be at least 1")
    flat = _alight_flat_compact(truth_table, n)
    candidates = ["\n".join(flat)]
    if len(flat) <= width:
        candidates.append(flat)
    for columns in range(1, min(width, len(flat)) + 1):
        chunk = _alight_chunk(len(truth_table), columns)
        folded = _alight_folded(_alight_units(truth_table, n, chunk), columns)
        if _dimensions(folded)[0] <= width:
            candidates.append(folded)

    def score(program: str) -> tuple[int, int, int]:
        rendered_width, height = _dimensions(program)
        return max(rendered_width, height), rendered_width * height, len(program)

    return min(candidates, key=score)


def alight(truth_table: str, width: int | None = None) -> str:
    """Return an Alight program printing ``truth_table``'s entry for its input.

    Reads ``n`` characters, folds them into the row by Horner, prints the
    table character: a branch-free single line, ``O(2**n)`` literal plus
    ``O(n)`` reads.  ``width`` is a hard bound; the layout minimizing
    ``max(width, height)`` wins, ties preferring less area.
    """
    n = _validate_truth_table(truth_table)
    flat = _alight_flat_compact(truth_table, n)
    if width is None:
        return flat
    return _alight_balanced(truth_table, n, width)
