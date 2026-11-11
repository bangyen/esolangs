"""Named witnesses for the generated resource bounds."""

from tests.proofs._witnesses import _bitdeque_tokens, _bitdeque_worst


def _named_witnesses(n: int) -> tuple[str, ...]:
    """Return additional truth tables for the resource ledger."""
    return (_bitdeque_worst(n), _bitdeque_tokens(n)) if n >= 3 else ()


def resource_tables(n: int) -> tuple[str, ...]:
    """Return additional cases in the order used for resource measurement."""
    width = 1 << n
    tables: tuple[str, ...] = ()
    tables += ("10" + "01" * (width // 2 - 1),)
    tables += _named_witnesses(n)
    return tables
