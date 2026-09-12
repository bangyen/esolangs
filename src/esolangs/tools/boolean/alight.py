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


def _alight_chunk(rows: int, width: int) -> int:
    """How many table entries one lookup may carry, inside ``width``.

    A chunked lookup is a guard and the lookup it guards, which have to
    share a row with the turn -- so what is left for the literal is the
    width less all three.  The index text is bounded by the largest row
    number the table has, which is what makes this a formula rather than a
    search.
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

    A ``skip`` guards *the next command along the heading*, so the two have
    to stay on one row: a fold between them would leave the ``skip``
    skipping the turn instead of the lookup, and the walk would not turn.

    The table is one string literal, which is one token of one command and
    so sets how narrow the program can go.  Splitting it into chunks makes
    the floor the chunk size instead of ``2 ** n``, at one guarded lookup
    per chunk.

    Each chunk is guarded only from *below* -- it runs whenever the index
    has reached it -- so every chunk up to the one that holds the index
    runs, and the last to run is the right one.  The earlier ones read past
    the end of their own piece, which the language makes ``nil`` rather than
    an error (the wiki's rule, and only the three-argument *set* form of
    ``at`` raises), so they write a value the correct chunk then overwrites.
    One guard a chunk is what that buys: bounding both ends would take a
    second ``skip`` on the same row.
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


def _alight_folded(units: list[list[str]], width: int) -> str:
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

    ``width`` folds that line into a boustrophedon (:func:`_alight_folded`)
    and, when the literal alone would still overflow, **splits the literal**
    into guarded chunks (:func:`_alight_units`).  The literal used to be the
    floor -- one token of one command, ``2 ** n`` characters -- and chunking
    is what takes that away: the floor becomes one chunk plus its guard and
    the turn they share a row with, which the width itself picks.
    """
    n = _validate_truth_table(truth_table)
    flat = ";".join(
        ";".join(u) for u in _alight_units(truth_table, n, len(truth_table))
    )
    flat += ";"
    if width is None or len(flat) <= width:
        return flat
    units = _alight_units(truth_table, n, _alight_chunk(len(truth_table), width))
    return _alight_folded(units, width)
