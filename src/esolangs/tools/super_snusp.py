"""Boolean-function generator for Super SNUSP.

Tables use a linear packed-integer lookup, and never the language's random
``=`` opcode.  A packed integer has no subtrees to fold or share.
"""

import re
from math import isqrt

from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Language, Shape
from esolangs.tools.helpers import (
    _validate_truth_table,
    input_weights,
)
from esolangs.tools.wrap import balance_score

__all__ = ["super_snusp"]


_TWO_INPUT_SHORT = {
    # These executed forms reuse 48 both to decode each input and to encode
    # the answer, keeping the literal at the bottom of the stack.  n=2 is the
    # only arity: 723 vs 907 characters over all 16 tables (20.3%), 72 vs 256
    # (72%) on these five.
    "0000": "48{,-> ,-<}.",
    "0011": "48{,-> ,-<^.",
    "0101": "48{,-> ,-<>^.",
    "0110": "48{,-> ,-<^{>^.",
    "0111": "48{,-> ,-<^{>|.",
}


def _emit_lookup(truth_table: str) -> str:
    """Emit a linear-size integer lookup for ``truth_table``.

    The input row is accumulated by Horner's rule in cell 0.  Cell 1 then
    builds the reversed table as one binary integer at run time, shifts it by
    that row, and takes the low bit.  Each table entry emits one ``*`` and a
    one entry emits one extra ``)``, so generation and output are O(T).  An
    ignored input is read into cell 1 and left there for the next read, or
    for ``>0``, to overwrite; the table indexes the rest.
    """
    weights, truth_table = input_weights(
        truth_table, _validate_truth_table(truth_table)
    )
    out = ['"']
    for weight in weights:
        # acc *= 2; read and normalize the next ASCII bit; acc += bit.
        out.extend((">2{<*$", ">,>48{<-$", "{<+$") if weight else (">,<",))
    # Keep 2 on the value stack while cell 1 builds the packed table.  The
    # reversed source order makes truth_table[row] bit ``row`` of the integer.
    out.append(">0>2{<")
    out.extend("*)" if bit == "1" else "*" for bit in reversed(truth_table))
    # Shift by the row saved in cell 0, reduce modulo 2, encode as ASCII.
    out.append("<{>]$%$>48{<+$.")
    return "".join(out)


def _super_snusp_flat(truth_table: str) -> str:
    """Emit the straight-line program: the lookup, or a fixed form at n=2.

    A bounded ANF evaluator beat the lookup by only 1.92% at its n=4 cap
    (polarity pass 1.59%), under the 10% bar.  Every path consumes exactly
    ``n`` input lines.
    """
    n = _validate_truth_table(truth_table)
    if n == 2 and truth_table in _TWO_INPUT_SHORT:
        # An explicit START marker removes the spec's undocumented default
        # heading from generated programs; it is a no-op once execution begins.
        return '"' + _TWO_INPUT_SHORT[truth_table]
    return _emit_lookup(truth_table)


def _super_snusp_tokens(program: str) -> list[str]:
    """Split ``program`` into the pieces a fold may not break apart.

    Every command is one cell except a run of digits: a digit multiplies
    what the cell already holds by ten, and *any* non-digit clears that, so
    the mirrors of a fold between ``4`` and ``8`` would leave 4 and 8
    instead of 48.
    """
    return re.findall(r"\d+|.", program, re.S)


def _super_snusp_folded(program: str, width: int) -> str:
    r"""Fold ``program`` into a boustrophedon inside ``width`` columns.

    ``\\`` then ``/`` stacked turn an eastward row round in one row and one
    column; at the west edge ``/`` then ``\\`` turn it back.  A westward row
    is written in the order the pointer meets its cells (right to left on the
    page).  Mirrors sit at the far edges with a blank gap before them, which
    the pointer walks over, so no padding commands are needed.  ``width`` is
    raised to two more than the longest token (``48``).
    """
    tokens = _super_snusp_tokens(program)
    limit = max(width, max(len(token) for token in tokens) + 2)
    cells: dict[tuple[int, int], str] = {}
    row, col, step = 0, 0, 1
    index = 0
    # One row per iteration; the last breaks out before placing mirrors.
    while True:
        edge = limit - 1 if step == 1 else 0
        mirror, under = ("\\", "/") if step == 1 else ("/", "\\")
        room = abs(edge - col)
        taken: list[str] = []
        used = 0
        while index < len(tokens):
            token = tokens[index]
            if taken and used + len(token) > room:
                break
            taken.append(token)
            used += len(token)
            index += 1
        for i, char in enumerate("".join(taken)):
            cells[row, col + i * step] = char
        if index == len(tokens):
            break
        cells[row, edge] = mirror
        cells[row + 1, edge] = under
        row += 1
        step = -step
        col = edge + step
    height = max(r for r, _ in cells) + 1
    ends: dict[int, int] = {}
    for r, c in cells:
        ends[r] = max(ends.get(r, 0), c)
    return "\n".join(
        "".join(cells.get((r, c), " ") for c in range(ends.get(r, -1) + 1)).rstrip()
        for r in range(height)
    )


def super_snusp(truth_table: str, width: int | None = None) -> str:
    """Build a deterministic Super SNUSP program for ``truth_table``.

    The integer lookup emits one or two commands per table entry and O(n)
    setup while consuming every input.

    ``width`` asks for a column count, and the straight line folds into a
    boustrophedon to meet one -- see :func:`_super_snusp_folded`, where the
    mirrors turn a row round in one row and one column.  A width under the
    floor returns the narrowest program rather than refusing.
    """
    return _super_snusp_layout(_super_snusp_flat(truth_table), width)


def _super_snusp_layout(flat: str, width: int | None) -> str:
    """Return the natural, vertical, or folded layout of ``flat``."""
    if width is None or len(flat) <= width:
        return flat
    if 0 < width < 3:
        # START may be absent (wiki); the bottom-right rightward entry
        # meets a slash and climbs the complete straight evaluator.
        return "\n".join(reversed("/" + flat[1:]))
    if width < 4:
        pieces = []
        for token in _super_snusp_tokens(flat):
            if len(token) == 1:
                pieces.append(token)
            else:
                # The only multi-digit literal emitted is 48.
                pieces.append("6{8*")
        flat = "".join(pieces)
    return _super_snusp_folded(flat, width)


def balance_super_snusp(flat: str) -> str:
    """Return the best-balanced supported layout of a generated straight line.

    Tokens must have at most two cells. For s=ceil(sqrt(L)), the normal
    fold's W=H crossing lies at s+1 or s+2; s covers the preceding width.
    Row count decreases with width, so only crossing neighbors can win.
    """
    if any(len(token) > 2 for token in _super_snusp_tokens(flat)):
        raise ValueError("Super SNUSP balancing requires tokens of at most two cells")
    side = isqrt(len(flat) - 1) + 1
    # W rows hold at most (W-1)^2 cells and at least W*(W-3)+1:
    # first-row room is W-1, later room W-2, and each row wastes at most one.
    lower = _super_snusp_layout(flat, max(4, side))
    middle = _super_snusp_layout(flat, max(4, side + 1))
    upper = _super_snusp_layout(flat, max(4, side + 2))
    vertical = _super_snusp_layout(flat, 1)
    narrow = _super_snusp_layout(flat, 3)
    return min((flat, lower, middle, upper, vertical, narrow), key=balance_score)


def _balance(_table: str, default: str) -> str:
    """Balance the already-generated straight line."""
    return balance_super_snusp(default)


LANGUAGE = Language(
    "Super SNUSP",
    "grid_based.super_snusp",
    boolean=super_snusp,
    # A sum, not a tree: a lookup over the essential inputs only.
    shape=Shape.REDUCING,
    split=True,
    contract=BooleanContract(
        input_shape="char_stream",
    ),
    balance=_balance,
    no_wrap="a row is a grid row; a break moves code, it does not reflow",
    empty_program="Super SNUSP program cannot be empty",
)
