"""Line image-program source and interpreter adapter.

Line encodes a Brainfuck-style program as a black path on a white raster.
Turns and kinks select tape, arithmetic, input, and output operations; a
T-junction branches on the current cell.  The filled arrowhead chooses the
entry point and initial direction.  Source must be a lossless PNG because
anti-aliasing changes the path geometry.

Input/output:
    Input numbers are whitespace-delimited integer tokens.  Outputs are
    decimal, unseparated.  An input read at EOF raises.

Errors:
    ProgramError: a JPEG or unreadable PNG; an image with no ink; no
    cursor, more than one arrowhead-shaped region, or a largest thick region
    that is not arrowhead-shaped; no path beyond the cursor; a scale that is
    not uniform Line pixel squares; a unit that is not a positive integer;
    ink left unaccounted for after extraction (corrupt or over-compressed).
    InputExhaustedError: an input read at EOF.
    ArgumentError: an input token that is not an integer.

Decisions:
    * The spec does not define input text framing.
"""

from __future__ import annotations

from collections.abc import Mapping
from functools import cache, lru_cache
from typing import TYPE_CHECKING, Any, cast

from esolangs.raster import Pixel, Raster, Rows
from esolangs.runtime._lifecycle import HALTED_REPORT, CompletionReport
from esolangs.runtime._machine import RuntimePlan
from esolangs.runtime._program import RunnerProgram
from esolangs.runtime._state import WorkspaceModel, WorkspaceSnapshot
from esolangs.runtime.io import IO

from .extract import extract_mask
from .mask import from_grey
from .simulate import IO as _LINE_IO
from .simulate import (
    _advance,
    _drive,
    _freeze_node,
    _freeze_program,
    _needs_input,
    _State,
    compile_program,
)
from .simulate import run_compiled as _run_compiled
from .simulate import run_node as _run_node

if TYPE_CHECKING:
    from esolangs.languages.line.generator.layout import Node

    from .simulate import _Compiled, _Frame

__all__ = ["run"]


def _luma(pixel: Pixel) -> int:
    red, green, blue = pixel
    return (red * 19595 + green * 38470 + blue * 7471 + 0x8000) >> 16


def _grey_rows(rows: Rows) -> list[bytearray]:
    """Reduce RGB rows to Line's greyscale input representation.

    A run of one pixel object is copied, not converted: about 4x faster on
    generated rasters (n=8: 504 vs 2091 ms) and no slower on noise.
    """
    cache: dict[int, tuple[tuple[Pixel, ...], bytes]] = {}
    pixels: dict[int, tuple[Pixel, int]] = {}
    cache_pixels = True
    grey = []
    for row in rows:
        cached = cache.get(id(row))
        if cached is None:
            if not cache_pixels:
                levels = bytes(map(_luma, row))
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
                        level = _luma(pixel)
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
    return compile_program(
        extract_mask(from_grey(_grey_rows(program.rows)), scale=scale)
    )


_WORKSPACE_MODEL = WorkspaceModel(
    "line-v1", ("node", "instruction", "pointer", "cells", "input_cursor")
)


class _Machine:
    """A Line run: immutable code and state with I/O handled by the shell."""

    @staticmethod
    def run_node(node: Node, io: IO) -> None:
        """Execute the graph retained by a generated raster."""
        _run_node(node, _LINE_IO(read=io.input_num, write=io.print_num))

    ip_shape = "grid"

    def __init__(
        self, program: Raster | tuple[_Frame, ...], io: IO, *, scale: int | None = None
    ) -> None:
        self.program = (
            _freeze_program(_compiled(program, scale))
            if isinstance(program, Raster)
            else program
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

    def workspace_snapshot(self) -> WorkspaceSnapshot:
        """Capture logical workspace independently of cycle keys and backing storage."""
        node, instruction, pointer, tape = self.state
        return _WORKSPACE_MODEL.capture(
            node=node,
            instruction=instruction,
            pointer=pointer,
            cells=frozenset((cell, value) for cell, value in tape if value),
            input_cursor=self.io.progress(),
        )

    def snapshot(self) -> tuple[object, ...]:
        node, at, pointer, tape = self.state
        cells = tuple((cell, value) for cell, value in tape if value)
        return node, at, pointer, cells, self.io.progress()

    def step(self) -> None:
        if self.halted:
            return
        value = self.io.input_num() if _needs_input(self.program, self.state) else None
        self.state, output = _advance(self.state, self.program, value)
        if output is not None:
            self.io.print_num(output)


def prepare_machine(source: RunnerProgram, options: Mapping[str, Any]) -> RuntimePlan:
    """Retain the instructions for each requested execution view."""
    if not isinstance(source, Raster):
        raise TypeError("line machines require raster source")
    if options.keys() - {"scale"}:
        raise TypeError("line machines accept only the scale runtime option")
    scale = options.get("scale")

    @cache
    def raster_program() -> tuple[_Frame, ...]:
        return _freeze_program(_compiled(source, scale))

    @cache
    def native_program() -> tuple[_Frame, ...]:
        if source._payload is not None and scale is None:  # noqa: SLF001 - language-owned payload
            return _freeze_node(cast("Node", source._payload))  # noqa: SLF001
        return raster_program()

    return RuntimePlan(
        lambda io: _Machine(raster_program(), io),
        lambda io: _execute(native_program(), io),
    )


def _execute(
    program: Raster | tuple[_Frame, ...], io: IO, *, scale: int | None = None
) -> CompletionReport:
    """Execute Line, writing decimal outputs through ``io``."""
    if not isinstance(program, Raster):
        _drive(program, _LINE_IO(read=io.input_num, write=io.print_num))
        return HALTED_REPORT
    if program._payload is not None and scale is None:  # noqa: SLF001 - language-owned payload
        _Machine.run_node(cast("Node", program._payload), io)  # noqa: SLF001
        return HALTED_REPORT
    _run_compiled(
        _compiled(program, scale),
        _LINE_IO(read=io.input_num, write=io.print_num),
    )
    return HALTED_REPORT


def run(program: Raster, io: IO, *, scale: int | None = None) -> None:
    """Execute a Line raster, writing decimal outputs through ``io``."""
    _execute(program, io, scale=scale)
