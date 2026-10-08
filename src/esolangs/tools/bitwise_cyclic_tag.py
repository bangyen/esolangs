"""Bitwise Cyclic Tag boolean program builder: the table as a forward walk.

BCT has no branch, so all an input can change is how much data is appended, and
so how far the pointer has moved when a later bit is read.  Input ``i`` appends
``2**(n-i+1)`` zeros when set, a sentinel ``1`` lands behind them, and the table
is one ``1 x 0 0`` cell a row consuming two zeros while advancing four -- so the
walk arrives at cell ``index`` and fires it, and no row can drop.  Emission is
``program,data``; the count and why a cell needs four bits: ``docs/proofs/index.md``.
"""

from __future__ import annotations

from esolangs.tools.helpers import TEMPLATE_CHAR, _validate_truth_table, input_weights

#: One bit of the initial data-string, so an input's run is one TEMPLATE_CHAR.
PAIR = ("0", "1")

#: The constant bit held behind the inputs, read after every walk zero.
_SENTINEL = "1"


def bitwise_cyclic_tag(truth_table: str) -> str:
    """Return the BCT template computing ``truth_table``."""
    n = _validate_truth_table(truth_table)
    # An ignored input appends nothing either way: its command is a bare ``0``.
    weights, table = input_weights(truth_table, n)
    parts = []
    for weight in weights:
        parts.append("10" * (2 * weight))
        parts.append("0")
    parts.append("1" + _SENTINEL)
    parts.append("0")
    for answer in table:
        parts.append("1" + answer + "00")
    data = TEMPLATE_CHAR * n + _SENTINEL
    return f"{''.join(parts)},{data}"
