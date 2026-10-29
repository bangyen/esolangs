"""EGL Boolean program generator: a painted grid row indexed by weighted guards.

Row 1 of a two-row grid holds the table, one cell an entry; each input's
``(-...)`` guard runs once when the bit is 1 and walks right by its Horner
weight, so the index accumulates with no branch per level; a symmetric
table walks one cell a 1 over m + 1 entries ([ablations.symmetric_count]).
A constant reads into a scratch cell and prints a literal cell.

Size:
    O(T) cells, one per entry.  n=10 parity: 556 chars, n=10 and: 552
    chars, n=10 random 1847: 3,091 chars.

Decisions:
    An indexed row is a cell, with no subtrees to fold or share.
"""

from esolangs.generation.helpers import (
    _validate_truth_table,
    input_weights,
    symmetric_weights,
)
from esolangs.generation.wrap import balance_score, balance_width
from esolangs.languages.egl.proof_formulas import workspace
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Language, Shape


def egl(truth_table: str, width: int | None = None) -> str:
    """Build an EGL program computing ``truth_table``; ``width`` wraps it."""
    return _program(truth_table, width)


def _program(truth_table: str, width: int | None = None) -> str:
    """Build the indexed grid or a two-cell read-and-print constant."""
    n = _validate_truth_table(truth_table)
    if len(set(truth_table)) == 1:
        return _wrap("2,1:" + "x" * n + ">" + "+" * int(truth_table[0]) + "=", width)
    builds = [input_weights(truth_table, n), symmetric_weights(truth_table, n)]
    # A symmetric table walks one cell a 1 over m + 1 entries
    # ([ablations.symmetric_count]).
    return min((_grid(*build, width) for build in builds if build is not None), key=len)


def _grid(weights: list[int], truth_table: str, width: int | None) -> str:
    """Paint ``truth_table`` in row 1 and walk to its entry by ``weights``."""
    size = len(truth_table)

    # Paint row 1 left to right, then fold both axes back to the origin: ``%``
    # sends (1, T - 1) to (1, 1) and ``^<`` on to the origin.  Row 0 is
    # scratch; each input is read under the pointer, and ``v=`` prints the
    # cell below.  An ignored input is a bare ``x`` the next read overwrites.
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


def _balance(_table: str, default: str) -> str:
    """Return the fold at the balanced width, never narrower than the header.

    The neighbouring widths and ``floor - 1`` never won on 564 tables at
    n=1..12 (``[ablations.balance_width_search]``).
    """
    floor = len(default.partition(":")[0]) + 1
    return min(
        default, _wrap(default, max(floor, balance_width(default))), key=balance_score
    )


LANGUAGE = Language(
    "EGL",
    "egl",
    category="grid_based",
    boolean=egl,
    # Not a tree: one painted grid cell per entry, walked to by weighted guards.
    shape=Shape.LOOKUP,
    contract=BooleanContract(
        input_shape="char_stream",
    ),
    balance=_balance,
    empty_program="EGL program must begin with 'width,height:'",
    proof_workspace=(workspace, True, (3, 5)),
)
