"""Boolean-function generator for Vandevelo."""

from esolangs.tools.helpers import _validate_truth_table

__all__ = ["vandevelo"]


def vandevelo(truth_table: str) -> str:
    """Build a Vandevelo program computing ``truth_table`` by termination."""
    n = _validate_truth_table(truth_table)
    lines = [f"i{index} ~> Inp?" for index in range(n)]
    lines.append("loop -> loop?")
    for row, result in enumerate(truth_table):
        if result == "0":
            continue
        bits = f"{row:0{n}b}"
        guards = [
            f"i{index}? {'!=' if bit == '1' else '=='} Nil?"
            for index, bit in enumerate(bits)
        ]
        lines.append(" :: ".join([*guards, "loop?"]))
    return "\n".join(lines)
