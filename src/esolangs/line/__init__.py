"""Shared Line rendering primitives and compatibility entry points."""

from esolangs.interpreters.io import ScriptedIO
from esolangs.raster import Raster


def generate(truth_table: str, *, scale: int = 1) -> Raster:
    """Return a Line raster computing the table."""
    from esolangs.tools.line import line

    return line(truth_table, scale=scale)


def balance(truth_table: str, default: Raster) -> Raster:
    """Return the balanced Line raster."""
    from esolangs.tools.line import balance

    return balance(truth_table, default)


def run(program: Raster, io: ScriptedIO, *, scale: int | None = None) -> None:
    """Execute a Line raster."""
    from esolangs.interpreters.tape_based.line import run

    run(program, io, scale=scale)
