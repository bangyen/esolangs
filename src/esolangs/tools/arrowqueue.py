"""Boolean-function generator for ArrowQueue: halt = 0, loop forever = 1.

A cascade: each stage doubles the queued markers then crosses the cell
(Horner); one ``+`` per row turns right at the indexed row.  The tree it
replaced (``n <= 4``) was at most 3.9% smaller at n=4 and kept ignored inputs.
Rows are reached by a Horner count, so no subtree is drawn to share.
Narrow paths drop ignored inputs too (area -46.8% / -70.5% at n=8, 1 / 2 ignored).
"""

from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Language
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

#: The same setter one column in, for the narrow paths.
_IGNORED_NARROW = [" " * 4 + TEMPLATE_CHAR]

#: The cascade's row per table entry: a ring right of the ``+``, or none.
_ROWS = {"0": [" +", "", ""], "1": [" + +~+", "   ~ ~", "   +~+"]}

#: A folded tail of ``1`` rows: every marker left laps the ``*`` square back
#: into one ``+``; the stop heading then enters the ring as on a ``1`` row.
_DRAINED_RING = ["*+ +~+", "** ~ ~", "   +~+"]


def arrowqueue(truth_table: str, width: int | None = None) -> str:
    """Build an ArrowQueue template that halts iff the table entry is ``0``."""
    n = _validate_truth_table(truth_table)
    width = max(width or 0, 0)  # 0, None and negative all mean unbounded
    weights, table = input_weights(truth_table, n)
    if 0 < width < 5:
        return _four_column_cascade(table, weights)
    narrow = 0 < width < 6
    leaves = _cascade(table)
    if narrow:
        leaves = [row[:2] + row[3:] for row in leaves]
    ignored = _IGNORED_NARROW if narrow else _IGNORED
    stages = [row for weight in weights for row in (_STAGE if weight else ignored)]
    rows = ["  ~*", *stages, *_MIDDLE, *leaves]
    return "\n".join(row.rstrip() for row in rows)


def _four_column_cascade(table: str, weights: list[int]) -> str:
    """Prepend a down marker to route the selector along column0."""
    # Shift input stages left; a clockwise detour lands down at column 1.
    stages = (row[1:] for w in weights for row in (_STAGE if w else _IGNORED_NARROW))
    rows = [" ~*", *stages, "**", "* *", " ~"]
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


def _compact(rows: list[str]) -> list[str]:
    """Drop the wholly blank rows and columns from the template's body.

    A blank line carries only straight travel; the header's glyphs sit past
    column 4, which every branch marks.
    """
    width = max(map(len, rows))
    padded = [row.ljust(width) for row in rows]
    kept = [row for row in padded if row.strip()]
    columns = [x for x in range(width) if any(row[x] != " " for row in kept)]
    return ["".join(row[x] for x in columns).rstrip() for row in kept]


LANGUAGE = Language(
    "ArrowQueue",
    "grid_based.arrowqueue",
    boolean=arrowqueue,
    split=True,
    contract=BooleanContract(
        answer_mode="termination",
        answer_values=("halts", "diverges"),
        note="ArrowQueue answers by termination -- it halts for a 0 result "
        "and loops forever for a 1, so only the halting branch is "
        "committed.  The headings printed are its interpreter-only "
        "queue dump, which the verdict does not read: the answer is "
        "that the program halted at all",
        parameterized=True,
    ),
)
