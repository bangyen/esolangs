"""Named witnesses for the generated resource bounds."""

from tests.proofs._witnesses import _asj_packed_worst


def _named_witnesses(n: int) -> tuple[str, ...]:
    """Return additional truth tables for the resource ledger."""
    return (_asj_packed_worst(n),) if n >= 6 else ()


def resource_tables(n: int) -> tuple[str, ...]:
    """Return additional cases in the order used for resource measurement."""
    width = 1 << n
    tables: tuple[str, ...] = ()
    # The packed decoder's worst now that the tree takes the lone zero:
    # ones but rows 8 mod 9 and the last, reaching it at n = 6.
    tables += (
        "".join("0" if r % 9 == 8 or r == width - 1 else "1" for r in range(width)),
    )
    tables += _named_witnesses(n)
    return tables
