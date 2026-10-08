"""Boolean-function generator for Alight.

Derived, not transliterated (the page is unimplemented).  Alight's
``at{list, index}`` takes the index as an expression, so the table is a
string literal and the input bits fold into its row by Horner's rule,
``row = ((b0 * 2 + b1) * 2 + b2)...``, minus their ASCII offset: O(n)
commands over an O(2**n) literal, no branching.  That is why ``alight``
sits in the contract test's ``_UNSHAPED`` list: a 0%
fold is the construction working.  The reads are unconditional and first.
"""

from esolangs._dialects import expression_syntax as validate_expression_syntax
from esolangs._dialects import list_update as validate_list_update
from esolangs.tools.helpers import _ASCII_ZERO, _validate_truth_table, input_weights

__all__ = ["alight"]


#: The two turns a fold spends.  ``turn`` pivots *at its own semicolon's
#: cell* and the next command begins one cell beyond it in the new heading,
#: so a fold is two of them: one along the row to face south, one written
#: downward to face along the next row.  Which one depends on the heading --
#: right of east is south and right of south is west, while it takes two
#: lefts to get from west back to east.
_ALIGHT_EAST_TURN = "turn right;"
_ALIGHT_WEST_TURN = "turn left;"

#: Width of a chunk's guard and lookup around the index text: ``skip i < I;``
#: is 10 + I, ``set r at{"", i-I};`` is 18 + I.
_ALIGHT_OVERHEAD = 28


def _half_before(value: int) -> str:
    """Return value minus one half without floating-point rounding."""
    return f"{value - 1}.5"


def _alight_chunk(rows: int, width: int) -> int:
    """How many table entries one lookup may carry, inside ``width``.

    A chunk's guard, lookup and turn share a row; the index text is bounded
    by the largest row number, so this is a formula.
    """
    index = len(_half_before(rows))
    overhead = _ALIGHT_OVERHEAD + 2 * index
    chunk = max(1, width - overhead - len(_ALIGHT_EAST_TURN))
    # For a short table the guard costs more than the literal saves; one
    # lookup unless splitting narrows the widest unit, else a smaller request
    # came back wider than a larger one.  Postfix, measured by area on random
    # tables: without the guard n=8 at width 300 is 83% larger (0% at 50-160
    # and 500).
    if len('set r at{"", i+0.5};') + rows <= overhead + chunk:
        return rows
    return chunk


def _alight_units(
    truth_table: str, n: int, chunk: int, essential: list[bool] | None = None
) -> list[list[str]]:
    """Build the commands, grouped into pieces a fold may not split.

    A ``skip`` guards the next command along the heading, so the pair stays
    on one row.  The first chunk is guarded from above (``i > end``), the
    rest from below (``i < start``); later chunks overwrite ``r`` (reading
    past a chunk's end is ``nil``, per the wiki).  An input ``essential``
    marks False is a bare ``inp a`` and ``truth_table`` is indexed by the rest.
    """
    units: list[list[str]] = [["begin"], ["var a"], ["var i"], ["var r"]]
    folded = False
    for kept in essential or [True] * n:
        units.append(["inp a"])
        if not kept:
            continue
        units.append(
            [f"set i i*2+a-{_ASCII_ZERO}" if folded else f"set i a-{_ASCII_ZERO}"]
        )
        folded = True
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
                        f"skip i > {_half_before(start + len(piece))}",
                        f'set r at{{"{piece}", i+0.5}}',
                    ]
                )
            else:
                low = _half_before(start)
                units.append([f"skip i < {low}", f'set r at{{"{piece}", i-{low}}}'])
    units.append(["out r"])
    units.append(["end"])
    return units


def _alight_flat_compact(
    truth_table: str, n: int, essential: list[bool] | None = None
) -> str:
    """Return the shorter straight lookup, with the index in ``at`` itself.

    Against the ``set i`` fold of ``_alight_units`` it is 10.3% shorter at n=8
    (13.8% at n=7), so the default path never builds units.

    An input ``essential`` marks False is read into ``r``, which the lookup
    overwrites, and ``truth_table`` is indexed by the rest.
    """
    essential = essential or [True] * n
    m = sum(essential)
    names = [chr(code) for code in range(ord("a"), ord("z") + 1) if code != ord("r")]
    names.extend(f"a{index}" for index in range(m - len(names)))
    expr = names[0]
    for name in names[1:m]:
        expr += f"*2+{name}"
    # Every input is its character code; the final half selects Alight's
    # half-integer list slot.  (Folding it into the offset, ``-N.5``, saved
    # 2 chars: 0.47% at n=8, retired.)
    expr += f"-{_ASCII_ZERO * ((1 << m) - 1)}+0.5"
    reads = iter(names[:m])
    return ";".join(
        ["begin", *(f"var {name}" for name in names[:m]), "var r"]
        + [f"inp {next(reads) if kept else 'r'}" for kept in essential]
        + [f'set r at{{"{truth_table}",{expr}}}', "out r", "end", ""]
    )


def _alight_folded(units: list[list[str]], width: int) -> str:
    """Lay ``units`` out as a boustrophedon inside ``width`` columns.

    A command is a word walked cell by cell, so a row end cuts it; the
    heading is steered by an east turn then a west turn, the second of each
    written downward from the cell beyond.  Westward rows
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
    # Every pass places a command; the pass that empties ``pending`` breaks.
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


def _flatten(units: list[list[str]]) -> str:
    """Return the commands of ``units`` as one semicolon-terminated line."""
    return ";".join(command for unit in units for command in unit) + ";"


def _fit(program: str, width: int) -> str | None:
    """Return ``program`` if it is at most ``width`` wide, else None."""
    return program if _dimensions(program)[0] <= width else None


def _smallest(*programs: str | None, minimax: bool = True) -> str:
    """Return the candidate with least ``max(width, height)``, then area.

    ``minimax=False`` (postfix) ranks by area alone.
    """

    def score(program: str) -> tuple[int, int, int]:
        w, h = _dimensions(program)
        return max(w, h) if minimax else 0, w * h, len(program)

    return min((p for p in programs if p is not None), key=score)


def _postfix_width(units: list[list[str]], width: int) -> str:
    """Return the fold of ``units`` if it fits ``width``, else one column."""
    program = _alight_folded(units, width)
    return program if _dimensions(program)[0] <= width else "\n".join(_flatten(units))


def alight(
    truth_table: str,
    width: int | None = None,
    *,
    expression_syntax: str = "infix",
    list_update: str = "in_place",
) -> str:
    """Return an Alight program printing ``truth_table``'s entry for its input.

    Reads ``n`` characters, folds them into the row by Horner, prints the
    table character: a branch-free single line, ``O(2**n)`` literal plus
    ``O(n)`` reads.  ``width`` is a hard bound; the layout minimizing
    ``max(width, height)`` wins for infix, ties preferring less area.
    Postfix folds commands or rotates them into one column.  Only
    two-argument ``at`` is emitted, so every ``list_update`` runs it.
    """
    n = _validate_truth_table(truth_table)
    validate_expression_syntax(expression_syntax)
    validate_list_update(list_update)
    if width is not None and width < 1:
        raise ValueError("width must be at least 1")
    weights, projected = input_weights(truth_table, n)
    essential = [bool(weight) for weight in weights]
    dropped = any(weights) and not all(weights)
    # An ignored input is read and dropped, and the table is indexed by the
    # rest.  A constant keeps every input.
    if width is None and dropped:
        if expression_syntax == "postfix":
            return _flatten(_postfix_units(projected, n, len(projected), essential))
        return _alight_flat_compact(projected, n, essential)
    if expression_syntax == "postfix":
        units = _postfix_units(
            truth_table,
            n,
            len(truth_table)
            if width is None
            else _alight_chunk(len(truth_table), width),
        )
        if width is None:
            return _flatten(units)
        program = _postfix_width(units, width)
        if dropped:
            units = _postfix_units(
                projected, n, _alight_chunk(len(projected), width), essential
            )
            return _smallest(program, _postfix_width(units, width), minimax=False)
        return program
    flat = _alight_flat_compact(truth_table, n)
    if width is None:
        return flat
    from esolangs.tools.alight.balance import select_alight  # circular

    program = select_alight(truth_table, n, width)
    if not dropped:
        return program
    # select_alight models n reads, so the dropped build is rendered here:
    # the model's plan for the projected table, and a fold at ``width``.
    # 32.6% by chars at n=8, 1 ignored, width 80 (audit); area measured in
    # the commit.  A candidate wider than ``width`` is discarded.
    from esolangs.tools.alight.balance import _Plan, _plans  # circular

    plan = min(
        (p for p in _plans(sum(essential)) if p.ready() <= width), key=_Plan.score
    )
    flat = _alight_flat_compact(projected, n, essential)
    if plan.kind < 2:  # a column, or the one row (never the minimum here)
        planned = ("\n".join(flat), flat)[plan.kind]
    else:
        planned = _alight_folded(
            _alight_units(projected, n, plan.chunk, essential), plan.columns
        )
    units = _alight_units(projected, n, _alight_chunk(len(projected), width), essential)
    return _smallest(
        program, _fit(planned, width), _fit(_alight_folded(units, width), width)
    )


def _postfix_units(
    table: str, n: int, chunk: int, essential: list[bool] | None = None
) -> list[list[str]]:
    """Emit the same row fold and guarded lookups in postfix notation.

    An input ``essential`` marks False is a bare ``inp a`` the next read
    overwrites, and ``table`` is indexed by the rest.
    """
    units = [["begin"], ["var a"], ["var i"], ["var r"]]
    folded = False
    for kept in essential or [True] * n:
        units.append(["inp a"])
        if not kept:
            continue
        units.append(
            [
                f"set i i 2 * a + {_ASCII_ZERO} -"
                if folded
                else f"set i a {_ASCII_ZERO} -"
            ]
        )
        folded = True
    for start in range(0, len(table), chunk):
        piece = table[start : start + chunk]
        index = "i 0.5 +" if start == 0 else f"i {_half_before(start)} -"
        lookup = f'set r at{{"{piece}", {index}}}'
        if chunk >= len(table):
            units.append([lookup])
        elif start == 0:
            units.append([f"skip i {_half_before(len(piece))} >", lookup])
        else:
            units.append([f"skip i {_half_before(start)} <", lookup])
    return [*units, ["out r"], ["end"]]
