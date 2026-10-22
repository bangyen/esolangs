"""Executed word and snapshot-bit bounds."""


def execution(n: int, _: str) -> int:
    """5N + 21n + 9, N the most distinct subtables a diagram holds.

    A level of height h has 2^(n-h) positions and 2^2^h subtables; the
    branch avoids building 2^2^h when it is the larger.
    """
    nodes = sum(
        1 << (1 << h) if 1 << h <= n - h else 1 << (n - h) for h in range(n + 1)
    )
    return 5 * nodes + 21 * n + 9


def workspace(n: int, p: str) -> int:
    """Frames, globals, locals and input exact; the stack at its heaviest ``If``.

    The frame holds the program's words once (8L - 40D - 47 + bl(5D+6): the
    pc reaches the last of 5D + 7 words); the globals every definition once
    (8L - 288D - 8r - 288, r the root name's length: the start is not
    stored); one local ``d`` is 17; the input count is bl(n).  An ``If``
    stacks its two child bodies, 174 characters and their two names each,
    then ``{2, c}`` and ``1``: 2808 + 32w at most, reached only with a
    chain above it, whose local rides the same row.
    """
    text = str(p)
    defs = text.count(" %%Empty %%Makecontain %%Store")
    root = len(text.split()[-5]) - 4
    name = max(len(str(defs + 1)), 1 + len(str(n)))
    bl = int.bit_length
    return (
        16 * len(text)
        - 328 * defs
        - 8 * root
        + 2490
        + 32 * name
        + bl(5 * defs + 6)
        + bl(n)
    )
