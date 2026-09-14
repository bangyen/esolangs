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

    def emit(lo: int, hi: int, bits: str) -> None:
        span = truth_table[lo:hi]
        if "1" not in span:
            return
        if "0" not in span:
            append(bits)
            return
        mid = (lo + hi) // 2
        emit(lo, mid, bits + "0")
        emit(mid, hi, bits + "1")

    def append(bits: str) -> None:
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

    emit(0, 2**n, "")
    return "\n".join(lines)
