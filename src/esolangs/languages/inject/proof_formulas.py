"""Snapshot-bit bounds."""


def _regex_chars(n: int) -> int:
    """Sum the counted-or-literal regex widths across the halving levels."""
    if n <= 3:
        return (1 << n) - 1
    # For exponents 3..30, floor(i log10(2)) = floor(3i/10).
    # The quotient's full decades contribute 15q(q-1)+9q; the last
    # decade adds 3q per term and crosses the local widths at i=4 and 7.
    compact = min(n, 31)
    q, r = divmod(compact, 10)
    digits = 15 * q * (q - 1) + 9 * q + 3 * q * r + max(0, r - 4) + max(0, r - 7)
    # Above exponent 30 each term uses only full 2^31 chunks of width 13.
    return 4 * compact - 5 + digits + 13 * ((1 << max(0, n - 31)) - 1)


def _constant(program: str) -> bool:
    return program.startswith(("readto a\nreadto a\n", "readto a\nsend z\n"))


def execution_terms(_: int, program: str) -> dict[str, int]:
    """Mark the literal-tail construction."""
    return {"C": int(_constant(program))}


def scaling_terms(n: int, _: str) -> dict[str, int]:
    """Expose the same halving widths used by the workspace proof."""
    return {"R": _regex_chars(n)}


def workspace_terms(n: int, program: str) -> dict[str, int]:
    """Combine the literal-tail marker and shared halving-width count."""
    return {"C": int(_constant(program)), "R": _regex_chars(n)}
