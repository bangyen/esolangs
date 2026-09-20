"""Line image-program source and interpreter adapter.

Line encodes a Brainfuck-style program as a black path on a white raster.
Turns and kinks select tape, arithmetic, input, and output operations; a
T-junction branches on the current cell.  The filled arrowhead chooses the
entry point and initial direction.  Source must be a lossless PNG because
anti-aliasing changes the path geometry.
"""

from __future__ import annotations

from functools import cache
from typing import TYPE_CHECKING, cast

from esolangs.interpreters.io import ScriptedIO
from esolangs.raster import Raster, Rows

from .extract import extract_mask
from .mask import from_grey
from .simulate import IO
from .simulate import run as _run

if TYPE_CHECKING:
    from .render import Node


def _grey_rows(rows: Rows) -> list[bytearray]:
    """Reduce RGB rows to Line's greyscale input representation."""
    return [
        bytearray(
            (red * 19595 + green * 38470 + blue * 7471 + 0x8000) >> 16
            for red, green, blue in row
        )
        for row in rows
    ]


def _render_node(node: Node) -> Rows:
    """Render a generated Line graph into shared RGB rows."""
    from .render import render

    canvas = render(node)
    return tuple(tuple((level, level, level) for level in row) for row in canvas.pixels)


@cache
def generate(truth_table: str) -> Raster:
    """Return a Line raster computing ``truth_table``."""
    from .line_boolean import line_boolean

    node = line_boolean(truth_table)
    return Raster(
        _materialize=lambda: _render_node(node),
        _payload=node,
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


def run(program: Raster, io: ScriptedIO) -> None:
    """Execute a Line raster, writing decimal outputs through ``io``."""
    if program._payload is not None:  # noqa: SLF001 - language-owned payload
        _run_node(cast("Node", program._payload), io)  # noqa: SLF001
        return
    _run(
        extract_mask(from_grey(_grey_rows(program.rows))),
        IO(read=io.input_num, write=io.print_num),
    )
