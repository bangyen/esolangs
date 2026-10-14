"""Boolean template generator for bfpda."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from functools import partial
from typing import NamedTuple

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

# Per-input command allowance and fixed overhead for decoder candidates. The
# residual dispatch guard, the flag return, and one command per input pair
# bound every decoder variant below this limit for a table of width ``n``.
_DECODER_BUDGET_PER_INPUT = 10
_DECODER_BUDGET_OVERHEAD = 2


def _decoder_budget(n: int) -> int:
    """Return the command budget bounding decoder candidates for width ``n``."""
    return _DECODER_BUDGET_PER_INPUT * n + _DECODER_BUDGET_OVERHEAD


type _Emit = Callable[[str | int], None]


@dataclass(frozen=True)
class _TreeContext:
    """The validated table in reflected form; every builder reads only this."""

    n: int
    reflected: str
    constant: Callable[[int, int], bool]
    ids: list[list[int]]


def _prepare(table: str) -> _TreeContext:
    n = _validate_truth_table(table)
    reflected = reflected_table(table, n)
    return _TreeContext(
        n, reflected, constant_span_test(reflected), subtree_ids(reflected)
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
    plain, _ = _bfpda_tree(context)
    shared = repeated_block(context.reflected)
    candidates = [plain]
    budget = _decoder_budget(context.n)
    if shared is not None:
        candidate, commands = _bfpda_tree(context, shared)
        if commands <= budget:
            candidates.append(candidate)
    bank = best_bank(context, budget, min(map(len, candidates)))
    if bank is not None:
        candidates.append(bank)

    mixed = best_mixed_bank(context, budget, min(map(len, candidates)))
    if mixed is not None:
        candidates.append(mixed)
    return min(candidates, key=len)


def _tree_head(n: int) -> str:
    # Marker then bit, per input in name order.
    return "<".join(["@<" + TEMPLATE_CHAR] * n)


def _tree_leaf(n: int, level: int, value: str) -> str:
    # ``left`` cells still hold untested inputs; a one stops on the bottom
    # marker and prints it (left == 0: only that marker remains).
    left = 2 * (n - level)
    if value == "0":
        return ">" * left + "."
    return ">" * (left - 1) + ".>" if left else "@.>"


def _plain_node(
    context: _TreeContext, pieces: list[str]
) -> Callable[[int, int, int], BranchCost]:
    """Return the unprotected inline-tree walker.

    The stack hands back the *last* input first: level ``i`` tests input
    ``n - 1 - i``, row bit ``i``; bit-reversed, each subtree is a span.
    """
    n, reflected, constant, ids = (
        context.n,
        context.reflected,
        context.constant,
        context.ids,
    )

    def node(i: int, lo: int, hi: int) -> BranchCost:
        if i == n or constant(lo, hi):
            code = _tree_leaf(n, i, reflected[lo])
            pieces.append(code)
            return len(code), None
        mid = (lo + hi) // 2
        below = ids[i + 1]
        if below[lo >> (n - i - 1)] == below[mid >> (n - i - 1)]:
            pieces.append(">>")
            return add_cost(node(i + 1, lo, mid), 2)
        pieces.append("[>>")
        one = node(i + 1, mid, hi)
        pieces.append("]>[>")
        zero = node(i + 1, lo, mid)
        pieces.append("]")
        one_arm = add_cost(one, 3)
        zero_arm = add_cost(zero, 2)
        return add_cost(merge_cost(one_arm, zero_arm), 3)

    return node


def _emit_plain_tree(context: _TreeContext) -> tuple[str, BranchCost]:
    """Emit an inline tree."""
    n = context.n
    pieces = [_tree_head(n)]
    cost = _plain_node(context, pieces)(0, 0, 1 << n)
    return "".join(pieces), cost


def _guarded_prefix(
    context: _TreeContext,
    pieces: list[str],
    leaf: Callable[[int, int, int], BranchCost | None],
) -> Callable[[int, int, int], BranchCost]:
    """Return a sentinel-protected tree walker with the shared guarded-arm shape.

    The mid/below equal-ids check emits ``">>"`` and descends with cost 2;
    otherwise a ``"[>>"`` guard splits into a one arm (closed with
    ``"<<]>[>"``, cost arm 5) and a zero arm (closed with ``"<]>"``, cost
    arm 3), merged with cost 4. ``leaf`` emits the level-specific leaf code
    and returns ``None`` to keep descending instead.
    """
    n, ids = context.n, context.ids

    def prefix(i: int, lo: int, hi: int) -> BranchCost:
        done = leaf(i, lo, hi)
        if done is not None:
            return done
        mid = (lo + hi) // 2
        below = ids[i + 1]
        if below[lo >> (n - i - 1)] == below[mid >> (n - i - 1)]:
            pieces.append(">>")
            return add_cost(prefix(i + 1, lo, mid), 2)
        pieces.append("[>>")
        one = prefix(i + 1, mid, hi)
        pieces.append("<<]>[>")
        zero = prefix(i + 1, lo, mid)
        pieces.append("<]>")
        # Each child returns a flag above its remaining input stack. Two
        # zero sentinels suppress the other arm after a one-side return;
        # one zero closes a zero-side return, then the common pop exposes
        # the flag again. At depth >= 2 this stays below the input peak.
        one_arm = add_cost(one, 5)
        zero_arm = add_cost(zero, 3)
        return add_cost(merge_cost(one_arm, zero_arm), 4)

    return prefix


def _emit_shared_tree(
    context: _TreeContext, shared: tuple[int, int]
) -> tuple[str, BranchCost]:
    """Emit a tree whose repeated residual is deferred behind a dispatch."""
    n = context.n
    reflected, constant, ids = context.reflected, context.constant, context.ids
    depth, row = shared
    match = ids[depth][row >> (n - depth)]
    pieces = [_tree_head(n)]

    def leaf(i: int, lo: int, hi: int) -> BranchCost | None:
        if i == depth and ids[i][lo >> (n - i)] == match:
            pieces.append("<@")
            return None, 2
        if i == n or constant(lo, hi):
            code = _tree_leaf(n, i, reflected[lo]) + "<"
            pieces.append(code)
            return len(code), None
        return None

    cost = _guarded_prefix(context, pieces, leaf)(0, 0, 1 << n)
    pieces.append("[>")
    body = _plain_node(context, pieces)(depth, row, row + (1 << (n - depth)))
    pieces.append("]")
    return "".join(pieces), dispatch_cost(cost, normal_cost(body) + 3, 1)


def _walk_decoder[T](
    width: int,
    count: int,
    leaf: Callable[[int, int], T],
    skip: Callable[[Callable[[], T]], T],
    split: Callable[[Callable[[], T], Callable[[], T]], T],
) -> T:
    """Walk a ``width``-bit label-word decoder, dispatching node shapes to callbacks.

    Bit ``width - 1`` is tested first. ``leaf`` receives the label and the
    accumulated path cost (2 per uniform bit, 6/5 per one/zero arm), which
    pricing callbacks add to each body's tail cost. ``skip`` handles a bit
    position where every label agrees; ``split`` handles a genuine split and
    receives thunks for the one and zero children, so each callback controls
    the exact visit order of its arms.
    """

    def visit(bit: int, labels: tuple[int, ...], cost: int) -> T:
        if bit < 0:
            return leaf(labels[0], cost)
        zero = tuple(label for label in labels if not label & (1 << bit))
        one = tuple(label for label in labels if label & (1 << bit))
        if not zero or not one:
            both = zero or one
            return skip(lambda: visit(bit - 1, both, cost + 2))
        return split(
            lambda: visit(bit - 1, one, cost + 6),
            lambda: visit(bit - 1, zero, cost + 5),
        )

    return visit(width - 1, tuple(range(count)), 0)


class _Layout(NamedTuple):
    """A classifier bank's labels: one representative row per residual."""

    depth: int
    span: int
    width: int
    rows: tuple[int, ...]
    labels: dict[int, int]


def _classifier_layout(
    context: _TreeContext,
    classes: tuple[str, ...],
    depth: int,
    class_rows: tuple[int, ...] | None,
) -> _Layout:
    """Validate a classifier bank and label its residuals in row order."""
    n, reflected = context.n, context.reflected
    if len(classes) < 2 or len(set(classes)) != len(classes):
        raise ValueError("a classifier needs at least two distinct residuals")
    if not 2 <= depth < n:
        raise ValueError("a protected classifier needs at least two consumed inputs")
    span = 1 << (n - depth)
    rows = class_rows or tuple(
        next(i for i in range(0, 1 << n, span) if reflected[i : i + span] == block)
        for block in classes
    )
    class_ids = tuple(context.ids[depth][row // span] for row in rows)
    if len(class_ids) < 2 or len(set(class_ids)) != len(class_ids):
        raise ValueError("a classifier needs at least two distinct residuals")
    width = (len(class_ids) - 1).bit_length()
    if depth < width + 1:
        raise ValueError("a classifier word exceeds the retired stack space")
    labels = {state: label for label, state in enumerate(class_ids)}
    return _Layout(depth, span, width, rows, labels)


def _emit_classifier_decoder(
    plain: Callable[[int, int, int], BranchCost],
    layout: _Layout,
    pieces: list[str],
) -> BranchCost:
    """Emit the label decoder with each residual inline; return its cost."""

    def leaf(label: int, _cost: int) -> BranchCost:
        row = layout.rows[label]
        return plain(layout.depth, row, row + layout.span)

    def skip(child: Callable[[], BranchCost]) -> BranchCost:
        pieces.append(">>")
        return add_cost(child(), 2)

    def split(
        one: Callable[[], BranchCost], zero: Callable[[], BranchCost]
    ) -> BranchCost:
        pieces.append("[>>")
        one_arm = add_cost(one(), 3)
        pieces.append("]>[>")
        zero_arm = add_cost(zero(), 2)
        pieces.append("]")
        return add_cost(merge_cost(one_arm, zero_arm), 3)

    return _walk_decoder(layout.width, len(layout.rows), leaf, skip, split)


def _emit_classifier_tree(
    context: _TreeContext,
    classes: tuple[str, ...],
    class_depth: int,
    class_rows: tuple[int, ...] | None,
) -> tuple[str, BranchCost]:
    """Emit a sentinel-protected classifier prefix plus its label decoder."""
    n, ids = context.n, context.ids
    layout = _classifier_layout(context, classes, class_depth, class_rows)
    pieces = [_tree_head(n)]

    def leaf(i: int, lo: int, _hi: int) -> BranchCost | None:
        if i == class_depth:
            label = layout.labels[ids[i][lo >> (n - i)]]
            code = "".join(
                "<@<" + ("@" if label & (1 << bit) else "")
                for bit in range(layout.width)
            )
        elif i == n:
            code = _tree_leaf(n, i, context.reflected[lo])
        else:
            return None
        pieces.append(code)
        return len(code), None

    cost = _guarded_prefix(context, pieces, leaf)(0, 0, 1 << n)
    body = _emit_classifier_decoder(_plain_node(context, pieces), layout, pieces)
    combined: BranchCost = normal_cost(cost) + normal_cost(body), None
    return "".join(pieces), combined


def _bfpda_tree(
    context: _TreeContext,
    shared: tuple[int, int] | None = None,
    *,
    classes: tuple[str, ...] | None = None,
    class_depth: int = 2,
    class_rows: tuple[int, ...] | None = None,
) -> tuple[str, int]:
    """Emit an inline tree, a shared residual, or a classifier bank."""
    if classes is not None:
        program, cost = _emit_classifier_tree(context, classes, class_depth, class_rows)
    elif shared is not None:
        program, cost = _emit_shared_tree(context, shared)
    else:
        program, cost = _emit_plain_tree(context)
    return program, 4 * context.n - 1 + normal_cost(cost)


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
    decoder_size, tails = _price_decoder(
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


def _cheapest_bank(
    context: _TreeContext, command_budget: int, size_limit: int
) -> tuple[int, tuple[int, ...], _Metric] | None:
    """Return (depth, representative rows, price) of the cheapest admitted bank."""
    # Prefixes and decoder labels sum O(T) across depths; suffix metrics
    # are reused, and only the winning bank's bodies are emitted.
    bodies = _body_metrics(context)
    best: tuple[tuple[int, bool, int], tuple[int, ...], _Metric] | None = None
    for depth in range(2, context.n):
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
    return rank[2], indexes, metric


def best_bank(
    context: _TreeContext, command_budget: int, size_limit: int
) -> str | None:
    """Price all banks; two-class banks precede larger banks on a size tie."""
    cheapest = _cheapest_bank(context, command_budget, size_limit)
    if cheapest is None:
        return None
    depth, indexes, metric = cheapest
    span = 1 << (context.n - depth)
    rows = tuple(index * span for index in indexes)
    classes = tuple(context.reflected[row : row + span] for row in rows)
    program, _ = _bfpda_tree(
        context, classes=classes, class_depth=depth, class_rows=rows
    )
    if len(program) != metric.size:
        raise ValueError("emitted BF-PDA bank disagrees with its price")
    return program


def _price_decoder(
    width: int, bodies: tuple[_Metric, ...]
) -> tuple[int, dict[int, int]]:
    """Price a label-word decoder: its size and each body's tail cost."""

    def price_leaf(label: int, cost: int) -> int:
        tails[label] = cost + bodies[label].commands
        return bodies[label].size

    def price_skip(child: Callable[[], int]) -> int:
        return 2 + child()

    def price_split(one: Callable[[], int], zero: Callable[[], int]) -> int:
        return 8 + one() + zero()

    tails: dict[int, int] = {}
    return _walk_decoder(width, len(bodies), price_leaf, price_skip, price_split), tails


def _emit_decoder(width: int, bodies: tuple[_Metric, ...], emit: _Emit) -> None:
    """Emit a label-word decoder; it consumes every bit/marker pair first."""

    def emit_leaf(label: int, _cost: int) -> None:
        emit(label)

    def emit_skip(child: Callable[[], None]) -> None:
        emit(">>")
        child()

    def emit_split(one: Callable[[], None], zero: Callable[[], None]) -> None:
        emit("[>>")
        one()
        emit("]>[>")
        zero()
        emit("]")

    _walk_decoder(width, len(bodies), emit_leaf, emit_skip, emit_split)


@dataclass(frozen=True, slots=True)
class _MixedBank:
    """A mixed bank's shared blocks and their decoder pricing."""

    tree: _TreeContext
    blocks: tuple[tuple[int, int], ...]
    selected: dict[tuple[int, int], int]
    width: int
    metrics: list[dict[int, _Metric]]
    tails: dict[int, int]


def _selection(
    tree: _TreeContext, blocks: tuple[tuple[int, int], ...]
) -> dict[tuple[int, int], int]:
    """Map each block's (depth, residual id) to its decoder label."""
    return {
        (d, tree.ids[d][row >> (tree.n - d)]): i for i, (d, row) in enumerate(blocks)
    }


def _collect_mixed_used(
    ids: list[list[int]],
    selected: dict[tuple[int, int], int],
    depth: int,
    index: int,
    used: set[int],
) -> None:
    """Mark repeated blocks reachable from a mixed-bank prefix walk."""
    state = ids[depth][index]
    target = selected.get((depth, state))
    if target is not None:
        used.add(target)
    elif state >= 2:
        _collect_mixed_used(ids, selected, depth + 1, 2 * index, used)
        if ids[depth + 1][2 * index] != ids[depth + 1][2 * index + 1]:
            _collect_mixed_used(ids, selected, depth + 1, 2 * index + 1, used)


def _mixed_blocks(tree: _TreeContext) -> tuple[tuple[int, int], ...]:
    """Return the repeated blocks a mixed prefix actually reaches."""
    blocks = repeated_definitions(tree.reflected)
    width = max(1, (len(blocks) - 1).bit_length())
    # A word occupies 2w cells, its pending flag one, and a returning arm
    # two sentinels. 2w+3 <= 2d fits the retired d input pairs. Completed
    # unshared leaves empty the input stack before returning their zero flag.
    blocks = tuple((d, row) for d, row in blocks if d >= width + 2)
    used: set[int] = set()
    _collect_mixed_used(tree.ids, _selection(tree, blocks), 0, 0, used)
    return tuple(item for i, item in enumerate(blocks) if i in used)


def _mixed_prefix(
    bank: _MixedBank, depth: int, index: int, emit: _Emit | None = None
) -> _Metric:
    """Price, or emit when ``emit`` is given, a mixed-bank prefix walk."""
    tree = bank.tree
    put: _Emit = emit or (lambda _piece: None)
    state = tree.ids[depth][index]
    target = bank.selected.get((depth, state))
    if target is not None:
        size = 3 * bank.width + target.bit_count() + 2
        for bit in range(bank.width):
            put("<@<" + ("@" if target & (1 << bit) else ""))
        put("<@")
        return _Metric(size, size + bank.tails[target] + 3)
    if state < 2:
        size = bank.metrics[depth][state].size + 1
        put(_tree_leaf(tree.n, depth, str(state)) + "<")
        return _Metric(size, size + 1)
    zero, one = tree.ids[depth + 1][2 * index : 2 * index + 2]
    if zero == one:
        put(">>")
        value = _mixed_prefix(bank, depth + 1, 2 * index, emit)
        return _Metric(2 + value.size, 2 + value.commands)
    put("[>>")
    right = _mixed_prefix(bank, depth + 1, 2 * index + 1, emit)
    put("<<]>[>")
    left = _mixed_prefix(bank, depth + 1, 2 * index, emit)
    put("<]>")
    return _Metric(
        12 + left.size + right.size, max(7 + left.commands, 9 + right.commands)
    )


def _mixed_inline(
    tree: _TreeContext, depth: int, index: int, pieces: list[str]
) -> None:
    """Render a complete mixed-bank body inline onto ``pieces``."""
    state = tree.ids[depth][index]
    if state < 2:
        pieces.append(_tree_leaf(tree.n, depth, str(state)))
        return
    zero, one = tree.ids[depth + 1][2 * index : 2 * index + 2]
    if zero == one:
        pieces.append(">>")
        _mixed_inline(tree, depth + 1, 2 * index, pieces)
    else:
        pieces.append("[>>")
        _mixed_inline(tree, depth + 1, 2 * index + 1, pieces)
        pieces.append("]>[>")
        _mixed_inline(tree, depth + 1, 2 * index, pieces)
        pieces.append("]")


def _mixed_emit(bank: _MixedBank, pieces: list[str], piece: str | int) -> None:
    """Route a decoder emission to a body render or a literal piece of text."""
    if isinstance(piece, int):
        depth, row = bank.blocks[piece]
        _mixed_inline(bank.tree, depth, row >> (bank.tree.n - depth), pieces)
    else:
        pieces.append(piece)


def best_mixed_bank(
    context: _TreeContext, command_budget: int, size_limit: int
) -> str | None:
    """Emit reachable repeated states at different depths when bounds admit them."""
    n = context.n
    blocks = _mixed_blocks(context)
    if len(blocks) < 2:
        return None
    width = (len(blocks) - 1).bit_length()
    metrics = _body_metrics(context)
    bodies = tuple(metrics[d][context.ids[d][row >> (n - d)]] for d, row in blocks)
    decoder_size, tails = _price_decoder(width, bodies)
    bank = _MixedBank(
        context, blocks, _selection(context, blocks), width, metrics, tails
    )
    tree = _mixed_prefix(bank, 0, 0)
    header = _tree_head(n)
    size = len(header) + tree.size + decoder_size + 3
    if size >= size_limit or len(header) + tree.commands > command_budget:
        return None
    # O(T/log T) residuals give O(T) decoder digits. Price the prefix once;
    # render complete bodies only after their combined text fits inline O(T).
    pieces = [header]
    emit = partial(_mixed_emit, bank, pieces)
    _mixed_prefix(bank, 0, 0, emit)
    pieces.append("[>")
    _emit_decoder(width, bodies, emit)
    pieces.append("]")
    program = "".join(pieces)
    if len(program) != size:
        raise ValueError("emitted BF-PDA mixed bank disagrees with its price")
    return program


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
