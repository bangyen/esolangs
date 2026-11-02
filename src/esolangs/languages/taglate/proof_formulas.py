"""Command and written-state ceilings for printable nibble leaves."""


def execution(n: int, _: str) -> int:
    """Static command text plus fourteen extra four-command parity iterations."""
    return 5 * (1 << n) // 2 + 12 * n * n + 11 * n + 63


def workspace(n: int, p: str) -> int:
    """At most T/2+7n+4 six-bit cells, plus cursor and input progress."""
    return 3 * (1 << n) + 42 * n + 24 + n.bit_length() + len(p).bit_length()
