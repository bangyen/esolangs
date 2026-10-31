"""Super SNUSP Boolean program generator: a packed-integer lookup.

Horner's rule folds the inputs into a row in cell 0; cell 1 holds the table
as one decimal literal (a digit run is ``cell * 10 + digit``), shifts it by
the row and takes the low bit.  The random ``=`` opcode is never used.  At
n=2 five tables use a fixed short form.

Size:
    The table's decimal digits, at most ceil(0.30103(T-1)), plus 19n + 21
    chars;
    n=2 parity: 16 chars, n=16 and: 20,054 chars, n=16 parity: 20,053 chars.

Decisions:
    A packed integer has no subtrees to fold or share.  A bounded ANF
    evaluator beat the former ``*``-per-entry lookup by only 2.83% at its n=4
    cap (all 65,536 tables; 0.80% without the polarity pass), under the 10%
    bar, and the decimal literal is smaller still.
"""

import re
from math import isqrt

from esolangs.generation.helpers import (
    _validate_truth_table,
    input_weights,
)
from esolangs.generation.token_balance import CELL_ASPECT
from esolangs.generation.wrap import balance_score
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Language, Shape

__all__ = ["super_snusp"]


_TWO_INPUT_SHORT = {
    # These executed forms reuse 48 both to decode each input and to encode
    # the answer, keeping the literal at the bottom of the stack.  n=2 is the
    # only arity ([ablations.two_input_short_forms]).
    "0000": "48{,-> ,-<}.",
    "0011": "48{,-> ,-<^.",
    "0101": "48{,-> ,-<>^.",
    "0110": "48{,-> ,-<^{>^.",
    "0111": "48{,-> ,-<^{>|.",
}


def _decimal(value: int, width: int = 0) -> str:
    """Return ``value`` in decimal, zero-padded to ``width``.

    Halves by powers of ten: ``str`` refuses integers past 4,300 digits, and
    a global ``sys.set_int_max_str_digits`` would be process-wide state.
    """
    if value.bit_length() <= 12000:
        return str(value).zfill(width)
    half = value.bit_length() * 3 // 20
    high, low = divmod(value, 10**half)
    return _decimal(high, max(width - half, 0)) + _decimal(low, half)


def _emit_lookup(truth_table: str) -> str:
    """Emit a linear-size integer lookup for ``truth_table``.

    The input row is accumulated by Horner's rule in cell 0.  Cell 1 then
    holds the reversed table as one decimal integer, shifts it by that row,
    and takes the low bit; output is O(T) digits.  An ignored input is read
    into cell 1 and left there for the next read, or for the literal's first
    digit, to overwrite; the table indexes the rest.
    """
    weights, truth_table = input_weights(
        truth_table, _validate_truth_table(truth_table)
    )
    out = ['"']
    for weight in weights:
        # acc *= 2; read and normalize the next ASCII bit; acc += bit.
        out.extend((">2{<*$", ">,>48{<-$", "{<+$") if weight else (">,<",))
    # Keep 2 on the value stack, then write the reversed table as one decimal
    # literal in cell 1: a digit run is ``cell * 10 + digit`` and its first
    # digit replaces the cell.  The reversed source order makes
    # truth_table[row] bit ``row`` of the integer.
    value = int(truth_table[::-1], 2)
    # Encode the bit as 49 ^ bit (the complement) or 48 + bit, one character
    # either way, so use whichever integer has fewer digits.
    plain, other = _decimal(value), _decimal((1 << len(truth_table)) - 1 - value)
    flip = len(other) < len(plain)
    out.append(f">>2{{<{other if flip else plain}")
    # Shift by the row saved in cell 0, reduce modulo 2, encode as ASCII.
    out.append("<{>]$%$>49{<^$." if flip else "<{>]$%$>48{<+$.")
    return "".join(out)


def _super_snusp_flat(truth_table: str) -> str:
    """Emit the straight-line program: the lookup, or a fixed form at n=2.

    Every path consumes exactly ``n`` input lines.
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
    """Build a Super SNUSP program; ``width`` folds it (:func:`_super_snusp_folded`).

    A width under the floor returns the narrowest program rather than refusing.
    """
    return _super_snusp_layout(_super_snusp_flat(truth_table), width)


def _fold_floor(flat: str) -> int:
    """Return the narrowest fold width: two more than the longest token."""
    return max(len(token) for token in _super_snusp_tokens(flat)) + 2


def _super_snusp_layout(flat: str, width: int | None) -> str:
    """Return the natural, vertical, or folded layout of ``flat``."""
    if width is None or len(flat) <= width:
        return flat
    if 0 < width < _fold_floor(flat):
        # START may be absent (wiki); the bottom-right rightward entry
        # meets a slash and climbs the complete straight evaluator.  At width
        # 3 this is 53% fewer characters than the fold (356 tables, n<=7).
        # A fold cannot split the decimal literal, so a width under it
        # climbs too, in one column.
        return "\n".join(reversed("/" + flat[1:]))
    return _super_snusp_folded(flat, width)


def balance_super_snusp(flat: str) -> str:
    """Return the best-balanced supported layout of a generated straight line.

    For A=CELL_ASPECT and s=ceil(sqrt(A*L)), the normal fold's W=A*H crossing
    and its predecessor lie in [s-1, s+(4+A)//2] when every token has at most
    two cells.  Row count decreases with width, so only crossing neighbors can
    win.  The decimal literal cannot be split, so the narrowest fold that
    holds it whole is a candidate too.
    """
    side = isqrt(CELL_ASPECT * len(flat) - 1) + 1
    # H rows hold at most (W-1)+(H-1)(W-2) cells and at least
    # (W-2)+(H-2)(W-3)+1: first-row room is W-1, later room W-2, and each
    # row wastes at most one.  So H >= (L-1)/(W-2) and H <= (L+W-5)/(W-3).
    floor = _fold_floor(flat)
    folds = [
        _super_snusp_layout(flat, max(floor, width))
        for width in (*range(side - 1, side + (4 + CELL_ASPECT) // 2 + 1), floor)
    ]
    vertical = _super_snusp_layout(flat, 1)
    return min((flat, *folds, vertical), key=balance_score)


def _balance(_table: str, default: str) -> str:
    """Balance the already-generated straight line."""
    return balance_super_snusp(default)


LANGUAGE = Language(
    "Super SNUSP",
    "super_snusp",
    category="grid_based",
    random=True,
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
    grid=True,
)
