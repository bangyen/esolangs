"""Snapshot-bit bounds."""

from esolangs.generation.packed_decoder import _sbleq_constant, read_direct_layout

bl = int.bit_length


def workspace_terms(n: int, program: str) -> dict[str, int]:
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
    if cells[:2] == [-1, 0]:
        if not any(
            cells == list(map(int, _sbleq_constant(n, bit, direct=True).split()))
            for bit in "01"
        ):
            raise ValueError("invalid constant reader")
        return {"B": image, "P": size, "G": 0, "C": 1, "M": 0, "I": 0, "A": 0, "D": 0}
    regions = read_direct_layout(cells, n)
    if (
        cells[regions.chunk_load] != regions.chunks
        or cells[regions.load_increment + 1] != regions.chunk_load
        or cells[regions.reader : regions.reader + 3] != [-1, regions.cells["TMP"], 0]
    ):
        raise ValueError(
            "packed reader or self-modifying load points outside its region"
        )
    m = cells[regions.cells["N"]]
    first = regions.chunks + 1
    return {
        "B": image,
        "P": regions.last_instruction,
        "G": 0,
        "C": 0,
        "M": m,
        "I": int(regions.reader + 3 == regions.decoder),
        "A": max((2 * bl(o) + bl(m - o) for o in range(1, m)), default=0),
        "D": bl(first + 2**m // m - 1) - bl(first),
    }
