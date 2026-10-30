"""Cyclic tag Boolean program generator: zeros in the queue count the row.

Each step deletes the queue's first bit and, if it was 1, appends the
current production; the production pointer advances either way.  The queue
is the inputs, then a marker ``1``:

- Production i belongs to input i: a 1 appends one ``0`` per unit of the
  input's weight, so the queue gains ``row`` zeros.
- The marker meets production n, ``1``, re-appends itself, then meets its
  row's production: empty for a 1 (the marker is the last bit deleted),
  ``0`` for a 0 (the appended 0 is).  The queue then runs dry.

``0110`` on row 2 is ``00;0;1;0;;;0,101``.  A constant table is one empty
production: the inputs are deleted unread, then the literal answer.

Size:
    About 3T chars, one production per row, none shared (a rule runs once a
    cycle); n=8 and: 785 chars, n=16 and: 196,641 chars.
"""

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


def _program(truth_table: str) -> str:
    """Build the indexed padding walk, or an empty-production constant root."""
    n = _validate_truth_table(truth_table)
    if len(set(truth_table)) == 1:
        return "," + TEMPLATE_CHAR * n + truth_table[0]
    # An ignored input's rule is empty: its symbol is deleted unread.
    weights, table = input_weights(truth_table, n)
    rules = ["0" * weight for weight in weights]
    rules.append("1")
    # The marker is the last bit deleted when its row's rule is empty (a 1);
    # a 0 appends one 0 that is deleted last.
    rules.extend("" if answer == "1" else "0" for answer in table)
    return ";".join(rules) + "," + TEMPLATE_CHAR * n + "1"


LANGUAGE = Language(
    "Cyclic tag",
    "cyclic_tag",
    category="queue_based",
    boolean=cyclic_tag,
    # A positional production walk, not a tree of callable residuals.
    shape=Shape.LOOKUP,
    contract=BooleanContract(
        note="Inputs fill the initial queue; the final deleted bit is the answer.",
    ),
    wrap=wrap_chars,
    empty_program="Cyclic tag requires productions,queue using bits and semicolons",
    example=Example(pair=PAIR),
)
