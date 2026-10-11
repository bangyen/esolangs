"""Bounds for inline expressions and shared, ordered expression frames."""

from math import ceil


def execution(n: int, program: str) -> int:
    """Initialize K definitions; a selected level enters at most three split frames."""
    definitions = program.count("=") - 1
    return (
        max(21, ceil(65 * n / 2) - 21) + definitions + 2 * min(definitions, 3 * n + 1)
    )


def workspace(n: int, program: str) -> int:
    """Count serials, typed values and function metadata in the snapshot."""
    bl = int.bit_length
    if program.count("=") == 1:
        f = 2 * n + 7
        v = sum(bl(s) + bl(s + 1) + bl(s + 5) for s in range(2 * n + 15, 9 * n - 5, 7))
        w = bl(2 * n - 1) + bl(2 * n + 3) + bl(2 * n + 13)
        w += bl(f) + 2 * bl(f + 1) + bl(f + 2) + bl(f + 4)
        return 179 * n + 400 + v + w
    # A selected cofactor contributes <=3 split frames and one NOT frame.
    # Splitting moves pending expression nodes between frames; it duplicates none.
    frames, pending = 4 * n + 3, 6 * n + 5
    serial_bits, name_bits = bl(2 * len(program) + 2), bl(len(program))
    # A frame's function key, statement, value, return flag and optional x local.
    frame_bits = 198 + 8 * name_bits + 3 * serial_bits
    # A pending node has its serial and at most two tagged integer operands.
    node_bits = serial_bits + 114
    return (
        frames * frame_bits + pending * node_bits + 65 * n + name_bits + bl(2 * n - 1)
    )


FORMULAS = {
    "execution": (execution, False, (3, 4, 5, 6, 8)),
    "workspace": (workspace, False, (3, 4, 5, 6, 8)),
}
