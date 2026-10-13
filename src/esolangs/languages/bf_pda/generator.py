"""Boolean template generator for bfpda."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from esolangs.generation.helpers import (
    TEMPLATE_CHAR,
    _validate_truth_table,
    constant_span_test,
    reflected_table,
    subtree_ids,
)
from esolangs.generation.shared_block import (
    BranchCost,
    add_cost,
    dispatch_cost,
    merge_cost,
    normal_cost,
    repeated_block,
    repeated_definitions,
)
from esolangs.generation.wrap import wrap_chars
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Example, Language

__all__ = ["BFPDA_PAIR", "bfpda"]


BFPDA_PAIR = ("x", "@")


@dataclass(frozen=True)
class _TreeContext:
    reflected: str
    constant: Callable[[int, int], bool]
    ids: list[list[int]]


def _prepare(table: str) -> _TreeContext:
    reflected = reflected_table(table, _validate_truth_table(table))
    return _TreeContext(
        reflected, constant_span_test(reflected), subtree_ids(reflected)
    )


def bfpda(truth_table: str) -> str:
    """Return a BF-PDA template for a binary, MSB-first ``2**n`` truth table.

    The last input is tested first; every arm empties the stack so its ``]``
    exits. A shared residual returns a flag protected by zero sentinels,
    then runs once after the prefix. Residual banks return binary words of
    bit/marker pairs; the decoder consumes every pair before its definition.
    Retired stack space, inline text and the existing command bound guard
    admission. Characters outside @.<>[] are comments; the first marker is bare @.
    """
    context = _prepare(truth_table)
    plain, _ = _bfpda_tree(truth_table, context=context)
    n = _validate_truth_table(truth_table)
    reflected = context.reflected
    shared = repeated_block(reflected)
    candidates = [plain]
    if shared is not None:
        candidate, commands = _bfpda_tree(truth_table, shared, context=context)
        if commands <= 10 * n + 2:
            candidates.append(candidate)
    bank = best_bank(truth_table, context, 10 * n + 2, min(map(len, candidates)))
    if bank is not None:
        candidates.append(bank)

    mixed = best_mixed_bank(context, 10 * n + 2, min(map(len, candidates)))
    if mixed is not None:
        candidates.append(mixed)
    return min(candidates, key=len)


def _bfpda_tree(
    table: str,
    shared: tuple[int, int] | None = None,
    *,
    classes: tuple[str, ...] | None = None,
    class_depth: int = 2,
    class_rows: tuple[int, ...] | None = None,
    context: _TreeContext | None = None,
) -> tuple[str, int]:
    """Emit an inline tree or a sentinel-protected shared residual."""
    n = _validate_truth_table(table)

    # Marker then bit, per input in name order.
    head = "<".join(["@<" + TEMPLATE_CHAR] * n)

    def leaf(level: int, value: str) -> str:
        # ``left`` cells still hold untested inputs; a one stops on the bottom
        # marker and prints it (left == 0: only that marker remains).
        left = 2 * (n - level)
        if value == "0":
            return ">" * left + "."
        return ">" * (left - 1) + ".>" if left else "@.>"

    # The stack hands back the *last* input first: level ``i`` tests input
    # ``n - 1 - i``, row bit ``i``; bit-reversed, each subtree is a span.
    if context is None:
        context = _prepare(table)
    reflected, constant, ids = context.reflected, context.constant, context.ids
    rows: tuple[int, ...] = ()
    class_ids: tuple[int, ...] = ()
    labels_by_id: dict[int, int] = {}
    width = 0
    if classes is not None:
        if len(classes) < 2 or len(set(classes)) != len(classes):
            raise ValueError("a classifier needs at least two distinct residuals")
        if not 2 <= class_depth < n:
            raise ValueError(
                "a protected classifier needs at least two consumed inputs"
            )
        span = 1 << (n - class_depth)
        rows = class_rows or tuple(
            next(i for i in range(0, 1 << n, span) if reflected[i : i + span] == block)
            for block in classes
        )
        class_ids = tuple(ids[class_depth][row // span] for row in rows)
        if len(class_ids) < 2 or len(set(class_ids)) != len(class_ids):
            raise ValueError("a classifier needs at least two distinct residuals")
        labels_by_id = {state: label for label, state in enumerate(class_ids)}
        width = (len(class_ids) - 1).bit_length()
        if class_depth < width + 1:
            raise ValueError("a classifier word exceeds the retired stack space")
    pieces = [head]
    protected = shared is not None or classes is not None

    def node(i: int, lo: int, hi: int) -> BranchCost:
        if classes is not None and i == class_depth:
            label = labels_by_id[ids[i][lo >> (n - i)]]
            code = "".join(
                "<@<" + ("@" if label & (1 << bit) else "") for bit in range(width)
            )
            pieces.append(code)
            return len(code), None
        if (
            shared is not None
            and i == shared[0]
            and ids[i][lo >> (n - i)] == ids[i][shared[1] >> (n - i)]
        ):
            pieces.append("<@")
            return None, 2
        if i == n or (classes is None and constant(lo, hi)):
            code = leaf(i, reflected[lo]) + ("<" if shared is not None else "")
            pieces.append(code)
            return len(code), None
        mid = (lo + hi) // 2
        below = ids[i + 1]
        if below[lo >> (n - i - 1)] == below[mid >> (n - i - 1)]:
            pieces.append(">>")
            return add_cost(node(i + 1, lo, mid), 2)
        pieces.append("[>>")
        one = node(i + 1, mid, hi)
        pieces.append("<<]>[>" if protected else "]>[>")
        zero = node(i + 1, lo, mid)
        pieces.append("<]>" if protected else "]")
        if not protected:
            return add_cost(merge_cost(add_cost(one, 3), add_cost(zero, 2)), 3)
        # Each child returns a flag above its remaining input stack. Two
        # zero sentinels suppress the other arm after a one-side return;
        # one zero closes a zero-side return, then the common pop exposes
        # the flag again. At depth >= 2 this stays below the input peak.
        return add_cost(merge_cost(add_cost(one, 5), add_cost(zero, 3)), 4)

    cost = node(0, 0, 1 << n)
    if classes is not None:
        span = 1 << (n - class_depth)
        classes = None
        protected = False

        def decode(bit: int, labels: tuple[int, ...]) -> BranchCost:
            if bit < 0:
                row = rows[labels[0]]
                return node(class_depth, row, row + span)
            zero_labels = tuple(label for label in labels if not label & (1 << bit))
            one_labels = tuple(label for label in labels if label & (1 << bit))
            if not zero_labels or not one_labels:
                pieces.append(">>")
                return add_cost(decode(bit - 1, zero_labels or one_labels), 2)
            pieces.append("[>>")
            one = decode(bit - 1, one_labels)
            pieces.append("]>[>")
            zero = decode(bit - 1, zero_labels)
            pieces.append("]")
            return add_cost(merge_cost(add_cost(one, 3), add_cost(zero, 2)), 3)

        body = decode(width - 1, tuple(range(len(rows))))
        cost = normal_cost(cost) + normal_cost(body), None
    elif shared is not None:
        depth, row = shared
        pieces.append("[>")
        shared = None
        protected = False
        body = node(depth, row, row + (1 << (n - depth)))
        pieces.append("]")
        cost = dispatch_cost(cost, normal_cost(body) + 3, 1)
    return "".join(pieces), 4 * n - 1 + normal_cost(cost)


LANGUAGE = Language(
    "BF-PDA",
    "bf_pda",
    category="stack_based",
    boolean=bfpda,
    contract=BooleanContract(),
    wrap=wrap_chars,
    empty_program="BF-PDA program cannot be empty",
    example=Example(pair=BFPDA_PAIR),
)


@dataclass(frozen=True, slots=True)
class _Metric:
    size: int
    commands: int


def _body_metrics(context: _TreeContext) -> list[dict[int, _Metric]]:
    ids = context.ids
    n = len(ids) - 1
    metrics: list[dict[int, _Metric]] = [{} for _ in ids]
    for depth in range(n, -1, -1):
        for index, state in enumerate(ids[depth]):
            if state in metrics[depth]:
                continue
            if state < 2:
                length = 3 if depth == n and state == 1 else 2 * (n - depth) + 1
                metric = _Metric(length, length)
            else:
                zero_id, one_id = ids[depth + 1][2 * index : 2 * index + 2]
                zero, one = metrics[depth + 1][zero_id], metrics[depth + 1][one_id]
                metric = (
                    _Metric(2 + zero.size, 2 + zero.commands)
                    if zero_id == one_id
                    else _Metric(
                        8 + zero.size + one.size,
                        max(5 + zero.commands, 6 + one.commands),
                    )
                )
            metrics[depth][state] = metric
    return metrics


def _price(
    context: _TreeContext,
    depth: int,
    states: tuple[int, ...],
    bodies: list[dict[int, _Metric]],
) -> _Metric:
    # Larger banks correlate each decoder/body tail with its prefix: separate
    # maxima can belong to different residuals and reject a valid bank.
    width = (len(states) - 1).bit_length()
    decoder_size, tails = _decoder(
        width, tuple(bodies[depth][state] for state in states)
    )
    if len(states) == 2:
        # Preserve two-class admission: 00000100 at depth 2 costs 47 with
        # separate prefix/body maxima, versus 46 with correlated tails.
        tails = dict.fromkeys(tails, max(tails.values()))
    labels_by_id = {state: label for label, state in enumerate(states)}

    def prefix(level: int, index: int) -> _Metric:
        state = context.ids[level][index]
        if level == depth:
            label = labels_by_id[state]
            length = 3 * width + label.bit_count()
            return _Metric(length, length + tails[label])
        zero_id, one_id = context.ids[level + 1][2 * index : 2 * index + 2]
        zero = prefix(level + 1, 2 * index)
        if zero_id == one_id:
            return _Metric(2 + zero.size, 2 + zero.commands)
        one = prefix(level + 1, 2 * index + 1)
        return _Metric(
            12 + zero.size + one.size, max(7 + zero.commands, 9 + one.commands)
        )

    priced = prefix(0, 0)
    header = 4 * (len(context.ids) - 1) - 1
    return _Metric(header + priced.size + decoder_size, header + priced.commands)


def best_bank(
    table: str, context: _TreeContext, command_budget: int, size_limit: int
) -> str | None:
    """Price all banks; two-class banks precede larger banks on a size tie."""
    # Prefixes and decoder labels sum O(T) across depths; suffix metrics
    # are reused, and only the winning bank's bodies are emitted.
    bodies = _body_metrics(context)
    best: tuple[tuple[int, bool, int], tuple[int, ...], _Metric] | None = None
    n = len(context.ids) - 1
    for depth in range(2, n):
        representatives: dict[int, int] = {}
        for index, state in enumerate(context.ids[depth]):
            representatives.setdefault(state, index)
        width = (len(representatives) - 1).bit_length()
        # A word uses 2w stack cells plus two return sentinels. Replacing
        # 2d consumed inputs therefore needs d >= w+1; peak stack stays 2n.
        if len(representatives) < 2 or width + 1 > depth:
            continue
        metric = _price(context, depth, tuple(representatives), bodies)
        rank = metric.size, len(representatives) > 2, depth
        if (
            metric.commands <= command_budget
            and metric.size < size_limit
            and (best is None or rank < best[0])
        ):
            best = rank, tuple(representatives.values()), metric
    if best is None:
        return None
    rank, indexes, metric = best
    depth = rank[2]
    span = 1 << (n - depth)
    rows = tuple(index * span for index in indexes)
    classes = tuple(context.reflected[row : row + span] for row in rows)
    program, _ = _bfpda_tree(
        table, classes=classes, class_depth=depth, class_rows=rows, context=context
    )
    if len(program) != metric.size:
        raise ValueError("emitted BF-PDA bank disagrees with its price")
    return program


type _Emit = Callable[[str | int], None]


def _decoder(
    width: int, bodies: tuple[_Metric, ...], emit: _Emit | None = None
) -> tuple[int, dict[int, int]]:
    tails: dict[int, int] = {}

    def visit(bit: int, labels: tuple[int, ...], cost: int) -> int:
        if bit < 0:
            target = labels[0]
            tails[target] = cost + bodies[target].commands
            if emit is not None:
                emit(target)
            return bodies[target].size
        zero = tuple(label for label in labels if not label & (1 << bit))
        one = tuple(label for label in labels if label & (1 << bit))
        if not zero or not one:
            if emit is not None:
                emit(">>")
            return 2 + visit(bit - 1, zero or one, cost + 2)
        if emit is not None:
            emit("[>>")
        one_size = visit(bit - 1, one, cost + 6)
        if emit is not None:
            emit("]>[>")
        zero_size = visit(bit - 1, zero, cost + 5)
        if emit is not None:
            emit("]")
        return 8 + one_size + zero_size

    return visit(width - 1, tuple(range(len(bodies))), 0), tails


def best_mixed_bank(
    context: _TreeContext, command_budget: int, size_limit: int
) -> str | None:
    """Emit reachable repeated states at different depths when bounds admit them."""
    ids = context.ids
    n = len(ids) - 1
    blocks = repeated_definitions(context.reflected)
    width = max(1, (len(blocks) - 1).bit_length())
    # A word occupies 2w cells, its pending flag one, and a returning arm
    # two sentinels. 2w+3 <= 2d fits the retired d input pairs. Completed
    # unshared leaves empty the input stack before returning their zero flag.
    blocks = tuple((d, row) for d, row in blocks if d >= width + 2)
    selected = {(d, ids[d][row >> (n - d)]): i for i, (d, row) in enumerate(blocks)}
    used: set[int] = set()

    def collect(depth: int, index: int) -> None:
        state = ids[depth][index]
        target = selected.get((depth, state))
        if target is not None:
            used.add(target)
        elif state >= 2:
            collect(depth + 1, 2 * index)
            if ids[depth + 1][2 * index] != ids[depth + 1][2 * index + 1]:
                collect(depth + 1, 2 * index + 1)

    collect(0, 0)
    blocks = tuple(item for i, item in enumerate(blocks) if i in used)
    if len(blocks) < 2:
        return None
    width = (len(blocks) - 1).bit_length()
    selected = {(d, ids[d][row >> (n - d)]): i for i, (d, row) in enumerate(blocks)}
    metrics = _body_metrics(context)
    bodies = tuple(metrics[d][ids[d][row >> (n - d)]] for d, row in blocks)
    decoder_size, tails = _decoder(width, bodies)

    def leaf(depth: int, state: int) -> str:
        remaining = 2 * (n - depth)
        if state == 0:
            return ">" * remaining + "."
        return ">" * (remaining - 1) + ".>" if remaining else "@.>"

    def prefix(depth: int, index: int, emit: _Emit | None = None) -> _Metric:
        state = ids[depth][index]
        target = selected.get((depth, state))
        if target is not None:
            size = 3 * width + target.bit_count() + 2
            if emit is not None:
                for bit in range(width):
                    emit("<@<" + ("@" if target & (1 << bit) else ""))
                emit("<@")
            return _Metric(size, size + tails[target] + 3)
        if state < 2:
            size = metrics[depth][state].size + 1
            if emit is not None:
                emit(leaf(depth, state) + "<")
            return _Metric(size, size + 1)
        zero, one = ids[depth + 1][2 * index : 2 * index + 2]
        if zero == one:
            if emit is not None:
                emit(">>")
            value = prefix(depth + 1, 2 * index, emit)
            return _Metric(2 + value.size, 2 + value.commands)
        if emit is not None:
            emit("[>>")
        right = prefix(depth + 1, 2 * index + 1, emit)
        if emit is not None:
            emit("<<]>[>")
        left = prefix(depth + 1, 2 * index, emit)
        if emit is not None:
            emit("<]>")
        return _Metric(
            12 + left.size + right.size, max(7 + left.commands, 9 + right.commands)
        )

    tree = prefix(0, 0)
    header = "<".join(["@<" + TEMPLATE_CHAR] * n)
    size = len(header) + tree.size + decoder_size + 3
    if size >= size_limit or len(header) + tree.commands > command_budget:
        return None
    # O(T/log T) residuals give O(T) decoder digits. Price the prefix once;
    # render complete bodies only after their combined text fits inline O(T).
    pieces = [header]

    def inline(depth: int, index: int) -> None:
        state = ids[depth][index]
        if state < 2:
            pieces.append(leaf(depth, state))
            return
        zero, one = ids[depth + 1][2 * index : 2 * index + 2]
        if zero == one:
            pieces.append(">>")
            inline(depth + 1, 2 * index)
        else:
            pieces.append("[>>")
            inline(depth + 1, 2 * index + 1)
            pieces.append("]>[>")
            inline(depth + 1, 2 * index)
            pieces.append("]")

    def emit(piece: str | int) -> None:
        if isinstance(piece, int):
            depth, row = blocks[piece]
            inline(depth, row >> (n - depth))
        else:
            pieces.append(piece)

    prefix(0, 0, emit)
    pieces.append("[>")
    _decoder(width, bodies, emit)
    pieces.append("]")
    program = "".join(pieces)
    if len(program) != size:
        raise ValueError("emitted BF-PDA mixed bank disagrees with its price")
    return program
