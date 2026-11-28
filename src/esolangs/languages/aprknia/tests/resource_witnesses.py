"""Named witnesses for Aprknia resource maxima."""

from tests.support.witness_tables import parity


def resource_tables(n: int) -> tuple[str, ...]:
    """Include both parities to invert the final pair on the all-one row."""
    return (parity(n).translate(str.maketrans("01", "10")),)
