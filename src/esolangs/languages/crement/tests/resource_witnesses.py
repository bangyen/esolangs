"""Witnesses for Crement's exact resource bounds."""


def _unequal_pairs(n: int) -> str:
    """Ordered unequal leaf pairs (x, x + d), d from V/2: every level distinct."""
    if n <= 10:
        values = sorted(range(16), key=lambda v: v >> 2 == v & 3)
        cells = []
        for i in range(1 << (n - 3)):
            cells += [values[i % 16], values[(i + 8 + i // 16) % 16]]
        return "".join(f"{v:04b}" for v in cells)
    width = 8 if n <= 19 else 16
    size = 1 << width
    out = []
    for j in range(1 << (n - 4 if width == 8 else n - 5)):
        x, t = j % size, j // size
        d = (t + size // 2 - 1) % (size - 1) + 1
        out += [x, (x + d) % size]
    return "".join(f"{v:0{width}b}" for v in out)


def resource_tables(n: int) -> tuple[str, ...]:
    """Exercise the largest source and the generic halting path."""
    if n < 2:
        return ()
    # Implication reaches the two-input source maximum.
    return _unequal_pairs(n) if n >= 3 else "1101", "01" + "0" * ((1 << n) - 2)
