"""Befunge-98 boolean program builder: the lookup table, uncapped.

``befunge_98(truth_table)`` reads one ``0``/``1`` integer token per input,
folds them into a row index with Horner's rule, and ``g`` reads the answer
out of a table below the header, ``2**ceil(n/2)`` cells per row.  Befunge's
80x25 torus caps the same lookup at thirteen inputs; Funge-98 space is
unbounded, so this one is total: T + O(sqrt(T)) cells of source and O(n)
executed commands, no branch and no loop.
"""

from esolangs.tools.befunge import _fold_header
from esolangs.tools.helpers import _validate_truth_table


def befunge_98(truth_table: str, width: int | None = None) -> str:
    """Return a Befunge-98 program printing ``truth_table``'s answer.

    With ``width``, the table is ``width`` cells a row and the header folds
    to fit: snaking rows from three columns, one command a row below that.
    """
    n = _validate_truth_table(truth_table)
    if width is None or width <= 0:
        shift = (n + 1) // 2
        # ``1`` then ``2*`` shift times is the row width ``2**shift``.
        literal = "1" + "2*" * shift
        rows = [_header(n, literal, "1")]
        rows.extend(_table(truth_table, 1 << shift))
        return "\n".join(rows)
    literal = _literal(width)

    # Rows the header occupies, given the literal for its own row count.
    # The literal grows by one digit per decade, so two applications from
    # one row reach a count that holds its own literal.
    def needed(rows: int) -> int:
        cells = len(_header(n, literal, _literal(rows)))
        return cells + 1 if width < 3 else -(-cells // (width - 2))

    header_rows = needed(needed(1))
    header = _header(n, literal, _literal(header_rows))
    if needed(header_rows) > header_rows:
        raise AssertionError("the header outgrew its reserved rows")
    if width < 3:
        lines = ["v", *header]
        lines.extend("" for _ in range(header_rows - len(lines)))
    else:
        lines = _fold_header(header, width, header_rows)
    lines.extend(_table(truth_table, width))
    return "\n".join(lines)


def _header(n: int, width: str, rows: str) -> str:
    """Fold ``n`` reads into an index and print the table cell it names.

    Every command is one cell -- ``68*`` pushes 48, what ``'0`` would -- so
    a fold may cut the header anywhere: a turn between ``'`` and its
    operand would fetch the turn instead.
    """
    tail = rows + "+g68*-.@"
    return "0" + "&\\2*+" * n + ":" + width + "%\\" + width + "/" + tail


def _table(truth_table: str, width: int) -> list[str]:
    starts = range(0, len(truth_table), width)
    return [truth_table[base : base + width] for base in starts]


def _literal(value: int) -> str:
    """Push ``value``: one hex digit below 16, decimal Horner above."""
    if value < 16:
        return format(value, "x")
    digits = str(value)
    return digits[0] + "".join("a*" + digit + "+" for digit in digits[1:])
