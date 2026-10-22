"""Snapshot-bit bounds."""

bl = int.bit_length


def workspace(n: int, p: str) -> int:
    """Exact worst bits by route: image, rewritten cells, pc and cursor.

    Tree: every input cell and the byte cell are rewritten (6n + 5).  Constant:
    the first cell takes a byte (4).  Packed decoder, m inputs essential,
    chunks of m: the worst of the read (an input byte beside the index and
    its carry), the chunk advance, and the first halving of a top-set chunk
    (3m - 5 + max_o(2bl(o) + bl(m-o)) - 2 - bl(m), o the row's offset),
    plus 5 if the last read input is ignored, plus a bit if the chunk
    pointer reaches a longer address.
    """
    cells = [int(word) for word in str(p).split()]
    image = sum(bl(abs(v)) + (v == 0) + (v < 0) for v in cells)
    size = len(cells)
    if cells[0] == 0:
        return image + 6 * n + 5 + bl(size - 3) + bl(n)
    data = next(
        (i for i in range(size - 5) if cells[i : i + 5] == [0, 1, -1, -48, 48]),
        None,
    )
    if data is None:
        return image + 4 + bl(size) + bl(n)
    m = cells[data + 5]
    last = max(i for i in range(0, data, 3) if cells[i] == -1)
    ignored = cells[last + 3] != data + 4
    first = data + 18
    pointer = bl(first + 2**m // m - 1) - bl(first)
    copy = max((2 * bl(o) + bl(m - o) for o in range(1, m)), default=0)
    halving = 3 * m - 7 - bl(m) + copy
    advance = bl(2**m - 1 - m) - 1 + 2 * bl(m) - 1
    rows = (
        max(2 * m - 2, m + 4),
        (advance if m > 1 else 1) + 5 * ignored,
        (halving + pointer if m > 1 else 0) + 5 * ignored,
    )
    return image + max(rows) + bl(data - 3) + bl(n)
