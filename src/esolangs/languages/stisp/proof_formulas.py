"""Snapshot-bit bounds."""


def workspace(n: int, _: str) -> int:
    """16 bits a frame, 8 a digit of the root atom's id, at most D + 1."""
    nodes = sum(min(1 << k, (1 << (1 << (n - k))) - 2) for k in range(n))
    return 16 * n + 8 * len(str(nodes + 1))
