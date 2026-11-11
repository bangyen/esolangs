"""Named witnesses for the generated resource bounds."""

from tests.support.witness_tables import second_last_zero


def _named_witnesses(n: int) -> tuple[str, ...]:
    """Return additional truth tables for the resource ledger."""
    return ("10" + "1" * ((1 << n) - 2),)


def resource_tables(n: int) -> tuple[str, ...]:
    """Return additional cases in the order used for resource measurement."""
    tables: tuple[str, ...] = ()
    tables += (second_last_zero(n),)
    tables += _named_witnesses(n)
    return tables
