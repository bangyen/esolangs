"""Parenthesys Boolean program generator: the table as a lookup string.

The row is one nested Horner expression: ``$`` reads the first input and
each later one wraps it as ``[+|[*|E|2]|$]``, whose arguments evaluate in
order, so the reads stay in input order.  Below n=5, ``ind`` prints
character ``row + 1`` of ``x`` and the table: the ``x`` keeps an all-digit
table a string, whatever a number's text would become.

From n=5 each character packs eight rows as ``U+4E00 + v``: the first three
inputs pick the bit, the rest the character.  The bit is the
``(2**s * ord) % 256 > 127`` test, which reads bit ``7 - s`` of the code
(the offset is a multiple of 256, so it drops out); its ``2**s`` goes first
so the reads stay in order.

Size:
    n<5: 12n + 5 + T chars, 6n + 2 steps; n>=5: 12n + 23 + T/8 chars,
    6n + 8 steps; n=10 parity: 271 chars, n=10 random 1847: 271 chars.
"""

from esolangs.generation.helpers import _validate_truth_table
from esolangs.registry._language import Language, Shape

#: Rows a packed character holds are ``2**_BITS``; the offset is a multiple of that.
_BITS = 3
_OFFSET = 0x4E00


def _horner(reads: int) -> str:
    """The reads as one binary number, first input most significant."""
    row = "$"
    for _ in range(reads - 1):
        row = f"[+|[*|{row}|2]|$]"
    return row


def parenthesys(truth_table: str) -> str:
    """Build a Parenthesys program printing ``truth_table[row]`` for the inputs."""
    n = _validate_truth_table(truth_table)
    if n < 5:
        return f"([ind|[+|{_horner(n)}|1]|x{truth_table}])"
    columns = len(truth_table) >> _BITS
    table = "".join(
        chr(_OFFSET + int("".join(truth_table[s * columns + c] for s in range(8)), 2))
        for c in range(columns)
    )
    column = f"[ord|[ind|{_horner(n - _BITS)}|{table}]|0]"
    return f"([gt|[%|[*|[^|2|{_horner(_BITS)}]|{column}]|256]|127])"


LANGUAGE = Language(
    "Parenthesys",
    "parenthesys",
    category="other",
    boolean=parenthesys,
    # Not a tree: one string literal the row indexes.
    shape=Shape.LOOKUP,
    no_wrap="a line break is a literal: inside the table it shifts every row",
)
