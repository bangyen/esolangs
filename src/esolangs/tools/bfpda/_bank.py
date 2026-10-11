"""Price whole residual banks before emitting the shortest admitted word bank."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.tools.bfpda import _TreeContext


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
    # Each label keeps its own decoder/body tail: independent prefix and
    # body maxima can belong to different residuals and reject a valid bank.
    width = (len(states) - 1).bit_length()
    tails: dict[int, int] = {}

    def decoder(bit: int, labels: tuple[int, ...], commands: int) -> int:
        if bit < 0:
            label = labels[0]
            body = bodies[depth][states[label]]
            tails[label] = commands + body.commands
            return body.size
        zero = tuple(label for label in labels if not label & (1 << bit))
        one = tuple(label for label in labels if label & (1 << bit))
        if not zero or not one:
            return 2 + decoder(bit - 1, zero or one, commands + 2)
        return (
            8
            + decoder(bit - 1, one, commands + 6)
            + decoder(bit - 1, zero, commands + 5)
        )

    decoder_size = decoder(width - 1, tuple(range(len(states))), 0)
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
    """Price every bank with at least three classes, emitting only its winner."""
    from esolangs.tools.bfpda import _bfpda_tree

    bodies = _body_metrics(context)
    best: tuple[int, tuple[int, ...], _Metric] | None = None
    n = len(context.ids) - 1
    for depth in range(2, n):
        representatives: dict[int, int] = {}
        for index, state in enumerate(context.ids[depth]):
            representatives.setdefault(state, index)
        width = (len(representatives) - 1).bit_length()
        # A word uses 2w stack cells plus two return sentinels. Replacing
        # 2d consumed inputs therefore needs d >= w+1; peak stack stays 2n.
        if len(representatives) < 3 or width + 1 > depth:
            continue
        metric = _price(context, depth, tuple(representatives), bodies)
        if metric.commands <= command_budget and metric.size < size_limit:
            size_limit = metric.size
            best = depth, tuple(representatives.values()), metric
    if best is None:
        return None
    depth, indexes, metric = best
    span = 1 << (n - depth)
    rows = tuple(index * span for index in indexes)
    classes = tuple(context.reflected[row : row + span] for row in rows)
    program, _ = _bfpda_tree(
        table, classes=classes, class_depth=depth, class_rows=rows, context=context
    )
    if len(program) != metric.size:
        raise ValueError("emitted BF-PDA bank disagrees with its price")
    return program
