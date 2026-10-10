"""Price a mixed-level residual bank with ternary pending words."""

from __future__ import annotations

from collections.abc import Callable

from esolangs.tools.helpers import subtree_ids
from esolangs.tools.shared_block import repeated_definitions
from esolangs.tools.sstack_binary import _inline_metrics, _Metric

_PROLOGUE = '"49/b""48/c""1/f""2/g""3/a"'
type _Emit = Callable[[str | int], None]


def _width(classes: int) -> int:
    width, capacity = 1, 3
    while capacity < classes:
        width, capacity = width + 1, capacity * 3
    return width


def _decoder(
    width: int, bodies: tuple[_Metric, ...], emit: _Emit | None = None
) -> tuple[int, dict[int, int]]:
    def visit(bit: int, labels: tuple[int, ...]) -> tuple[int, dict[int, int]]:
        if bit < 0:
            target = labels[0]
            if emit is not None:
                emit(target)
            return bodies[target].chars, {target: bodies[target].commands}
        divisor = 3**bit
        arms = [
            (value, tuple(label for label in labels if label // divisor % 3 == value))
            for value in (2, 1, 0)
        ]
        arms = [(value, group) for value, group in arms if group]
        if len(arms) == 1 and bit < width - 1:
            if emit is not None:
                emit("~e~")
            chars, tails = visit(bit - 1, arms[0][1])
            return chars + 3, {target: cost + 1 for target, cost in tails.items()}
        chars, costs = 0, {}
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


def best_ternary_bank(
    table: str,
    build: Callable[[str], tuple[str, int]],
    command_budget: int,
    size_limit: int,
) -> tuple[str, int] | None:
    """Emit the reachable mixed-level bank when its exact price is admitted."""
    ids = subtree_ids(table)
    n = len(ids) - 1
    blocks = repeated_definitions(table)
    width = _width(len(blocks))
    # References 1/2/3 use five bits; each pending digit uses at most two.
    # 2w+5 <= 6r pays from unread inputs. A popped prefix input pays for the
    # references after decoding. The persistent 3 under a read differs from
    # both ASCII guards, so a body's one-shot branches still cannot repeat.
    blocks = tuple((d, row) for d, row in blocks if width <= 3 * (n - d) - 3)
    selected = {(d, ids[d][row >> (n - d)]): i for i, (d, row) in enumerate(blocks)}
    used: set[int] = set()

    def collect(depth: int, block: int) -> None:
        key = ids[depth][block]
        target = selected.get((depth, key))
        if target is not None:
            used.add(target)
        elif key >= 2:
            zero, one = ids[depth + 1][2 * block : 2 * block + 2]
            collect(depth + 1, 2 * block)
            if zero != one:
                collect(depth + 1, 2 * block + 1)

    collect(0, 0)
    blocks = tuple(item for i, item in enumerate(blocks) if i in used)
    if len(blocks) < 2:
        return None
    width = _width(len(blocks))
    selected = {(d, ids[d][row >> (n - d)]): i for i, (d, row) in enumerate(blocks)}
    metrics = _inline_metrics(ids)
    bodies = tuple(metrics[d][ids[d][row >> (n - d)]] for d, row in blocks)
    decoder_chars, tails = _decoder(width, bodies)

    inactive = (len(blocks) - 1) // 3 ** (width - 1) + 1

    def prefix(depth: int, block: int, emit: _Emit | None = None) -> _Metric:
        key = ids[depth][block]
        target = selected.get((depth, key))
        if target is not None:
            if emit is not None:
                for bit in range(width):
                    emit(f'"{1 + target // 3**bit % 3}/e"')
            return _Metric(5 * width, width + tails[target])
        if key < 2:
            if emit is not None:
                emit(";d;" * (n - depth) + (":b:" if key else ":c:"))
            value = metrics[depth][key]
            return _Metric(value.chars, value.commands + inactive)
        zero, one = ids[depth + 1][2 * block : 2 * block + 2]
        if zero == one:
            if emit is not None:
                emit(";d;")
            value = prefix(depth + 1, 2 * block, emit)
            return _Metric(3 + value.chars, 1 + value.commands)
        if emit is not None:
            emit(";a;[a\\b/~a~")
        right = prefix(depth + 1, 2 * block + 1, emit)
        if emit is not None:
            emit("][a\\c/~a~")
        left = prefix(depth + 1, 2 * block, emit)
        if emit is not None:
            emit("]")
        return _Metric(
            21 + left.chars + right.chars, 6 + max(left.commands, right.commands)
        )

    tree = prefix(0, 0)
    chars = len(_PROLOGUE) + tree.chars + decoder_chars
    commands = 5 + tree.commands
    if chars >= size_limit or commands > command_budget:
        return None
    # There are O(T/log T) residuals, hence O(T) decoder digits. Pricing uses
    # one folded-tree traversal; bodies render only after total text fits the
    # inline O(T) limit. No complete body is allowed to defer a second time.
    out: list[str] = [_PROLOGUE]

    def emit(piece: str | int) -> None:
        if isinstance(piece, int):
            depth, row = blocks[piece]
            program, _ = build(table[row : row + (1 << (n - depth))])
            out.append(program[12:])
        else:
            out.append(piece)

    prefix(0, 0, emit)
    _decoder(width, bodies, emit)
    program = "".join(out)
    if len(program) != chars:
        raise ValueError("emitted SStack ternary bank disagrees with its price")
    return program, commands
