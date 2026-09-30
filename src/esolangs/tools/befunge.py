"""Befunge boolean program builder: the grid is the lookup table.

``befunge(truth_table)`` reads one ``0``/``1`` line per input, folds them
into a row index with Horner's rule, and reads the answer out of a grid the
generator wrote, one cell per table entry.  ``g`` addresses a cell by
coordinate, so the table is data the instruction pointer never walks: O(T)
cells of source and O(n) executed commands, no branch and no loop.
"""

from __future__ import annotations

from esolangs.tools.helpers import _parity_bias, _validate_truth_table

#: ``6 * 8``: Befunge has no multi-digit literal, so 48 is built arithmetically.
_ASCII_ZERO = "68*"
_END = ".@"


def befunge(truth_table: str, width: int | None = None) -> str:
    """Return a Befunge grid computing ``truth_table``.

    The natural grid has a straight header and a power-of-two table width
    near ``sqrt(T)``.  An over-wide header folds along alternating rows;
    ``g`` addresses the table below them.  The width floor reserves enough
    cells for both within the 80x25 torus.  Tables above ten inputs raise
    ``ValueError``: their cells alone exceed the torus. Narrow parity uses
    one vertical column of input sums modulo two instead.
    """
    n = _validate_truth_table(truth_table)
    count = 1 << n
    if count > 1024:
        raise ValueError("Befunge supports at most ten inputs on its 80x25 grid")
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
    folded = []
    for row, base in enumerate(range(0, len(header), columns - 2)):
        payload = header[base : base + columns - 2].ljust(columns - 2)
        folded.append(
            ">" + payload + "v" if row % 2 == 0 else "v" + payload[::-1] + "<"
        )
    folded.extend("" for _ in range(header_rows - len(folded)))
    folded.extend(
        truth_table[base : base + columns] for base in range(0, count, columns)
    )
    return "\n".join(folded)


def _literal(value: int) -> str:
    """Push ``value`` with decimal Horner arithmetic, one digit per cell."""
    digits = str(value)
    return digits[0] + "".join("91+*" + digit + "+" for digit in digits[1:])
