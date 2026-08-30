"""Boolean-function generator for Z-to-ALC (L variant).

The generator *constructs* its programs: there is no search, no simulator,
and no cache.  A truth table becomes a branch-free array lookup, and the
lookup's commands are placed on a Collatz trajectory taken from the
committed anchor table, which makes the placement collision-free by
construction rather than by trial.
"""

from esolangs.tools.boolean.helpers import (
    _ASCII_ONE,
    _ASCII_ZERO,
    _validate_truth_table,
)
from esolangs.tools.ztoalc_starts import ANCHORS

__all__ = ["ztoalc_l_boolean"]

# Largest program the generator will materialize, in lines.  The emitted
# string has one line per value up to the trajectory's peak, so a table
# whose anchor peaks past this would be built as a multi-gigabyte string:
# the peak grows far faster than the command count (n == 9 already peaks at
# 1.2e7 and n == 11 at 3.2e14).  The old tree generator carried the same
# 2**22 ceiling for the same reason.
_MAX_LINES = 2**22


def _anchor_for(length: int) -> int:
    """Return a Collatz start whose trajectory covers ``length`` commands.

    The committed ``ANCHORS`` table maps a length interval to the start with
    the smallest trajectory peak across that interval, so this is a lookup
    rather than a search -- the same table the ZTOALC L *text* generator
    uses to place its characters.
    """
    for end, start in ANCHORS:
        if end >= length:
            return start
    raise ValueError(
        f"the ZTOALC L boolean generator needs a trajectory of {length} steps "
        f"(the longest committed anchor reaches {ANCHORS[-1][0]})",
    )


def _collatz_prefix(start: int, length: int) -> list[int]:
    """Return the first ``length`` values of ``start``'s Collatz trajectory."""
    values: list[int] = []
    value = start
    for _ in range(length):
        values.append(value)
        value = value // 2 if value % 2 == 0 else 3 * value + 1
    return values


def _commands(truth_table: str, n: int) -> list[str]:
    """Return the command sequence computing ``truth_table``, in run order.

    A constant table is answered by printing the constant, having consumed
    its inputs so the program still drains the stream the way every other
    generator's does.  Otherwise the table becomes an array lookup: the
    inputs are read and normalized, their row index is accumulated by
    double-and-add, the table is one-hot encoded into an array, and the
    selected element is printed.
    """
    if len(set(truth_table)) == 1:
        return [f"x{i} = input" for i in range(n)] + [
            f"print {_ASCII_ZERO + int(truth_table[0])}",
        ]

    # The array is initialized one *selected* row at a time, so encoding
    # whichever of the one-rows and zero-rows is the shorter list caps the
    # init block at ``2**(n - 1)`` commands.  Selecting the zero-rows means
    # the array holds the complement, which the tail inverts by printing
    # ``'1' - r`` instead of ``'0' + r`` -- the same command count either
    # way, so the saving is free.
    ones = [c for c in range(2**n) if truth_table[c] == "1"]
    zeros = [c for c in range(2**n) if truth_table[c] == "0"]
    complemented = len(ones) > len(zeros)
    rows = zeros if complemented else ones

    cmds: list[str] = []
    for i in range(n):
        cmds.append(f"x{i} = input")
        cmds.append(f"x{i} - {_ASCII_ZERO}")

    # The row index, most significant input first: ``s`` is doubled and the
    # next bit added, so ``s`` ends at ``sum(x_i << (n - 1 - i))``, which is
    # exactly how the table is indexed.  ``s += s`` is a legal doubling --
    # the interpreter evaluates a command's target and its operand
    # independently -- so no scratch variable is needed.
    cmds.append("s = x0")
    for i in range(1, n):
        cmds.append("s += s")
        cmds.append(f"s += x{i}")

    cmds.append(f"t = [{2**n}]")
    cmds.extend(f"t[{row}] = 1" for row in rows)
    cmds.append("r = t[s]")
    if complemented:
        cmds.append(f"q = {_ASCII_ONE}")
        cmds.append("q -= r")
        cmds.append("print q")
    else:
        cmds.append(f"r + {_ASCII_ZERO}")
        cmds.append("print r")
    return cmds


def ztoalc_l_boolean(truth_table: str) -> str:
    """Build a ZTOALC L program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.

    **The program is constructed, not searched for.**  ZTOALC L's control
    flow is the Collatz trajectory of the value on line 1, which used to
    make placement the hard part: the generator laid a decision tree on
    ``p * 2**k`` descents, and whether a tree's branch targets and its
    leaves' Collatz tails collided was decidable only by simulating every
    candidate.  So it tried each start in turn, and each input order on top
    of that, with a simulator as the sole gate -- and still refused dense
    non-symmetric tables past ``n == 3``, because for those no start and no
    order placed.

    Two changes remove the search entirely.

    First, **the branching goes away.**  A truth table is an array lookup:
    read and normalize the inputs, accumulate the row index by
    double-and-add (``s += s`` then ``s += x{i}``), one-hot the table into
    ``t = [2**n]``, and print ``t[s]``.  Nothing branches, so there are no
    branch targets to collide and the commands form one straight run.

    Second, **the run is placed on a trajectory, not a descent.**  A Collatz
    trajectory visits distinct values until it reaches 1 -- a repeat would
    be a cycle it never escapes -- so placing command ``j`` on the ``j``-th
    value visited guarantees each command sits on its own line and executes
    once, in order.  The start comes from the committed anchor table
    (:mod:`esolangs.tools.ztoalc_starts`), chosen by command count, so it is
    a lookup.  That is the whole placement argument, and it holds for every
    table.

    Reordering the inputs is gone with the search.  It bought two things
    here, and the construction moots both: there is no tree to fold, and the
    program's length depends only on the command count, which is
    permutation-invariant (the table's one-count does not move when its
    inputs are renamed).

    The programs are also much shorter.  The old generator's fallback for a
    dense symmetric table was a branch-free program on the pure
    power-of-two descent, whose ``2**L`` lines meant XOR4 rendered as
    524,288 lines; a trajectory's peak grows far slower than ``2**L``, and
    XOR4 is now 484.  The dense table that previously needed a reordered
    tree to place at all is 388 lines, down from 36,864.

    Two limits remain, and both are size, not placement.  A table needing
    more commands than the longest committed anchor covers, or whose
    trajectory peaks past ``_MAX_LINES``, raises :class:`ValueError` rather
    than building a program that cannot be materialized.  Sparse tables
    reach further than dense ones, since the array init is one command per
    selected row.

    Verified against the real interpreter for every table at ``n <= 3``
    exhaustively, and for random and structured tables at ``n == 4`` through
    ``n == 7``.
    """
    n = _validate_truth_table(truth_table)
    cmds = _commands(truth_table, n)
    start = _anchor_for(len(cmds))
    values = _collatz_prefix(start, len(cmds))

    size = max(max(values), 1)
    if size > _MAX_LINES:
        raise ValueError(
            f"the ZTOALC L boolean generator would need {size} lines for this "
            f"table at n == {n}, past the {_MAX_LINES}-line limit",
        )

    lines = [""] * size
    lines[0] = str(start)
    for value, cmd in zip(values, cmds, strict=True):
        lines[value - 1] = cmd
    return "\n".join(lines)
