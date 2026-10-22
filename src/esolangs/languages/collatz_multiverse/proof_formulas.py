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


def _cell_values(n: int) -> list[int]:
    """Cell value at each code 0..m-1 of the worst table.

    The m values with most set bits (ties to the larger value); codes follow
    ascending value, the lowest nonzero value taking the top code.
    """
    m = min(16, 1 << (n - 2))
    kept = sorted(range(16), key=lambda v: (v.bit_count(), v))[16 - m :]
    top = min(v for v in kept if v)
    return [*(v for v in sorted(kept) if v != top), top]


def workspace(n: int, _: str) -> int:
    """End state of the all-ones row of the worst table, per snapshot part.

    Registers: the constants closure, negativeOne, z, o, s (the last cell's
    line), t (decoder base + 4 m + 0 for code m-1, select 3) and the weights.
    Arrays: A holds every cell but the first (code 0 is a pad); D one entry per
    set bit of the m cell values.  Then ip and the input counter (2n - 1).
    """
    bl = int.bit_length
    cells, high = 1 << (n - 2), n - 2
    values = _cell_values(n)
    m = len(values)
    consts = _constants(n)
    cap_d = 2 * len(consts) + 5  # the decoder's capture line
    cap_s = cap_d + 4 * m + 2  # the cells' capture line
    lines = cells + 3 * n + 4 * m + 2 * len(consts) + 10
    regs = sum(8 * (1 + len(str(k))) + bl(k) for k in consts | {1, 2})
    regs += 90 + 9 + 14 + 16 + bl(cap_s + cells) + bl(cap_d + 4 * m)
    regs += sum(8 * (1 + len(str(i))) for i in range(n))
    regs += (high * (high + 1) // 2 - 1 if high >= 2 else 0) + 6
    a = 8 + sum(bl(cap_s + 1 + i) for i in range(1, cells))
    a += sum(bl(4 * c) for c in range(1, m)) + (cells - m) * bl(4 * (m - 1))
    d = 8 + sum(
        bl(cap_d + 1 + 4 * c + j) + 1
        for c, v in enumerate(values)
        for j in range(4)
        if v >> j & 1
    )
    return regs + a + d + bl(lines + 1) + bl(2 * n - 1)
