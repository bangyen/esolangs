"""Befunge boolean program builder: the grid is the lookup table.

``befunge(truth_table)`` reads one ``0``/``1`` integer token per input, folds them
into a row index with Horner's rule, and reads the answer out of a grid the
generator wrote, one cell per entry through ten inputs and six bits per cell
above that. ``g`` addresses data the instruction pointer never walks: O(T)
cells of source and O(n) executed commands, no branch and no loop.
"""

from __future__ import annotations

from math import isqrt

from esolangs.exceptions import GeneratorCapError
from esolangs.interpreters.source_hints import with_hint
from esolangs.tools.helpers import _parity_bias, _validate_truth_table
from esolangs.tools.wrap import balance_score

#: ``6 * 8``: Befunge has no multi-digit literal, so 48 is built arithmetically.
_ASCII_ZERO = "68*"
_END = ".@"


MAX_INPUTS = 13


def befunge(truth_table: str, width: int | None = None) -> str:
    """Return a Befunge grid computing ``truth_table``.

    The natural grid has a straight header and a power-of-two table width
    near ``sqrt(T)``.  An over-wide header folds along alternating rows;
    ``g`` addresses the table below them.  The width floor reserves enough
    cells for both within the 80x25 torus. Above ten inputs, printable ASCII
    cells pack six answers each; tables above thirteen inputs raise
    ``GeneratorCapError``. Narrow parity uses one vertical column of sums
    modulo two instead.
    """
    n = _validate_truth_table(truth_table)
    count = 1 << n
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
    if n > 10:
        return _packed_befunge(truth_table, n, width)
    if width is not None and 0 < width < 4:
        bias = _parity_bias(truth_table)
        if bias is not None:
            # At most 25 commands even at n=10, within the native torus.
            header = "v&" + "&+" * (n - 1) + "2%" + ("!" if bias else "") + _END
            return "\n".join(header)
    shift = (n + 1) // 2
    table_width = 1 << shift
    # ``1`` then ``2*`` shift times is ``2**shift``; both are single commands.
    build_width = "1" + "2*" * shift
    header = (
        "0"
        + "&\\2*+" * n
        + ":"
        + build_width
        + "%\\"
        + build_width
        + "/1+g"
        + _ASCII_ZERO
        + "-"
        + _END
    )
    rows = [header]
    rows.extend(
        truth_table[base : base + table_width] for base in range(0, count, table_width)
    )
    plain = "\n".join(rows)
    if width is None or width <= 0:
        width = 80
    if max(map(len, rows)) <= min(width, 80) and len(rows) <= 25:
        return plain
    # At most two decimal digits per coordinate on the 80x25 torus.
    # Reserving 23 rows of payload leaves the ceiling slack below 25 rows.
    header_bound = 5 * n + 34
    columns = min(80, max(width, 4, (count + header_bound + 22) // 23 + 2))
    # Single-digit column counts save twelve literal cells.  This named
    # bound applies only when it proves that the count remains single-digit.
    narrow_bound = 5 * n + 22
    narrow_columns = max(width, 4, (count + narrow_bound + 22) // 23 + 2)
    if narrow_columns < 10:
        columns, header_bound = narrow_columns, narrow_bound
    header_rows = (header_bound + columns - 3) // (columns - 2)
    literal = _literal(columns)
    header = (
        "0"
        + "&\\2*+" * n
        + ":"
        + literal
        + "%\\"
        + literal
        + "/"
        + _literal(header_rows)
        + "+g"
        + _ASCII_ZERO
        + "-"
        + _END
    )
    folded = _fold_header(header, columns, header_rows)
    folded.extend(
        truth_table[base : base + columns] for base in range(0, count, columns)
    )
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


def _packed_befunge(truth_table: str, n: int, width: int | None) -> str:
    """Return a six-bit printable-ASCII lookup within the fixed torus."""
    count = (len(truth_table) + 5) // 6
    # Two-digit columns and a single-digit header offset cost 64 cells
    # beyond the input fold. The floor gives at most six header rows and
    # ceil(B/(W-2)) + ceil(T/W) <= 25, including the n=13 dense build.
    bound = 5 * n + 64
    requested = 80 if width is None or width <= 0 else width
    columns = min(80, max(requested, (count + bound + 22) // 23 + 2))
    header_rows = (bound + columns - 3) // (columns - 2)
    literal = _literal(columns)
    # For u = row % 6, its binary digits build 2**u without a loop:
    # (1+u%2)*(1+3*((u//2)%2))*(1+15*(u//4)).
    header = (
        "0"
        + "&\\2*+" * n
        + ":6%:2%1+\\:2/2%3*1+\\4/35**1+**\\6/:"
        + literal
        + "%\\"
        + literal
        + "/"
        + _literal(header_rows)
        + "+g48*-\\/2%.@"
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

    Each fixed header bound B gives H=ceil(B/(W-2))+ceil(T/W).
    Its W=H crossing lies between s and s+2 for s=ceil(sqrt(B+T)).
    """
    n = _validate_truth_table(truth_table)
    count = 1 << n
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
    candidates = [default]
    layouts = [(5 * n + 22, 4, 9), (5 * n + 34, 10, 80)]
    if n > 10:
        count = (count + 5) // 6
        layouts = [(5 * n + 64, 10, 80)]
    for bound, low, high in layouts:
        floor = max(low, (count + bound + 22) // 23 + 2)
        if floor > high:
            continue
        side = isqrt(count + bound - 1) + 1
        # H >= (B+T)/W and H <= (B+T)/(W-2)+2. Only the
        # crossing and its predecessor can minimize |W-H| in each range.
        candidates.extend(
            befunge(truth_table, min(high, max(floor, width)))
            for width in (side - 1, side, side + 1, side + 2)
        )
    if n <= 10 and _parity_bias(truth_table) is not None:
        candidates.append(befunge(truth_table, 1))
    return min(candidates, key=balance_score)
