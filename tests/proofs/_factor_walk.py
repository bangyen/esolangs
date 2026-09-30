"""Factor witness with an input-directed walk through literal truth bits."""

from esolangs.tools.helpers import _validate_truth_table


def walked_program(truth_table: str) -> str:
    """Read bits in order, moving left on zero, then print the addressed cell."""
    n = _validate_truth_table(truth_table)
    data = ">" + ">>".join("+" if bit == "1" else "" for bit in truth_table) + "<"
    address = "".join(
        "," + "-" * 49 + "[+" + "<" * (1 << (n - i)) + "]" for i in range(n)
    )
    return data + address + ">" + "+" * 48 + "."
