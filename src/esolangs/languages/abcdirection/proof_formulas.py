"""Executed command bounds the ledger notation cannot state."""


# Row 0 of AND (every input essential, T - 1 zeros) maximises every term at
# once: the write row and its zero detours, the band's zero bits, and the read
# block's d drops of 6 + rows cells.  Reached at n = 1..13; exhaustive to n = 3.
def execution(n: int, _: str) -> int:
    """5T + 97n + 150 + d + 6⌈d/3⌉ + max(0, 8n + 35 - T), d = (2n + 4) mod 5."""
    t = 1 << n
    d = (2 * n + 4) % 5
    return 5 * t + 97 * n + 150 + d + 6 * -(-d // 3) + max(0, 8 * n + 35 - t)
