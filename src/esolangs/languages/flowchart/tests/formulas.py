"""Flowchart's emitted cells: two rows of the spine's length."""


def _cells(n: int, _: str) -> int:
    """28T + 72n + 38 = 2 * (4R + 10T + 36n + 23) at R = T - 1 runs.

    Spine columns: 4 a set (R), 6 a push, 4 a ``[ >`` (T/2 - 1) and 4 a
    junction rail pair (2T - 4), 4 a ``/ /`` (8n - 7) and a switch (n).
    """
    return 28 * (1 << n) + 72 * n + 38


FORMULAS = {"scaling": (_cells, True, (2, 3, 4, 5, 6, 7, 8))}
