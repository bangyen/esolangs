"""Cyclic tag Boolean program generator: zeros in the queue count the row.

Each step deletes the queue's first bit and, if it was 1, appends the
current production; the production pointer advances either way.  The queue
is the inputs, then a marker ``1``:

- Production i belongs to input i: a 1 appends two ``0`` per unit of the
  input's weight, so the queue gains 2 * row zeros.
- The marker meets production n, ``1``, and re-appends itself behind them.
- Each zero only advances the pointer, so the marker then meets its row's
  production, which appends the answer bit.  The row's second production
  is empty, so deleting that bit appends nothing and the queue runs dry:
  the last deleted bit, which the interpreter prints, is the answer.

``0110`` on inputs 1, 0 (row 2) is ``0000;00;1;0;;1;;1;;0;,101``.  Its queue
goes 101, 010000, 10000, 00001, 0001, 001, 01, 1, then 1 again as row 2
appends its answer, then empty: it prints 1.  A constant table is one empty
production: the inputs are deleted unread, then the literal answer.

Size:
    About 5T chars, two productions per row, none shared (a rule runs once a
    cycle); n=10 random 1847: 5,141 chars, n=16 and: 327,713 chars.
"""

from esolangs.generation.constant_projection import balance_legacy_walk
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


def cyclic_tag(truth_table: str) -> str:
    """Return an ordered queue embed with final-deletion output."""
    return _program(truth_table)


def _program(truth_table: str, *, keep_constant_walk: bool = False) -> str:
    """Build the indexed padding walk, or an empty-production constant root."""
    n = _validate_truth_table(truth_table)
    if len(set(truth_table)) == 1 and not keep_constant_walk:
        return "," + TEMPLATE_CHAR * n + truth_table[0]
    # An ignored input's rule is empty: its symbol is deleted unread.
    weights, table = input_weights(truth_table, n)
    rules = ["0" * (2 * weight) for weight in weights]
    rules.append("1")  # the marker re-appends itself behind the zeros
    for answer in table:
        rules.extend((answer, ""))  # the answer, then an empty rule to delete it
    return ";".join(rules) + "," + TEMPLATE_CHAR * n + "1"


def balance_cyclic_tag(table: str, default: str) -> str:
    """Keep the old constant walk when its wrapped shape balances better."""
    return balance_legacy_walk(
        table,
        default,
        "cyclic_tag",
        PAIR,
        lambda t: _program(t, keep_constant_walk=True),
    )


LANGUAGE = Language(
    "Cyclic tag",
    "cyclic_tag",
    category="queue_based",
    boolean=cyclic_tag,
    balance=balance_cyclic_tag,
    # A positional production walk, not a tree of callable residuals.
    shape=Shape.LOOKUP,
    contract=BooleanContract(
        note="Inputs fill the initial queue; the final deleted bit is the answer.",
    ),
    wrap=wrap_chars,
    empty_program="Cyclic tag requires productions,queue using bits and semicolons",
    example=Example(pair=PAIR),
)
