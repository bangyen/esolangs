"""Project constants to one row while retaining their old balanced shape."""

from esolangs.tools.helpers import essential_inputs
from esolangs.tools.wrap import balance_program, balance_score


def projected_inputs(table: str, n: int, *, keep_constant_input: bool) -> list[int]:
    """Return essential inputs, optionally retaining the legacy constant index."""
    used = essential_inputs(table, n)
    return used or ([0] if keep_constant_input else [])


def balanced_projection(default: str, legacy: str, language_id: str) -> str:
    """Return the better wrapped shape, retaining the previous constant layout."""
    if default == legacy:
        return balance_program(default, language_id)
    return min(
        balance_program(default, language_id),
        balance_program(legacy, language_id),
        key=balance_score,
    )
