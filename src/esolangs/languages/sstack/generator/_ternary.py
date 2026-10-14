"""Price a mixed-level residual bank with ternary pending words."""

from __future__ import annotations

from collections.abc import Callable

from esolangs.generation.helpers import subtree_ids
from esolangs.generation.shared_block import repeated_definitions
from esolangs.languages.sstack.generator._binary import _PROLOGUE as _BUILT_PROLOGUE
from esolangs.languages.sstack.generator._binary import (
    _decoder as _radix_decoder,
)
from esolangs.languages.sstack.generator._binary import (
    _inline_metrics,
    _prefix,
)

_PROLOGUE = '"49/b""48/c""1/f""2/g""3/a"'


def _width(classes: int) -> int:
    width, capacity = 1, 3
    while capacity < classes:
        width, capacity = width + 1, capacity * 3
    return width


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
    decoder_chars, tails = _radix_decoder(width, bodies, radix=3)

    inactive = (len(blocks) - 1) // 3 ** (width - 1) + 1

    tree = _prefix(ids, metrics, selected, width, tails, radix=3, inactive=inactive)
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
            out.append(program[len(_BUILT_PROLOGUE) :])
        else:
            out.append(piece)

    _prefix(ids, metrics, selected, width, tails, radix=3, inactive=inactive, emit=emit)
    _radix_decoder(width, bodies, emit, radix=3)
    program = "".join(out)
    if len(program) != chars:
        raise ValueError("emitted SStack ternary bank disagrees with its price")
    return program, commands
