"""The validated countdown candidate used by Suffolk regression probes."""

from esolangs.generation.helpers import _validate_truth_table
from esolangs.languages.suffolk.generator import _lookup


def _suffolk_lookup(truth_table: str) -> str:
    """Build the validated countdown candidate for a regression probe."""
    return _lookup(truth_table, _validate_truth_table(truth_table))
