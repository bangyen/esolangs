"""Named witnesses for NQ source size."""

from tests.support.witness_tables import parity


def resource_tables(n: int) -> tuple[str, ...]:
    """Flip the first parity bit to fold exactly one leaf pair."""
    return ("1" + parity(n)[1:],)
