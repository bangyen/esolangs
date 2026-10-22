"""Clockwise's emitted cells: the flat build's six rows by its width."""


def _cells(n: int, _: str) -> int:
    """30T + 48n + 24: six rows of 5T + 8n + 4 columns, every input essential.

    Width 5 * 2^k + 7(n - t) + k + 4 for k essential inputs, t trailing; the
    stacked build only wins where it is smaller.
    """
    return 30 * (1 << n) + 48 * n + 24


FORMULAS = {"scaling": (_cells, True, (2, 3, 4, 5, 6, 7, 8))}
