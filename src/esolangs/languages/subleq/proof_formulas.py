"""Snapshot-bit bounds."""


def workspace(n: int, p: str) -> int:
    """Image bits of the program's cells, 6n + 5 rewritten, pc and cursor."""
    bl = int.bit_length
    cells = [int(word) for word in str(p).split()]
    image = sum(bl(abs(v)) + (v == 0) + (v < 0) for v in cells)
    return image + 6 * n + 5 + bl(len(cells)) + bl(n)
