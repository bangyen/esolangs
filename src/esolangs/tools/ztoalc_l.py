"""Boolean-function generator for Z-to-ALC (L variant).

Constructed, not searched: a branch-free chunked array lookup whose
commands sit on the smallest values of a committed anchor's Collatz
trajectory, sized by the L-th smallest value rather than the peak.
"""

from functools import cache

from esolangs.exceptions import GeneratorCapError
from esolangs.tools.helpers import _ASCII_ZERO, _validate_truth_table
from esolangs.tools.ztoalc_starts import ANCHORS

__all__ = ["ztoalc_l"]

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

    A constant table prints after draining its inputs.  Otherwise the table
    is ``2**hi`` chunks of ``2**lo`` rows (``lo = min(n, 2)``): the first
    ``hi`` inputs index a chunk-code array ``t``, the last ``lo`` a shared
    decode array ``u``, and ``u[t[s]][v]`` is the answer (256 commands at
    ``n == 10`` where one-hot init spent 512).  Indices accumulate by
    double-and-add on the raw bytes, with one closing subtraction of
    ``'0' * (2**bits - 1)``.
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

    The final 1 is excluded: the machine halts there.
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

    The ``length`` smallest usable values of the first anchor covering it,
    in visit order, so the size is the ``length``-th smallest value, not
    the prefix peak that capped the old placement at eight inputs.  Chosen
    by ``end``, not by having room: ignoring it cost up to 2.7x at ``n == 8``.
    """
    for end, start in ANCHORS:
        values = _usable_values(start, _MAX_LINES)
        # ``end`` was derived at the committed ceiling; a tightened
        # ``_MAX_LINES`` shrinks the trajectory out from under it, so the
        # room is rechecked rather than trusted
        if length > end or len(values) < length:
            continue
        bound = sorted(values)[length - 1]
        return start, [v for v in values if v <= bound]
    capacity = max(len(_usable_values(s, _MAX_LINES)) for _, s in ANCHORS)
    raise GeneratorCapError(
        f"the ZTOALC L boolean generator needs {length} command lines at or "
        f"below {_MAX_LINES}; the committed anchors offer at most {capacity}",
    )


def ztoalc_l(truth_table: str, width: int | None = None) -> str:
    """Build a ZTOALC L program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n``, MSB first.
    Nothing branches (:func:`_commands`), and command ``j`` sits on the
    ``j``-th smallest trajectory value below ``_MAX_LINES``; other visited
    lines are no-ops.  The old prefix placement peaked at 1.2e7 lines at
    ``n == 9``; now dense ``n == 10`` is 329 commands against 386 slots.
    ``n == 11`` needs more (587 dense, 545 parity, against a sieved record
    of 395) and raises :class:`ValueError`.  Verified exhaustively at
    ``n <= 3``, on random and structured tables at ``n = 4..9``, and every
    row of a dense table and parity at ``n == 10``.
    """
    n = _validate_truth_table(truth_table)
    cmds = _commands(truth_table, n)
    if width is not None and "r = u[t[s]][v]" in cmds and width < 14:
        at = cmds.index("r = u[t[s]][v]")
        cmds[at : at + 1] = ["r = t[s]", "r = u[r]", "r = r[v]"]
    start, slots = _slots(len(cmds))
    lines = [""] * max(slots)
    lines[0] = str(start)
    for value, cmd in zip(slots, cmds, strict=True):
        lines[value - 1] = cmd
    return "\n".join(lines)
