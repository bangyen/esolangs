"""Smallfuck boolean generator: a folded local-result decision tree."""

from esolangs.tools.helpers import (
    TEMPLATE_CHAR,
    _validate_truth_table,
    constant_span_test,
)

PAIR = ("[*]>>>", "***>>>")


class _Builder:
    """Emit pointer-tracked macros over initially zero cells."""

    def __init__(self) -> None:
        self.at = 0
        self.code: list[str] = []

    def move(self, cell: int) -> None:
        delta = cell - self.at
        self.code.append((">" if delta >= 0 else "<") * abs(delta))
        self.at = cell

    def flip(self, cell: int) -> None:
        self.move(cell)
        self.code.append("*")


def smallfuck(truth_table: str) -> str:
    """Return a Smallfuck template whose final tape cell 2 is the answer."""
    n = _validate_truth_table(truth_table)
    constant = constant_span_test(truth_table)
    builder = _Builder()
    builder.code.append(TEMPLATE_CHAR * (len(PAIR[0]) * n))
    builder.at = 3 * n

    def transfer(source: int, target: int) -> None:
        builder.move(source)
        builder.code.append("[*")
        builder.flip(target)
        builder.move(source)
        builder.code.append("]")

    def tree(level: int, lo: int, hi: int) -> None:
        result = 3 * level + 2
        if constant(lo, hi):
            if truth_table[lo] == "1":
                builder.flip(result)
            return
        bit, flag = 3 * level, 3 * level + 1
        child = 3 * (level + 1) + 2
        builder.flip(flag)
        builder.move(bit)
        builder.code.append("[*")
        builder.flip(flag)
        tree(level + 1, (lo + hi) // 2, hi)
        transfer(child, result)
        builder.move(bit)
        builder.code.append("]")
        builder.move(flag)
        builder.code.append("[*")
        tree(level + 1, lo, (lo + hi) // 2)
        transfer(child, result)
        builder.move(flag)
        builder.code.append("]")

    tree(0, 0, len(truth_table))
    return "".join(builder.code).ljust(3, ">")
