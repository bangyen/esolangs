r"""Boolean-function generator for Z-to-ALC (L variant)."""

from functools import cache

from esolangs.exceptions import GeneratorCapError
from esolangs.tools.boolean.helpers import _ASCII_ZERO, _validate_truth_table
from esolangs.tools.ztoalc_starts import ANCHORS

__all__ = ["ztoalc_l"]

# Commands are placed only on.
# the emitted line count's.
# carried).
# visits 386 values at or below.
# and the best start anywhere.
# of every start to 2**22), so.
# a better anchor.
_MAX_LINES = 2**22


def _commands(truth_table: str, n: int) -> list[str]:
    r"""Return the command sequence computing ``truth_table``, in run order."""
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

    # A zero chunk is free: ``t``'s.
    # ``sorted(set(chunks))``.
    # exists whenever ``t[s]`` can.
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
    r"""Trajectory values of ``start`` at or below ``cap``, in visit order."""
    values: list[int] = []
    value = start
    while value != 1:
        if value <= cap:
            values.append(value)
        value = value // 2 if value % 2 == 0 else 3 * value + 1
    return tuple(values)


def _slots(length: int) -> tuple[int, list[int]]:
    r"""Return an anchor start and the lines its commands occupy."""
    for _, start in ANCHORS:
        values = _usable_values(start, _MAX_LINES)
        if len(values) < length:
            continue
        bound = sorted(values)[length - 1]
        return start, [v for v in values if v <= bound]
    capacity = max(len(_usable_values(s, _MAX_LINES)) for _, s in ANCHORS)
    raise GeneratorCapError(
        f"the ZTOALC L boolean generator needs {length} command lines at or "
        f"below {_MAX_LINES}; the committed anchors offer at most {capacity}",
    )


def ztoalc_l(truth_table: str) -> str:
    r"""Build a ZTOALC L program computing the given truth table."""
    n = _validate_truth_table(truth_table)
    cmds = _commands(truth_table, n)
    start, slots = _slots(len(cmds))
    lines = [""] * max(slots)
    lines[0] = str(start)
    for value, cmd in zip(slots, cmds, strict=True):
        lines[value - 1] = cmd
    return "\n".join(lines)
