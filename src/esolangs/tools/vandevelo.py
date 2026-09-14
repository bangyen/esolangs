"""Boolean-function generator for Vandevelo."""

from esolangs.tools.helpers import _validate_truth_table

__all__ = ["vandevelo"]


_ALPHABET = "abcdefghijkmnopqrstuvwxyzABCDEFGHJKLMOPQRSTUVWXYZ0123456789_&*$"
_RESERVED = {"Inp", "Nil", "l", "loop"}


def _name(index: int) -> str:
    """Return the ``index``th shortest non-reserved Vandevelo name."""
    base = len(_ALPHABET)
    value = index + 1
    chars = []
    while value:
        value, digit = divmod(value - 1, base)
        chars.append(_ALPHABET[digit])
    return "".join(reversed(chars))


def vandevelo(truth_table: str, width: int | None = None) -> str:
    """Build a Vandevelo program computing ``truth_table`` by termination."""
    n = _validate_truth_table(truth_table)
    compact = width is not None
    names = [_name(index) for index in range(n)]
    lines = (
        [f"{names[index]}~>Inp?" for index in range(n)]
        if compact
        else [f"{names[index]} ~> Inp?" for index in range(n)]
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
                f"{names[index]}? {'!=' if bit == '1' else '=='} Nil?"
                for index, bit in enumerate(bits)
            ]
            lines.append(" :: ".join([*guards, "loop?"]))

    emit(0, 2**n, "")
    return "\n".join(lines)
