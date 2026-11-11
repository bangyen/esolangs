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
    AND/NOR use a marker10 and one answer1; other row rules are empty.
    About 3T chars, one production per row, none shared (a rule runs once a
    cycle); n=8 and: 534 chars, n=16 and: 131,110 chars.
"""

from esolangs.generation.helpers import (
    _validate_truth_table,
    input_weights,
)
from esolangs.generation.requests import GenerationRequest
from esolangs.generation.template import (
    InputSlot,
    TemplateLayout,
    layout_fragments,
)

_INPUT = InputSlot(1)


def cyclic_tag(truth_table: str) -> str:
    """Return an ordered queue embed with final-deletion output."""
    return _layout(truth_table).source


def _layout(truth_table: str) -> TemplateLayout:
    n = _validate_truth_table(truth_table)
    if len(set(truth_table)) == 1:
        return layout_fragments((",", *(_INPUT,) * n, truth_table[0]))
    # An ignored input's rule is empty: its symbol is deleted unread.
    weights, table = input_weights(truth_table, n)
    rules = ["0" * weight for weight in weights]
    # AND/NOR pass [ablations.trick_prototype_20261102_minority_named].
    # Marker10 leaves zero last unless the selected row appends a one.
    # That one fires two slots later; AND needs two empty guards, NOR
    # already has that empty slot in its table. The exact saving is T-3-g.
    guards = 2 if table[-1] == "1" else 0
    if (
        table.count("1") == 1
        and (table[0] == "1" or table[-1] == "1")
        and len(table) > 3 + guards
    ):
        rules.append("10")
        rules.extend("1" if answer == "1" else "" for answer in table)
        rules.extend([""] * guards)
        return layout_fragments((";".join(rules) + ",", *(_INPUT,) * n, "1"))
    rules.append("1")
    # The marker is the last bit deleted when its row's rule is empty (a 1);
    # a 0 appends one 0 that is deleted last.
    rules.extend("" if answer == "1" else "0" for answer in table)
    return layout_fragments((";".join(rules) + ",", *(_INPUT,) * n, "1"))


def cyclic_tag_request(request: GenerationRequest) -> TemplateLayout:
    """Emit source through the declared generation request interface."""
    return _layout(request.table)
