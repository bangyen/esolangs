"""Piet Boolean program generator: push the table, roll out the entry.

Pushes one entry per row, reads the inputs into a row number, and ``roll``
brings the entry to the top to print.  A one-hot or one-cold table is a
product of literals instead; see :mod:`esolangs.generation.raster_lookup`.

Size:
    O(T) codels; n=10 parity: 2,226 codels, n=10 and: 66 codels.
"""

from functools import cache

from esolangs.generation.helpers import _validate_truth_table
from esolangs.generation.raster_lookup import _INITIAL, _next_colour, _operations, strip
from esolangs.generation.raster_lookup.balance import (
    _bounded_operations,
    balance,
    folded,
)
from esolangs.generation.raster_lookup.packing import _raster_score, smallest
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
def _packed(truth_table: str) -> Raster:
    """Return the least-area packed layout, bounded by the strip."""
    return smallest(_bounded_operations(truth_table), _generate(truth_table))


@cache
def _smallest(truth_table: str) -> Raster:
    """Return the strip, or the least-area packed layout.

    The strip wins a tie; see [ablations.area_default].
    """
    flat, packed = _generate(truth_table), _packed(truth_table)
    return packed if _area(packed) < _area(flat) else flat


def _balance(truth_table: str, default: Raster) -> Raster:
    """Balance the strip, keeping the packed default when it is squarer.

    Seeded with the packed default, the balancer's area ceiling left it
    unchanged on random tables; the strip gives -24.4% balanced area at
    n=7 and parity / majority -14% to -26% at n=7..9
    ([ablations.balance_strip_seed]).
    """
    return min(balance(truth_table, _generate(truth_table)), default, key=_raster_score)


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
    balance=_balance,
    eof="an exhausted input command is ignored, as the spec requires",
    example=Example(scale=80),
)
