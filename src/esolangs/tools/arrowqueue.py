"""Boolean-function generator for ArrowQueue: halt = 0, loop forever = 1.

A cascade: each stage doubles the queued markers then crosses the cell
(Horner); one ``+`` per row turns right at the indexed row.  The tree it
replaced (``n <= 4``) was at most 3.9% smaller at n=4 and kept ignored inputs.
Rows are reached by a Horner count, so no subtree is drawn to share.
"""

from esolangs.tools.helpers import (
    TEMPLATE_CHAR,
    _validate_truth_table,
    input_weights,
)

#: Each input's cell: ``~`` pushes a down heading, ``.`` nothing.
PAIR = (".", "~")

_MIDDLE = ["*~* ", "*  *", "*  *", "~ ~ ", "*~* ", "**  ", "*  *"]


_STAGE = ["  *+*", "   ~" + TEMPLATE_CHAR, "   ~", "  **", " *~*", " *  *"]

#: An ignored input's setter, off the selector's path: either fill leaves the
#: queue as it found it, so the cascade indexes the essential inputs alone.
_IGNORED = [" " * 5 + TEMPLATE_CHAR]

#: The cascade's row per table entry: a ring right of the ``+``, or none.
_ROWS = {"0": [" +", "", ""], "1": [" + +~+", "   ~ ~", "   +~+"]}

#: A folded tail of ``1`` rows: every marker left laps the ``*`` square back
#: into one ``+``; the stop heading then enters the ring as on a ``1`` row.
_DRAINED_RING = ["*+ +~+", "** ~ ~", "   +~+"]


def arrowqueue(truth_table: str, width: int | None = None) -> str:
    """Build an ArrowQueue template that halts iff the table entry is ``0``."""
    n = _validate_truth_table(truth_table)
    width = max(width or 0, 0)  # 0, None and negative all mean unbounded
    if 0 < width < 5:
        return _four_column_cascade(truth_table, n)
    narrow = 0 < width < 6
    # Five columns leave no room for an ignored input's setter.
    weights, table = ([1] * n, truth_table) if narrow else input_weights(truth_table, n)
    leaves = _cascade(table)
    if narrow:
        leaves = [row[:2] + row[3:] for row in leaves]
    stages = [row for weight in weights for row in (_STAGE if weight else _IGNORED)]
    rows = ["  ~*", *stages, *_MIDDLE, *leaves]
    return "\n".join(row.rstrip() for row in rows)


def _four_column_cascade(table: str, n: int) -> str:
    """Prepend a down marker to route the selector along column0; no input drop."""
    # Shift input stages left; a clockwise detour lands down at column 1.
    rows = [" ~*", *(row[1:] for row in _STAGE * n), "**", "* *", " ~"]
    # Append D, rotate the D markers to the R sentinel; queue becomes D^(index+1),R.
    rows.extend(["*+~*", " ~", "**"])
    rows.extend(_MIDDLE)
    # The extra D turns leftward travel down; consuming it restores the queue.
    rows.append("+*")
    for bit in table:
        # Unfold the constant tail: its old drain loop uses column0.
        rows.extend((row[:2] + row[3:])[1:] for row in _ROWS[bit])
    return "\n".join(row.rstrip() for row in rows)


def _cascade(truth_table: str) -> list[str]:
    """Build the cascade's rows, the table's constant tail folded.

    A ``0`` tail is dropped (running off the grid halts); a ``1`` tail is
    one :data:`_DRAINED_RING`, popping the markers the dropped rows would.
    """
    tail = len(truth_table.rstrip(truth_table[-1]))
    rows = [row for bit in truth_table[:tail] for row in _ROWS[bit]]
    return [*rows, *_DRAINED_RING] if truth_table[-1] == "1" else rows
