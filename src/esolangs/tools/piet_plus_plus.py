"""Build linear-size Piet++ programs for Boolean truth tables.

Piet's lookup recoloured: Piet++ keeps Piet's traversal, push-int, roll,
not, arithmetic and numeric I/O, so each Piet command maps to its Piet++
colour delta and the same strip computes the table (T + O(n) codels).
"""

from __future__ import annotations

from functools import cache

from esolangs.raster import Raster
from esolangs.tools.helpers import _validate_truth_table
from esolangs.tools.piet import (
    _ADD,
    _IN_NUMBER,
    _MULTIPLY,
    _NOT,
    _OUT_NUMBER,
    _POP,
    _PUSH,
    _ROLL,
    _SUBTRACT,
    Change,
    Pixel,
    _operations,
    strip,
)

# Piet (hue, lightness) change -> Piet++ (red, green, blue) level delta.
_DELTAS = {
    _PUSH: (1, 0, 0),
    _POP: (3, 0, 0),
    _ADD: (0, 0, 3),
    _SUBTRACT: (1, 0, 3),
    _MULTIPLY: (2, 0, 3),
    _NOT: (2, 1, 0),
    _ROLL: (1, 0, 1),
    _IN_NUMBER: (3, 1, 1),
    _OUT_NUMBER: (1, 1, 2),
}


def _next_colour(colour: Pixel, change: Change) -> Pixel:
    """Apply a delta, keeping green at level 1 or 2: never black or white."""
    red, green, blue = (level // 85 for level in colour)
    dr, dg, db = _DELTAS[change]
    return (red + dr) % 4 * 85, (2 - (green + dg) % 2) * 85, (blue + db) % 4 * 85


@cache
def _generate(truth_table: str) -> Raster:
    inputs = _validate_truth_table(truth_table)
    return strip(_operations(truth_table, inputs), (0, 170, 0), _next_colour)


def piet_plus_plus(truth_table: str) -> Raster:
    """Return a Piet++ raster computing ``truth_table``."""
    return _generate(truth_table)
