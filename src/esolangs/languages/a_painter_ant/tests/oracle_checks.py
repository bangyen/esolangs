"""Complex-coordinate model of the ant and its visited rectangle."""

from itertools import product

import pytest

from esolangs.languages.a_painter_ant.interpreter import _Machine
from esolangs.runtime.io import ScriptedIO

_DIRECTIONS = dict(zip("eswn", (1, 1j, -1, -1j), strict=True))


def _check(factory, source):
    commands = source.split()
    io = ScriptedIO("unused")
    machine = factory(source, io)
    ant = 0j
    white = set()
    visited = {ant}

    for command in commands * 4:
        if command == "P":
            white.add(ant)
        elif command == "p":
            white.discard(ant)
        else:
            destination = ant + _DIRECTIONS[command.lower()]
            if (destination in white) == command.isupper():
                ant = destination
            visited.add(ant)
        machine.step()
        assert complex(machine.x, machine.y) == ant
        assert {
            complex(*cell) for cell, value in machine.grid.items() if value
        } == white
        assert {complex(*cell) for cell in machine.visited} == visited
        assert not machine.halted
        assert io.position() == 0
        assert io.getvalue() == ""

    xs = [int(cell.real) for cell in visited]
    ys = [int(cell.imag) for cell in visited]
    picture = []
    for y in range(min(ys), max(ys) + 1):
        row = []
        for x in range(min(xs), max(xs) + 1):
            cell = complex(x, y)
            row.append((".#", "o@")[cell == ant][cell in white])
        picture.append("".join(row))
    machine.interrupt()
    for _ in range(3):
        machine.step()
        assert io.getvalue() == "\n".join(picture)


def check_raw_a_painter_ant():
    for commands in product("nsewNSEWpP", repeat=3):
        _check(_Machine, " ".join(commands))
    for source in ("", "P e W p n S", "P e P s P n W"):
        _check(_Machine, source)
    with pytest.raises(ValueError, match="unknown instruction"):
        _check(_Machine, "n ?")

    class ReversedColours(_Machine):
        def __init__(self, code, io):
            super().__init__(code.swapcase(), io)

    with pytest.raises(AssertionError):
        _check(ReversedColours, "P e W")
