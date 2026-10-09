"""Build linear-size Piet++ programs for Boolean truth tables.

Piet's lookup recoloured: Piet++ keeps Piet's traversal, push-int, roll,
not, arithmetic and numeric I/O, so each Piet command maps to its Piet++
colour delta. Compact turns and bounded pushes replace the strip only
when they reduce raster area.
A constant half is folded as in Piet; a strip has no subtrees to share.
"""

from __future__ import annotations

from functools import cache
from math import isqrt

from esolangs.raster import Raster
from esolangs.registry._language import Language, SourceKind
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
from esolangs.tools.piet.balance import (
    _MIN_COLUMNS,
    _POINTER,
    _bounded_operations,
    _emit,
    _plan,
)

# Piet (hue, lightness) change -> Piet++ (red, green, blue) level delta.
_DELTAS = {
    _PUSH: (1, 0, 0),
    _POINTER: (2, 1, 3),
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
    initial = (0, 170, 0)
    default = strip(_operations(truth_table, inputs), initial, _next_colour)
    operations = _bounded_operations(truth_table)
    # Seed 20261009, 200 tables/arity: n=7 area 223839 -> 180736;
    # n=8 419430 -> 301751 codels. All 256 n=3 tables retain their strip.
    cells = sum(operation.size for operation in operations)
    # Alternating two/three-row turns set the aspect scale; one width
    # keeps default generation linear instead of enumerating row-fit regimes.
    columns = max(_MIN_COLUMNS, isqrt(5 * cells // 2) + 7)
    plan = _plan(operations, columns, columns + 1, compact=True)
    if plan.width * plan.height >= len(default.rows[0]) * len(default.rows):
        return default
    return _emit(operations, plan, initial=initial, next_colour=_next_colour)


def piet_plus_plus(truth_table: str) -> Raster:
    """Return a Piet++ raster computing ``truth_table``."""
    return _generate(truth_table)


LANGUAGE = Language(
    "Piet++",
    "stack_based.piet_plus_plus",
    # The slug rule drops "++" and would collide with Piet.
    id="piet_plus_plus",
    source_kind=SourceKind.RASTER,
    boolean=piet_plus_plus,
    no_wrap="strip or compact folded path; layout chooses its own width",
    eof="an exhausted In command is ignored, as the page recommends",
)
