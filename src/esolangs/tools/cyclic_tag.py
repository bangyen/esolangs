"""Linear padding construction for Cyclic tag.

One rule a row is the index step; dropping rows moves the walk, and a rule
runs once a cycle, so none is shared.
"""

from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Example, Language, Shape
from esolangs.tools.bitwise_cyclic_tag import PAIR
from esolangs.tools.helpers import TEMPLATE_CHAR, _validate_truth_table, input_weights
from esolangs.tools.wrap import wrap_chars


def cyclic_tag(truth_table: str) -> str:
    """Return an ordered queue embed with final-deletion output."""
    n = _validate_truth_table(truth_table)
    # An ignored input's rule is empty: its symbol is deleted unread.
    weights, table = input_weights(truth_table, n)
    rules = ["0" * (2 * weight) for weight in weights]
    rules.append("1")
    for answer in table:
        rules.extend((answer, ""))
    return ";".join(rules) + "," + TEMPLATE_CHAR * n + "1"


LANGUAGE = Language(
    "Cyclic tag",
    "queue_based.cyclic_tag",
    boolean=cyclic_tag,
    # Not a tree: no branch, so every table of an arity is one length.
    shape=Shape.LOOKUP,
    contract=BooleanContract(
        note="Inputs fill the initial queue; the final deleted bit is the answer.",
    ),
    wrap=wrap_chars,
    empty_program="Cyclic tag requires productions,queue using bits and semicolons",
    example=Example(pair=PAIR),
)
