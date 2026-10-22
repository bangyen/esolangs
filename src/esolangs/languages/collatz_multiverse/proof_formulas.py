"""Executed command and snapshot-bit bounds."""


def execution(n: int, _: str) -> int:
    """Lines of an all-essential table with min(16, T/4) distinct cells.

    No line branches, so every line runs once: constants 4 + 2K, the decoder
    1 + 4m, a parity pad, the cells 1 + T/4 and the address 3n + 3.  K is the
    closure of 48, 4c (0 < c < m) and the weights 2^j under k -> (k - c)/2,
    c = (k - 2) mod 4, as ``_cm_plan`` splits a constant.  Both terms grow
    with the essential inputs and the distinct cells, so this is the worst.
    """
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
    return (1 << n) // 4 + 3 * n + 4 * m + 10 + 2 * len(seen)


def workspace(n: int, p: str) -> int:
    """The stated workspace bound, evaluated for n and the program."""
    bl = int.bit_length
    return (
        -(-(1 << n) // 4) * (bl(len(p) // 17) + 6)
        + 64 * (bl(len(p) // 17) + 1)
        + (n * n + 168) * (8 * n + bl(len(p)) + 9) // 2
        + 2 * bl(len(p))
        + 115
    )
