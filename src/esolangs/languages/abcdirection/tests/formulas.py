"""ABCDirection's emitted cells: five rows of the AND table's width."""


def _cells(n: int, _: str) -> int:
    """10T + 45n + 50 + 10⌈d/3⌉ + 5max(0, 8n+35-T), d = (n + 3) mod 5."""
    t = 1 << n
    d = (n + 3) % 5
    return 10 * t + 45 * n + 50 + 10 * -(-d // 3) + 5 * max(0, 8 * n + 35 - t)
