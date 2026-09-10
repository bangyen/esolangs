"""Boolean-function generator for Z-to-ALC (L variant).

The generator *constructs* its programs: there is no search, no simulator,
and no cache.  A truth table becomes a branch-free chunked array lookup,
and the lookup's commands are placed on the smallest values of a committed
anchor's Collatz trajectory -- collision-free by construction, and sized by
the L-th smallest value visited rather than the trajectory's peak.
"""

from functools import cache

from esolangs.tools.boolean.helpers import _ASCII_ZERO, _validate_truth_table
from esolangs.tools.ztoalc_starts import ANCHORS

__all__ = ["ztoalc_l_boolean"]

# Commands are placed only on trajectory values at or below this, so it is
# the emitted line count's ceiling (the same 2**22 the old tree generator
# carried).  What bounds arity is the anchors' capacity *under* it: 511935
# visits 386 values at or below 2**22, the most of any committed anchor,
# and the best start anywhere under the ceiling reaches only 395 (a sieve
# of every start to 2**22), so a bigger table needs a higher ceiling, not
# a better anchor.
_MAX_LINES = 2**22


def _commands(truth_table: str, n: int) -> list[str]:
    """Return the command sequence computing ``truth_table``, in run order.

    A constant table prints its constant, having consumed its inputs so the
    program still drains the stream.  Otherwise the table is split into
    ``2**hi`` chunks of ``2**lo`` rows (``lo = min(n, 2)``): the first
    ``hi`` inputs index a chunk-code array ``t``, the last ``lo`` index the
    code's bits through a shared decode array ``u``, and ``u[t[s]][v]`` is
    the answer.  Chunking is what carries ten inputs: the old one-hot init
    spent one command per selected row (512 at ``n == 10``), where a chunk
    set carries four rows in one command (256), plus a decode block capped
    at ``1 + 16 + 32`` whatever the table says.

    Each index is accumulated by double-and-add directly on the raw input
    bytes -- the ``'0'`` offsets double along with the bits, so one closing
    subtraction of ``'0' * (2**bits - 1)`` normalizes the whole index.
    """
    if len(set(truth_table)) == 1:
        return [f"x{i} = input" for i in range(n)] + [
            f"print {_ASCII_ZERO + int(truth_table[0])}",
        ]

    lo = min(n, 2)
    hi = n - lo
    width = 2**lo
    chunks = [int(truth_table[c * width : (c + 1) * width], 2) for c in range(2**hi)]

    cmds: list[str] = []
    if hi:
        cmds.append("s = input")
        for _ in range(hi - 1):
            cmds.append("s += s")
            cmds.append("s += input")
        cmds.append(f"s -= {_ASCII_ZERO * (2**hi - 1)}")
    else:
        cmds.append("s = 0")
    cmds.append("v = input")
    for _ in range(lo - 1):
        cmds.append("v += v")
        cmds.append("v += input")
    cmds.append(f"v -= {_ASCII_ZERO * (width - 1)}")

    # A zero chunk is free: ``t``'s elements default to 0, and code 0 is in
    # ``sorted(set(chunks))`` exactly when some chunk needs it, so ``u[0]``
    # exists whenever ``t[s]`` can be 0.
    cmds.append(f"t = [{2**hi}]")
    cmds.extend(f"t[{c}] = {k}" for c, k in enumerate(chunks) if k)
    cmds.append(f"u = [{2**width}]")
    for k in sorted(set(chunks)):
        cmds.append(f"u[{k}] = [{width}]")
        cmds.extend(
            f"u[{k}][{j}] = 1" for j in range(width) if (k >> (width - 1 - j)) & 1
        )
    cmds.append("r = u[t[s]][v]")
    cmds.append(f"r += {_ASCII_ZERO}")
    cmds.append("print r")
    return cmds


@cache
def _usable_values(start: int, cap: int) -> tuple[int, ...]:
    """Trajectory values of ``start`` at or below ``cap``, in visit order.

    The final 1 is excluded: the machine halts there without executing the
    line, and line 1 holds the start value anyway.
    """
    values: list[int] = []
    value = start
    while value != 1:
        if value <= cap:
            values.append(value)
        value = value // 2 if value % 2 == 0 else 3 * value + 1
    return tuple(values)


def _slots(length: int) -> tuple[int, list[int]]:
    """Return an anchor start and the lines its commands occupy.

    The slots are the ``length`` smallest usable values of the first
    anchor with enough of them, kept in visit order -- a subset of the
    trajectory's positions is still visited in trajectory order, so the
    commands run once each, in sequence, and the emitted size is the
    ``length``-th smallest value instead of the prefix peak (the peak is
    what capped the old placement at eight inputs).
    """
    for _, start in ANCHORS:
        values = _usable_values(start, _MAX_LINES)
        if len(values) < length:
            continue
        bound = sorted(values)[length - 1]
        return start, [v for v in values if v <= bound]
    capacity = max(len(_usable_values(s, _MAX_LINES)) for _, s in ANCHORS)
    raise ValueError(
        f"the ZTOALC L boolean generator needs {length} command lines at or "
        f"below {_MAX_LINES}; the committed anchors offer at most {capacity}",
    )


def ztoalc_l_boolean(truth_table: str) -> str:
    """Build a ZTOALC L program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.

    **The program is constructed, not searched for.**  Nothing branches:
    the inputs are folded into two indexes by double-and-add and answered
    by one nested lookup, so there are no branch targets to collide and
    the commands form one straight run (:func:`_commands`).

    Placement puts command ``j`` on the ``j``-th smallest value the
    anchor's trajectory visits below ``_MAX_LINES``, in visit order.  A
    trajectory visits distinct values until it reaches 1, so each command
    sits on its own line and executes once, in order; every other visited
    line is blank or beyond the code's end, and the interpreter reads both
    as no-ops.  The old placement used the trajectory's *prefix*, whose
    peak grows superexponentially (1.2e7 lines at ``n == 9``) and capped
    the generator at eight inputs; the smallest-values placement and the
    chunked lookup together put dense ``n == 10`` at 329 commands worst
    case against the anchors' 386-slot capacity.  ``n == 11`` needs more
    commands than any start under the ceiling can hold (587 dense, 545
    parity, against a sieved record of 395), so it raises
    :class:`ValueError` -- now a capacity limit rather than a peak.

    Verified against the real interpreter for every table at ``n <= 3``
    exhaustively, for random and structured tables at ``n == 4`` through
    ``n == 9``, and for every row of a dense pseudo-random table and of
    parity at ``n == 10``.
    """
    n = _validate_truth_table(truth_table)
    cmds = _commands(truth_table, n)
    start, slots = _slots(len(cmds))
    lines = [""] * max(slots)
    lines[0] = str(start)
    for value, cmd in zip(slots, cmds, strict=True):
        lines[value - 1] = cmd
    return "\n".join(lines)
