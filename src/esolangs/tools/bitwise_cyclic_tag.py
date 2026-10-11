"""Bitwise Cyclic Tag boolean program builder: the table as a forward walk.

BCT has no branch, so all an input can change is how much data is appended, and
so how far the pointer has moved when a later bit is read.  Input ``i`` appends
``2**(n-i+1)`` zeros when set, a sentinel ``1`` lands behind them, and the table
is one ``1 x 0 0`` cell a row consuming two zeros while advancing four -- so the
walk arrives at cell ``index`` and fires it, and no indexed row can drop.
Constants delete the embedded inputs and a literal answer with a cyclic ``0``.
Emission is ``program,data``; the count and why a cell needs four bits:
``docs/proofs/index.md``.
"""

from __future__ import annotations

from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Example, Language, Shape
from esolangs.tools.constant_projection import balanced_projection
from esolangs.tools.helpers import (
    TEMPLATE_CHAR,
    _validate_truth_table,
    input_weights,
    mark_runs,
    unmark,
)
from esolangs.tools.wrap import balance_program, wrap_chars

#: One bit of the initial data-string, so an input's run is one TEMPLATE_CHAR.
PAIR = ("0", "1")

#: The constant bit held behind the inputs, read after every walk zero.
_SENTINEL = "1"


def bitwise_cyclic_tag(truth_table: str) -> str:
    """Return the BCT template computing ``truth_table``."""
    return _program(truth_table)


def _program(truth_table: str, *, keep_constant_walk: bool = False) -> str:
    """Build the indexed walk, or delete inputs and a literal constant answer."""
    n = _validate_truth_table(truth_table)
    if len(set(truth_table)) == 1 and not keep_constant_walk:
        return "0," + TEMPLATE_CHAR * n + truth_table[0]
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


def balance_bitwise_cyclic_tag(table: str, default: str) -> str:
    """Retain the old constant walk if its wrapped shape balances better."""
    n = _validate_truth_table(table)
    pairs = (PAIR,) * n
    marked = mark_runs(default, TEMPLATE_CHAR, pairs)
    if len(set(table)) > 1:
        return unmark(balance_program(marked, "bitwise_cyclic_tag"), TEMPLATE_CHAR, n)
    legacy = mark_runs(_program(table, keep_constant_walk=True), TEMPLATE_CHAR, pairs)
    return unmark(
        balanced_projection(marked, legacy, "bitwise_cyclic_tag"), TEMPLATE_CHAR, n
    )


LANGUAGE = Language(
    "Bitwise Cyclic Tag",
    "queue_based.bitwise_cyclic_tag",
    boolean=bitwise_cyclic_tag,
    balance=balance_bitwise_cyclic_tag,
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
