"""Executed command and snapshot-bit bounds the ledger notation cannot state."""


def execution(n: int, _: str) -> int:
    """Tree to n = 6: every node distinct, all-ones row; then T - 1 ones."""
    if n < 7:
        return (1 << n) + 296 * n + 682
    return 18 * (1 << n) + 56 * n + 4


def workspace(n: int, _: str) -> int:
    """Tree to n = 6: n + 1 input cells; then 3T + 1 cells, one-hot."""
    if n < 7:
        return 8 * n + 26
    return 12 * (1 << n) + 2 * n + 11 + 2 * n.bit_length()
