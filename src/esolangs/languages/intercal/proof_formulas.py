"""Exact emitted-route costs, with separate conservative global ceilings."""

import re
from math import isqrt

_VARIABLE_MAX = 65535
_STATEMENT = re.compile(r"\b(?:DO|PLEASE)\s+")
_ASSIGNMENT = re.compile(
    r"([.:,])\s*(\d+)(?:\s+SUB\s+#\s*(\d+))?\s*<-\s*(?:#\s*(\d+))?"
)


def _named(n: int) -> int:
    """Bound repeated BDD nodes by indegrees and the bottom-level capacities."""
    t = 1 << n
    if n <= 21:
        return min((t >> 3) + 2, (t >> 4) + 14, (t >> 5) + 254)
    return (t >> 6) + (1 << 16) - 2


def _arrays(n: int, named: int) -> int:
    """Bound array declarations after the scalar namespace fills."""
    spilled = 2 * n - 2 + named - _VARIABLE_MAX
    return (spilled - 1) // (isqrt(spilled - 1) + 1) + 1 if spilled > 0 else 0


def _bl_sum(m: int) -> int:
    """Return sum(k.bit_length() for k in range(1, m + 1))."""
    if m <= 0:
        return 0
    b = m.bit_length()
    return (b - 2) * (1 << (b - 1)) + 1 + b * (m - (1 << (b - 1)) + 1)


def execution_terms(_: int, program: str) -> dict[str, int]:
    """Count straight-line statements, including GIVE UP, in any wrapping."""
    return {"S": len(_STATEMENT.findall(program))}


def workspace_terms(_: int, program: str) -> dict[str, int]:
    """Price the final write set; all-one inputs attain every mask's two bits.

    Inputs, negations, shared nodes and result are Boolean. A named selector
    mask is 1 or 2; all selectors equal to one make every mask 2 together.
    Entries persist, and the final cursor maximizes its width. Constants
    overwrite .1, so their repeated assignments contribute one scalar.
    """
    scalars: dict[tuple[str, int], int] = {}
    arrays: dict[int, tuple[int, set[int]]] = {}
    statements = _STATEMENT.split(program)[1:]
    for statement in statements:
        matched = _ASSIGNMENT.match(statement)
        if matched is None:
            continue
        tag, number, subscript, dimension = matched.groups()
        index = int(number)
        if tag != ",":
            scalars[tag, index] = 2 if tag == ":" else 1
        elif subscript is None:
            assert dimension is not None
            arrays[index] = int(dimension), set()
        else:
            arrays[index][1].add(int(subscript) - 1)
    bits = sum(8 + key.bit_length() + value for (_, key), value in scalars.items())
    bits += sum(
        8
        + key.bit_length()
        + width.bit_length()
        + sum((index.bit_length() or 1) + 1 for index in written)
        for key, (width, written) in arrays.items()
    )
    return {"B": bits, "S": len(statements)}


def global_execution(n: int) -> int:
    """Bound all routes; old repeated-node caps remain ceilings, not maxima."""
    if n <= 4:
        # Every non-root BDD node can be named at most once, plus aliases.
        return 3 * n + (1 << n) + 2
    return 2 * n + _named(n) + _arrays(n, _named(n)) + n - 2


def global_workspace(n: int) -> int:
    """Bound the dot/array write set and at most n-2 two-bit colon masks."""
    bl = int.bit_length
    if n <= 4:
        top = 2 * n + (1 << n)
        return 9 * top + _bl_sum(top) + 10 * n + _bl_sum(n) + bl(global_execution(n))
    named = _named(n)
    top = 2 * n - 2 + named
    spilled = top - _VARIABLE_MAX
    if spilled <= 0:
        total = 9 * top + _bl_sum(top)
    else:
        width = isqrt(spilled - 1) + 1
        arrays = _arrays(n, named)
        total = 9 * _VARIABLE_MAX + _bl_sum(_VARIABLE_MAX)
        total += arrays * (8 + bl(width)) + _bl_sum(arrays)
        full = width + 1 + _bl_sum(width - 1)
        last = spilled - (arrays - 1) * width
        total += (arrays - 1) * full + last + 1 + _bl_sum(last - 1)
    # Reordering can put the n-2 masks on the largest keys :3 through :n.
    return total + 10 * (n - 2) + _bl_sum(n) - _bl_sum(2) + bl(global_execution(n))
