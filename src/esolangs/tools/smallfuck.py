"""Smallfuck boolean generator: a decision tree with banded result cells."""

from esolangs.tools.helpers import (
    TEMPLATE_CHAR,
    _validate_truth_table,
    best_input_order,
    constant_span_test,
)

PAIR = ("[*]>>>", "***>>>")

#: Levels sharing one result cell; measured best of 2 to 5 at n = 3 to 10.
BAND = 3


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
    """Return a Smallfuck template whose final tape cell 2 is the answer.

    Input ``i`` is stored in cell ``3 i`` before the tree runs, so a level
    may test any of them: the shorter of the identity and greedy orders is
    kept (:func:`best_input_order`).
    """
    return best_input_order(truth_table, _smallfuck_ordered)


def _smallfuck_ordered(truth_table: str, perm: tuple[int, ...]) -> str:
    """Emit one order's template; level ``k`` tests input ``perm[k]``.

    ``truth_table`` is already permuted.  Level ``k`` keeps its flag in
    cell ``3 k + 1``.  Answers are XORed into one cell per band of
    :data:`BAND` levels, counted up from the leaves: a band's top level
    ``k`` owns cell ``3 k + 2`` and transfers it into its parent's cell
    when done, so a flip travels at most ``3 BAND`` cells and a node costs
    O(1) either way.  An arm whose lower half is constant needs no flag:
    that constant is flipped in first and the upper arm built inverted, so
    a node over two leaves is ``result ^= bit`` alone.
    """
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

    def arm(level: int, lo: int, hi: int, result: int, on: str) -> None:
        """XOR into ``result`` whether the span's answer is ``on``."""
        if constant(lo, hi):
            if truth_table[lo] == on:
                builder.flip(result)
        elif level < 0 or (n - BAND - level - 1) % BAND:
            tree(level + 1, lo, hi, result, on)
        else:
            own = 3 * (level + 1) + 2
            tree(level + 1, lo, hi, own, on)
            transfer(own, result)

    def tree(level: int, lo: int, hi: int, result: int, on: str) -> None:
        bit, flag, mid = 3 * perm[level], 3 * level + 1, (lo + hi) // 2
        if constant(lo, mid):
            if truth_table[lo] == on:
                builder.flip(result)
                on = "01"[on == "0"]
            builder.move(bit)
            builder.code.append("[*")
            arm(level, mid, hi, result, on)
            builder.move(bit)
            builder.code.append("]")
            return
        builder.flip(flag)
        builder.move(bit)
        builder.code.append("[*")
        builder.flip(flag)
        arm(level, mid, hi, result, on)
        builder.move(bit)
        builder.code.append("]")
        builder.move(flag)
        builder.code.append("[*")
        arm(level, lo, mid, result, on)
        builder.move(flag)
        builder.code.append("]")

    arm(-1, 0, len(truth_table), 2, "1")
    return _trim_tail("".join(builder.code)).ljust(3, ">")


def _trim_tail(code: str) -> str:
    """Drop the moves among the ``]`` that end the program.

    A ``]`` falls through only on a zero cell, so the next ``]`` needs no
    move to find one, and after the last nothing reads the pointer.
    """
    stop = len(code.rstrip("<>]"))
    first = code.find("]", stop)
    if first < 0:
        return code
    return code[:first] + "]" * code.count("]", first)
