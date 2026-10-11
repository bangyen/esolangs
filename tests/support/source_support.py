"""Normalize emitted text and raster source for development checks."""

from esolangs.raster import Raster


def source_units(program: object) -> int:
    """Return characters for text, pixels for raster source."""
    if isinstance(program, Raster):
        return sum(map(len, program.rows))
    return len(str(program))
