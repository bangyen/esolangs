"""Executed command bounds the ledger notation cannot state."""


# Row 0 of AND (every input essential, T - 1 zeros) maximises every term at
# once: 4n+1 teeth (seven fixed commands each), the write row's zero
# detours, the band's zero bits and d read-block drops (6 + rows cells).
# Reached at n = 1..13; exhaustive to n = 3.
def execution(n: int, _: str) -> int:
    """5T + 69n + 157 + d + 6⌈d/3⌉ + max(0, 8n + 35 - T), d = (n + 3) mod 5."""
    t = 1 << n
    d = (n + 3) % 5
    return 5 * t + 69 * n + 157 + d + 6 * -(-d // 3) + max(0, 8 * n + 35 - t)
