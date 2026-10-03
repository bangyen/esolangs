"""Linear padding construction for Cyclic tag."""

from esolangs.tools.helpers import TEMPLATE_CHAR, _validate_truth_table

PAIR = ("0", "1")


def cyclic_tag(truth_table: str) -> str:
    """Return an ordered queue embed with final-deletion output."""
    n = _validate_truth_table(truth_table)
    rules = ["0" * (1 << (n - i)) for i in range(n)]
    rules.append("1")
    for answer in truth_table:
        rules.extend((answer, ""))
    return ";".join(rules) + "," + TEMPLATE_CHAR * n + "1"
