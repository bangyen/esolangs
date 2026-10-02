"""Compatibility entry points for Piet."""

from esolangs.interpreters.stack_based.piet import run as run
from esolangs.raster import Raster


def generate(truth_table: str, width: int | None = None, *, scale: int = 1) -> Raster:
    """Return a Piet raster computing the table."""
    from esolangs.tools.piet import piet

    return piet(truth_table, width, scale=scale)
