"""Snapshot-bit bounds."""


def _regex_chars(n: int) -> int:
    """Sum the n counted-or-literal regex widths, one per halving."""
    total = 0
    chunk = 1 << 31
    for i in range(n):
        full, tail = divmod(1 << i, chunk)
        total += full * (3 + len(str(chunk))) + min(tail, 3 + len(str(tail)))
    return total


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
    return _inject(n, p)
