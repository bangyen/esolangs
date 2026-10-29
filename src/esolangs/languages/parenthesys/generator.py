"""Parenthesys Boolean program generator: the table as one string.

The row is one nested Horner expression: ``$`` reads the first input and
each later one wraps it as ``[+|[*|E|2]|$]``, whose arguments evaluate in
order, so the reads stay in input order.  ``ind`` prints character
``row + 1`` of ``x`` and the table: the ``x`` keeps an all-digit table a
string, whatever a number's text would become.

Size:
    12n + 5 + T chars; 6n + 2 steps; n=10 parity: 1149 chars, n=10
    random 1847: 1149 chars.
"""

from esolangs.generation.helpers import _validate_truth_table
from esolangs.registry._language import Language, Shape


def parenthesys(truth_table: str) -> str:
    """Build a Parenthesys program printing ``truth_table[row]`` for the inputs."""
    n = _validate_truth_table(truth_table)
    row = "$"
    for _ in range(n - 1):
        row = f"[+|[*|{row}|2]|$]"
    return f"([ind|[+|{row}|1]|x{truth_table}])"


LANGUAGE = Language(
    "Parenthesys",
    "parenthesys",
    category="other",
    boolean=parenthesys,
    # Not a tree: one string literal the row indexes.
    shape=Shape.LOOKUP,
    no_wrap="a line break is a literal: inside the table it shifts every row",
)
