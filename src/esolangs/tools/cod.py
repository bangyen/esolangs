"""Linear Boolean-function generator for COD's parameterized convention.

Each placeholder contributes its binary-weight distance once.  The filled
four-row program stops over the selected cell in a complete answer strip,
drops through that baked-in bit, and reaches a shared border print.
"""

from esolangs.tools.helpers import _validate_truth_table

__all__ = ["cod"]


def cod(truth_table: str) -> str:
    """Return an O(T) COD template for a truth table of length T."""
    n = _validate_truth_table(truth_table)
    markers = "".join(f"{{X{i}}}" for i in range(n))
    answers = "".join(")" if bit == "1" else " " for bit in truth_table)
    return markers + "\n~~~~" + answers + "~"


def _instantiate_cod(template: str, bits: list[int]) -> str:
    """Fill a COD template by routing to its weighted table column."""
    marker, answer_row = template.split("\n")
    n = len(bits)
    if marker != "".join(f"{{X{i}}}" for i in range(n)):
        raise ValueError("bits do not match COD template")
    table = answer_row[4:-1]
    if len(table) != 1 << n:
        raise ValueError("bits do not match COD template")

    route = "".join(
        " " * (1 << (n - 1 - i)) if bit else "" for i, bit in enumerate(bits)
    )
    selected = len(route)
    width = len(table) + 5
    top = "~~~>" + " " * (selected + 1) + "~" * (len(table) - selected)
    middle = answer_row.ljust(width, "~")
    output = "---" + " " * (selected + 2) + "~" * (len(table) - selected)
    return "\n".join((top, middle, output, "~" * width))
