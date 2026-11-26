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
from functools import cached_property, lru_cache, partial
from typing import TYPE_CHECKING, Any, cast

from esolangs.raster import Pixel, Raster, Rows
from esolangs.runtime._input_retry import RejectedInput
from esolangs.runtime._lifecycle import HALTED_REPORT, CompletionReport
from esolangs.runtime._machine import RuntimePlan
from esolangs.runtime._program import RunnerProgram
from esolangs.runtime._state import WorkspaceModel, WorkspaceSnapshot, WorkspaceVariant
from esolangs.runtime.io import IO, _BufferedOutput
from esolangs.runtime.memory import format_integer

from .extract import extract_mask
from .mask import from_grey
from .simulate import IO as _LINE_IO
from .simulate import (
    _advance,
    _Cursor,
    _drive,
    _freeze_node,
    _freeze_program,
    _needs_input,
    compile_program,
)

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
    grey = program._grey_rows()  # noqa: SLF001 - native greyscale scanlines
    rows = _grey_rows(program.rows) if grey is None else grey
    return compile_program(extract_mask(from_grey(rows), scale=scale))


_WORKSPACE_MODEL = WorkspaceModel(
    "line-v1", ("node", "instruction", "pointer", "cells", "input_cursor")
)


class _Machine:
    """A Line run with private tape and retryable I/O."""

    ip_shape = "grid"

    def __init__(
        self, program: Raster | tuple[_Frame, ...], io: IO, *, scale: int | None = None
    ) -> None:
        self.program = (
            _freeze_program(_compiled(program, scale))
            if isinstance(program, Raster)
            else program
        )
        self.cursor: _Cursor = (0, 0, 0)
        self.tape: dict[int, int] = {}
        self.io = io
        self._writer = _BufferedOutput()
        self._rejected_input = RejectedInput()

    @property
    def halted(self) -> bool:
        return self.cursor[0] is None

    @property
    def ip(self) -> tuple[int, ...] | None:
        node, at = self.cursor[:2]
        if node is None:
            return None
        frame = self.program[node]
        at += frame.offset
        return frame.positions[at] if at < len(frame.ops) else frame.end

    @property
    def memory(self) -> tuple[int, ...]:
        tape = self.tape
        return tuple(
            tape.get(i, 0)
            for i in range(min(tape, default=0), max(tape, default=0) + 1)
        )

    def workspace_snapshot(self) -> WorkspaceSnapshot:
        """Capture logical workspace independently of cycle keys and backing storage."""
        node, instruction, pointer = self.cursor
        accepted = self._writer.accepted
        return _WORKSPACE_MODEL.capture(
            node=node,
            instruction=WorkspaceVariant("pending_output", (instruction, accepted))
            if accepted
            else instruction,
            pointer=pointer,
            cells=frozenset(
                (cell, value) for cell, value in self.tape.items() if value
            ),
            input_cursor=self._rejected_input.cursor(self.io.progress()),
        )

    def snapshot(self) -> tuple[object, ...]:
        node, at, pointer = self.cursor
        cells = tuple(
            sorted((cell, value) for cell, value in self.tape.items() if value)
        )
        boundary = self._rejected_input.snapshot(
            (node, at, pointer, cells, self.io.progress())
        )
        accepted = self._writer.accepted
        return (*boundary, accepted) if accepted else boundary

    def step(self) -> None:
        if self.halted:
            return
        value = (
            self._rejected_input.read(self.io, self.io.input_num)
            if _needs_input(self.program, self.cursor)
            else None
        )
        pointer = self.cursor[2]
        cursor, write, output = _advance(
            self.cursor, self.program, self.tape.get(pointer, 0), value
        )
        if output is not None:
            self._writer.write(
                self.io,
                format_integer(output),
                first=partial(self.io.print_num, output),
            )
        if write is not None:
            self.tape[pointer] = write
        self.cursor = cursor


class _Program:
    """Lazily bind native instructions and debugger coordinates to one raster."""

    def __init__(self, source: Raster, scale: int | None) -> None:
        self.source = source
        self.scale = scale

    @cached_property
    def pixels(self) -> tuple[_Frame, ...]:
        return _freeze_program(_compiled(self.source, self.scale))

    @cached_property
    def native(self) -> tuple[_Frame, ...]:
        graph = self.source._payload  # noqa: SLF001 - language-owned payload
        if graph is not None and self.scale is None:
            return _freeze_node(cast("Node", graph))
        return self.pixels


def prepare_machine(source: RunnerProgram, options: Mapping[str, Any]) -> RuntimePlan:
    """Retain the instructions for each requested execution view."""
    if not isinstance(source, Raster):
        raise TypeError("line machines require raster source")
    if options.keys() - {"scale"}:
        raise TypeError("line machines accept only the scale runtime option")
    program = _Program(source, options.get("scale"))
    return RuntimePlan(
        lambda io: _Machine(program.pixels, io),
        lambda io: _execute(program, io),
    )


def _execute(
    program: Raster | _Program, io: IO, *, scale: int | None = None
) -> CompletionReport:
    if isinstance(program, Raster):
        program = _Program(program, scale)
    _drive(program.native, _LINE_IO(read=io.input_num, write=io.print_num))
    return HALTED_REPORT


def run(program: Raster, io: IO, *, scale: int | None = None) -> None:
    """Execute a Line raster, writing decimal outputs through ``io``."""
    _execute(program, io, scale=scale)
