"""Executed command and snapshot-bit bounds the ledger notation cannot state."""


def execution(n: int, program: str) -> int:
    """Constants drain at most 49; otherwise tree to n=6, then T-1 ones."""
    if program.startswith(" }}" + "," * n + "}-#/)"):
        # Ten steps a ring pass, with the final reflection skipped; any heading.
        return n + 491 + program.split("\n", 1)[0].endswith("+x")
    if n < 7:
        return (1 << n) + 296 * n + 682
    return 18 * (1 << n) + 56 * n + 4


def workspace(n: int, _: str) -> int:
    """Tree to n = 6: n + 1 input cells; then 3T + 1 cells, one-hot."""
    if n < 7:
        return 8 * n + 26
    return 12 * (1 << n) + 2 * n + 11 + 2 * n.bit_length()
