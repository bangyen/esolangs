"""Line image-program source and interpreter adapter.

Line reads decimal input lines; EOF raises ``EOFError``.  It raises
``ValueError`` for malformed rasters.
"""

from dataclasses import dataclass

from esolangs.interpreters.io import ScriptedIO

from . import png
from .extract import extract_mask
from .mask import from_grey
from .simulate import IO
from .simulate import run as _run


class _Machine:
    """Line's non-steppable interpreter traits for capability reporting."""

    steppable_to_answer = False


@dataclass(frozen=True)
class Raster:
    """An immutable 8-bit greyscale image source, stored row by row."""

    rows: tuple[bytes, ...]

    def __post_init__(self) -> None:
        """Validate the rectangular raster shape."""
        width = len(self.rows[0]) if self.rows else 0
        if not self.rows or not width or any(len(row) != width for row in self.rows):
            raise ValueError("Raster needs non-empty equal-width rows")

    @classmethod
    def from_png(cls, data: bytes) -> "Raster":
        """Decode PNG bytes into a raster source."""
        return cls(tuple(bytes(row) for row in png.read_grey(data)))


def run(program: Raster, io: ScriptedIO) -> None:
    """Execute a Line raster, writing decimal outputs through ``io``."""
    stroke = extract_mask(from_grey([bytearray(row) for row in program.rows]))
    _run(
        stroke,
        IO(read=io.input_num, write=io.print_num),
    )
