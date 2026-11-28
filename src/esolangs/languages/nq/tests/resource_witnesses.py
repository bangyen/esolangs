"""Named witnesses for NQ resource bounds."""

from tests.support.witness_tables import parity


def resource_tables(n: int) -> tuple[str, ...]:
    """Fold one leaf pair, or drive the final instruction with a written flag."""
    table = parity(n)
    size = "1" + table[1:]
    return (size, "1110" + table[4:]) if 2 <= n <= 6 else (size,)
