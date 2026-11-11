"""Named witnesses for the generated resource bounds."""

from tests.support.witness_tables import second_last_zero


def resource_tables(n: int) -> tuple[str, ...]:
    """Return additional cases in the order used for resource measurement."""
    tables: tuple[str, ...] = ()
    tables += (second_last_zero(n),)
    return tables
