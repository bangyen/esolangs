"""Line image-program source and interpreter adapter."""

from dataclasses import dataclass

from esolangs.interpreters.io import ScriptedIO

from . import png
from .extract import extract_mask
from .mask import from_grey
from .simulate import IO
from .simulate import run as _run


@dataclass(frozen=True)
class Raster:
    """An immutable 8-bit RGB image source, stored row by row."""

    rows: tuple[tuple[tuple[int, int, int], ...], ...]

    def __post_init__(self) -> None:
        """Validate the rectangular raster shape."""
        width = len(self.rows[0]) if self.rows else 0
        valid = all(
            len(pixel) == 3 and all(0 <= value <= 255 for value in pixel)
            for row in self.rows
            for pixel in row
        )
        if not self.rows or not width or any(len(row) != width for row in self.rows):
            raise ValueError("Raster needs non-empty equal-width rows")
        if not valid:
            raise ValueError("Raster pixels must be 8-bit RGB triples")

    @classmethod
    def from_png(cls, data: bytes) -> "Raster":
        """Decode PNG bytes into a raster source."""
        return cls(tuple(tuple(row) for row in png.read_rgb(data)))

    def to_png(self) -> bytes:
        """Encode this raster as PNG bytes."""
        return png.write_rgb([list(row) for row in self.rows])

    def grey_rows(self) -> list[bytearray]:
        """Return rows reduced to Line's greyscale input representation."""
        return [
            bytearray(
                (red * 19595 + green * 38470 + blue * 7471 + 0x8000) >> 16
                for red, green, blue in row
            )
            for row in self.rows
        ]


def run(program: Raster, io: ScriptedIO) -> None:
    """Execute a Line raster, writing decimal outputs through ``io``."""
    stroke = extract_mask(from_grey(program.grey_rows()))
    _run(
        stroke,
        IO(read=io.input_num, write=io.print_num),
    )
