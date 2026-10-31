"""Snapshot-bit bounds for the default (``swap_marker="new"``) dialect."""


def workspace(n: int, program: str) -> int:
    """Program-grid bits, the data marks at the widest coordinates, positions.

    Each ``*`` or ``-`` runs at most once and writes one mark; a pointer
    moves a cell a step from inside the box. The area fold also stays below
    15T+33n+11 commands: c>=5 and r>=3 give at most 10T+44n+3sqrt(T)+6
    from n=5; n<=4 is checked directly.
    """
    lines = program.split("\n")
    width, height = max(map(len, lines)), len(lines)
    bits = writes = 0
    for y, line in enumerate(lines):
        for x, char in enumerate(line):
            if char not in " ><^v":
                bits += 8 + max(1, x.bit_length()) + max(1, y.bit_length())
                writes += char in "*-"
    reach = max(width, height) + (15 << n) + 33 * n + 11
    coord = reach.bit_length() + 1
    return bits + writes * (8 + 2 * coord) + 4 * coord + 5 + max(1, n.bit_length())
