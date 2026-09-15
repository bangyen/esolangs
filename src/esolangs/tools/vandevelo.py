"""Boolean-function generator for Vandevelo."""

from esolangs.tools.helpers import _validate_truth_table, constant_span_test

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
    constant = constant_span_test(truth_table)

    def emit(lo: int, hi: int, depth: int, prefix: int) -> None:
        if constant(lo, hi):
            if truth_table[lo] == "1":
                append(depth, prefix)
            return
        mid = (lo + hi) // 2
        emit(lo, mid, depth + 1, prefix << 1)
        emit(mid, hi, depth + 1, (prefix << 1) | 1)

    def append(depth: int, prefix: int) -> None:
        bits = [(prefix >> (depth - 1 - index)) & 1 for index in range(depth)]
        if compact:
            guards = [
                f"{names[index]}?{'!=' if bit else '=='}Nil?"
                for index, bit in enumerate(bits)
            ]
            lines.append("::".join([*guards, "l?"]))
        else:
            guards = [
                f"{names[index]}? {'!=' if bit else '=='} Nil?"
                for index, bit in enumerate(bits)
            ]
            lines.append(" :: ".join([*guards, "loop?"]))

    emit(0, 2**n, 0, 0)
    return "\n".join(lines)
