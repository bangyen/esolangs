"""Named witnesses for the generated resource bounds."""

from tests.proofs._witnesses import _underload_worst


def resource_tables(n: int) -> tuple[str, ...]:
    """Return additional truth tables for the resource ledger."""
    size = (
        "10",
        "1001",
        "10010110",
        "1001011001101001",
        "11111100110000111110011100111100",
    )
    extra = (size[n - 1],) if 1 <= n <= len(size) else ()
    previous = (_underload_worst(n),) if n >= 3 else ()
    return (*previous, *extra)
