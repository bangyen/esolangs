"""Named witnesses for the generated resource bounds."""

from tests.proofs._witness_builders import _brainif_worst


def _longest_path(n: int) -> str:
    """Make each lower residual on the all-one row take both gotos."""
    if n <= 3:
        return ("10", "1110", "10111010")[n - 1]
    a, b, c, d = "00", "01", "10", "11"
    for _ in range(n - 3):
        a, b, c, d = a + b, c + d, a + c, c + c
    return a + b + c + d


def resource_tables(n: int) -> tuple[str, ...]:
    """Return additional truth tables for the resource ledger."""
    size = ("", "10", "1110", "11100100", "1110010011010101")
    extra = (size[n],) if n < len(size) else ()
    return (_brainif_worst(n) if n >= 2 else "11", _longest_path(n), *extra)
