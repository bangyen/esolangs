"""Shared addresses of the packed decoder's code and operand regions."""

from .isa import _char_for

# Spill navigation and column dispatch.
_SPILL_DISPATCH = 5024
_SPILL_BRANCH = 5046
_COLUMN_DISPATCH = 38469

_BANK = 729
_SPILL_MARKER_BASE = 57592
_COLUMN_COUNT = 243
_HIGH_OPERAND_OFFSET = 79
_COLUMN_MARKER_BASE = 51031
_COLUMN_MARKER_STRIDE = 3

# Lookup operands and the hubs that classify their glyphs.
_LOOKUP = range(5213, 5548)
_ONE_HUB = 41551
_SHORT_HUB = 45925
_LONG_HUB = 54673

# Printer entries and taps are indexed by the same output slot.
_PRINTERS = (4513, 4663, 4585)
_TAPS = (139, 127, 130)


def _word_column(word: int) -> int:
    """Return the payload word's column within its address band."""
    return (word - 1) % _COLUMN_COUNT


def _column_marker(column: int) -> int:
    """Return the marker before the column's short-hub companion."""
    return _COLUMN_MARKER_BASE + _COLUMN_MARKER_STRIDE * column


def _high_cell(word: int) -> int:
    """Return the high lookup operand for the payload word's band."""
    return (word - 1) // _COLUMN_COUNT * _COLUMN_COUNT + _HIGH_OPERAND_OFFSET


def _lookup_base(word: int, raw: int, marker: int) -> int:
    """Return the payload's lookup address before adding a printer tap."""
    high = _char_for("p", _high_cell(word))
    return 5113 + 3 * _char_for("p", 19745 + high - raw) - marker
