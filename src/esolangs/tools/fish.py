"""Fish boolean generator: a one-row table read with ``g``."""

from esolangs.tools.helpers import _validate_truth_table


def fish(truth_table: str) -> str:
    """Return a Fish program computing ``truth_table`` in linear source."""
    n = _validate_truth_table(truth_table)
    # Read ASCII bits, fold the row number, then fetch the digit below.
    header = "0" + "i68*-$2*+" * n + "1g68*-n;"
    return header + "\n" + truth_table
