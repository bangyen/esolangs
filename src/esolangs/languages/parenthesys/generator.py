"""Parenthesys Boolean program generator: the table as a lookup string.

Below n=4, nested Horner reads index character ``row + 1`` of ``x`` and
the table; ``x`` keeps an all-digit table a string.
From n=4, a character packs eight rows as ``U+4E00 + v``. The first three
inputs select its bit, the rest its column, preserving input order.
Three decimal digits abc modulo 8 give 4a+2b+c; two give 2a+b. Read groups
of at most three this way, combining full groups in radix 8. The final
``(2**s * ord) % 256 > 127`` selects bit ``7 - s`` of the character.

Size:
    n<4: 12n + 5 + T chars, 6n + 2 steps. From n=4: T/8 + 54 + G chars
    and 25 + H steps; G/H are the grouped column's characters/ops.
    n=10 parity: 223 chars, n=10 random 1847: 223 chars.
    Constants read each input then print the bit: n + 3 chars.
"""

from esolangs.generation.helpers import _validate_truth_table
from esolangs.registry._language import Language, Shape
from esolangs.runtime._definition import RuntimeSpec

#: Rows a packed character holds are ``2**_BITS``; the offset is a multiple of that.
_BITS = 3
_OFFSET = 0x4E00


def _horner(reads: int) -> str:
    """The reads as one binary number, first input most significant."""
    row = "$"
    for _ in range(reads - 1):
        row = f"[+|[*|{row}|2]|$]"
    return row


def _grouped(reads: int) -> str:
    """Read up to three digits modulo 8, then append groups in radix 8."""
    first = (reads - 1) % 3 + 1
    row = "$" if first == 1 else "[%|" + "$" * first + "|8]"
    for _ in range(first, reads, 3):
        row = f"[+|[*|{row}|8]|[%|$$$|8]]"
    return row


def parenthesys(truth_table: str) -> str:
    """Build a Parenthesys program printing ``truth_table[row]`` for the inputs."""
    n = _validate_truth_table(truth_table)
    if truth_table.count(truth_table[0]) == len(truth_table):
        return "$" * n + f"({truth_table[0]})"
    if n < 4:
        return f"([ind|[+|{_horner(n)}|1]|x{truth_table}])"
    columns = len(truth_table) >> _BITS
    table = "".join(
        chr(_OFFSET + int("".join(truth_table[s * columns + c] for s in range(8)), 2))
        for c in range(columns)
    )
    column = f"[ord|[ind|{_grouped(n - _BITS)}|{table}]|0]"
    return f"([gt|[%|[*|[^|2|{_grouped(_BITS)}]|{column}]|256]|127])"


LANGUAGE = Language(
    "Parenthesys",
    RuntimeSpec("parenthesys", category="other"),
    boolean=parenthesys,
    # Not a tree: one string literal the row indexes.
    shape=Shape.LOOKUP,
    no_wrap="a line break is a literal: inside the table it shifts every row",
)
