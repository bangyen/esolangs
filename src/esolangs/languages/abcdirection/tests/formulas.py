"""ABCDirection's emitted cells: five rows of the AND table's width."""


def _cells(n: int, _: str) -> int:
    """10T + 85n + 40 + 10⌈d/3⌉ + 5max(0, 8n+35-T), d = (2n + 4) mod 5."""
    t = 1 << n
    d = (2 * n + 4) % 5
    return 10 * t + 85 * n + 40 + 10 * -(-d // 3) + 5 * max(0, 8 * n + 35 - t)


FORMULAS = {"scaling": (_cells, True, (3, 4, 5, 6, 7))}
