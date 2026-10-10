"""Smallfuck boolean generator: a decision tree with banded result cells."""

import re
from collections.abc import Callable
from itertools import pairwise
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
from esolangs.tools.shared_block import ContinuationCost as _Cost
from esolangs.tools.shared_block import (
    _repeated_blocks,
    repeated_bank,
    repeated_block,
    repeated_blocks,
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
    1.1% at n=8, under the 10% bar). Repeated residuals defer through level
    flags or same-level banks and run after the band transfers; inline text
    and the existing command bound guard admission. Two-input complements
    share a three-bit code; a retired zero-arm input holds its high bit.
    Three dense n=16 tables average 921,290 -> 723,753 characters (-21.44%);
    both builds execute five rows per table.
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
    """Compare inline text, one residual, levels and same-level banks."""
    plain, _ = _smallfuck_tree(table, perm)
    shared = repeated_block(table)
    paired = _paired_roots(table)
    if shared is None:
        if not paired:
            return plain
        candidate, commands = _smallfuck_tree(table, perm, paired_roots=paired)
        n = len(perm)
        return (
            candidate
            if commands <= 9 * n * n + 100 * n + 20 and len(candidate) < len(plain)
            else plain
        )
    candidate, commands = _smallfuck_tree(table, perm, shared)
    n = len(perm)
    forms = [(plain, 0), (candidate, commands)]
    plans: list[tuple[tuple[tuple[int, int], ...], tuple[int, ...]]] = [
        (repeated_blocks(table), ())
    ]
    plans.extend(repeated_bank(table, ranked=ranked) for ranked in (False, True))
    for blocks, flags in dict.fromkeys(plans):
        if len(blocks) > 1:
            forms.append(
                _smallfuck_tree(table, perm, shared_blocks=blocks, flag_levels=flags)
            )
    if paired:
        forms.append(_smallfuck_tree(table, perm, paired_roots=paired))
    return min(
        (code for code, cost in forms if cost <= 9 * n * n + 100 * n + 20), key=len
    )


def _paired_roots(table: str) -> tuple[tuple[int, int], ...]:
    """Return repeated two-input functions, identifying complements."""
    n = _validate_truth_table(table)
    if n < 4:
        return ()
    pairs: dict[int, tuple[int, int]] = {}
    for depth, row, saving in _repeated_blocks(table, include_single=True):
        if depth == n - 2:
            word = int(table[row : row + 4], 2)
            canonical = min(word, word ^ 15)
            previous, first = pairs.get(canonical, (0, row))
            pairs[canonical] = (previous + saving // 4 + 1, first)
    return tuple((code, row) for code, (copies, row) in pairs.items() if copies > 1)


def _smallfuck_tree(
    truth_table: str,
    perm: tuple[int, ...],
    shared: tuple[int, int] | None = None,
    *,
    shared_blocks: tuple[tuple[int, int], ...] = (),
    flag_levels: tuple[int, ...] = (),
    paired_roots: tuple[tuple[int, int], ...] = (),
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
    blocks = (shared,) if shared is not None else shared_blocks
    depths = tuple(depth for depth, _ in blocks)
    if flag_levels:
        if (
            len(flag_levels) != len(blocks)
            or len(set(depths)) != 1
            or len(set(flag_levels)) != len(flag_levels)
            or any(level < depths[0] or level >= n for level in flag_levels)
        ):
            raise ValueError("a bank needs distinct unused flags at one level")
    elif any(left >= right for left, right in pairwise(depths)):
        raise ValueError("deferred levels must be distinct and increasing")
    if any(depth < 0 or depth >= n for depth in depths):
        raise ValueError("deferred levels must be distinct and increasing")
    pending_levels = flag_levels or depths
    selected = {
        (depth, ids[depth][row >> (n - depth)]): i
        for i, (depth, row) in enumerate(blocks)
    }
    if len(selected) != len(blocks):
        raise ValueError("deferred definitions must name distinct residuals")
    pairs = dict(paired_roots)
    pair_depth = n - 2
    pair_phase = bool(pairs)
    if pairs and (n < 4 or blocks):
        raise ValueError(
            "paired roots need two retired levels and no other definitions"
        )

    def split(
        bit: int, flag: int, one: Callable[[], _Cost], zero: Callable[[], _Cost]
    ) -> _Cost:
        start = builder.count
        builder.flip(flag)
        builder.loop(bit)
        one_start = builder.count
        builder.flip(flag)
        body_start = builder.count
        one_cost = one()
        one_flat = builder.count - body_start
        builder.end(bit)
        one_cost = _Cost(builder.count - one_start - one_flat + 1, (one_cost,))
        between = builder.count
        builder.loop(flag)
        common = one_start - start - 1 + builder.count - between - 1
        zero_start = builder.count
        body_start = builder.count
        zero_cost = zero()
        zero_flat = builder.count - body_start
        builder.end(flag)
        zero_cost = _Cost(builder.count - zero_start - zero_flat + 2, (zero_cost,))
        return _Cost(common, (_Cost(1, (one_cost,)), zero_cost))

    def clear_prefix(level: int) -> None:
        for unread in range(level, pair_depth):
            bit = 3 * perm[unread]
            builder.loop(bit)
            builder.end(bit)

    def transfer(source: int, target: int) -> None:
        builder.loop(source)
        builder.flip(target)
        builder.end(source)

    def arm(
        level: int, lo: int, hi: int, result: int, on: str, free: int = -1
    ) -> _Cost:
        """XOR into ``result`` whether the span's answer is ``on``."""
        start = builder.count
        if constant(lo, hi):
            if truth_table[lo] == on:
                builder.flip(result)
            if pair_phase:
                clear_prefix(level + 1)
            return _Cost(builder.count - start)
        if level < 0 or (n - BAND - level - 1) % BAND:
            return tree(level + 1, lo, hi, result, on, free)
        own = 3 * (level + 1) + 2
        cost = tree(level + 1, lo, hi, own, on, free)
        tail = builder.count
        transfer(own, result)
        return _Cost(builder.count - tail + 1, (cost,))

    def tree(
        level: int, lo: int, hi: int, result: int, on: str, free: int = -1
    ) -> _Cost:
        start = builder.count
        if pair_phase and level == pair_depth:
            # A zero arm has passed its input's only loop; an ignored input
            # is freed by clearing it. The nearest such cell holds bit 2.
            # Its weighted distances sum s*2**(d-s) = O(2**d), so marks stay O(T).
            word = int(truth_table[lo : lo + 4], 2)
            canonical = min(word, word ^ 15)
            if canonical in pairs and (not canonical & 4 or free >= 0):
                if (truth_table[lo] == "1") != (on == "0"):
                    builder.flip(result)
                for mask, cell in (
                    (1, 3 * pair_depth + 1),
                    (2, 3 * (pair_depth + 1) + 1),
                    (4, 3 * perm[free]),
                ):
                    if canonical & mask:
                        builder.flip(cell)
                return _Cost(builder.count - start, target=canonical)
        key = (level, ids[level][lo >> (n - level)])
        if key in selected:
            # A complemented arm contributes its constant now; the common
            # suffix contributes the function itself after band transfers.
            if on == "0":
                builder.flip(result)
            builder.flip(3 * pending_levels[selected[key]] + 1)
            return _Cost(builder.count - start, target=selected[key])
        bit, flag, mid = 3 * perm[level], 3 * level + 1, (lo + hi) // 2
        below = ids[level + 1]
        if below[lo >> (n - level - 1)] == below[mid >> (n - level - 1)]:
            if pair_phase and level < pair_depth:
                builder.loop(bit)
                builder.end(bit)
                free = level
            extra = builder.count - start
            return _Cost(extra, (arm(level, lo, mid, result, on, free),))
        if constant(lo, mid) and not (pair_phase and level < pair_depth):
            if truth_table[lo] == on:
                builder.flip(result)
                on = "1" if on == "0" else "0"
            builder.loop(bit)
            body_start = builder.count
            cost = arm(level, mid, hi, result, on, free)
            flat = builder.count - body_start
            builder.end(bit)
            return _Cost(
                0,
                (
                    _Cost(builder.count - start - flat + 1, (cost,)),
                    _Cost(body_start - start - 1),
                ),
            )
        zero_free = level if pair_phase and level < pair_depth else free
        return split(
            bit,
            flag,
            lambda: arm(level, mid, hi, result, on, free),
            lambda: arm(level, lo, mid, result, on, zero_free),
        )

    prefix = arm(-1, 0, len(truth_table), 2, "1")
    if pairs:
        pair_phase = False
        collector = 3 * (pair_depth - 1) + 1
        # Used inputs are zero; constant leaves clear the unused prefix.
        # Only the high code bit can survive, in at most one input cell.
        skipped = delta = 0
        for level in range(pair_depth):
            start = builder.count
            bit = 3 * perm[level]
            builder.loop(bit)
            empty = builder.count - start - 1
            builder.flip(collector)
            builder.end(bit)
            skipped += empty
            delta = max(delta, builder.count - start - empty)
        bits = (collector, 3 * (pair_depth + 1) + 1, 3 * pair_depth + 1)
        guards = (
            3 * (pair_depth - 2) + 1,
            3 * perm[pair_depth - 1],
            3 * perm[pair_depth - 2],
        )

        def decode(at: int, labels: tuple[int, ...]) -> _Cost:
            start = builder.count
            if at == 3:
                code = labels[0]
                cost = 0
                if code in pairs:
                    row = pairs[code]
                    body = tree(
                        pair_depth,
                        row,
                        row + 4,
                        2,
                        "0" if truth_table[row] == "1" else "1",
                    )
                    cost = body.evaluate({None: 0})
                return _Cost(cost, target=code or None)
            mask = 4 >> at
            zero = tuple(code for code in labels if not code & mask)
            one = tuple(code for code in labels if code & mask)
            if not zero or not one:
                if one:
                    builder.flip(bits[at])
                extra = builder.count - start
                return _Cost(extra, (decode(at + 1, one or zero),))
            return split(
                bits[at],
                guards[at],
                lambda: decode(at + 1, one),
                lambda: decode(at + 1, zero),
            )

        model = decode(0, (0, *pairs))
        pair_tails: dict[int | None, int] = {}

        def price(cost: _Cost, extra: int = 0) -> None:
            extra += cost.value
            if cost.children:
                for child in cost.children:
                    price(child, extra)
            else:
                target = cost.target
                pair_tails[target] = (
                    skipped + extra + (delta if target and target & 4 else 0)
                )

        price(model)
        program = _trim_tail("".join(builder.code)).ljust(3, ">")
        return program, len(PAIR[0]) * n + prefix.evaluate(pair_tails) + 1
    empty_tails: dict[int | None, int] = {
        None: 0,
        **dict.fromkeys(range(len(blocks)), 0),
    }
    cost = len(PAIR[0]) * n + prefix.evaluate(empty_tails)
    stages = []
    # Only the first band of each definition transfers to distant cell 2.
    # At most n definitions add O(n**2) movement, absorbed by T = 2**n.
    for i, (depth, row) in enumerate(blocks):
        pending = 3 * pending_levels[i] + 1
        start = builder.count
        builder.loop(pending)
        skipped = builder.count - start - 1
        del selected[depth, ids[depth][row >> (n - depth)]]
        body_start = builder.count
        body_cost = tree(depth, row, row + (1 << (n - depth)), 2, "1")
        flat = builder.count - body_start
        builder.end(pending)
        active = builder.count - start - flat + 1
        cost += body_cost.evaluate(empty_tails) + active
        stages.append((i, body_cost, active, skipped))
    if shared_blocks:
        tails: dict[int | None, int] = {None: 0}
        for i, body, active, skipped in reversed(stages):
            commands = active + body.evaluate(tails)
            tails = {target: value + skipped for target, value in tails.items()}
            tails[i] = commands
        cost = len(PAIR[0]) * n + prefix.evaluate(tails) + 1
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
