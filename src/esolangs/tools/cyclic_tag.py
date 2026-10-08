"""Linear padding construction for Cyclic tag.

One rule a row is the index step; dropping rows moves the walk.
"""

from esolangs.tools.helpers import TEMPLATE_CHAR, _validate_truth_table, input_weights


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
