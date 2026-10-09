"""Smallfuck boolean generator: a decision tree with banded result cells."""

import re
from collections.abc import Callable
from typing import Any

from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Example, Language
from esolangs.tools.helpers import (
    TEMPLATE_CHAR,
    _validate_truth_table,
    constant_span_test,
    in_input_order,
    mark_runs,
    move_text,
    same_up_to_wrapping,
    subtree_ids,
    unmark,
)
from esolangs.tools.shared_block import repeated_block
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
        self.count = 0

    def emit(self, code: str) -> None:
        self.code.append(code)
        self.count += len(code)

    def move(self, cell: int) -> None:
        self.emit(move_text(self.at, cell, ">", "<"))
        self.at = cell

    def flip(self, cell: int) -> None:
        self.move(cell)
        self.emit("*")

    def loop(self, cell: int) -> None:
        self.move(cell)
        self.emit("[*")

    def end(self, cell: int) -> None:
        self.move(cell)
        self.emit("]")


def smallfuck(truth_table: str, width: int | None = None) -> str:
    """Return a Smallfuck template whose final tape cell 2 is the answer.

    Input ``i`` is stored in cell ``3 i`` before the tree runs, so a level
    may test any of them; splits stay in input order (a greedy order saves
    1.1% at n=8, under the 10% bar). A repeated residual is deferred
    with its first level flag and emitted once after the band transfers;
    inline text and the existing command bound guard admission.
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


def _smallfuck_ordered(table: str, perm: tuple[int, ...]) -> str:
    """Compare inline text with a deferred repeated residual."""
    plain, _ = _smallfuck_tree(table, perm)
    shared = repeated_block(table)
    if shared is None:
        return plain
    candidate, commands = _smallfuck_tree(table, perm, shared)
    n = len(perm)
    return (
        candidate
        if commands <= 9 * n * n + 100 * n + 20 and len(candidate) < len(plain)
        else plain
    )


def _smallfuck_tree(
    truth_table: str, perm: tuple[int, ...], shared: tuple[int, int] | None = None
) -> tuple[str, int]:
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
    builder.emit(TEMPLATE_CHAR * (len(PAIR[0]) * n))
    pending = 3 * shared[0] + 1 if shared is not None else 0

    def transfer(source: int, target: int) -> None:
        builder.loop(source)
        builder.flip(target)
        builder.end(source)

    def arm(level: int, lo: int, hi: int, result: int, on: str) -> int:
        """XOR into ``result`` whether the span's answer is ``on``."""
        start = builder.count
        if constant(lo, hi):
            if truth_table[lo] == on:
                builder.flip(result)
            return builder.count - start
        if level < 0 or (n - BAND - level - 1) % BAND:
            return tree(level + 1, lo, hi, result, on)
        own = 3 * (level + 1) + 2
        cost = tree(level + 1, lo, hi, own, on)
        tail = builder.count
        transfer(own, result)
        return cost + builder.count - tail + 1

    def tree(level: int, lo: int, hi: int, result: int, on: str) -> int:
        start = builder.count
        if (
            shared is not None
            and level == shared[0]
            and ids[level][lo >> (n - level)] == ids[level][shared[1] >> (n - level)]
        ):
            # A complemented arm contributes its constant now; the common
            # suffix contributes the function itself after band transfers.
            if on == "0":
                builder.flip(result)
            builder.flip(pending)
            return builder.count - start
        bit, flag, mid = 3 * perm[level], 3 * level + 1, (lo + hi) // 2
        below = ids[level + 1]
        if below[lo >> (n - level - 1)] == below[mid >> (n - level - 1)]:
            return arm(level, lo, mid, result, on)
        if constant(lo, mid):
            if truth_table[lo] == on:
                builder.flip(result)
                on = "1" if on == "0" else "0"
            builder.loop(bit)
            body_start = builder.count
            cost = arm(level, mid, hi, result, on)
            flat = builder.count - body_start
            builder.end(bit)
            return cost + builder.count - start - flat + 1
        builder.flip(flag)
        builder.loop(bit)
        one_start = builder.count
        builder.flip(flag)
        body_start = builder.count
        one_cost = arm(level, mid, hi, result, on)
        one_flat = builder.count - body_start
        builder.end(bit)
        one_cost += builder.count - one_start - one_flat + 1
        between = builder.count
        builder.loop(flag)
        # A skipped loop executes its opener, not its immediate flip.
        common = one_start - start - 1 + builder.count - between - 1
        zero_start = builder.count
        body_start = builder.count
        zero_cost = arm(level, lo, mid, result, on)
        zero_flat = builder.count - body_start
        builder.end(flag)
        zero_cost += builder.count - zero_start - zero_flat + 2
        return common + max(one_cost + 1, zero_cost)

    cost = len(PAIR[0]) * n + arm(-1, 0, len(truth_table), 2, "1")
    if shared is not None:
        depth, row = shared
        start = builder.count
        builder.loop(pending)
        shared = None
        body_start = builder.count
        body_cost = tree(depth, row, row + (1 << (n - depth)), 2, "1")
        flat = builder.count - body_start
        builder.end(pending)
        cost += body_cost + builder.count - start - flat + 1
    program = _trim_tail("".join(builder.code)).ljust(3, ">")
    return program, cost


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


def _same_layout(template: str, plain: str, layout: Callable[[int], Any]) -> bool:
    """Newlines carry no commands: compare the narrow layouts without them."""
    for width in (1, 4):
        if template.replace("\n", "") == str(layout(width)).replace("\n", ""):
            return True
    return same_up_to_wrapping(template, plain)


LANGUAGE = Language(
    "Smallfuck",
    "tape_based.smallfuck",
    weekly_mutation=("interpreter", "generator"),
    boolean=smallfuck,
    same_layout=_same_layout,
    contract=BooleanContract(
        note="Smallfuck defines no I/O; this implementation prints final cell 2",
    ),
    wrap=wrap_chars,
    balance=_balance,
    example=Example(setters=smallfuck_setters),
)
