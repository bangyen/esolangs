"""Executed command bounds."""


def execution(n: int, _: str) -> int:
    r"""A one-row header: ``0``, ``&\2*+`` an input, 27 index commands.

    An ignored input reads as ``&$``, so ``k`` essential inputs run
    ``28 + 2n + 3k``; the worst table has every input essential.
    """
    if n <= 7:
        return 5 * n + 28
    return 5 * n + 67


def workspace(n: int, _: str) -> int:
    """Peak written bits: the cursor, the stack, the done flag, the input cursor.

    Plain grid (n <= 7): only the column moves, to the header's end 5n + 27,
    and the stack peaks at [i, i, 8, 9, 1].  Packed (n >= 8): the folded
    header also writes row, dx, dy and column 79, and the stack peaks at
    [2^u, q, q, 8, 9, 1], q = i // 6, u = i % 6 = 5.
    """
    bl = int.bit_length
    cursor = 11 if n > 7 else bl(5 * n + 28)
    stack = 2 * n + (11 if n > 7 else 9)
    return cursor + stack + 1 + bl(2 * n - 1)
