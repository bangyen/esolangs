"""Befunge Boolean program generator: the grid is the lookup table.

Reads one ``0``/``1`` integer token per input, folds them into a row index
with Horner's rule, and ``g`` fetches the answer from a table the instruction
pointer never walks: one cell per entry through ten inputs, six per cell above.

Size:
    O(T) cells, O(n) executed commands, no branch or loop; n=4 parity: 65
    chars, n=10 random 1847: 1,115 chars, n=13 random 1847: 1,545 chars.

Raises:
    GeneratorCapError: more than thirteen inputs, past the 80x25 grid.

Decisions:
    A grid has no subtrees, so nothing folds or is shared.
"""

from __future__ import annotations

from math import isqrt

from esolangs.exceptions import GeneratorCapError
from esolangs.generation.helpers import (
    _parity_bias,
    _validate_truth_table,
    input_weights,
)
from esolangs.generation.token_balance import CELL_ASPECT
from esolangs.generation.wrap import balance_score
from esolangs.languages.befunge.proof_formulas import execution, workspace
from esolangs.registry._language import Example, Language, Shape
from esolangs.runtime.source_hints import with_hint

#: ``6 * 8``: Befunge has no multi-digit literal, so 48 is built arithmetically.
_ASCII_ZERO = "68*"
_END = ".@"

MAX_INPUTS = 13
#: Header cells beyond the input reads: narrow (single-digit columns), wide
#: (two-digit columns), packed (two-digit columns plus the six-bit decode).
_BOUND_NARROW = 22
_BOUND_WIDE = 34
_BOUND_PACKED = 64

#: Projected-count cap for the natural layout: a table whose projection
#: onto its essential inputs has at most this many entries is laid out
#: at its natural width instead of the grid's 80.  It saves area at
#: counts 1 and 2 and loses at counts 4 and 8, so the wide layout keeps
#: every larger table ([ablations.sqrt_width_layout]).
_NATURAL_LAYOUT_MAX_COUNT = 2


def _check_cap(n: int) -> None:
    if n > MAX_INPUTS:
        raise with_hint(
            GeneratorCapError(
                "Befunge supports at most thirteen inputs on its 80x25 grid"
            ),
            (
                "check another generator's limits; width "
                "cannot enlarge Befunge's fixed 80x25 grid"
            ),
        )


def _min_columns(count: int, bound: int) -> int:
    """Return the fewest columns that keep ``count`` and ``bound`` under 25 rows."""
    return (count + bound + 22) // 23 + 2


def _header_rows(bound: int, columns: int) -> int:
    """Return the rows a header of ``bound`` cells folds into at ``columns``."""
    return (bound + columns - 3) // (columns - 2)


def _header(reads: str, width: str, offset: str) -> str:
    """Return the lookup header: fold ``reads`` into an index, print ``g`` at it."""
    return (
        "0"
        + reads
        + ":"
        + width
        + "%\\"
        + width
        + "/"
        + offset
        + "+g"
        + _ASCII_ZERO
        + "-"
        + _END
    )


def _natural_befunge(truth_table: str) -> str:
    """Return a Befunge grid at the table's natural width.

    The pre-#20 default build, kept for the smallest projections: a
    straight header over a power-of-two table width near ``sqrt(T)``.
    """
    n = _validate_truth_table(truth_table)
    _check_cap(n)
    # An ignored input is read and popped; the table indexes the rest.
    weights, table = input_weights(truth_table, n)
    reads = "".join("&\\2*+" if weight else "&$" for weight in weights)
    count = len(table)
    # The natural grid: a straight header over a power-of-two table width near
    # ``sqrt(T)``.  At counts up to _NATURAL_LAYOUT_MAX_COUNT that is the
    # header over one row, and the header is at most 49 cells (n=13), so it
    # never needs the 80x25 fold the wide build has.
    table_width, build_width = _natural_width(count)
    return "\n".join(_rows(_header(reads, build_width, "1"), table, table_width))


def _natural_width(count: int) -> tuple[int, str]:
    """Return the power-of-two table width near ``sqrt(count)`` and its push."""
    shift = count.bit_length() // 2
    # ``1`` then ``2*`` shift times is ``2**shift``; both are single commands.
    return 1 << shift, "1" + "2*" * shift


def _rows(header: str, table: str, step: int) -> list[str]:
    """Return ``header`` over ``table`` cut into rows of ``step`` cells."""
    return [header, *(table[at : at + step] for at in range(0, len(table), step))]


def befunge(truth_table: str, width: int | None = None) -> str:
    """Return a Befunge grid computing ``truth_table``, at most ``width`` wide."""
    n = _validate_truth_table(truth_table)
    _check_cap(n)
    # An ignored input is read and popped; the table indexes the rest.
    weights, table = input_weights(truth_table, n)
    if width is None and len(table) <= _NATURAL_LAYOUT_MAX_COUNT:
        # The smallest projections take the natural layout (see the
        # cap's note); an explicit width keeps the wide build.
        return _natural_befunge(truth_table)
    reads = "".join("&\\2*+" if weight else "&$" for weight in weights)
    if len(table) > 1 << 10:
        return _packed_befunge(table, reads, width)
    if width is not None and width < 4:
        bias = _parity_bias(truth_table)
        if bias is not None:
            # One vertical column of sums modulo two: at most 25 commands even
            # at n=10, within the native torus.
            header = "v&" + "&+" * (n - 1) + "2%" + ("!" if bias else "") + _END
            return "\n".join(header)
    count = len(table)
    if width is None:
        # The default build lays the table at the grid's width: at the
        # natural sqrt width the header sets the longest row while the
        # narrow table multiplies the row count, costing 2.5-4.1x the
        # wide layout's area at n=6..8 (retirement candidate 20).  An
        # explicit width still tries the natural layout first.
        table_width = 80
        build_width = _literal(80)
    else:
        # The natural grid: a straight header over a power-of-two table
        # width near ``sqrt(T)``; an over-wide header folds
        # (:func:`_fold_header`).
        table_width, build_width = _natural_width(count)
    rows = _rows(_header(reads, build_width, "1"), table, table_width)
    plain = "\n".join(rows)
    if width is None:
        width = 80
    if max(map(len, rows)) <= min(width, 80) and len(rows) <= 25:
        return plain
    # At most two decimal digits per coordinate on the 80x25 torus.
    # Reserving 23 rows of payload leaves the ceiling slack below 25 rows.
    # Single-digit column counts save twelve literal cells (10.5% of area at
    # n=6, widths 4-8; unreachable at n>=7); the narrow bound applies only
    # when it proves that the count remains single-digit.
    header_bound = len(reads) + _BOUND_NARROW
    columns = max(width, 4, _min_columns(count, header_bound))
    if columns >= 10:
        header_bound = len(reads) + _BOUND_WIDE
        columns = min(80, max(width, 4, _min_columns(count, header_bound)))
    literal = _literal(columns)
    header = _header(reads, literal, "1")
    if len(header) <= columns:
        # The header fits on one row: folding it over two rows adds a
        # full row of area and buys nothing at n=9/10, where 78 header
        # cells fit the 80 columns ([ablations.header_folding]).  Narrower
        # widths still fold below.
        return "\n".join(_rows(header, table, columns))
    header_rows = _header_rows(header_bound, columns)
    header = _header(reads, literal, _literal(header_rows))
    folded = _fold_header(header, columns, header_rows)
    folded.extend(table[base : base + columns] for base in range(0, count, columns))
    return "\n".join(folded)


def _fold_header(header: str, columns: int, header_rows: int) -> list[str]:
    """Return alternating instruction rows with the reserved table offset."""
    folded = []
    for row, base in enumerate(range(0, len(header), columns - 2)):
        payload = header[base : base + columns - 2].ljust(columns - 2)
        folded.append(
            ">" + payload + "v" if row % 2 == 0 else "v" + payload[::-1] + "<"
        )
    folded.extend("" for _ in range(header_rows - len(folded)))
    return folded


def _packed_befunge(truth_table: str, reads: str, width: int | None) -> str:
    """Return a six-bit printable-ASCII lookup within the fixed torus."""
    count = (len(truth_table) + 5) // 6
    # Two-digit columns and a single-digit header offset cost 64 cells
    # beyond the input fold. The floor gives at most six header rows and
    # ceil(B/(W-2)) + ceil(T/W) <= 25, including the n=13 dense build.
    bound = len(reads) + _BOUND_PACKED
    requested = 80 if width is None else width
    columns = min(80, max(requested, _min_columns(count, bound)))
    header_rows = _header_rows(bound, columns)
    literal = _literal(columns)
    # For u = row % 6, its binary digits build 2**u without a loop:
    # (1+u%2)*(1+3*((u//2)%2))*(1+15*(u//4)).
    header = (
        "0"
        + reads
        + ":6%:2%1+\\:2/2%3*1+\\4/35**1+**\\6/:"
        + literal
        + "%\\"
        + literal
        + "/"
        + _literal(header_rows)
        + "+g48*-\\/2%"  # 48* is 32, the packed chr offset
        + _END
    )
    folded = _fold_header(header, columns, header_rows)
    data = "".join(
        chr(32 + int(truth_table[base : base + 6][::-1], 2))
        for base in range(0, len(truth_table), 6)
    )
    folded.extend(data[base : base + columns] for base in range(0, count, columns))
    return "\n".join(folded)


def _literal(value: int) -> str:
    """Push ``value`` with decimal Horner arithmetic, one digit per cell."""
    digits = str(value)
    return digits[0] + "".join("91+*" + digit + "+" for digit in digits[1:])


def balance_befunge(truth_table: str, default: str) -> str:
    """Return the best-balanced supported Befunge grid within its 80x25 torus.

    Each fixed header bound B gives H=ceil(B/(W-2))+ceil(T/W).  With
    A=CELL_ASPECT, its W=A*H crossing lies between s and s+2A for
    s=ceil(sqrt(A*(B+T))).
    """
    n = _validate_truth_table(truth_table)
    count = 1 << n
    _check_cap(n)
    candidates = [default]
    layouts = [(5 * n + _BOUND_NARROW, 4, 9), (5 * n + _BOUND_WIDE, 10, 80)]
    if n > 10:
        count = (count + 5) // 6
        layouts = [(5 * n + _BOUND_PACKED, 10, 80)]
    for bound, low, high in layouts:
        floor = max(low, _min_columns(count, bound))
        if floor > high:
            continue
        side = isqrt(CELL_ASPECT * (count + bound) - 1) + 1
        # H >= (B+T)/W and H <= (B+T)/(W-2)+2.  The winner is one of the
        # crossing's neighbours: over 192 layouts (n=1..13) offsets -1..2
        # from s won every one, and 3..4 never beat them (test oracle).
        candidates.extend(
            befunge(truth_table, min(high, max(floor, width)))
            for width in (side - 1, side, side + 1, side + 2)
        )
    if n <= 10 and _parity_bias(truth_table) is not None:
        candidates.append(befunge(truth_table, 1))
    return min(candidates, key=balance_score)


LANGUAGE = Language(
    "Befunge",
    "befunge",
    category="grid_based",
    layout_switch=(10, 11),
    random=True,
    generator_max_inputs=MAX_INPUTS,
    boolean=befunge,
    # Not a tree: reads a packed grid cell with ``g``.
    shape=Shape.LOOKUP,
    split=True,
    balance=balance_befunge,
    no_wrap="a row is a grid row and the lookup table is indexed by column",
    empty_program="Befunge program cannot be empty",
    # ``.`` writes the digit and a trailing space, so the committed
    # answer carries it and the sweep strips it.
    example=Example(expected="0 "),
    proof_execution=(execution, True, (3, 9, 11)),
    proof_workspace=(workspace, True, (3, 9, 11)),
    grid=True,
)
