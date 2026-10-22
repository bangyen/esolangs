"""Executed command and snapshot-bit bounds."""


def _constants(n: int) -> set[int]:
    """The closure of 48, 4c (0 < c < m) and the weights 2^j under _cm_plan."""
    m = min(16, 1 << (n - 2))
    weights = (1 << j for j in range(n - 2))
    todo = [k for k in (*(4 * c for c in range(1, m)), 48, *weights) if k > 2]
    seen: set[int] = set()
    while todo:
        k = todo.pop()
        if k not in seen:
            seen.add(k)
            c = (k - 2) % 4
            todo += [v for v in ((k - c) // 2, c) if v > 2]
    return seen


def execution(n: int, _: str) -> int:
    """Lines of an all-essential table with min(16, T/4) distinct cells.

    No line branches, so every line runs once: constants 4 + 2K, the decoder
    1 + 4m, a parity pad, the cells 1 + T/4 and the address 3n + 3.  K is the
    closure of 48, 4c (0 < c < m) and the weights 2^j under k -> (k - c)/2,
    c = (k - 2) mod 4, as ``_cm_plan`` splits a constant.  Both terms grow
    with the essential inputs and the distinct cells, so this is the worst.
    """
    m = min(16, 1 << (n - 2))
    return (1 << n) // 4 + 3 * n + 4 * m + 10 + 2 * len(_constants(n))


def workspace(n: int, p: str) -> int:
    """Registers by name and value, the two arrays by entry, the pointer, input.

    Constants k<v> hold v; negativeOne, z, s, t, o and the weights w_i are the
    rest.  A holds at most T/4 cells, D one entry a set bit of the m codes.
    """
    bl = int.bit_length
    lines = len(p) // 17  # every line has at least 17 characters
    lam = bl(lines)
    m = min(16, 1 << (n - 2))
    high = n - 2
    regs = sum(8 * (1 + len(str(k))) + bl(k) for k in _constants(n) | {1, 2})
    regs += 90 + 9 + 2 * (8 + lam) + 14
    regs += sum(8 * (1 + len(str(i))) for i in range(n))
    regs += (high * (high + 1) // 2 - 1 if high >= 2 else 0) + 6
    arrays = 8 + (1 << (n - 2)) * (lam + bl(4 * (m - 1))) + 8 + (2 * m + 6) * (lam + 1)
    return regs + arrays + bl(lines + 1) + bl(2 * n)
