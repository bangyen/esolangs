"""Alight Boolean program generator: a Horner row index into a string literal.

Derived, not transliterated (the page is unimplemented).  Alight's
``at{list, index}`` takes the index as an expression, so the table is a
string literal and the input bits fold into its row by Horner's rule,
``row = ((b0 * 2 + b1) * 2 + b2)...``, minus their ASCII offset.  The reads
are unconditional and first.

Size:
    O(n) commands over an O(2**n) literal, no branching.
    n=10 random 1847: 1,227 chars, n=16 random 1847: 65,837 chars.
    A zero fold is the construction working (``shape`` is ``LOOKUP``): a
    literal has no subtrees to fold or share.
"""

from collections.abc import Callable
from math import isqrt, prod
from typing import NamedTuple

from esolangs.generation.helpers import (
    _ASCII_ZERO,
    _validate_truth_table,
    input_weights,
)
from esolangs.generation.wrap import balance_score
from esolangs.languages.alight.interpreter._dialect import (
    EXPRESSION_SYNTAXES,
    LIST_UPDATES,
)
from esolangs.languages.alight.interpreter._dialect import (
    expression_syntax as validate_expression_syntax,
)
from esolangs.languages.alight.interpreter._dialect import (
    list_update as validate_list_update,
)
from esolangs.languages.alight.proof_formulas import workspace
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Language, Shape

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


def _constant_units(table: str, inputs: int) -> list[list[str]]:
    """Read into one disposable variable and replace it with the literal."""
    # Empty tables are the layout model's one-character placeholder.
    value = str(_ASCII_ZERO + int(table)) if table else "0"
    return [
        ["begin"],
        ["var r"],
        *[["inp r"] for _ in range(inputs)],
        [f"set r {value}"],
        ["out r"],
        ["end"],
    ]


def _alight_units(
    truth_table: str,
    n: int,
    chunk: int,
    essential: list[bool] | None = None,
    *,
    postfix: bool = False,
) -> list[list[str]]:
    """Build notation-specific commands grouped into indivisible fold units.

    Guards and lookups stay on one row. The first chunk's guard is an upper
    bound, later guards are lower bounds; ignored inputs are read without
    advancing the index. Later lookups may overwrite an out-of-range nil.
    """
    if essential is not None and not any(essential):
        return _constant_units(truth_table, n)
    units: list[list[str]] = [["begin"], ["var a"], ["var i"], ["var r"]]
    first, fold = (
        (f"a {_ASCII_ZERO} -", f"i 2 * a + {_ASCII_ZERO} -")
        if postfix
        else (f"a-{_ASCII_ZERO}", f"i*2+a-{_ASCII_ZERO}")
    )
    folded = False
    for kept in essential or [True] * n:
        units.append(["inp a"])
        if kept:
            units.append([f"set i {fold if folded else first}"])
            folded = True
    rows = len(truth_table)
    # The empty literal is the planner's placeholder, with one lookup unit.
    starts = (0,) if chunk >= rows else range(0, rows, chunk)
    for start in starts:
        piece = truth_table[start : start + chunk]
        low = _half_before(start)
        # Character positions are 0.5, 1.5, ... rather than integer indices.
        index = (
            ("i 0.5 +" if start == 0 else f"i {low} -")
            if postfix
            else ("i+0.5" if start == 0 else f"i-{low}")
        )
        lookup = f'set r at{{"{piece}", {index}}}'
        if chunk >= rows:
            units.append([lookup])
        else:
            bound = _half_before(len(piece)) if start == 0 else low
            op = ">" if start == 0 else "<"
            condition = f"i {bound} {op}" if postfix else f"i {op} {bound}"
            units.append([f"skip {condition}", lookup])
    return [*units, ["out r"], ["end"]]


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
    if not m:
        return _flatten(_constant_units(truth_table, n))
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
    return _fit(program, width) or "\n".join(_flatten(units))


def alight(
    truth_table: str,
    width: int | None = None,
    *,
    expression_syntax: str = "infix",
    list_update: str = "in_place",
) -> str:
    """Return an Alight program printing ``truth_table``'s entry for its input.

    ``width`` is a hard bound; infix takes the squarest of a few layouts, by
    ``max(width, height)``, ties by area; postfix folds or rotates into one
    column.  Only two-argument ``at`` is emitted, so every ``list_update``
    runs it.
    """
    return _program(
        truth_table, width, expression_syntax=expression_syntax, list_update=list_update
    )


class _Build(NamedTuple):
    """Resolved inputs for one layout decision.

    ``dropped`` marks tables with ignored inputs, read and dropped while the
    rest index the lookup; ``table`` and ``kept`` are then the projected table
    and its essential inputs, else the raw table and ``None``.
    """

    truth_table: str
    n: int
    width: int | None
    projected: str
    essential: list[bool]
    dropped: bool

    @property
    def table(self) -> str:
        return self.projected if self.dropped else self.truth_table

    @property
    def kept(self) -> list[bool] | None:
        return self.essential if self.dropped else None


def _layout_flat_infix(build: _Build) -> str:
    """Return the unbounded infix layout: one straight lookup."""
    return _alight_flat_compact(build.table, build.n, build.kept)


def _layout_flat_postfix(build: _Build) -> str:
    """Return the unbounded postfix layout: one straight lookup."""
    return _flatten(_postfix_units(build.table, build.n, len(build.table), build.kept))


def _layout_bounded_infix(build: _Build) -> str:
    """Return the bounded infix layout, planned from the projection if inputs drop."""
    width = build.width
    assert width is not None
    if build.dropped:
        return _layout_bounded_dropped(build)
    return select_alight(build.truth_table, build.n, width)


def _layout_bounded_postfix(build: _Build) -> str:
    """Return the bounded postfix layout, projected too when inputs drop."""
    width = build.width
    assert width is not None
    units = _postfix_units(
        build.truth_table,
        build.n,
        _alight_chunk(len(build.truth_table), width),
    )
    program = _postfix_width(units, width)
    if not build.dropped:
        return program
    units = _postfix_units(
        build.projected,
        build.n,
        _alight_chunk(len(build.projected), width),
        build.essential,
    )
    return _smallest(program, _postfix_width(units, width), minimax=False)


def _layout_bounded_dropped(build: _Build) -> str:
    """Return the bounded infix layout with dropped inputs.

    The projected table is laid out over the essential reads, with the
    ignored ones read and dropped.  32.6% by chars at n=8, 1 ignored,
    width 80 (audit).
    """
    width = build.width
    assert width is not None
    essential = build.essential
    planned = select_alight(build.projected, build.n, width, essential)
    if any(essential):
        return planned
    program = select_alight(build.truth_table, build.n, width)
    flat = _alight_flat_compact(build.projected, build.n, essential)
    return _smallest(
        *_constant_candidates(program, [program, _fit(planned, width)], flat, width)
    )


def _constant_candidates(
    program: str, candidates: list[str | None], flat: str, width: int
) -> list[str | None]:
    """Pin constant tables to the legacy layout's size.

    With no essential inputs the fold planner can pick a squarer fold far
    larger than the legacy pick -- at n=4, width 40 the area grew from 121
    to 682 cells -- so the flat line and its column form are always
    considered, and every candidate must be no longer and no larger in area
    than the ``select_alight`` program.  Pinned by
    ``test_constant_lookup_executes_every_layout`` (n=4, width 40).
    """
    candidates = [*candidates, _fit(flat, width), "\n".join(flat)]
    area = prod(_dimensions(program))
    return [
        candidate
        for candidate in candidates
        if candidate is not None
        and len(candidate) <= len(program)
        and prod(_dimensions(candidate)) <= area
    ]


_STRATEGIES: dict[tuple[str, bool], Callable[[_Build], str]] = {
    ("infix", True): _layout_flat_infix,
    ("postfix", True): _layout_flat_postfix,
    ("infix", False): _layout_bounded_infix,
    ("postfix", False): _layout_bounded_postfix,
}


def _program(
    truth_table: str,
    width: int | None = None,
    *,
    expression_syntax: str = "infix",
    list_update: str = "in_place",
) -> str:
    """Lay out the lookup over the essential inputs."""
    n = _validate_truth_table(truth_table)
    _dialect(expression_syntax, list_update)
    if width is not None and width < 1:
        raise ValueError("width must be at least 1")
    weights, projected = input_weights(truth_table, n)
    essential = [bool(weight) for weight in weights]
    # An ignored input is read and dropped, and the table is indexed by the
    # rest, including the one-entry table of a constant.
    dropped = not all(weights)
    build = _Build(
        truth_table=truth_table,
        n=n,
        width=width,
        projected=projected,
        essential=essential,
        dropped=dropped,
    )
    return _STRATEGIES[expression_syntax, width is None](build)


def _postfix_units(
    table: str, n: int, chunk: int, essential: list[bool] | None = None
) -> list[list[str]]:
    """Build the fold units in postfix notation."""
    return _alight_units(table, n, chunk, essential, postfix=True)


def _dialect(expression_syntax: str = "infix", list_update: str = "in_place") -> None:
    """Validate Alight's dialect settings, one keyword per setting."""
    validate_expression_syntax(expression_syntax)
    validate_list_update(list_update)


#: ``2 * size / scale`` is the squared chunk count at which a fold's width
#: (a chunk plus its guard, about ``size / count + 41``) meets its height (about
#: 11 rows per chunk, doubled when ranked by ``balance_score``).  Fitted on
#: n=5..14, where the best count's 5% band always holds floor or ceil of the root.
_SQUARE_SCALE = {"minimax": 17, "balance": 39}


def _square_chunks(size: int, kind: str) -> set[int]:
    """Return the chunk sizes of the two chunk counts around the square root."""
    count = max(1, isqrt(2 * size // _SQUARE_SCALE[kind]))
    return {-(-size // count), -(-size // (count + 1))}


def _folds(
    table: str,
    n: int,
    chunks: set[int],
    essential: list[bool] | None,
    *,
    postfix: bool = False,
    columns: int = 0,
) -> list[str]:
    """Return each chunk size folded at ``columns``, else as narrow as it goes."""
    return [
        _alight_folded(
            _alight_units(table, n, chunk, essential, postfix=postfix), columns
        )
        for chunk in sorted(chunks)
    ]


_COLUMN_SCALES = (4, 5, 6)


def _square_columns(length: int, kind: str) -> set[int]:
    """Return the widths around the one at which ``length`` cells fold square.

    Each fold row adds about 11 rows of height (22 under ``balance_score``).
    """
    root = isqrt(length * (11 if kind == "minimax" else 22))
    return {root * scale // 5 for scale in _COLUMN_SCALES}


def select_alight(
    table: str, n: int, width: int, essential: list[bool] | None = None
) -> str:
    """Return the squarest of the straight, vertical and square-root fold layouts.

    The widest lookup that fits ``width`` joins the square-root folds, so a
    narrow request still folds; layouts wider than ``width`` are dropped and
    the vertical line, one column, always fits.
    """
    flat = _alight_flat_compact(table, n, essential)
    chunks = _square_chunks(len(table), "minimax")
    chunks.add(min(len(table), _alight_chunk(len(table), width)))
    layouts = [flat, "\n".join(flat), *_folds(table, n, chunks, essential)]
    for columns in _square_columns(len(flat), "minimax"):
        layouts += _folds(
            table, n, {len(table)}, essential, columns=min(width, columns)
        )
    return _smallest(*(_fit(layout, width) for layout in layouts))


def balance_alight(
    table: str,
    default: str,
    *,
    expression_syntax: str = "infix",
) -> str:
    """Balance the layouts that can win the native minimax width selector."""
    n = _validate_truth_table(table)
    weights, projected = input_weights(table, n)
    # Constants have no index inputs; reads remain in stream order.
    essential = [bool(weight) for weight in weights]
    return _balance_projected(projected, n, default, essential, expression_syntax)


def _balance_projected(
    table: str, n: int, default: str, essential: list[bool], expression_syntax: str
) -> str:
    """Balance an indexed lookup after projecting its input dimensions.

    Folds at the square-root chunk counts of both aspect ratios compete with
    ``default``: geometry ignores the literal's bits, so the best count is a
    function of the table size alone.
    """
    postfix = expression_syntax == "postfix"
    chunks = _square_chunks(len(table), "balance")
    candidates = [default, *_folds(table, n, chunks, essential, postfix=postfix)]
    for columns in _square_columns(len(default), "balance"):
        candidates += _folds(
            table, n, {len(table)}, essential, postfix=postfix, columns=columns
        )
    return min(candidates, key=balance_score)


LANGUAGE = Language(
    "Alight",
    "alight",
    category="grid_based",
    boolean=alight,
    dialect=_dialect,
    dialect_values={
        "expression_syntax": EXPRESSION_SYNTAXES,
        "list_update": LIST_UPDATES,
    },
    # Not a tree: a Horner row index into a string literal.
    shape=Shape.LOOKUP,
    split=True,
    contract=BooleanContract(
        input_shape="char_stream",
    ),
    balance=balance_alight,
    no_wrap="a command is a word walked cell by cell; a row end cuts it",
    eof="it raises its own error before the read is reached",
    underfed_raises=True,
    empty_program="empty program",
    proof_workspace=(workspace, True, (3, 5)),
)
