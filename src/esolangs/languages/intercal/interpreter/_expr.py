"""INTERCAL expression evaluation, digit words and Roman numeral output."""

from __future__ import annotations

from collections.abc import Mapping

from esolangs.exceptions import HaltError
from esolangs.languages.intercal.interpreter._parse import (
    _fail,
    _Key,
    _Node,
    _parse_expression,
    _unary,
)
from esolangs.languages.intercal.interpreter._pmap import _PMap

type _Value = tuple[int, int]
#: An array's dimensions and its data.  A write returns new data sharing the
#: untouched buckets, so a step never edits the arrays it was handed.
type _Array = tuple[tuple[int, ...], _PMap[int, int]]
_NO_DATA: _PMap[int, int] = _PMap()

# Digit words 0-9: English and, as the manual says C-INTERCAL accepts
# (src/numerals.c), Sanskrit, Basque, Tagalog, Classical Nahuatl, Georgian,
# Kwakiutl, Volapuk and Latin.
_DIGIT_WORDS = (
    "ZERO ONE TWO THREE FOUR FIVE SIX SEVEN EIGHT NINE",
    "SUTYA EKA DVI TRI CHATUR PANCHAN SHASH SAPTAM ASHTAN NAVAN",
    "ZEROA BAT BI HIRO LAU BORTZ SEI ZAZPI ZORTZI BEDERATZI",
    "WALA ISA DALAWA TATLO APAT LIMA ANIM PITO WALO SIYAM",
    "AHTLE CE OME IEI NAUI NACUILI CHIQUACE CHICOME CHICUE CHICUNAUI",
    "NULI ERTI ORI SAMI OTXI XUTI EKSVI SHVIDI RVA CXRA",
    "KE'YOS 'NEM MAL'H YUDEXW MU SEK'A Q'ETL'A ETLEBU MALHGWENALH 'NA'NE'MA",
    "NOS BAL TEL KIL FOL LUL MÄL VEL JÖL ZÜL",
    "NIL UNUS DUO TRES QUATTUOR QUINQUE SEX SEPTEM OCTO NOVEM",
)
_DIGITS = {
    word: digit for line in _DIGIT_WORDS for digit, word in enumerate(line.split())
} | {
    "OH": 0, "NINER": 9, "SHUTYA": 0, 'M\\"AL': 6, 'J\\"OL': 8, 'Z\\"UL': 9,
    "NIHIL": 0, "UNA": 1, "UNUM": 1, "DUAE": 2, "QUATUOR": 4,
}  # fmt: skip

_WIDTH = {".": 16, ":": 32, ",": 16, ";": 32}
_ONESPOT_MAX = 0xFFFF
_TWOSPOT_MAX = 0xFFFFFFFF
_NEXT_LIMIT = 80

# Bit reversal of a byte, for Turing Tape output (C-INTERCAL's binout).
_REVERSED = tuple(int(f"{byte:08b}"[::-1], 2) for byte in range(256))


def _spread(value: int) -> int:
    """Move bit ``k`` of a 16-bit value to bit ``2k``."""
    value = (value | (value << 8)) & 0x00FF00FF
    value = (value | (value << 4)) & 0x0F0F0F0F
    value = (value | (value << 2)) & 0x33333333
    return (value | (value << 1)) & 0x55555555


def _select(value: int, mask: int) -> int:
    result = place = 0
    while mask:
        low = mask & -mask
        if value & low:
            result |= 1 << place
        place += 1
        mask ^= low
    return result


def _evaluate(
    node: _Node, scalars: Mapping[_Key, int], arrays: Mapping[_Key, _Array]
) -> _Value:
    """Return ``(value, width)``; C-INTERCAL types every result statically."""
    tag = node.tag
    if tag == "#":
        return node.arg1, 16
    if tag == "." or tag == ":":
        return scalars.get((tag, node.arg1), 0), _WIDTH[tag]
    if tag == "u":
        value, width = _evaluate(node.arg2, scalars, arrays)
        return _unary(value, width, node.arg1), width
    if tag == "$":
        left, _ = _evaluate(node.arg1, scalars, arrays)
        right, _ = _evaluate(node.arg2, scalars, arrays)
        if left > _ONESPOT_MAX or right > _ONESPOT_MAX:
            raise _fail(
                "E533",
                "INTERCAL mingle needs two onespot values",
                hint="use two 16-bit onespot values as mingle operands",
            )
        return (_spread(left) << 1) | _spread(right), 32
    if tag == "~":
        left, _ = _evaluate(node.arg1, scalars, arrays)
        right, width = _evaluate(node.arg2, scalars, arrays)
        return _select(left, right), width
    data, index = _element(node, scalars, arrays)
    return data.get(index, 0), _WIDTH[node.arg1]


def _element(
    node: _Node, scalars: Mapping[_Key, int], arrays: Mapping[_Key, _Array]
) -> tuple[_PMap[int, int], int]:
    """Locate a subscripted element: its array's store and flat index."""
    sigil, number, subscripts = node.arg1, node.arg2, node.arg3
    dimensions, data = arrays.get((sigil, number), ((), _NO_DATA))
    if len(subscripts) != len(dimensions):
        raise _fail(
            "E241",
            "INTERCAL subscripts do not match the array's dimensions",
            hint="dimension the array first and give one subscript per dimension",
        )
    index = 0
    for subscript, size in zip(subscripts, dimensions, strict=True):
        value, _ = _evaluate(subscript, scalars, arrays)
        if not 1 <= value <= size:
            raise _fail("E241", "INTERCAL subscript out of range")
        index = index * size + value - 1
    return data, index


def _expression(text: str, variables: dict[int, int]) -> tuple[_Value, int]:
    """Parse and evaluate one expression over onespot ``variables``."""
    node, end = _parse_expression(text, 0)
    scalars = {(".", number): value for number, value in variables.items()}
    return _evaluate(node, scalars, {}), end


def _roman(value: int) -> str:
    """Return Roman output; emit a separate overbar line when needed."""
    if not 0 <= value <= _TWOSPOT_MAX:
        raise HaltError("INTERCAL output out of range")
    chunks: list[tuple[str, str]] = []
    place = 0
    while value:
        value, digit = divmod(value, 10)
        group, column = divmod(place, 3)
        one, five, ten = ("IVX", "XLC", "CDM")[column]
        if column == 0 and group and digit <= 3:
            text = "M" * digit
            group -= 1
        elif digit <= 3:
            text = one * digit
        elif digit == 4:
            text = one + five
        elif digit <= 8:
            text = five + one * (digit - 5)
        else:
            text = one + ten
        if group >= 2:
            text = text.lower()
        chunks.append((text, ("_" if group % 2 else " ") * len(text)))
        place += 1
    body = "".join(text for text, _bars in reversed(chunks))
    bars = "".join(bars for _text, bars in reversed(chunks)) or "_"
    # "Zero is indicated by an overline with no character underneath."
    return bars + "\n" + body if "_" in bars else body
