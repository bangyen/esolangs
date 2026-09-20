"""Befunge boolean program builder: the grid is the lookup table.

``befunge(truth_table)`` reads one ``0``/``1`` line per input, folds them
into a row index with Horner's rule, and reads the answer out of a grid the
generator wrote, one cell per table entry.  ``g`` addresses a cell by
coordinate, so the table is data the instruction pointer never walks: O(T)
cells of source and O(n) executed commands, no branch and no loop.
"""

from __future__ import annotations

from esolangs.tools.helpers import _validate_truth_table

#: ``6 * 8``: Befunge has no multi-digit literal, so 48 is built arithmetically.
_ASCII_ZERO = "68*"


def befunge(truth_table: str) -> str:
    """Return a Befunge grid computing ``truth_table``.

    Row 0 is the header, which consumes the bits and ``g``s the answer; the
    table follows, ``width`` columns wide, so row ``r`` sits at
    ``(r % width, 1 + r // width)``.  ``width`` is a power of two near
    ``sqrt(T)``, built by doubling so the header stays O(n) wide, and the
    answer is the cell's character less the ASCII zero.
    """
    n = _validate_truth_table(truth_table)
    count = 1 << n
    shift = (n + 1) // 2
    width = 1 << shift
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
        + "-.@"
    )
    rows = [header]
    rows.extend(truth_table[base : base + width] for base in range(0, count, width))
    return "\n".join(rows)
