"""Piet Boolean program generator: push the table, roll out the entry.

Pushes one entry per row, reads the inputs into a row number, and ``roll``
brings the entry to the top to print.  A one-hot or one-cold table is a
product of literals instead; see :mod:`esolangs.generation.raster_lookup`.

Size:
    O(T) codels; n=10 parity: 2,226 codels, n=10 and: 66 codels.
"""

from functools import cache
from math import isqrt

from esolangs.generation.helpers import _validate_truth_table
from esolangs.generation.raster_lookup import _INITIAL, _next_colour, _operations, strip
from esolangs.generation.raster_lookup.balance import (
    _bounded_operations,
    balance,
    folded,
)
from esolangs.generation.raster_lookup.packing import pack
from esolangs.raster import Raster
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Example, Language, SourceKind


@cache
def _generate(truth_table: str) -> Raster:
    """Return a Piet raster computing ``truth_table``."""
    inputs = _validate_truth_table(truth_table)
    return strip(_operations(truth_table, inputs), _INITIAL, _next_colour)


def _area(image: Raster) -> int:
    return len(image.rows) * len(image.rows[0])


@cache
def _smallest(truth_table: str) -> Raster:
    """Return the strip or the packed fold, whichever has less area (tie: strip).

    The fold is drawn once at the balance path's dense width, ``sqrt(2C) + 9``
    for ``C`` codels of operations, then packed: no width sweep, so O(T).  It
    runs five to six more steps per turn; see [ablations.area_default].
    """
    flat = _generate(truth_table)
    operations = _bounded_operations(truth_table)
    cells = sum(operation.size for operation in operations)
    fold = pack(operations, folded(truth_table, isqrt(2 * cells - 1) + 9))
    return fold if _area(fold) < _area(flat) else flat


def piet(truth_table: str, width: int | None = None, *, scale: int = 1) -> Raster:
    """Return a Piet raster computing the table."""
    if width is not None:
        return folded(truth_table, width).upscaled(scale)
    return _smallest(truth_table).upscaled(scale)


LANGUAGE = Language(
    "Piet",
    "piet",
    category="stack_based",
    source_kind=SourceKind.RASTER,
    boolean=piet,
    contract=BooleanContract(
        note="the committed example is drawn at 80 pixels per codel; "
        "generate draws 1 unless --scale says otherwise"
    ),
    balance=balance,
    eof="an exhausted input command is ignored, as the spec requires",
    example=Example(scale=80),
)
