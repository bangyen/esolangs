"""Line image-program source and interpreter adapter.

Line encodes a Brainfuck-style program as a black path on a white raster.
Turns and kinks select tape, arithmetic, input, and output operations; a
T-junction branches on the current cell.  The filled arrowhead chooses the
entry point and initial direction.  Source must be a lossless PNG because
anti-aliasing changes the path geometry.
"""

from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING, cast

from esolangs.interpreters.io import ScriptedIO
from esolangs.raster import Pixel, Raster, Rows

from .extract import extract_mask
from .mask import from_grey
from .simulate import IO
from .simulate import run_compiled as _run_compiled

if TYPE_CHECKING:
    from .render import Node
    from .simulate import _Compiled


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


def _render_node(
    node: Node, heading: tuple[int, int] = (-1, 0), *, compact: bool = True
) -> Rows:
    """Render a generated Line graph into shared RGB rows."""
    from .render import render

    canvas = render(node, start_heading=heading, acyclic=True, compact=compact)
    palette = tuple((level, level, level) for level in range(256))
    cache: dict[bytes, tuple[Pixel, ...]] = {}
    rows = []
    for row in canvas.pixels:
        key = bytes(row)
        pixels = cache.get(key)
        if pixels is None:
            pixels = tuple(palette[level] for level in row)
            if len(cache) < 1024:
                cache[key] = pixels
        rows.append(pixels)
    return tuple(rows)


@lru_cache(maxsize=8)
def _generate(truth_table: str) -> Raster:
    """Return a Line raster computing ``truth_table``."""
    from .line_boolean import line_boolean

    node = line_boolean(truth_table)
    return Raster(
        _materialize=lambda: _render_node(node),
        _payload=node,
    )


def generate(truth_table: str, *, scale: int = 1) -> Raster:
    """Return a Line raster enlarged by an integer pixel factor."""
    return _generate(truth_table).upscaled(scale)


def balance(truth_table: str, _default: Raster) -> Raster:
    """Choose the most balanced compact or previous forward/reverse tree."""
    from .line_boolean import line_boolean
    from .render import _UNIT
    from .tree_layout import tree_extents

    plans = []
    previous = []
    for reverse in (False, True):
        node = line_boolean(truth_table, reverse=reverse)
        y0, y1, x0, x1 = tree_extents(node)[id(node)]
        width, height = (x1 - x0 + 2) * _UNIT, (y1 - y0 + 2) * _UNIT
        heading = (-1, 0)
        plans.append(((abs(width - height), width * height, width), node, heading))
        y0, y1, x0, x1 = tree_extents(node, compact=False)[id(node)]
        width, height = (x1 - x0 + 2) * _UNIT, (y1 - y0 + 2) * _UNIT
        previous.append(((abs(width - height), width * height, width), node, heading))
    score, selected, heading = min(plans, key=lambda plan: plan[0])
    old_score, old_selected, old_heading = min(previous, key=lambda plan: plan[0])
    # 01101110 ties in imbalance but grows 1,187,200 -> 1,276,000 pixels.
    compact = score <= old_score
    if not compact:
        selected, heading = old_selected, old_heading
    return Raster(
        _materialize=lambda: _render_node(selected, heading, compact=compact),
        _payload=selected,
    )


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


@lru_cache(maxsize=8)
def _compiled(program: Raster, scale: int | None = None) -> _Compiled:
    from .simulate import compile_program

    return compile_program(
        extract_mask(from_grey(_grey_rows(program.rows)), scale=scale)
    )


def _source_view(program: Raster) -> str:
    """Return the cropped, normalized pixel grid used by the walker."""
    from .extract import crop_to_content, normalize_scale

    mask = normalize_scale(crop_to_content(from_grey(_grey_rows(program.rows))))
    return "\n".join(
        "".join("#" if mask[y, x] else " " for x in range(mask.width))
        for y in range(mask.height)
    )


class _Machine:
    """Step a compiled pixel path, retaining tape and input state."""

    ip_shape = "grid"

    def __init__(
        self, program: Raster, io: ScriptedIO, *, scale: int | None = None
    ) -> None:
        from collections import defaultdict

        from .simulate import _Compiled

        self.node: _Compiled | None = _compiled(program, scale)
        self.at = 0
        self.pointer = 0
        self.tape: dict[int, int] = defaultdict(int)
        self.io = io

    @property
    def halted(self) -> bool:
        return self.node is None

    @property
    def ip(self) -> tuple[int, ...] | None:
        if self.node is None:
            return None
        return (
            self.node.positions[self.at]
            if self.at < len(self.node.ops)
            else self.node.end
        )

    @property
    def memory(self) -> tuple[int, ...]:
        return tuple(
            self.tape.get(i, 0)
            for i in range(min(self.tape, default=0), max(self.tape, default=0) + 1)
        )

    @property
    def stack(self) -> tuple[object, ...]:
        return ()

    def snapshot(self) -> tuple[object, ...]:
        cells = tuple(
            sorted((cell, value) for cell, value in self.tape.items() if value)
        )
        return id(self.node), self.at, self.pointer, cells, self.io.position()

    def step(self) -> None:
        node = self.node
        if node is None:
            return
        if self.at == len(node.ops):
            if node.zero is None and node.nonzero is None:
                self.node = node.goto
            else:
                self.node = node.zero if self.tape[self.pointer] == 0 else node.nonzero
            self.at = 0
            return
        call = node.ops[self.at]
        if call.op == "+":
            self.tape[self.pointer] += call.count
        elif call.op == "-":
            self.tape[self.pointer] -= call.count
        elif call.op == ">":
            self.pointer += 1
        elif call.op == "<":
            self.pointer -= 1
        elif call.op == "i":
            self.tape[self.pointer] = self.io.input_num()
        elif call.op == "o":
            self.io.print_num(self.tape[self.pointer])
        else:  # pragma: no cover - classify_ops emits only the six cases above
            raise ValueError(f"unknown opcode {call.op!r}")
        self.at += 1


def run(program: Raster, io: ScriptedIO, *, scale: int | None = None) -> None:
    """Execute a Line raster, writing decimal outputs through ``io``."""
    if program._payload is not None and scale is None:  # noqa: SLF001 - language-owned payload
        _run_node(cast("Node", program._payload), io)  # noqa: SLF001
        return
    _run_compiled(
        _compiled(program, scale),
        IO(read=io.input_num, write=io.print_num),
    )
