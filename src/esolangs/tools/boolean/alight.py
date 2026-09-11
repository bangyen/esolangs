"""Boolean-function generator for Alight.

The construction is *derived*: the wiki has no truth machine to copy, and
the page is marked unimplemented, so nothing here is transliterated.

What Alight gives that the other grid languages do not is an indexable list
with an *out-of-line* index -- ``at{list, index}`` takes the index as an
expression rather than as a walk.  So the truth table needs no branching at
all: encode it as a string literal, fold the input bits into its row number,
and read the answer out.

    row = ((b0 * 2 + b1) * 2 + b2) ...

which is Horner's rule, and it is spelled directly as
``set i i*2+a-48`` because expressions evaluate strictly left to right --
the same reading the wiki's own ``len{l}-0.5`` forces.  Each input costs one
``inp`` and one ``set``, so the program is O(n) commands over an O(2**n)
table literal, with no decision tree, no leaves and no turns: it is one
straight eastward line.

That shape is why ``alight`` sits in the contract test's ``_UNSHAPED`` list
alongside ``ztoalc_l``.  Both are branch-free lookups, so there are
no subtrees to collapse and a one-dependency table renders the same length
as parity -- a 0% fold that is the construction working, not regressing.

The reads are unconditional and come before the lookup, so every table of a
given arity consumes exactly ``n`` inputs, whatever the table says.
"""

from esolangs.tools.boolean.helpers import _ASCII_ZERO, _validate_truth_table

__all__ = ["alight"]

#: The two turns a fold spends.  ``turn`` pivots *at its own semicolon's
#: cell* and the next command begins one cell beyond it in the new heading,
#: so a fold is two of them: one along the row to face south, one written
#: downward to face along the next row.  Which one depends on the heading --
#: right of east is south and right of south is west, while it takes two
#: lefts to get from west back to east.
_ALIGHT_EAST_TURN = "turn right;"
_ALIGHT_WEST_TURN = "turn left;"


def _alight_folded(commands: list[str], width: int) -> str:
    """Lay ``commands`` out as a boustrophedon inside ``width`` columns.

    A command is a *word walked cell by cell*, so a row end cuts one in
    half -- which is why Alight cannot be reflowed after the fact and has
    to be laid out here instead.  What makes the layout possible is that
    the walk's heading is steerable: a row runs east, two ``turn right``
    bring it round to run west, and two ``turn left`` bring it back.  The
    first of each pair sits on the row and pivots at its own semicolon; the
    second is written *downward* from the cell beyond it, which is what
    turns the walk along the next row.

    Going west the characters are written in the order the walk meets
    them, which is right to left on the page -- so a westward ``end;``
    reads ``;dne``.  Nothing is reversed; the row is.

    **The turn always sits at the far edge**, and the gap before it is
    filled with bare semicolons -- the empty command, which the language
    makes a nop.  Folding where the commands happen to run out instead
    leaves the next row starting wherever that was, so it gets less than a
    full row to work with, and a long command then has nowhere to go but
    off the left edge.  Padding costs nothing and makes every row the same
    width.

    The floor is the longest single command plus the turn that shares its
    row, and for this generator that is the table literal: ``2 ** n``
    characters that cannot be split, since a string is one token of one
    command.  A width under the floor is raised to it.
    """
    longest = max(len(command) for command in commands) + 1
    # Every row runs the full span, so one command plus its turn is what a
    # row has to hold; a narrower request cannot be met by folding.
    limit = max(width, longest + len(_ALIGHT_EAST_TURN) + 1)
    cells: dict[tuple[int, int], str] = {}
    row, col, step = 0, 0, 1
    pending = list(commands)
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
            piece = pending[0] + ";"
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
    # A row is trimmed to its last *written* cell rather than stripped:
    # ``turn right`` has a space in the middle, so a vertical turn writes a
    # blank that is part of a command and has to survive.
    return "\n".join(
        "".join(cells.get((r, c), " ") for c in range(ends.get(r, -1) + 1))
        for r in range(height)
    )


def alight(truth_table: str, width: int | None = None) -> str:
    """Return an Alight program printing ``truth_table``'s entry for its input.

    Reads ``n`` characters (one per line, ``'0'`` or ``'1'``), folds them
    into the table's row index by Horner's rule, and prints the table
    character at that row.

    The table is a string literal indexed by ``at``, so the emitted program
    has no branches: its length is ``O(2**n)`` in the literal plus ``O(n)``
    in the reads, and it is a single line of commands running east from
    ``begin``.
    """
    n = _validate_truth_table(truth_table)

    # ``i`` accumulates the row index; ``a`` holds the digit just read.  A
    # digit arrives as its character code, so each read is normalized by
    # subtracting ``'0'`` -- the same offset every generator here spends.
    commands = ["begin", "var a", "var i", "var r"]
    for k in range(n):
        commands.append("inp a")
        # Horner: the first bit seeds the accumulator, each later one
        # doubles it and adds itself.  Left-to-right evaluation is what
        # makes ``i*2+a-48`` mean ``((i*2)+a)-48`` without parentheses,
        # which Alight has none of.
        if k == 0:
            commands.append(f"set i a-{_ASCII_ZERO}")
        else:
            commands.append(f"set i i*2+a-{_ASCII_ZERO}")
    # Indices run 0.5, 1.5, ... so the row number is offset by a half.
    commands.append(f'set r at{{"{truth_table}", i+0.5}}')
    commands.append("out r")
    commands.append("end")
    flat = ";".join(commands) + ";"
    if width is None or len(flat) <= width:
        return flat
    return _alight_folded(commands, width)
