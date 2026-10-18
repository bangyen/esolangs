"""Price every same-level bank, emitting only the shortest admitted one.

Digits 1/2 differ from an empty pending stack's zero. Each decoder consumes
the complete word before its body, so parent guards fail when it returns.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from esolangs.generation.helpers import subtree_ids
from esolangs.generation.shared_block import _repeated_blocks
from esolangs.languages.sstack.generator._walk import _Hooks, _TreeWalk

_PROLOGUE = '"49/b""48/c"'
_REFERENCES = '"1/f""2/g"'
type _Builder = Callable[[str], tuple[str, int]]
type _Emit = Callable[[str | int], None]


@dataclass(frozen=True, slots=True)
class _Metric:
    chars: int
    commands: int


@dataclass(frozen=True, slots=True)
class _Plan:
    depth: int
    rows: tuple[int, ...]
    metric: _Metric


def _inline_metrics(ids: list[list[int]]) -> list[dict[int, _Metric]]:
    n = len(ids) - 1
    result: list[dict[int, _Metric]] = [{} for _ in ids]
    for depth in range(n, -1, -1):
        remaining = n - depth
        for block, key in enumerate(ids[depth]):
            if key in result[depth]:
                continue
            if key < 2:
                value = _Metric(3 * remaining + 3, remaining + 1)
            else:
                zero, one = ids[depth + 1][2 * block : 2 * block + 2]
                left, right = result[depth + 1][zero], result[depth + 1][one]
                value = (
                    _Metric(3 + left.chars, 1 + left.commands)
                    if zero == one
                    else _Metric(
                        21 + left.chars + right.chars,
                        6 + max(left.commands, right.commands),
                    )
                )
            result[depth][key] = value
    return result


def _decoder(
    width: int,
    bodies: tuple[_Metric, ...],
    emit: _Emit | None = None,
) -> tuple[int, dict[int, int]]:
    def visit(bit: int, labels: tuple[int, ...]) -> tuple[int, dict[int, int]]:
        if bit < 0:
            target = labels[0]
            if emit is not None:
                emit(target)
            return bodies[target].chars, {target: bodies[target].commands}
        arms = [
            (value, tuple(label for label in labels if label >> bit & 1 == value))
            for value in (1, 0)
        ]
        arms = [(value, group) for value, group in arms if group]
        # Only an active parent reaches a fixed digit. Pop it without a test;
        # the root retains both guards so an absent pending word is a no-op.
        if len(arms) == 1 and bit < width - 1:
            if emit is not None:
                emit("~e~")
            chars, tails = visit(bit - 1, arms[0][1])
            return chars + 3, {target: cost + 1 for target, cost in tails.items()}
        chars = 0
        costs = {}
        for value, group in arms:
            if emit is not None:
                emit("[e\\" + "fga"[value] + "/~e~")
            size, tails = visit(bit - 1, group)
            if emit is not None:
                emit("]")
            chars += size + 9
            costs.update(
                {target: cost + 3 + len(arms) for target, cost in tails.items()}
            )
        return chars, costs

    return visit(width - 1, tuple(range(len(bodies))))


def _silent(_item: str | int) -> None:
    """Discard an emission: the pricing walk builds text nowhere."""


def _prefix_hooks(
    metrics: list[dict[int, _Metric]],
    selected: dict[tuple[int, int], int],
    width: int,
    tails: dict[int, int],
    stop_depth: int | None,
    emit: _Emit,
) -> _Hooks[_Metric]:
    """Return the bank prefix's hooks: bank hits, bank-level leaves, pricing."""

    def hit(
        depth: int, key: int, _lo: int, _remaining: int, _context: object
    ) -> _Metric | None:
        if (depth, key) not in selected:
            return None
        target = selected[depth, key]
        for bit in range(width):
            emit(f'"{1 + (target >> bit & 1)}/e"')
        return _Metric(5 * width, width + tails[target])

    def leaf(
        depth: int, key: int, lo: int, remaining: int, _context: object
    ) -> _Metric:
        if depth == stop_depth:
            # ``lo`` is the bank span's first row: the body index itself.
            emit(lo)
        else:
            emit(";d;" * remaining + (":b:" if key else ":c:"))
        value = metrics[depth][key]
        return _Metric(value.chars, value.commands + 2)

    return _Hooks(
        hit=hit,
        leaf=leaf,
        skipped=lambda child: _Metric(3 + child.chars, 1 + child.commands),
        branched=lambda one, zero: _Metric(
            21 + zero.chars + one.chars, 6 + max(zero.commands, one.commands)
        ),
        leaf_at=lambda depth, key: depth == stop_depth or key < 2,
    )


def _prefix_metric(
    ids: list[list[int]],
    metrics: list[dict[int, _Metric]],
    selected: dict[tuple[int, int], int],
    width: int,
    tails: dict[int, int],
    *,
    stop_depth: int | None = None,
) -> _Metric:
    """Price the prefix tree down to ``stop_depth`` without emitting it."""
    hooks = _prefix_hooks(metrics, selected, width, tails, stop_depth, _silent)
    return _TreeWalk(ids, _silent, hooks).walk(len(ids) - 1, 0)


def _emit_prefix(
    ids: list[list[int]],
    metrics: list[dict[int, _Metric]],
    depth: int,
    rows: tuple[int, ...],
    emit: _Emit,
) -> None:
    """Emit the prefix tree for the bank at ``depth`` over ``rows``."""
    n = len(ids) - 1
    width = (len(rows) - 1).bit_length()
    selected = {ids[depth][row >> (n - depth)]: i for i, row in enumerate(rows)}
    bodies = tuple(metrics[depth][key] for key in selected)
    _, tails = _decoder(width, bodies)
    by_depth = {(depth, key): target for key, target in selected.items()}
    hooks = _prefix_hooks(metrics, by_depth, width, tails, depth, emit)
    _TreeWalk(ids, emit, hooks).walk(n, 0)


def _price(
    ids: list[list[int]],
    metrics: list[dict[int, _Metric]],
    depth: int,
    rows: tuple[int, ...],
) -> _Plan:
    n = len(ids) - 1
    width = (len(rows) - 1).bit_length()
    selected = {ids[depth][row >> (n - depth)]: i for i, row in enumerate(rows)}
    bodies = tuple(metrics[depth][key] for key in selected)
    decoder_chars, tails = _decoder(width, bodies)

    value = _prefix_metric(
        ids,
        metrics,
        {(depth, key): target for key, target in selected.items()},
        width,
        tails,
        stop_depth=depth,
    )
    return _Plan(
        depth, rows, _Metric(22 + value.chars + decoder_chars, 4 + value.commands)
    )


def _render(
    table: str, ids: list[list[int]], plan: _Plan, build: _Builder
) -> tuple[str, int]:
    n = len(ids) - 1
    depth, rows = plan.depth, plan.rows
    remaining = n - depth
    width = (len(rows) - 1).bit_length()
    selected = {ids[depth][row >> remaining]: i for i, row in enumerate(rows)}
    metrics = _inline_metrics(ids)
    bodies: dict[int, str] = {}

    def body(row: int) -> str:
        key = ids[depth][row >> remaining]
        if key not in bodies:
            program, commands = build(table[row : row + (1 << remaining)])
            expected = metrics[depth][key]
            if not program.startswith(_PROLOGUE) or (
                len(program) - len(_PROLOGUE),
                commands - 2,
            ) != (expected.chars, expected.commands):
                raise ValueError("inline SStack builder disagrees with the bank price")
            bodies[key] = program[len(_PROLOGUE) :]
        return bodies[key]

    out = [_PROLOGUE]
    _emit_prefix(
        ids,
        metrics,
        depth,
        rows,
        lambda item: out.append(item if isinstance(item, str) else body(item)),
    )
    out.append(_REFERENCES)

    def emit(item: str | int) -> None:
        out.append(item if isinstance(item, str) else body(rows[item]))

    _decoder(width, tuple(metrics[depth][key] for key in selected), emit)
    program = "".join(out)
    if len(program) != plan.metric.chars:
        raise ValueError("emitted SStack bank disagrees with its size price")
    return program, plan.metric.commands


def binary_bank(
    table: str, blocks: tuple[tuple[int, int], ...], build: _Builder
) -> tuple[str, int]:
    """Emit one same-level bank whose bit word fits the retired-input budget."""
    ids = subtree_ids(table)
    n = len(ids) - 1
    if len(blocks) < 2 or len({depth for depth, _ in blocks}) != 1:
        raise ValueError("a binary bank needs multiple definitions at one level")
    depth = blocks[0][0]
    width = (len(blocks) - 1).bit_length()
    if not 0 <= depth <= n - 2 or width > 3 * (n - depth) - 2:
        raise ValueError("binary labels exceed the unread-input bit budget")
    span = 1 << (n - depth)
    rows = tuple(row for _, row in blocks)
    if any(row < 0 or row % span or row + span > len(table) for row in rows):
        raise ValueError("definitions must name aligned table spans")
    keys = [ids[depth][row // span] for row in rows]
    if len(set(keys)) != len(keys) or any(key < 2 for key in keys):
        raise ValueError("definitions must name distinct nonconstant residuals")
    return _render(table, ids, _price(ids, _inline_metrics(ids), depth, rows), build)


def best_binary_bank(
    table: str, build: _Builder, command_budget: int, size_limit: int
) -> tuple[str, int] | None:
    """Price all folded-tree levels in O(T), then emit the best admitted bank."""
    ids = subtree_ids(table)
    n = len(ids) - 1
    metrics = _inline_metrics(ids)
    groups: dict[int, list[int]] = {}
    for depth, row, _ in _repeated_blocks(table):
        groups.setdefault(depth, []).append(row)
    best = None
    for depth, rows in groups.items():
        width = (len(rows) - 1).bit_length()
        # The pending word costs at most 2w bits and its references cost three.
        # 2w+3 <= 6r pays for both from r unread six-bit input bytes. A body
        # has consumed the word; one popped prefix test pays for its references.
        if len(rows) < 2 or width > 3 * (n - depth) - 2:
            continue
        candidate = _price(ids, metrics, depth, tuple(rows))
        if (
            candidate.metric.commands <= command_budget
            and candidate.metric.chars < size_limit
        ):
            best, size_limit = candidate, candidate.metric.chars
    # Prefixes stop at their bank level: sum_d 2**d = O(T). For a span 2**r,
    # there are at most T/2**r bank states, each carrying O(r) label digits;
    # decoder and body work summed over all levels is O(T) as well.
    return (
        None
        if best is None
        else binary_bank(table, tuple((best.depth, row) for row in best.rows), build)
    )
