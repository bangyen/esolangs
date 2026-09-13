"""Boolean-function generator for Vandevelo."""

from esolangs.tools.helpers import _validate_truth_table

__all__ = ["vandevelo"]


def vandevelo(truth_table: str, width: int | None = None) -> str:
    """Build a Vandevelo program computing ``truth_table`` by termination."""
    n = _validate_truth_table(truth_table)
    compact = width is not None
    names = [chr(code) for code in range(ord("a"), ord("z") + 1) if code != ord("l")]
    names.extend(f"a{index}" for index in range(n - len(names)))
    lines = (
        [f"{names[index]}~>Inp?" for index in range(n)]
        if compact
        else [f"i{index} ~> Inp?" for index in range(n)]
    )
    lines.append("l->l?" if compact else "loop -> loop?")
    for row, result in enumerate(truth_table):
        if result == "0":
            continue
        bits = f"{row:0{n}b}"
        if compact:
            guards = [
                f"{names[index]}?{'!=' if bit == '1' else '=='}Nil?"
                for index, bit in enumerate(bits)
            ]
            lines.append("::".join([*guards, "l?"]))
        else:
            guards = [
                f"i{index}? {'!=' if bit == '1' else '=='} Nil?"
                for index, bit in enumerate(bits)
            ]
            lines.append(" :: ".join([*guards, "loop?"]))
    return "\n".join(lines)
