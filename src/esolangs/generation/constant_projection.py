"""Project constants to one row while retaining their old balanced shape."""

from collections.abc import Callable

from esolangs.generation.helpers import (
    TEMPLATE_CHAR,
    _validate_truth_table,
    essential_inputs,
    mark_runs,
    unmark,
)
from esolangs.generation.wrap import balance_program, balance_score


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


def balance_legacy_walk(
    table: str,
    default: str,
    language_id: str,
    pair: tuple[str, str],
    legacy_program: Callable[[str], str],
) -> str:
    """Keep the old constant walk when its wrapped shape balances better.

    Shared by the generators with a ``keep_constant_walk`` legacy path:
    the legacy program is built by ``legacy_program(table)``.
    """
    n = _validate_truth_table(table)
    pairs = (pair,) * n
    marked = mark_runs(default, TEMPLATE_CHAR, pairs)
    if len(set(table)) > 1:
        return unmark(balance_program(marked, language_id), TEMPLATE_CHAR, n)
    legacy = mark_runs(legacy_program(table), TEMPLATE_CHAR, pairs)
    return unmark(balanced_projection(marked, legacy, language_id), TEMPLATE_CHAR, n)
