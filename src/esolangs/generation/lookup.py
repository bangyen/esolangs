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
