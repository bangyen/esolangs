"""Snapshot-bit bounds."""

bl = int.bit_length


def workspace_terms(_: int, program: str) -> dict[str, int]:
    """Measure the memory image and the active reader/decoder layout."""
    cells = [int(word) for word in program.split()]
    image = sum(bl(v) + (v == 0) + (v < 0) for v in cells)
    size = len(cells)
    if cells[0] == 0:
        return {
            "B": image,
            "P": size - 3,
            "G": 1,
            "C": 0,
            "M": 0,
            "I": 0,
            "A": 0,
            "D": 0,
        }
    data = next(
        (i for i in range(size - 5) if cells[i : i + 5] == [0, 1, -1, -48, 48]),
        None,
    )
    if data is None:
        return {"B": image, "P": size, "G": 0, "C": 1, "M": 0, "I": 0, "A": 0, "D": 0}
    m = cells[data + 5]
    last = max(i for i in range(0, data, 3) if cells[i] == -1)
    first = data + 18
    return {
        "B": image,
        "P": data - 3,
        "G": 0,
        "C": 0,
        "M": m,
        "I": int(cells[last + 3] != data + 4),
        "A": max((2 * bl(o) + bl(m - o) for o in range(1, m)), default=0),
        "D": bl(first + 2**m // m - 1) - bl(first),
    }
