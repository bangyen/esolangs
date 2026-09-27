"""Bitwise Cyclic Tag boolean program builder: the table as a forward walk.

BCT has no I/O and no branch.  The commands executed are a fixed cyclic
sequence, so the program position after ``k`` steps does not depend on the
input at all; the only thing an input can change is *how much* data is
appended, and therefore how far the program has advanced by the time a
later data-bit is read.  That makes address arithmetic the natural
construction rather than a clever one: convert the inputs into a length,
and let the length carry the pointer to the row.

Input ``i`` is met by ``10`` repeated ``2**(n-i+1)`` times and then a ``0``
that deletes it, so a set bit appends that many zeros and a clear bit
appends none.  The zeros therefore total exactly ``2 * index``.  Behind the
inputs the data-string carries a constant ``1``, which appends one ``1`` of
its own -- landing after every zero, since appends go to the right end --
and is then deleted.

The table is one four-bit cell ``1 x 0 0`` per row, in index order, ``x``
being that row's answer.  Passing over a zero costs a whole cell: ``1x``
does not fire on a leading ``0``, and the two ``0``s delete two zeros while
the pointer advances four bits.  So ``2 * index`` zeros land the pointer on
cell ``index`` precisely, with the held-back ``1`` now leftmost.  There
``1x`` fires and appends the answer, the first ``0`` consumes the ``1`` and
the second consumes the answer, the data-string empties and the run stops --
so the answer is the bit the last ``0`` consumed, which is the convention
the interpreter prints.

The program is ``8T + n - 1`` bits and the whole source ``8T + 2n + 1``
characters, the data-string and the separator being the rest; a run is at
most ``5T + n`` steps.  All ``Theta(T)``: ``4T`` of the program appends the
walk at two bits a zero, and ``4T`` is the table at four bits a row.  Both
figures are exact, not bounds, and the suite pins them.  The program never
wraps, so the
cyclic schedule is unused -- a straight line is what a loop-less
construction wants, and the interpreter's wrap is covered by its own tests.

The second ``0`` in a cell is what costs the factor: a three-bit ``1 x 0``
cell would halve both regions, but then the appended answer is still on the
data-string when the *next* cell's ``1x`` reads it, so a ``1`` answer
appends the following row's bit and cascades down the table until it meets a
``0``, returning that instead.  The second ``0`` consumes the answer inside
the cell that produced it, before any later ``1`` can see it.  Two zeros a
cell is the price of a readout that cannot cascade.
"""

from __future__ import annotations

from esolangs.tools.helpers import TEMPLATE_CHAR, _validate_truth_table

#: How each input is set: one bit of the initial data-string, so the run is
#: one :data:`TEMPLATE_CHAR`.
PAIR = ("0", "1")

#: The constant bit held behind the inputs.  It is appended once and read
#: after every walk zero, which is what makes it the marker that arrives at
#: the addressed cell.
_SENTINEL = "1"


def bitwise_cyclic_tag(truth_table: str) -> str:
    """Return a BCT template computing ``truth_table``.

    The template is ``program,data``: the data-string is one
    :data:`TEMPLATE_CHAR` per input followed by the sentinel, and
    :func:`~esolangs.instantiate` fills the runs with :data:`PAIR`.
    """
    n = _validate_truth_table(truth_table)
    parts = []
    for i in range(1, n + 1):
        # A set bit appends 2**(n-i+1) zeros, which is two walk zeros per
        # unit of this input's place value -- one cell's worth each.
        parts.append("10" * (1 << (n - i + 1)))
        parts.append("0")  # delete the input bit, whichever way it went
    parts.append("1" + _SENTINEL)  # the sentinel appends itself, last of all
    parts.append("0")  # and is deleted, leaving the walk zeros ahead of it
    for answer in truth_table:
        parts.append("1" + answer + "00")
    data = TEMPLATE_CHAR * n + _SENTINEL
    return f"{''.join(parts)},{data}"
