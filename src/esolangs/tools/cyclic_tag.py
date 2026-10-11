"""Linear padding construction for Cyclic tag.

One rule a row is the index step; dropping rows moves the walk, and a rule
runs once a cycle, so none is shared.
Constant roots use one empty production to delete the inputs and a literal answer.
"""

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
    rules.append("1")
    for answer in table:
        rules.extend((answer, ""))
    return ";".join(rules) + "," + TEMPLATE_CHAR * n + "1"


def balance_cyclic_tag(table: str, default: str) -> str:
    """Keep the old constant walk when its wrapped shape balances better."""
    n = _validate_truth_table(table)
    pairs = (PAIR,) * n
    marked = mark_runs(default, TEMPLATE_CHAR, pairs)
    if len(set(table)) > 1:
        return unmark(balance_program(marked, "cyclic_tag"), TEMPLATE_CHAR, n)
    legacy = mark_runs(_program(table, keep_constant_walk=True), TEMPLATE_CHAR, pairs)
    return unmark(balanced_projection(marked, legacy, "cyclic_tag"), TEMPLATE_CHAR, n)


LANGUAGE = Language(
    "Cyclic tag",
    "queue_based.cyclic_tag",
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
