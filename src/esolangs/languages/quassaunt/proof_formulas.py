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
    """Frames and globals from the definition count, stack at two child bodies."""
    text = str(p)
    defs = text.count(" %%Empty %%Makecontain %%Store")
    name = max(len(str(defs + 1)), 1 + len(str(n)))
    bl = int.bit_length
    return 16 * len(text) - 328 * defs + 2483 + 32 * name + bl(5 * defs + 6) + bl(n)
