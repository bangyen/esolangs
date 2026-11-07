"""Boolean row boundaries, counts and popcount lookup profiles."""


def change_points(table: str) -> list[int]:
    """Return ascending row boundaries whose adjacent outputs differ."""
    return [row for row in range(1, len(table)) if table[row] != table[row - 1]]


def prefix_counts(table: str, value: str) -> list[int]:
    """Return matching-entry counts for every prefix, including the empty one."""
    counts = [0]
    for entry in table:
        counts.append(counts[-1] + (entry == value))
    return counts


def symmetric_outputs(table: str, n: int) -> str | None:
    """Return outputs by popcount for a validated n-input symmetric table."""
    outputs = "".join(table[(1 << count) - 1] for count in range(n + 1))
    return (
        outputs
        if all(bit == outputs[row.bit_count()] for row, bit in enumerate(table))
        else None
    )


def packed_cells(
    table: str, bits: int, *, offset: int = 0, complement: bool = False
) -> str:
    """Pack consecutive bits little-endian; the last cell uses only its entries."""
    if bits <= 0:
        raise ValueError("bits must be positive")
    if complement:
        table = table.translate(str.maketrans("01", "10"))
    return "".join(
        chr(offset + int(table[start : start + bits][::-1], 2))
        for start in range(0, len(table), bits)
    )


def exceptional_row(table: str) -> tuple[int, bool] | None:
    """Return the unique one or zero row, preferring a one, and whether inverted."""
    if table.count("1") == 1:
        return table.index("1"), False
    if table.count("0") == 1:
        return table.index("0"), True
    return None


def majority_bias(table: str, n: int) -> bool | None:
    """Return the inversion of strict majority, or None for another table."""
    invert = table[0] == "1"
    return (
        invert
        if all(
            (bit == "1") == ((row.bit_count() > n // 2) ^ invert)
            for row, bit in enumerate(table)
        )
        else None
    )


def near_unanimity(table: str, n: int) -> bool:
    """Whether all but at most one input must be one, or its negation."""
    bit = "1" if table[0] == "0" else "0"
    return (
        n >= 2
        and table.count(bit) == n + 1
        and table[-1] == bit
        and all(table[len(table) - 1 - (1 << i)] == bit for i in range(n))
    )
