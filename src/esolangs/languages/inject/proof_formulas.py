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


def _inject(n: int, _: str) -> int:
    """The program text after the n reads, its label spans and cursor."""
    bl = int.bit_length
    # Regex spelling removes 2(T-1-R) characters from the written program:
    # the old 24T+512n+168 tape term loses eight bits per character.
    # Spans after the n reads: the four halving delimiters per input at odd
    # lines n+1.., then t, z, o and the n input blocks, all after the code.
    spans = sum(bl(n + 1 + 2 * j) for j in range(4 * n))
    spans += sum(bl(9 * n + k) for k in (1, 3, 4, 6, 7, 9))
    spans += sum(bl(9 * n + 10 + 3 * i) + bl(9 * n + 12 + 3 * i) for i in range(n))
    return (
        8 * (1 << n)
        + 512 * n
        + 184
        + 16 * _regex_chars(n)
        + bl(12 * n + 10)
        + bl(2 * n)
        + bl(n)
        + spans
    )


def workspace(n: int, p: str) -> int:
    """The stated workspace bound, evaluated for n and the program."""
    if _constant(p):
        bl = int.bit_length
        spans = sum(bl(n + k) for k in (1, 3, 4, 6))
        return 64 * n + 144 + bl(n + 7) + bl(2 * n) + bl(n) + spans
    return _inject(n, p)


def _constant(program: str) -> bool:
    return program.startswith(("readto a\nreadto a\n", "readto a\nsend z\n"))


def execution_terms(_: int, program: str) -> dict[str, int]:
    """Mark the literal-tail construction."""
    return {"C": int(_constant(program))}


def scaling_terms(n: int, _: str) -> dict[str, int]:
    """Expose the same halving widths used by the workspace proof."""
    return {"R": _regex_chars(n)}
