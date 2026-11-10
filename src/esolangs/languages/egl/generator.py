"""EGL Boolean program generator: a painted grid indexed by weighted guards.

Each three-row block holds reads, counters and painted table cells; each input's
``(-...)`` guard runs once when the bit is 1 and walks right by its low weight
or down three rows per high block, with no branch per level; a symmetric
table walks one cell a 1 over m + 1 entries ([ablations.symmetric_count]).
A constant reads into a scratch cell and prints a literal cell.

Size:
    O(T) grid cells.  n=10 parity: 288 chars, n=10 and: 284
    chars, n=10 random 1847: 1,936 chars.

Decisions:
    An indexed row is a cell, with no subtrees to fold or share.
"""

from esolangs.generation.helpers import (
    _validate_truth_table,
    input_weights,
    symmetric_weights,
)
from esolangs.generation.requests import BalanceRequest, GenerationRequest
from esolangs.generation.wrap import balance_score, balance_width
from esolangs.runtime._program import Program


def egl(truth_table: str, width: int | None = None) -> str:
    """Build an EGL program computing ``truth_table``; ``width`` wraps it."""
    n = _validate_truth_table(truth_table)
    if len(set(truth_table)) == 1:
        return _wrap("2,1:" + "x" * n + ">" + "+" * int(truth_table[0]) + "=", width)
    builds = [input_weights(truth_table, n), symmetric_weights(truth_table, n)]
    # A symmetric table walks one cell a 1 over m + 1 entries
    # ([ablations.symmetric_count]).
    return min(
        (
            _grid(*build, width, folded=k == 0)
            for k, build in enumerate(builds)
            if build is not None
        ),
        key=len,
    )


def _grid(
    weights: list[int], truth_table: str, width: int | None, *, folded: bool = False
) -> str:
    """Paint three-row blocks, then walk by binary or population-count weights."""
    size = len(truth_table)
    m = size.bit_length() - 1
    # [ablations.trick_prototype_20261102_folded_rows]: minimize W+5R
    # over power-of-two widths analytically; the count reader has one block.
    columns = 1 << min(m, (m + 3) // 2) if folded else size
    blocks = size // columns
    pieces = [f"{columns},{3 * blocks}:", "vv"]
    for row in range(blocks):
        cells = truth_table[row * columns : (row + 1) * columns]
        if row % 2:
            cells = cells[::-1]
        step = "<" if row % 2 else ">"
        pieces.append(step.join("+" if bit == "1" else "" for bit in cells))
        if row + 1 < blocks:
            pieces.append("vvv")
    # An even block count ends in column0, row3R-1: reflection lands at row1.
    pieces.append("_^" if blocks > 1 else "%^<")
    sub = "v" + "+" * 6 + "(-^" + "-" * 8 + "v)^"
    for weight in weights:
        if not weight:
            pieces.append("x")
            continue
        move = "v" * (3 * (weight // columns)) if weight >= columns else ">" * weight
        pieces.append(f"x{sub}(-{move})")
    pieces.append("vv=")
    return _wrap("".join(pieces), width)


def _wrap(program: str, width: int | None) -> str:
    """Fold the body without splitting the dimension header."""
    if width is None:
        return program
    header, rest = program.split(":", 1)
    header += ":"
    room = max(1, width)
    first = max(0, room - len(header))
    rows = [header + rest[:first]]
    rows.extend(rest[start : start + room] for start in range(first, len(rest), room))
    return "\n".join(rows)


def _balance(_table: str, default: str) -> str:
    """Return the fold at the balanced width, never narrower than the header.

    The neighbouring widths and ``floor - 1`` never won on 564 tables at
    n=1..12 (``[ablations.balance_width_search]``).
    """
    floor = len(default.partition(":")[0]) + 1
    return min(
        default, _wrap(default, max(floor, balance_width(default))), key=balance_score
    )


def egl_request(request: GenerationRequest) -> Program:
    """Emit source through the declared generation request interface."""
    if request.width is not None:
        return egl(request.table, request.width)
    return egl(request.table)


def egl_balance_request(request: BalanceRequest) -> Program:
    """Lay out source through the declared balance request interface."""
    return _balance(request.table, request.text_source())
