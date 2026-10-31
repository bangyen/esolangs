"""Flowchart's emitted cells: two rows of the spine's length."""


def _cells(n: int, _: str) -> int:
    """20T + 16 * 2^floor(n/2) + 12 * 2^ceil(n/2) + 72n + 14 = 2 * row.

    A row is 4 a set (R = T - 1 runs), 6 a push, 4 a ``[ >`` and 4 a cursor
    rail (2^floor(n/2) - 1 each: deques of 2^ceil(n/2) entries), 12 a pop
    pair (2^(ceil(n/2) - 1) - 1), 4 a ``/ /`` (8n - 7) and a switch (n).
    """
    k = (n + 1) // 2
    return 20 * (1 << n) + 16 * (1 << (n - k)) + 12 * (1 << k) + 72 * n + 14


FORMULAS = {"scaling": (_cells, True, (2, 3, 4, 5, 6, 7, 8))}
