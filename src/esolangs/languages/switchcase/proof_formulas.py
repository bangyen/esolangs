"""Execution and snapshot bounds for buffered residual dispatch."""


def diagram_cap(n: int) -> int:
    """A cap on distinct internal residuals, summed by depth."""
    # Avoid constructing the double-exponential term when the prefix cap wins.
    return sum(
        1 << depth if depth <= (1 << (n - depth)) else 1 << (1 << (n - depth))
        for depth in range(n)
    )


def execution(n: int, _p: str) -> int:
    """Every read, at most n dispatches, and a printing leaf; parity attains it."""
    return 6 * n + 8


def workspace(n: int, _p: str) -> int:
    """An upper bound including buffered names, character values and IO progress."""
    name = len(f"x{n - 1}")
    return (
        31
        + n * (8 * name + 6)
        + (n + 1).bit_length()
        + (n + diagram_cap(n) + 4).bit_length()
        + n.bit_length()
    )
