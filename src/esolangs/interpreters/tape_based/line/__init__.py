"""Line image-program source and interpreter adapter.

Line encodes a Brainfuck-style program as a black path on a white raster.
Turns and kinks select tape, arithmetic, input, and output operations; a
T-junction branches on the current cell.  The filled arrowhead chooses the
entry point and initial direction.  Source must be a lossless PNG because
anti-aliasing changes the path geometry.

Input numbers are whitespace-delimited integer tokens; the spec does not define
text framing. EOF raises EOFError.  Outputs are decimal, unseparated.
"""

from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING, cast

from esolangs._source import raster_source as load_source
from esolangs.interpreters.io import IO
from esolangs.raster import Pixel, Raster, Rows

from .extract import extract_mask
from .mask import from_grey
from .simulate import IO as _LINE_IO
from .simulate import _State
from .simulate import run_compiled as _run_compiled

if TYPE_CHECKING:
    from esolangs.tools.line.render import Node

    from .simulate import _Compiled

__all__ = ["load_source", "run"]

supports_scale = True


def _grey_rows(rows: Rows) -> list[bytearray]:
    """Reduce RGB rows to Line's greyscale input representation."""
    cache: dict[int, tuple[tuple[Pixel, ...], bytes]] = {}
    pixels: dict[int, tuple[Pixel, int]] = {}
    cache_pixels = True
    grey = []
    for row in rows:
        cached = cache.get(id(row))
        if cached is None:
            if not cache_pixels:
                levels = bytes(
                    (red * 19595 + green * 38470 + blue * 7471 + 0x8000) >> 16
                    for red, green, blue in row
                )
            else:
                converted = bytearray()
                previous: Pixel | None = None
                level = 0
                repeats = 0
                for pixel in row:
                    if pixel is previous:
                        repeats += 1
                        continue
                    if repeats:
                        converted.extend(bytes((level,)) * repeats)
                    cached_pixel = pixels.get(id(pixel)) if cache_pixels else None
                    if cached_pixel is None:
                        red, green, blue = pixel
                        level = (
                            red * 19595 + green * 38470 + blue * 7471 + 0x8000
                        ) >> 16
                        if cache_pixels:
                            pixels[id(pixel)] = pixel, level
                            cache_pixels = len(pixels) < 1024
                    else:
                        level = cached_pixel[1]
                    previous = pixel
                    repeats = 1
                converted.extend(bytes((level,)) * repeats)
                levels = bytes(converted)
            if len(cache) < 1024:
                cache[id(row)] = row, levels
        else:
            levels = cached[1]
        grey.append(bytearray(levels))
    return grey


@lru_cache(maxsize=8)
def _compiled(program: Raster, scale: int | None = None) -> _Compiled:
    from .simulate import compile_program

    return compile_program(
        extract_mask(from_grey(_grey_rows(program.rows)), scale=scale)
    )


class _Machine:
    """A Line run: immutable code and state with I/O handled by the shell."""

    @staticmethod
    def run_node(node: Node, io: IO) -> None:
        """Execute the graph retained by a generated raster."""
        from .simulate import run_node

        run_node(node, _LINE_IO(read=io.input_num, write=io.print_num))

    ip_shape = "grid"

    def __init__(self, program: Raster, io: IO, *, scale: int | None = None) -> None:
        from .simulate import _freeze_program

        self.program = _freeze_program(
            _compiled(program, scale if scale is not None else program.scale)
        )
        self.state: _State = (0, 0, 0, ())
        self.io = io

    @property
    def halted(self) -> bool:
        return self.state[0] is None

    @property
    def ip(self) -> tuple[int, ...] | None:
        node, at = self.state[:2]
        if node is None:
            return None
        frame = self.program[node]
        return frame.positions[at] if at < len(frame.ops) else frame.end

    @property
    def memory(self) -> tuple[int, ...]:
        tape = dict(self.state[3])
        return tuple(
            tape.get(i, 0)
            for i in range(min(tape, default=0), max(tape, default=0) + 1)
        )

    def snapshot(self) -> tuple[object, ...]:
        node, at, pointer, tape = self.state
        cells = tuple((cell, value) for cell, value in tape if value)
        return node, at, pointer, cells, self.io.progress()

    def step(self) -> None:
        from .simulate import _advance

        node, at = self.state[:2]
        if node is None:
            return
        frame = self.program[node]
        value = (
            self.io.input_num()
            if at < len(frame.ops) and frame.ops[at][0] == "i"
            else None
        )
        self.state, output = _advance(self.state, self.program, value)
        if output is not None:
            self.io.print_num(output)


def run(program: Raster, io: IO, *, scale: int | None = None) -> None:
    """Execute a Line raster, writing decimal outputs through ``io``."""
    if program._payload is not None and scale is None:  # noqa: SLF001 - language-owned payload
        _Machine.run_node(cast("Node", program._payload), io)  # noqa: SLF001
        return
    _run_compiled(
        _compiled(program, scale if scale is not None else program.scale),
        _LINE_IO(read=io.input_num, write=io.print_num),
    )
