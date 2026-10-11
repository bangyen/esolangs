"""Price a protected, mixed-level bank before rendering its definitions."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from esolangs.tools.bfpda._bank import _body_metrics, _Metric
from esolangs.tools.helpers import TEMPLATE_CHAR
from esolangs.tools.shared_block import repeated_definitions

if TYPE_CHECKING:
    from esolangs.tools.bfpda import _TreeContext

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
