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


def _render_node(node: Node, heading: tuple[int, int] = (-1, 0)) -> Rows:
    """Render a generated Line graph into shared RGB rows."""
    from .render import render

    canvas = render(node, start_heading=heading, acyclic=True)
    palette = tuple((level, level, level) for level in range(256))
    return tuple(tuple(palette[level] for level in row) for row in canvas.pixels)


@cache
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
    """Choose the more balanced forward or reverse input-test order."""
    from .line_boolean import line_boolean
    from .render import _UNIT
    from .tree_layout import tree_extents

    plans = []
    for reverse in (False, True):
        node = line_boolean(truth_table, reverse=reverse)
        y0, y1, x0, x1 = tree_extents(node)[id(node)]
        width, height = (x1 - x0 + 2) * _UNIT, (y1 - y0 + 2) * _UNIT
        heading = (-1, 0)
        plans.append(((abs(width - height), width * height, width), node, heading))
    _, selected, heading = min(plans, key=lambda plan: plan[0])
    return Raster(
        _materialize=lambda: _render_node(selected, heading), _payload=selected
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


def run(program: Raster, io: ScriptedIO, *, scale: int | None = None) -> None:
    """Execute a Line raster, writing decimal outputs through ``io``."""
    if program._payload is not None and scale is None:  # noqa: SLF001 - language-owned payload
        _run_node(cast("Node", program._payload), io)  # noqa: SLF001
        return
    _run(
        extract_mask(from_grey(_grey_rows(program.rows)), scale=scale),
        IO(read=io.input_num, write=io.print_num),
    )
