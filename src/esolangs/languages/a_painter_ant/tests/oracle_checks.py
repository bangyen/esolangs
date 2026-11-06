"""Complex-coordinate model of the ant and its visited rectangle."""

from itertools import product

import pytest

from esolangs.languages.a_painter_ant.interpreter import _Machine
from esolangs.runtime.io import ScriptedIO

_DIRECTIONS = dict(zip("eswn", (1, 1j, -1, -1j), strict=True))


def _check(factory, source, *, passes=4, cycle=None, output=None):
    commands = "".join(source.split())
    io = ScriptedIO("unused")
    machine = factory(source, io)
    ant = 0j
    white = set()
    painted = {}
    visited = {ant}

    def snapshot(instruction):
        cells = frozenset(
            ((int(cell.real), int(cell.imag)), colour)
            for cell, colour in painted.items()
        )
        return (cells, int(ant.real), int(ant.imag), instruction)

    saved = machine.workspace_snapshot()
    retained = {saved}
    first = snapshot(0) if cycle is not None and cycle.first_pass == 0 else None
    if cycle is not None:
        assert cycle.commands_per_pass == len(commands)
        assert passes == cycle.repeat_pass
    for step, command in enumerate(commands * passes, 1):
        if command == "P":
            white.add(ant)
            painted[ant] = 1
        elif command == "p":
            white.discard(ant)
            painted[ant] = 0
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
        expected = snapshot(step % len(commands))
        assert machine.snapshot() == expected
        assert machine.workspace_snapshot().parts == expected
        assert saved in retained
        if cycle is not None and step == cycle.first_pass * len(commands):
            first = expected
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
    if cycle is not None:
        assert snapshot(0) == first == cycle.state
    rendered = "\n".join(picture)
    if output is not None:
        assert rendered == output
    before_dump = machine.workspace_snapshot()
    machine.interrupt()
    for _ in range(3):
        machine.step()
        assert io.getvalue() == rendered
        assert machine.workspace_snapshot() == before_dump


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
