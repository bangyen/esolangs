"""Certify the straight-line parity reducer for seventeen-input addresses."""

from address17 import ALL1, ALL2, group_word
from parity_views import MASK, STORED_PARITY, TOGGLE

from esolangs.interpreters.other.malbolge import _crazy
from esolangs.tools.malbolge.core import _rot


def parity_operand(pointer: int) -> int:
    """Return 1458 exactly when ``pointer + 1`` is odd, otherwise zero."""
    indicator = _crazy(ALL1, _crazy(ALL2, pointer))
    accumulator = ALL2
    for _ in range(10):
        indicator = _rot(indicator)
        accumulator = _crazy(indicator, accumulator)
    return _crazy(accumulator, MASK)


def main() -> None:
    """Check every group and each of its three cell parities."""
    seen = set()
    for row in range(1 << 14):
        bits = [(row >> (13 - k)) & 1 for k in range(14)]
        pointer = _crazy(ALL2 - 2, group_word(bits))
        operand = parity_operand(pointer)
        assert operand == (TOGGLE if (pointer + 1) % 2 else 0)
        for offset in range(3):
            adjusted = operand ^ (TOGGLE if offset % 2 else 0)
            parity = (pointer + 1 + offset) % 2
            assert _crazy(adjusted, STORED_PARITY[0]) == STORED_PARITY[parity]
        seen.add(operand)
    assert seen == {0, TOGGLE}
    print("16,384 group parities and 49,152 cell parities: exact")
    print("reducer: 2 digit maps + 10 rotate/folds + 3 mask/toggle copies")


if __name__ == "__main__":
    main()
