"""Translate between Brainloller rasters and their Brainfuck command path."""

from __future__ import annotations

from esolangs.line import Raster

_COMMANDS = {
    (255, 0, 0): ">",
    (128, 0, 0): "<",
    (0, 255, 0): "+",
    (0, 128, 0): "-",
    (0, 0, 255): ".",
    (0, 0, 128): ",",
    (255, 255, 0): "[",
    (128, 128, 0): "]",
}
_CLOCKWISE = (0, 255, 255)
_COUNTERCLOCKWISE = (0, 128, 128)
_COLOURS = {command: colour for colour, command in _COMMANDS.items()}
_NOP = (255, 255, 255)


def decode(program: Raster) -> str:
    """Return the Brainfuck commands visited by a Brainloller instruction path."""
    y = x = 0
    dy, dx = 0, 1
    height, width = len(program.rows), len(program.rows[0])
    seen: set[tuple[int, int, int, int]] = set()
    commands: list[str] = []
    while 0 <= y < height and 0 <= x < width:
        state = (y, x, dy, dx)
        if state in seen:
            raise ValueError("Brainloller instruction path cycles")
        seen.add(state)
        pixel = program.rows[y][x]
        command = _COMMANDS.get(pixel)
        if command is not None:
            commands.append(command)
        elif pixel == _CLOCKWISE:
            dy, dx = dx, -dy
        elif pixel == _COUNTERCLOCKWISE:
            dy, dx = -dx, dy
        y += dy
        x += dx
    return "".join(commands)


def encode(code: str) -> Raster:
    """Return a one-row Brainloller raster for Brainfuck ``code``.

    Non-command characters become white no-ops, preserving their positions.
    """
    if not code:
        raise ValueError("Brainloller source needs at least one pixel")
    return Raster((tuple(_COLOURS.get(char, _NOP) for char in code),))
