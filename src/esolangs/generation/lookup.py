"""Lookup profiles indexed by the number of set inputs."""


def symmetric_outputs(table: str, n: int) -> str | None:
    """Return outputs by popcount for a validated n-input symmetric table."""
    outputs = "".join(table[(1 << count) - 1] for count in range(n + 1))
    return (
        outputs
        if all(bit == outputs[row.bit_count()] for row, bit in enumerate(table))
        else None
    )
