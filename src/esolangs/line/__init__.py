"""Line image-program source and interpreter adapter.

Line encodes a Brainfuck-style program as a black path on a white raster.
Turns and kinks select tape, arithmetic, input, and output operations; a
T-junction branches on the current cell.  The filled arrowhead chooses the
entry point and initial direction.  Source must be a lossless PNG because
anti-aliasing changes the path geometry.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import cache, cached_property
from typing import TYPE_CHECKING, cast

from esolangs.interpreters.io import ScriptedIO

from . import png
from .extract import Stroke, extract_mask
from .mask import from_grey
from .simulate import IO
from .simulate import run as _run

if TYPE_CHECKING:
    from .render import Node


Rows = tuple[tuple[tuple[int, int, int], ...], ...]


@dataclass(frozen=True, init=False, eq=False)
class Raster:
    """An immutable 8-bit RGB image source, stored row by row."""

    _rows: Rows | None = field(default=None, repr=False)
    _node: object | None = field(default=None, repr=False, compare=False)

    def __init__(
        self, rows: Rows | None = None, *, _node: object | None = None
    ) -> None:
        """Create a raster from pixels, or lazily from a generated Line graph."""
        object.__setattr__(self, "_rows", rows)
        object.__setattr__(self, "_node", _node)
        self.__post_init__()

    def __post_init__(self) -> None:
        """Validate the rectangular raster shape."""
        if self._rows is None:
            if self._node is None:
                raise ValueError("Raster needs pixels or a generated Line graph")
            return
        width = len(self._rows[0]) if self._rows else 0
        valid = all(
            len(pixel) == 3 and all(0 <= value <= 255 for value in pixel)
            for row in self._rows
            for pixel in row
        )
        if not self._rows or not width or any(len(row) != width for row in self._rows):
            raise ValueError("Raster needs non-empty equal-width rows")
        if not valid:
            raise ValueError("Raster pixels must be 8-bit RGB triples")

    def __eq__(self, other: object) -> bool:
        """Whether two rasters have identical RGB pixels."""
        return isinstance(other, Raster) and self.rows == other.rows

    def __hash__(self) -> int:
        """Hash the immutable RGB pixels."""
        return hash(self.rows)

    @property
    def rows(self) -> Rows:
        """Return RGB rows, rendering a generated Line graph on first access."""
        if self._rows is None:
            from .render import Node, render

            canvas = render(cast("Node", self._node))
            rows = tuple(
                tuple((level, level, level) for level in row) for row in canvas.pixels
            )
            object.__setattr__(self, "_rows", rows)
        return cast("Rows", self._rows)

    @classmethod
    def from_png(cls, data: bytes) -> Raster:
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

    @cached_property
    def stroke(self) -> Stroke:
        """Return the extracted path, cached across input rows."""
        return extract_mask(from_grey(self.grey_rows()))


@cache
def generate(truth_table: str) -> Raster:
    """Return a Line raster computing ``truth_table``."""
    from .line_boolean import line_boolean

    node = line_boolean(truth_table)
    return Raster(_node=node)


def _run_node(node: Node, io: ScriptedIO) -> None:
    """Execute the graph retained by a generated raster."""
    tape: dict[int, int] = {}
    pointer = 0
    current: Node | None = node
    while current is not None:
        if current.op == "+":
            tape[pointer] = tape.get(pointer, 0) + 1
        elif current.op == "-":
            tape[pointer] = tape.get(pointer, 0) - 1
        elif current.op == ">":
            pointer += 1
        elif current.op == "<":
            pointer -= 1
        elif current.op == "i":
            tape[pointer] = io.input_num()
        elif current.op == "o":
            io.print_num(tape.get(pointer, 0))
        elif current.op == "?":
            current = current.zero if tape.get(pointer, 0) == 0 else current.nonzero
            continue
        current = current.next or current.goto


def run(program: Raster, io: ScriptedIO) -> None:
    """Execute a Line raster, writing decimal outputs through ``io``."""
    if program._node is not None:  # noqa: SLF001 - same module owns the fast path
        _run_node(cast("Node", program._node), io)  # noqa: SLF001
        return
    _run(
        program.stroke,
        IO(read=io.input_num, write=io.print_num),
    )
