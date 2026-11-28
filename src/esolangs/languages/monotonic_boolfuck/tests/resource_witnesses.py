"""Named witnesses for Monotonic Boolfuck workspace."""

from tests.support.witness_tables import parity


def resource_tables(n: int) -> tuple[str, ...]:
    """Provide the inverted final pair on the root-zero witness row."""
    return (parity(n).translate(str.maketrans("01", "10")),)
