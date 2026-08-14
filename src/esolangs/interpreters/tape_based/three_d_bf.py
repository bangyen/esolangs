"""Interpreter for 3D Brainfuck.

A brainfuck variant whose memory array is a three-dimensional grid of byte
cells (wrapping 0-255) and whose blocks are placed on a three-dimensional
grid.  ``+``/``-``/``.``/``,`` operate on the array cell at the array
pointer; ``n``/``s``/``e``/``w``/``u``/``d`` move the array pointer along the
six axes; ``N``/``S``/``E``/``W``/``U``/``D`` set the instruction pointer's
heading; ``^``/``V``/``>``/``<``/``"``/``'`` set the generation pointer's
heading; and ``[``/``]`` loop on the array cell, matched by nesting over the
source like brainfuck.

The wiki (``esolangs.org/wiki/3D_Brainfuck``) specifies the instruction set
but not how blocks are initially placed or what the generation pointer emits.
Documented decisions filling those gaps:
- the source is a straight line of blocks along +X, block ``i`` at (i, 0, 0);
- the instruction pointer starts at (0, 0, 0) heading +X, executes the block
  at its cell, then advances one cell in its heading; moving onto a cell with
  no block halts the program;
- a heading block (``N``/``S``/``E``/``W``/``U``/``D``) only changes the
  heading; a heading other than +X immediately walks the pointer off the
  source line and halts;
- the array grid is unbounded, cells are created on demand and wrap 0-255;
- the generation pointer's heading is tracked but no blocks are emitted (the
  wiki's generation semantics are unspecified), so ``^``/``V``/``>``/``<``/
  ``"``/``'`` do not affect execution, and any other character is a comment;
- ``,`` raises :class:`EOFError` when input runs out (repo-wide convention);
  an unbalanced bracket pair is malformed (:class:`ValueError`).
"""

import sys

from esolangs.interpreters.io import IO

_HEADING = {
    "N": (1, 0, 0),
    "S": (-1, 0, 0),
    "E": (0, 0, 1),
    "W": (0, 0, -1),
    "U": (0, 1, 0),
    "D": (0, -1, 0),
}
_ARRAY = {
    "n": (1, 0, 0),
    "s": (-1, 0, 0),
    "e": (0, 0, 1),
    "w": (0, 0, -1),
    "u": (0, 1, 0),
    "d": (0, -1, 0),
}
_GENERATION = {
    "^": (1, 0, 0),
    "V": (-1, 0, 0),
    ">": (0, 0, 1),
    "<": (0, 0, -1),
    '"': (0, 1, 0),
    "'": (0, -1, 0),
}


def _matches(code: str) -> dict[int, int]:
    """Map each bracket to its partner, ``{open: close, close: open}``."""
    stack: list[int] = []
    res: dict[int, int] = {}
    for i, char in enumerate(code):
        if char == "[":
            stack.append(i)
        elif char == "]":
            if not stack:
                raise ValueError(f"unmatched ']' at position {i}")
            open_i = stack.pop()
            res[open_i] = i
            res[i] = open_i
    if stack:
        raise ValueError(f"unmatched '[' at position {stack[-1]}")
    return res


def run(code: str, io: IO) -> None:
    """Run a 3D Brainfuck program."""
    grid = {(i, 0, 0): char for i, char in enumerate(code)}
    m = _matches(code)
    cells: dict[tuple[int, int, int], int] = {}
    ap = (0, 0, 0)
    ip = (0, 0, 0)
    heading = (1, 0, 0)

    while ip in grid:
        char = grid[ip]
        if char in _HEADING:
            heading = _HEADING[char]
        elif char in _ARRAY:
            dx, dy, dz = _ARRAY[char]
            ap = (ap[0] + dx, ap[1] + dy, ap[2] + dz)
        elif char in "+-.,":
            if char == "+":
                cells[ap] = (cells.get(ap, 0) + 1) % 256
            elif char == "-":
                cells[ap] = (cells.get(ap, 0) - 1) % 256
            elif char == ".":
                io.print_char(chr(cells.get(ap, 0)))
            else:
                cells[ap] = io.input_char()
        elif char == "[":
            if cells.get(ap, 0) == 0:
                ip = (m[ip[0]] + 1, 0, 0)
                continue
        elif char == "]":
            if cells.get(ap, 0) != 0:
                ip = (m[ip[0]] + 1, 0, 0)
                continue
        elif char in _GENERATION:
            pass  # the generation heading is tracked but nothing is emitted
        else:
            pass  # any other character is a comment
        ip = (
            ip[0] + heading[0],
            ip[1] + heading[1],
            ip[2] + heading[2],
        )


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.read(), IO())
