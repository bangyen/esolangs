"""Snapshot-bit bounds."""


def workspace(n: int, _: str) -> int:
    """Code, stack and store each near E, the expanded program, at most 95T - 80."""
    bl = int.bit_length
    return 24 * (95 * (1 << n) - 80) - 1214 + bl(95 * (1 << n) - 80) + bl(n)
