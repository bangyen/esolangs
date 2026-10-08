"""Smallfuck boolean generator: a decision tree with banded result cells."""

import re

from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Language
from esolangs.tools.helpers import (
    TEMPLATE_CHAR,
    _validate_truth_table,
    constant_span_test,
    in_input_order,
    mark_runs,
    move_text,
    subtree_ids,
    unmark,
)
from esolangs.tools.token_balance import balanced_token_width
from esolangs.tools.wrap import _RUN, balance_score, wrap_chars

# Each input cell is fresh; zero needs no clear and one needs one flip.
PAIR = ("x>>>", "*>>>")

#: Levels sharing one result cell; measured best of 2 to 5 at n = 3 to 10.
BAND = 3


class _Builder:
    """Emit pointer-tracked macros over initially zero cells."""

    def __init__(self, start: int = 0) -> None:
        self.at = start
        self.code: list[str] = []

    def move(self, cell: int) -> None:
        self.code.append(move_text(self.at, cell, ">", "<"))
        self.at = cell

    def flip(self, cell: int) -> None:
        self.move(cell)
        self.code.append("*")

    def loop(self, cell: int) -> None:
        self.move(cell)
        self.code.append("[*")

    def end(self, cell: int) -> None:
        self.move(cell)
        self.code.append("]")


def smallfuck(truth_table: str, width: int | None = None) -> str:
    """Return a Smallfuck template whose final tape cell 2 is the answer.

    Input ``i`` is stored in cell ``3 i`` before the tree runs, so a level
    may test any of them; splits stay in input order (a greedy order saves
    1.1% at n=8, under the 10% bar).
    """
    natural = in_input_order(truth_table, _smallfuck_ordered)
    if width is None or width <= 0:
        return natural
    n = _validate_truth_table(truth_table)
    if width < len(PAIR[0]):
        natural = (TEMPLATE_CHAR + ">>>") * n + natural[len(PAIR[0]) * n :]
    from esolangs.tools.wrap import wrap_program

    marked = mark_runs(natural, TEMPLATE_CHAR, smallfuck_setters(natural, n))
    return unmark(wrap_program(marked, "smallfuck", width), TEMPLATE_CHAR, n)


def smallfuck_setters(template: str, n: int) -> tuple[tuple[str, str], ...]:
    """Keep the pointer walk outside narrow one-character input slots."""
    pair = ("x", "*") if template.replace("\n", "").startswith("$>>>") else PAIR
    return (pair,) * n


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
    ids = subtree_ids(truth_table)
    builder = _Builder(3 * n)
    builder.code.append(TEMPLATE_CHAR * (len(PAIR[0]) * n))

    def transfer(source: int, target: int) -> None:
        builder.loop(source)
        builder.flip(target)
        builder.end(source)

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
        below = ids[level + 1]
        if below[lo >> (n - level - 1)] == below[mid >> (n - level - 1)]:
            # Both halves agree, so the bit cannot matter: build one, untested.
            arm(level, lo, mid, result, on)
            return
        if constant(lo, mid):
            if truth_table[lo] == on:
                builder.flip(result)
                on = "1" if on == "0" else "0"
            builder.loop(bit)
            arm(level, mid, hi, result, on)
            builder.end(bit)
            return
        builder.flip(flag)
        builder.loop(bit)
        builder.flip(flag)
        arm(level, mid, hi, result, on)
        builder.end(bit)
        builder.loop(flag)
        arm(level, lo, mid, result, on)
        builder.end(flag)

    arm(-1, 0, len(truth_table), 2, "1")
    return _trim_tail("".join(builder.code)).ljust(3, ">")  # cell 2 must exist


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


def _balance(table: str, default: str) -> str:
    """Balance four-character setters and the one-character narrow setters."""
    n = _validate_truth_table(table)
    candidates = [default]
    for source, minimum, maximum in ((default, 4, None), (smallfuck(table, 3), 1, 3)):
        clean = source.replace("\n", "")
        marked = mark_runs(clean, TEMPLATE_CHAR, smallfuck_setters(clean, n))
        tokens = re.findall(f"{_RUN}|[\\s\\S]", marked)
        width = balanced_token_width(tokens, minimum=minimum, maximum=maximum)
        candidates.append(smallfuck(table, width))
    return min(candidates, key=balance_score)


LANGUAGE = Language(
    "Smallfuck",
    "tape_based.smallfuck",
    boolean=smallfuck,
    contract=BooleanContract(
        note="Smallfuck defines no I/O; this implementation prints final cell 2",
        parameterized=True,
    ),
    wrap=wrap_chars,
    balance=_balance,
)
