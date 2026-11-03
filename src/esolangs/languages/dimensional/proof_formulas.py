"""Snapshot-bit bounds."""


def workspace(n: int, _: str) -> int:
    """T+1 painted cells; omitting the initial zero doubling shortens ip by 16."""
    bl = int.bit_length
    return (
        sum(map(bl, range((1 << n) + 1)))
        + 5 * ((1 << n) + 1)
        + n * (n - 1) // 2
        + 4 * n
        + 6
        + bl(2 * (1 << n) + 20 * n + 40)
        + bl(2 * n - 1)
    )
