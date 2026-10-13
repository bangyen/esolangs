"""Boolean template generator for bfpda."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from functools import partial

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
    budget = _decoder_budget(n)
    if shared is not None:
        candidate, commands = _bfpda_tree(truth_table, shared, context=context)
        if commands <= budget:
            candidates.append(candidate)
    bank = best_bank(truth_table, context, budget, min(map(len, candidates)))
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
    n: int,
    reflected: str,
    constant: Callable[[int, int], bool],
    ids: list[list[int]],
    pieces: list[str],
) -> Callable[[int, int, int], BranchCost]:
    """Return the unprotected inline-tree walker.

    The stack hands back the *last* input first: level ``i`` tests input
    ``n - 1 - i``, row bit ``i``; bit-reversed, each subtree is a span.
    """

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


def _emit_plain_tree(table: str, context: _TreeContext) -> tuple[str, BranchCost]:
    """Emit an inline tree."""
    n = _validate_truth_table(table)
    reflected, constant, ids = context.reflected, context.constant, context.ids
    pieces = [_tree_head(n)]
    cost = _plain_node(n, reflected, constant, ids, pieces)(0, 0, 1 << n)
    return "".join(pieces), cost


def _guarded_prefix(
    n: int,
    ids: list[list[int]],
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
    table: str, shared: tuple[int, int], context: _TreeContext
) -> tuple[str, BranchCost]:
    """Emit a tree whose repeated residual is deferred behind a dispatch."""
    n = _validate_truth_table(table)
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

    cost = _guarded_prefix(n, ids, pieces, leaf)(0, 0, 1 << n)
    pieces.append("[>")
    body = _plain_node(n, reflected, constant, ids, pieces)(
        depth, row, row + (1 << (n - depth))
    )
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


def _emit_classifier_tree(
    table: str,
    classes: tuple[str, ...],
    class_depth: int,
    class_rows: tuple[int, ...] | None,
    context: _TreeContext,
) -> tuple[str, BranchCost]:
    """Emit a sentinel-protected classifier prefix plus its label decoder."""
    n = _validate_truth_table(table)
    reflected, constant, ids = context.reflected, context.constant, context.ids
    if len(classes) < 2 or len(set(classes)) != len(classes):
        raise ValueError("a classifier needs at least two distinct residuals")
    if not 2 <= class_depth < n:
        raise ValueError("a protected classifier needs at least two consumed inputs")
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
    pieces = [_tree_head(n)]

    def leaf(i: int, lo: int, _hi: int) -> BranchCost | None:
        if i == class_depth:
            label = labels_by_id[ids[i][lo >> (n - i)]]
            code = "".join(
                "<@<" + ("@" if label & (1 << bit) else "") for bit in range(width)
            )
            pieces.append(code)
            return len(code), None
        if i == n:
            code = _tree_leaf(n, i, reflected[lo])
            pieces.append(code)
            return len(code), None
        return None

    prefix = _guarded_prefix(n, ids, pieces, leaf)

    plain = _plain_node(n, reflected, constant, ids, pieces)

    def decode_leaf(label: int, _cost: int) -> BranchCost:
        row = rows[label]
        return plain(class_depth, row, row + span)

    def decode_skip(child: Callable[[], BranchCost]) -> BranchCost:
        pieces.append(">>")
        return add_cost(child(), 2)

    def decode_split(
        one: Callable[[], BranchCost], zero: Callable[[], BranchCost]
    ) -> BranchCost:
        pieces.append("[>>")
        one_arm = add_cost(one(), 3)
        pieces.append("]>[>")
        zero_arm = add_cost(zero(), 2)
        pieces.append("]")
        return add_cost(merge_cost(one_arm, zero_arm), 3)

    cost = prefix(0, 0, 1 << n)
    body = _walk_decoder(width, len(rows), decode_leaf, decode_skip, decode_split)
    combined: BranchCost = normal_cost(cost) + normal_cost(body), None
    return "".join(pieces), combined


def _bfpda_tree(
    table: str,
    shared: tuple[int, int] | None = None,
    *,
    classes: tuple[str, ...] | None = None,
    class_depth: int = 2,
    class_rows: tuple[int, ...] | None = None,
    context: _TreeContext | None = None,
) -> tuple[str, int]:
    """Emit an inline tree, a shared residual, or a classifier bank."""
    if context is None:
        context = _prepare(table)
    if classes is not None:
        program, cost = _emit_classifier_tree(
            table, classes, class_depth, class_rows, context
        )
    elif shared is not None:
        program, cost = _emit_shared_tree(table, shared, context)
    else:
        program, cost = _emit_plain_tree(table, context)
    n = _validate_truth_table(table)
    return program, 4 * n - 1 + normal_cost(cost)


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
class _MixedBankContext:
    """Explicit state for the mixed-bank walks, replacing closure capture."""

    ids: list[list[int]]
    n: int
    blocks: tuple[tuple[int, int], ...]
    selected: dict[tuple[int, int], int]
    width: int
    metrics: list[dict[int, _Metric]]
    tails: dict[int, int]


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


def _mixed_prefix(
    context: _MixedBankContext, depth: int, index: int, emit: _Emit | None = None
) -> _Metric:
    """Price, or emit when ``emit`` is given, a mixed-bank prefix walk."""
    state = context.ids[depth][index]
    target = context.selected.get((depth, state))
    if target is not None:
        size = 3 * context.width + target.bit_count() + 2
        if emit is not None:
            for bit in range(context.width):
                emit("<@<" + ("@" if target & (1 << bit) else ""))
            emit("<@")
        return _Metric(size, size + context.tails[target] + 3)
    if state < 2:
        size = context.metrics[depth][state].size + 1
        if emit is not None:
            emit(_tree_leaf(context.n, depth, str(state)) + "<")
        return _Metric(size, size + 1)
    zero, one = context.ids[depth + 1][2 * index : 2 * index + 2]
    if zero == one:
        if emit is not None:
            emit(">>")
        value = _mixed_prefix(context, depth + 1, 2 * index, emit)
        return _Metric(2 + value.size, 2 + value.commands)
    if emit is not None:
        emit("[>>")
    right = _mixed_prefix(context, depth + 1, 2 * index + 1, emit)
    if emit is not None:
        emit("<<]>[>")
    left = _mixed_prefix(context, depth + 1, 2 * index, emit)
    if emit is not None:
        emit("<]>")
    return _Metric(
        12 + left.size + right.size, max(7 + left.commands, 9 + right.commands)
    )


def _mixed_inline(
    context: _MixedBankContext, depth: int, index: int, pieces: list[str]
) -> None:
    """Render a complete mixed-bank body inline onto ``pieces``."""
    state = context.ids[depth][index]
    if state < 2:
        pieces.append(_tree_leaf(context.n, depth, str(state)))
        return
    zero, one = context.ids[depth + 1][2 * index : 2 * index + 2]
    if zero == one:
        pieces.append(">>")
        _mixed_inline(context, depth + 1, 2 * index, pieces)
    else:
        pieces.append("[>>")
        _mixed_inline(context, depth + 1, 2 * index + 1, pieces)
        pieces.append("]>[>")
        _mixed_inline(context, depth + 1, 2 * index, pieces)
        pieces.append("]")


def _mixed_emit(
    context: _MixedBankContext, pieces: list[str], piece: str | int
) -> None:
    """Route a decoder emission to a body render or a literal piece of text."""
    if isinstance(piece, int):
        depth, row = context.blocks[piece]
        _mixed_inline(context, depth, row >> (context.n - depth), pieces)
    else:
        pieces.append(piece)


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
    _collect_mixed_used(ids, selected, 0, 0, used)
    blocks = tuple(item for i, item in enumerate(blocks) if i in used)
    if len(blocks) < 2:
        return None
    width = (len(blocks) - 1).bit_length()
    selected = {(d, ids[d][row >> (n - d)]): i for i, (d, row) in enumerate(blocks)}
    metrics = _body_metrics(context)
    bodies = tuple(metrics[d][ids[d][row >> (n - d)]] for d, row in blocks)
    decoder_size, tails = _price_decoder(width, bodies)
    bank_context = _MixedBankContext(
        ids=ids,
        n=n,
        blocks=blocks,
        selected=selected,
        width=width,
        metrics=metrics,
        tails=tails,
    )
    tree = _mixed_prefix(bank_context, 0, 0)
    header = _tree_head(n)
    size = len(header) + tree.size + decoder_size + 3
    if size >= size_limit or len(header) + tree.commands > command_budget:
        return None
    # O(T/log T) residuals give O(T) decoder digits. Price the prefix once;
    # render complete bodies only after their combined text fits inline O(T).
    pieces = [header]
    _mixed_prefix(bank_context, 0, 0, partial(_mixed_emit, bank_context, pieces))
    pieces.append("[>")
    _emit_decoder(width, bodies, partial(_mixed_emit, bank_context, pieces))
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
