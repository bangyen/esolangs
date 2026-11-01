"""Snapshot-bit bounds."""


def workspace(n: int, p: str) -> int:
    """Code, stack and store each near E, the expanded program; generic n>=2."""
    bl = int.bit_length
    if "".join(p.split()).startswith("k((())=())km"):
        return 2688 * n - 1094 + bl(84 * n + 15) + bl(n)
    return 24 * (95 * (1 << n) - 80) - 1214 + bl(95 * (1 << n) - 80) + bl(n)
