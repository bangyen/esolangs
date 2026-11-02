"""Exact worst command and written-snapshot bounds for arithmetic tails."""


def execution(n: int, _: str) -> int:
    """Four commands per branch level, then a twelve-command arithmetic tail."""
    return 7 if n == 1 else 4 * n + 4


def workspace(n: int, _: str) -> int:
    """Two retained functions per level, a 17-bit constant tail, and one frame.

    A maximal mixed OR/XOR tree has length 9T/2-6. Its rightmost offsets
    need n+2 bits through the third branch, n+3 after that. The root's zero
    offset costs one bit; each function's tag costs sixteen. The terminal
    constant frame needs three command bits; its stack is two bits larger
    than the four-command-bit arithmetic tail. Small offset boundaries are explicit.
    """
    if n <= 4:
        return {2: 24, 3: 64, 4: 112}[n]
    return 2 * n * n + 34 * n - 61 + (2 * n - 1).bit_length()
