"""Boolean-function generator for Alight.

Derived, not transliterated (the page is unimplemented).  Alight's
``at{list, index}`` takes the index as an expression, so the table is a
string literal and the input bits fold into its row by Horner's rule,
``row = ((b0 * 2 + b1) * 2 + b2)...``, minus their ASCII offset: O(n)
commands over an O(2**n) literal, no branching.  That is why its
``shape`` is ``LOOKUP``: a 0% fold is the construction working: a literal has
no subtrees to fold or share.  The reads are unconditional and first.
"""

from collections.abc import Callable
from functools import cache
from itertools import pairwise
from math import isqrt, prod
from typing import NamedTuple

from esolangs.generation.helpers import (
    _ASCII_ZERO,
    _validate_truth_table,
    input_weights,
)
from esolangs.generation.token_balance import near_even_counts
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

    Reads ``n`` characters, folds them into the row by Horner, prints the
    table character: a branch-free single line, ``O(2**n)`` literal plus
    ``O(n)`` reads.  ``width`` is a hard bound; the layout minimizing
    ``max(width, height)`` wins for infix, ties preferring less area.
    Postfix folds commands or rotates them into one column.  Only
    two-argument ``at`` is emitted, so every ``list_update`` runs it.
    """
    return _program(
        truth_table, width, expression_syntax=expression_syntax, list_update=list_update
    )


class _Layout(NamedTuple):
    """The dimensions selecting an Alight layout strategy.

    ``expression_syntax`` is ``"infix"`` or ``"postfix"``; ``unbounded``
    is ``width is None``; ``dropped`` marks tables with ignored inputs,
    which are read and dropped while the rest index the lookup.
    """

    expression_syntax: str
    unbounded: bool
    dropped: bool


class _Build(NamedTuple):
    """Resolved inputs for one layout decision."""

    truth_table: str
    n: int
    width: int | None
    projected: str
    essential: list[bool]
    dropped: bool


def _layout_flat_infix(build: _Build) -> str:
    """Return the unbounded infix layout: one straight lookup."""
    if build.dropped:
        return _alight_flat_compact(build.projected, build.n, build.essential)
    return _alight_flat_compact(build.truth_table, build.n)


def _layout_flat_postfix(build: _Build) -> str:
    """Return the unbounded postfix layout: one straight lookup."""
    if build.dropped:
        return _flatten(
            _postfix_units(
                build.projected, build.n, len(build.projected), build.essential
            )
        )
    return _flatten(_postfix_units(build.truth_table, build.n, len(build.truth_table)))


def _layout_bounded_infix(build: _Build) -> str:
    """Return the bounded infix layout without dropped inputs."""
    width = build.width
    assert width is not None
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

    ``select_alight`` models ``n`` reads, so the dropped build is rendered
    from the model's plan for the projected table.  32.6% by chars at n=8,
    1 ignored, width 80 (audit).
    """
    width = build.width
    assert width is not None
    essential = build.essential
    plan = min(
        (p for p in _plans(build.n, tuple(essential)) if p.ready() <= width),
        key=_Plan.score,
    )
    planned = _emit(build.projected, build.n, plan, essential)
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


_STRATEGIES: dict[_Layout, Callable[[_Build], str]] = {
    _Layout("infix", unbounded=True, dropped=False): _layout_flat_infix,
    _Layout("infix", unbounded=True, dropped=True): _layout_flat_infix,
    _Layout("postfix", unbounded=True, dropped=False): _layout_flat_postfix,
    _Layout("postfix", unbounded=True, dropped=True): _layout_flat_postfix,
    _Layout("infix", unbounded=False, dropped=False): _layout_bounded_infix,
    _Layout("infix", unbounded=False, dropped=True): _layout_bounded_dropped,
    _Layout("postfix", unbounded=False, dropped=False): _layout_bounded_postfix,
    _Layout("postfix", unbounded=False, dropped=True): _layout_bounded_postfix,
}


def _program(
    truth_table: str,
    width: int | None = None,
    *,
    expression_syntax: str = "infix",
    list_update: str = "in_place",
    keep_constant_input: bool = False,
) -> str:
    """Lay out the lookup, optionally retaining constant-input indexing."""
    n = _validate_truth_table(truth_table)
    _dialect(expression_syntax, list_update)
    if width is not None and width < 1:
        raise ValueError("width must be at least 1")
    weights, projected = input_weights(truth_table, n)
    essential = [bool(weight) for weight in weights]
    # An ignored input is read and dropped, and the table is indexed by the
    # rest, including the one-entry table of a constant.
    dropped = not all(weights) and (any(weights) or not keep_constant_input)
    build = _Build(
        truth_table=truth_table,
        n=n,
        width=width,
        projected=projected,
        essential=essential,
        dropped=dropped,
    )
    return _STRATEGIES[
        _Layout(expression_syntax, unbounded=width is None, dropped=dropped)
    ](build)


def _postfix_units(
    table: str, n: int, chunk: int, essential: list[bool] | None = None
) -> list[list[str]]:
    """Build the fold units in postfix notation."""
    return _alight_units(table, n, chunk, essential, postfix=True)


def _dialect(expression_syntax: str = "infix", list_update: str = "in_place") -> None:
    """Validate Alight's dialect settings, one keyword per setting."""
    validate_expression_syntax(expression_syntax)
    validate_list_update(list_update)


_Affine = tuple[int, int]
_EAST = len(_ALIGHT_EAST_TURN)
_WEST = len(_ALIGHT_WEST_TURN)
#: ``_Plan.kind``, also a score tiebreak, so the order is load-bearing.
_COLUMN, _ROW, _FOLD = 0, 1, 2


class _Plan(NamedTuple):
    kind: int
    columns: int
    chunk: int
    width: int
    height: int
    length: int

    def score(self) -> tuple[int, int, int, int, int]:
        return (
            max(self.width, self.height),
            self.width * self.height,
            self.length,
            self.kind,
            self.columns,
        )

    def ready(self) -> int:
        return max(self.width, self.columns)


def _fold_shape(
    pieces: list[_Affine], span: _Affine, value: int, stop: int
) -> tuple[int, int, int, int]:
    """Return width, height, length and the next greedy row-fit transition.

    ``pieces`` are ``(slope, intercept)`` affine lengths of each row-unit as
    a function of the fold width ``value``; ``span`` is the same pair for
    the widest row.  Units are placed greedily left to right, each row
    reserving its turn's cells; a row fails when its affine width plus the
    turn reserve exceeds the widest row.  That boundary,
    ``rate * value + offset``, is linear in ``value``, so ``stop`` narrows
    to the nearest width that could change the fit, letting the caller step
    straight there instead of re-testing every width.
    """
    at = 0
    rows = 0
    while at < len(pieces):
        reserve = _EAST if rows == 0 else (_WEST + 1 if rows % 2 else _EAST + 1)
        used = (0, 0)
        while at < len(pieces):
            piece = pieces[at]
            total = (used[0] + piece[0], used[1] + piece[1])
            if used != (0, 0):
                rate = total[0] - span[0]
                offset = total[1] - span[1] + reserve
                failed = rate * value + offset > 0
                if rate < 0 and failed:
                    stop = min(stop, (offset - rate - 1) // -rate)
                elif rate > 0 and not failed:
                    stop = min(stop, -offset // rate + 1)
                if failed:
                    break
            used = total
            at += 1
        rows += 1
    columns = span[0] * value + span[1]
    last = used[0] * value + used[1]
    east, west = rows // 2, (rows - 1) // 2
    height = _EAST * east + _WEST * west + 1
    if rows == 1:
        return last, 1, last, stop
    final = columns if rows % 2 == 0 else last + 1
    east_ink = _EAST - 1 - _ALIGHT_EAST_TURN[:-1].count(" ")
    west_ink = _WEST - 1 - _ALIGHT_WEST_TURN[:-1].count(" ")
    length = (
        (rows - 1 + east_ink * east) * columns + west_ink * west + final + height - 1
    )
    return columns, height, length, stop


class _Rows(NamedTuple):
    """Fold-model inputs: literal ``size``, command widths around the lookup."""

    size: int
    prefix: list[int]
    lookup: int
    tail: list[int]
    flat: int

    @property
    def overhead(self) -> int:
        """Guard and lookup width around the index text."""
        return _ALIGHT_OVERHEAD + 2 * len(_half_before(self.size))


def _whole_folds(rows: _Rows) -> list[_Plan]:
    """Fold plans with the whole table in one lookup, one per fit transition.

    They win only at n<=4 (dropping them costs +74-84% minimax there, 0.00%
    at n=5..9 over 200 random tables, bounded and balanced).
    """
    size = rows.size
    shift = rows.overhead + _EAST
    whole = (
        1
        if _alight_chunk(size, 1) == size
        else shift + size + rows.lookup - rows.overhead
    )
    lengths = [*rows.prefix, size + rows.lookup, *rows.tail]
    pieces = [(0, length) for length in lengths]
    widest = max(lengths)
    lower = max(whole, widest + _EAST + 1)
    upper = max(lower, rows.flat)
    plans = []
    while lower <= upper:
        width, height, length, stop = _fold_shape(pieces, (1, 0), lower, upper + 1)
        columns = whole if lower == widest + _EAST + 1 else lower
        plans.append(_Plan(_FOLD, columns, size, width, height, length))
        lower = stop
    return plans


def _chunked_folds(rows: _Rows) -> list[_Plan]:
    """Fold plans splitting the table into ``count`` guarded lookups."""
    size = rows.size
    shift = rows.overhead + _EAST
    cutoff = size + rows.lookup - rows.overhead
    plans: list[_Plan] = []
    if cutoff <= 1:
        return plans
    maximum = cutoff - 1
    powers = []
    power = 10
    while power < size:
        powers.append(power + 1)
        power *= 10
    for count in near_even_counts(size):
        low = (size + count - 1) // count
        high = min(maximum, (size - 1) // (count - 1))
        if low > high:
            continue
        events = {low, high + 1}
        for number in range(1, count):
            events.update(
                point
                for power in powers
                if low < (point := (power + number - 1) // number) <= high
            )
        for lo, hi in pairwise(sorted(events)):
            first = (1, 30 + len(_half_before(lo)))
            pieces = [(0, length) for length in rows.prefix] + [first]
            for number in range(1, count):
                digits = len(_half_before(number * lo))
                pieces.append(
                    (1 - count, size + 27 + 2 * digits)
                    if number == count - 1
                    else (1, 27 + 2 * digits)
                )
            pieces.extend((0, length) for length in rows.tail)
            while lo < hi:
                width, height, length, stop = _fold_shape(pieces, (1, shift), lo, hi)
                columns = 1 if lo == 1 else lo + shift
                plans.append(_Plan(_FOLD, columns, lo, width, height, length))
                lo = stop
    return plans


@cache
def _plans(n: int, kept: tuple[bool, ...] | None = None) -> tuple[_Plan, ...]:
    """Return native-dominating fold endpoints; geometry ignores literal bits.

    ``kept`` marks the essential reads; the rest are bare ``inp`` and the
    table has ``2**sum(kept)`` rows.
    """
    essential = list(kept or (True,) * n)
    size = 1 << sum(essential)
    flat = size + len(_alight_flat_compact("", n, essential))
    base = [len(";".join(unit)) + 1 for unit in _alight_units("", n, 0, essential)]
    rows = _Rows(size, base[:-3], base[-3], base[-2:], flat)
    return (
        _Plan(_COLUMN, 0, 0, 1, flat, 2 * flat - 1),
        _Plan(_ROW, 0, 0, flat, 1, flat),
        *_whole_folds(rows),
        *_chunked_folds(rows),
    )


def _render(table: str, n: int, plan: _Plan, essential: list[bool] | None) -> str:
    """Return the program ``plan`` describes for ``table``."""
    flat = _alight_flat_compact(table, n, essential)
    if plan.kind == _COLUMN:
        return "\n".join(flat)
    if plan.kind == _ROW:
        return flat
    return _alight_folded(_alight_units(table, n, plan.chunk, essential), plan.columns)


def _emit(table: str, n: int, plan: _Plan, essential: list[bool] | None = None) -> str:
    program = _render(table, n, plan, essential)
    if (*_dimensions(program), len(program)) != (plan.width, plan.height, plan.length):
        raise AssertionError("Alight fold model disagrees with the rendered program")
    return program


def select_alight(table: str, n: int, width: int) -> str:
    """Return the original minimax winner among the permitted fit regimes."""
    plan = min((plan for plan in _plans(n) if plan.ready() <= width), key=_Plan.score)
    return _emit(table, n, plan)


def _squareness(width: int, height: int, length: int) -> tuple[int, int, int]:
    """Rank a shape: imbalance, then length, then width (``balance_score``'s order)."""
    return abs(width - height), length, width


def _balance_postfix(
    table: str, n: int, default: str, essential: list[bool] | None = None
) -> str:
    """Balance square-root chunks at greedy fold transitions."""
    width, height = _dimensions(default)
    best = _squareness(width, height, len(default))
    selected: tuple[list[list[str]], int, tuple[int, int, int]] | None = None
    # Whole-table chunks add 0.00% to the square-root chunk on 200 random
    # tables each at n=7 and 8; alone they lose 41-60% in area-imbalance.
    units = _postfix_units(table, n, isqrt(len(table) - 1) + 1, essential)
    pieces = [(0, len(";".join(unit)) + 1) for unit in units]
    lower = max(length for _, length in pieces) + _EAST + 1
    upper = sum(length for _, length in pieces)
    while lower <= upper:
        _, height, _, stop = _fold_shape(pieces, (1, 0), lower, upper + 1)
        # Height is constant until the next row-fit transition; its nearest
        # permitted width minimizes imbalance without a width sweep.
        columns = min(max(height, lower), stop - 1)
        width, height, length, _ = _fold_shape(pieces, (1, 0), columns, stop)
        score = _squareness(width, height, length)
        if score < best:
            best = score
            selected = units, columns, (width, height, length)
        lower = stop
    if selected is None:
        return default
    units, columns, shape = selected
    program = _alight_folded(units, columns)
    if (*_dimensions(program), len(program)) != shape:
        raise AssertionError("Alight postfix fold model disagrees with rendering")
    return program


def balance_alight(
    table: str,
    default: str,
    *,
    expression_syntax: str = "infix",
    keep_constant_input: bool = False,
) -> str:
    """Balance the layouts that can win the native minimax width selector."""
    n = _validate_truth_table(table)
    weights, projected = input_weights(table, n)
    # Constants have no index inputs; reads remain in stream order.
    essential = [bool(weight) for weight in weights]
    if not any(essential) and not keep_constant_input:
        legacy = _program(
            table, expression_syntax=expression_syntax, keep_constant_input=True
        )
        return min(
            _balance_projected(projected, n, default, essential, expression_syntax),
            balance_alight(
                table,
                legacy,
                expression_syntax=expression_syntax,
                keep_constant_input=True,
            ),
            key=balance_score,
        )
    if not any(essential) or all(essential):
        essential = [True] * n
        projected = table
    return _balance_projected(projected, n, default, essential, expression_syntax)


def _balance_projected(
    table: str, n: int, default: str, essential: list[bool], expression_syntax: str
) -> str:
    """Balance an indexed lookup after projecting its input dimensions."""
    if expression_syntax == "postfix":
        return _balance_postfix(table, n, default, essential)
    plans = _plans(n, tuple(essential))
    records = [next(plan for plan in plans if plan.kind == _ROW)]
    best: _Plan | None = None
    # Keep only the plans whose score improves as their ready width grows;
    # the balance winner is the squarest of those plus the row candidate.
    for plan in sorted(plans, key=lambda plan: (plan.ready(), plan.score())):
        if best is None or plan.score() < best.score():
            best = plan
            records.append(plan)
    selected = min(
        records, key=lambda plan: _squareness(plan.width, plan.height, plan.length)
    )
    return _emit(table, n, selected, essential)


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
)
