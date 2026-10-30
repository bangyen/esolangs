"""Bitwise Cyclic Tag Boolean program generator: the table as a forward walk.

BCT has no branch, so all an input can change is how much data is appended, and
so how far the pointer has moved when a later bit is read.  Input ``i`` appends
three zeros per unit of its place value over pairs of rows, the lowest input two,
and a sentinel ``1`` lands behind them.  A cell ``1 a 0 b 1 0 0`` holds two rows
and eats three zeros whatever ``b`` is (``b`` is a delete when 0, the operand of
the next ``1`` when 1), so the walk arrives at cell ``index // 2``; the sentinel
fires ``a`` or, two zeros later, ``b``, and the trailing ``00`` eats a 1 answer
so no indexed row cascades; a 0 answer is inert and the next delete eats it.
Constants delete the embedded inputs and a literal answer with a cyclic ``0``.
Emission is ``program,data``; the count and why a cell needs four bits:
``docs/proofs/index.md``.

Size:
    Theta(T) chars, 13/2 per row, independent of the table's values;
    n=10 random 1847: 6,679 chars, n=12 random 1847: 26,651 chars.
"""

from __future__ import annotations

from esolangs.generation.helpers import (
    TEMPLATE_CHAR,
    _validate_truth_table,
    input_weights,
)
from esolangs.generation.wrap import wrap_chars
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Example, Language, Shape

#: One bit of the initial data-string, so an input's run is one TEMPLATE_CHAR.
PAIR = ("0", "1")

#: The constant bit held behind the inputs, read after every walk zero.
_SENTINEL = "1"


def bitwise_cyclic_tag(truth_table: str) -> str:
    """Return the BCT template computing ``truth_table``."""
    return _program(truth_table)


def _read(weight: int) -> str:
    """One input's command: zeros it appends when set, then the ``0`` eating its bit."""
    if weight == 1:
        return "10" * 2 + "0"
    return "10" * (3 * (weight // 2)) + "0"


def _program(truth_table: str) -> str:
    """Build the indexed walk, or delete inputs and a literal constant answer."""
    n = _validate_truth_table(truth_table)
    if len(set(truth_table)) == 1:
        return "0," + TEMPLATE_CHAR * n + truth_table[0]
    # An ignored input appends nothing either way: its command is a bare ``0``.
    weights, table = input_weights(truth_table, n)
    reads = "".join(_read(weight) for weight in weights)
    rows = "".join(
        "1" + table[i] + "0" + table[i + 1] + "100" for i in range(0, len(table), 2)
    )
    return f"{reads}1{_SENTINEL}0{rows},{TEMPLATE_CHAR * n}{_SENTINEL}"


LANGUAGE = Language(
    "Bitwise Cyclic Tag",
    "bitwise_cyclic_tag",
    category="queue_based",
    boolean=bitwise_cyclic_tag,
    # A positional walk, not a tree of callable residuals.
    shape=Shape.LOOKUP,
    contract=BooleanContract(
        note="Bitwise Cyclic Tag has no I/O vocabulary at all: the inputs "
        "are bits of the initial data-string, and the answer is the "
        "bit the last 0 deletes, which the interpreter prints alone -- "
        "so the output is the answer and there is no position to name",
    ),
    # Safe anywhere: every space and newline is stripped before parsing.
    wrap=wrap_chars,
    example=Example(pair=PAIR),
)
