"""Named witnesses for Chicken resource bounds."""


def _largest_source(n: int) -> str:
    """Set the largest affordable weight while keeping all inputs essential."""
    width = 1 << n
    ones = width // 2 + 9 if n == 6 else min(width - 1, width // 2 + 8)
    rows = ["0"] * width
    for bit in range(n):
        rows[1 << bit] = "1"
    remaining = ones - n
    for row in range(1, width):
        if not remaining:
            break
        if rows[row] == "0":
            rows[row] = "1"
            remaining -= 1
    return "".join(rows)


def resource_tables(n: int) -> tuple[str, ...]:
    """Keep every variable essential and maximize nonconstant imbalance."""
    return ("0" + "1" * ((1 << n) - 1), _largest_source(n))
