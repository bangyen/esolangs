"""Executed command and snapshot-bit bounds."""

#: The indexed decoder's walk: its entry, prefix decoder and descent, and
#: shared body (+ 24 per class past the first), at the most classes the
#: prefix can label -- min(10, 2^(n-6)).  Defined at n = 8..12 only.
_INDEXED = {8: 265, 9: 371, 10: 435, 11: 539, 12: 561}


def _parity_chain(n: int, program: str) -> tuple[int, int] | None:
    """Recognize the actual stencil and any existing leading-discard column."""
    lines = program.split("\n")
    if len(lines) < 12:
        return None
    core = (len(lines[-12]) + 4) // 4
    if not 2 <= core <= n or lines[-12] != "'>'>" * (core - 2) + "'>'@":
        return None
    lead = n - core
    if not lead:
        return (core, 0) if len(lines) == 12 else None
    expected = "'" + ("$9" + "~" * 8) * (lead // 8)
    expected += f"${lead % 8 + 2}" + "~" * (lead % 8) + "0"
    return (core, len(expected)) if lines[:-12] == list(expected) else None


def execution(n: int, program: str) -> int:
    """The stated execution bound, evaluated for n and the program.

    An unshared tree walks at most 128 + 46*2^((n-6)/2) (even n) or
    128 + 64*2^((n-7)/2) (odd).  A shared leaf adds one travel along an
    axis of the grid, 28*2^((n-6)/2) - 3 or 28*2^((n-7)/2) - 3 cells.
    """
    if chain := _parity_chain(n, program):
        core, prefix = chain
        return 48 * core - 48 + prefix
    even = n % 2 == 0
    up = (46 if even else 64) + 28
    lane = 128 - 3 + up * 2 ** ((n - 6) // 2 if even else (n - 7) // 2)
    worst: int = max(lane, _INDEXED.get(n, 0))
    return worst


def _dig(n: int, p: str) -> int:
    """Byte grid, coordinates, two counters and the halt latch."""
    bl = int.bit_length
    lines = p.split("\n")
    rows, cols = len(lines), max(map(len, lines))
    return 8 * rows * cols + bl(rows - 1) + bl(cols - 1) + bl(2 * n - 1) + bl(n) + 11


def workspace(n: int, p: str) -> int:
    """The v2 bound, including its one-bit native halt latch."""
    if chain := _parity_chain(n, p):
        core, _ = chain
        # The off-path XNOR operand adds a column, never a visited coordinate.
        lines = p.split("\n")
        area = len(lines) * max(map(len, lines))
        bl = int.bit_length
        mole = 2 if core == 2 and max(map(len, lines)) == 5 else 3
        lead = n - core
        if lead:
            mole = max(mole, (9 if lead >= 8 else lead + 2).bit_length())
        return (
            8 * area
            + bl(len(lines) - 1)
            + bl(4 * core - 5)
            + bl(2 * n - 1)
            + bl(n)
            + 7
            + mole
        )
    # This capture opcode occurs only in indexed bodies. Class<=9, stride<=8:
    # stored offset<=72, row count<=81. Both num and mole need at most7 bits,
    # versus four in primitive leaves; every stored cell still fits one byte.
    indexed = any(";*$2" in line for line in p.split("\n"))
    return _dig(n, p) + (6 if indexed else 0)
