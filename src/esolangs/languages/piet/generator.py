"""Build raster truth-table programs."""

from functools import cache

from esolangs.generation.helpers import _validate_truth_table
from esolangs.generation.raster_lookup import _INITIAL, _next_colour, _operations, strip
from esolangs.generation.raster_lookup.balance import balance, folded
from esolangs.raster import Raster
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Example, Language, SourceKind


@cache
def _generate(truth_table: str) -> Raster:
    """Return a Piet raster computing ``truth_table``."""
    inputs = _validate_truth_table(truth_table)
    return strip(_operations(truth_table, inputs), _INITIAL, _next_colour)


def piet(truth_table: str, width: int | None = None, *, scale: int = 1) -> Raster:
    """Return a Piet raster computing the table."""
    if width is not None:
        return folded(truth_table, width).upscaled(scale)
    return _generate(truth_table).upscaled(scale)


LANGUAGE = Language(
    "Piet",
    "piet",
    category="stack_based",
    source_kind=SourceKind.RASTER,
    boolean=piet,
    contract=BooleanContract(note="80 pixels per codel"),
    balance=balance,
    eof="an exhausted input command is ignored, as the spec requires",
    example=Example(scale=80),
)
