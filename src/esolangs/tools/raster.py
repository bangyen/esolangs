"""Raster generators on the common Boolean-generator surface."""

from esolangs.raster import Raster


def line(truth_table: str) -> Raster:
    """Return a Line program computing the table."""
    from esolangs.line import generate

    return generate(truth_table)


def piet(truth_table: str, width: int | None = None) -> Raster:
    """Return a Piet program computing the table."""
    from esolangs.piet import generate

    return generate(truth_table, width)
