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


def execution_terms(n: int, program: str) -> dict[str, int]:
    """Identify parity chains and the indexed decoder's finite price."""
    chain = _parity_chain(n, program)
    core, prefix = chain or (0, 0)
    return {
        "C": int(chain is not None),
        "R": core,
        "P": prefix,
        "I": _INDEXED.get(n, 0),
    }


def workspace_terms(n: int, program: str) -> dict[str, int]:
    """Measure the byte grid, visited columns and auxiliary state."""
    lines = program.split("\n")
    rows, cols = len(lines), max(map(len, lines))
    if chain := _parity_chain(n, program):
        core, _ = chain
        # The off-path XNOR operand adds a column, never a visited coordinate.
        mole = 2 if core == 2 and cols == 5 else 3
        lead = n - core
        if lead:
            mole = max(mole, (9 if lead >= 8 else lead + 2).bit_length())
        return {"R": rows, "W": cols, "X": 4 * core - 5, "M": 7 + mole}
    # Indexed capture stores offsets <=72 and counts <=81, costing three
    # extra bits per register. The stored cell still fits one byte.
    indexed = any(";*$2" in line for line in lines)
    return {"R": rows, "W": cols, "X": cols - 1, "M": 11 + 6 * indexed}
