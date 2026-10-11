"""Boolean-function generator for EGL."""

from math import isqrt

from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Language, Shape
from esolangs.tools.helpers import _validate_truth_table, input_weights
from esolangs.tools.wrap import balance_score


def egl(truth_table: str, width: int | None = None) -> str:
    """Build an EGL program computing ``truth_table``.

    Row 1 of a two-row grid holds the table, one cell an entry; ``%`` sends
    ``(1, T - 1)`` to ``(1, 1)`` and ``^<`` on to the origin.  Row 0 is
    scratch: each input is read under the pointer and its ``(-...)`` guard,
    run once exactly when the bit is 1, walks right by the input's Horner
    weight, so the weights accumulate into the index with no branch per
    level, and ``v=`` prints the cell below.  An ignored input is a bare
    ``x`` the next read overwrites, and the table is indexed by the rest.  A
    constant reads into a scratch cell and prints its adjacent literal cell.
    An indexed row is a cell, with no subtrees to fold or share.
    """
    return _program(truth_table, width)


def _program(
    truth_table: str, width: int | None = None, *, keep_constant_table: bool = False
) -> str:
    """Build the indexed grid or a two-cell read-and-print constant."""
    n = _validate_truth_table(truth_table)
    if len(set(truth_table)) == 1 and not keep_constant_table:
        return _wrap("2,1:" + "x" * n + ">" + "+" * int(truth_table[0]) + "=", width)
    weights, projected = input_weights(truth_table, n)
    if any(weights):
        truth_table = projected
    else:
        weights = [1 << (n - 1 - index) for index in range(n)]
    size = len(truth_table)

    # Paint row 1 left to right, then fold both axes back to the origin.
    cells = ["+" if bit == "1" else "" for bit in truth_table]
    pieces = [f"{size},2:", "v", ">".join(cells), "%^<"]

    # One read and one weighted guard an input; the weights sum to T - 1.
    pieces += [f"x{'-' * 48}(-{'>' * weight})" if weight else "x" for weight in weights]
    pieces.append("v=")

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


def _balance(table: str, default: str) -> str:
    """Balance character folds above the header and its fixed-width regime."""
    if len(set(table)) == 1:
        legacy = _program(table, keep_constant_table=True)
        return min(_balanced(default), _balanced(legacy), key=balance_score)
    return _balanced(default)


def _balanced(default: str) -> str:
    """Return the best character fold across the header-width regimes."""
    header, _, body = default.partition(":")
    floor = len(header) + 1
    square = max(floor, isqrt(len(default) - 1) + 1)
    crossing = len(body) // (floor - 1)
    widths = {
        square,
        min(max(1, crossing), floor - 1),
        min(max(1, crossing + 1), floor - 1),
    }
    return min(default, *(_wrap(default, width) for width in widths), key=balance_score)


LANGUAGE = Language(
    "EGL",
    "grid_based.egl",
    boolean=egl,
    # Not a tree: one painted grid cell per entry, walked to by weighted guards.
    shape=Shape.LOOKUP,
    contract=BooleanContract(
        input_shape="char_stream",
    ),
    balance=_balance,
    empty_program="EGL program must begin with 'width,height:'",
)
