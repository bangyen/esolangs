"""Constant paths and the unchanged Church-pair envelopes."""


def execution(n: int, program: str) -> int:
    """Four rewrites per input for constants; otherwise the pair-tree bound."""
    if program.startswith("A0"):
        return 4 * n + 3
    return 35 * n + 45


def workspace(n: int, program: str) -> int:
    """Constant spine characters, pending bit, output flags and input cursor."""
    if program.startswith("A0"):
        return 32 * n + 27 + n.bit_length()
    t = 1 << n
    return max(88 * t + 232 * n + 235, 132 * t + 24 * n - 53) + n.bit_length()
