"""Flat tape/beam model of LaserFuck's memory and laser-movement sections.

https://esolangs.org/wiki/LaserFuck, revision 191932. Four initial headings,
scripted splits, all mirrors, bridges and tape I/O, bounded to 48 steps.
Used-cell, framing, second-start and post-halt choices follow Decisions.
"""

from itertools import product

import pytest

from esolangs.languages.laserfuck.interpreter import _Machine
from tests.interpreters.oracle_support import observed, stalled
from tests.interpreters.semantic_oracles import signed32


class _Draw:
    def __init__(self, heading, split):
        self.first, self.split = heading, split

    def randbelow(self, upper):
        if self.first is None:
            return self.split % upper
        value, self.first = self.first, None
        return value % upper


class _Model:
    def __init__(self, source, heading, split):
        width = max(map(len, source), default=0)
        self.grid = [line.ljust(width) for line in source]
        self.tape, self.pointer, self.beams, self.index = [(0, 0)], 0, [], 0
        self.bridges, self.position = set(), (0, 0, 0)
        self.second = self.dumped = False
        self.cursor = self.reads = self.draws = 0
        self.split, self.output = split, ""
        for y, line in enumerate(source):
            for x, char in enumerate(line):
                if char == "o":
                    if self.beams:
                        self.second = True
                        return
                    self.position = (y, x, heading)
                    self.beams.append(self.position)
                    self.draws += 1

    @property
    def halted(self):
        return self.second or not self.beams

    def state(self):
        return (
            self.pointer,
            tuple(self.tape),
            tuple(self.beams),
            self.index,
            frozenset(self.bridges),
            self.position,
            self.second,
            self.dumped,
            self.reads,
            self.draws,
        )

    def row(self):
        return self.state(), self.halted, self.output, self.cursor, self.cursor

    def write(self, value):
        self.tape[self.pointer] = signed32(value), 1

    def operate(self, command, y, x, direction, byte):
        if command == "x":
            self.beams.pop(self.index)
            self.bridges = {
                i - (i > self.index) for i in self.bridges if i != self.index
            }
            if self.beams:
                self.index %= len(self.beams)
            return
        value = self.tape[self.pointer][0]
        if command == ">":
            self.pointer += 1
            if self.pointer == len(self.tape):
                self.tape.append((0, 0))
        elif command == "<":
            if self.pointer:
                self.pointer -= 1
            else:
                self.tape.insert(0, (0, 0))
        elif command == "+":
            self.write(value + 1)
        elif command == "-":
            self.write(value - 1)
        elif command == ",":
            self.write(byte)
        elif command == "*":
            self.beams.append((y, x, (2 if direction < 2 else 0) + self.split % 2))
        elif command == "#":
            self.bridges.add(self.index)
        elif command == "/":
            direction = (3, 2, 1, 0)[direction]
        elif command == "\\":
            direction = (2, 3, 0, 1)[direction]
        elif command in "_(" and direction < 2 and (command == "_" or value):
            direction = 1 - direction
        elif command in "|)" and direction >= 2 and (command == "|" or value):
            direction = 5 - direction
        elif command in "^v{}":
            direction = "^v{}".index(command)
        self.beams[self.index] = (y, x, direction)
        self.index = (self.index + 1) % len(self.beams)

    def step(self, stdin):
        if self.halted:
            if not self.dumped:
                values = [v for v, painted in self.tape if painted and v >= 0]
                self.output = (
                    "".join(map(chr, values))
                    if self.grid and self.grid[0].startswith("ÿ")
                    else "\n".join(map(str, values))
                )
                self.dumped = True
            return None
        y, x, direction = self.beams[self.index]
        dy, dx = ((-1, 0), (1, 0), (0, -1), (0, 1))[direction]
        y, x = y + dy, x + dx
        self.position = y, x, direction
        if self.index in self.bridges:
            self.bridges.remove(self.index)
            self.beams[self.index] = self.position
            self.index = (self.index + 1) % len(self.beams)
            return None
        command = (
            self.grid[y][x]
            if 0 <= y < len(self.grid) and 0 <= x < len(self.grid[0])
            else "x"
        )
        byte = None
        if command == ",":
            if self.cursor == len(stdin):
                return "input"
            byte = ord(stdin[self.cursor])
            self.cursor, self.reads = self.cursor + 1, self.reads + 1
        if command == "*":
            self.draws += 1
        self.operate(command, y, x, direction, byte)
        return None


def _model(source, stdin, heading, split):
    machine = _Model(source, heading, split)
    trace = [machine.row()]
    for _ in range(48):
        if machine.halted:
            break
        error = machine.step(stdin)
        trace.append(machine.row())
        if error:
            return error, trace
    if machine.halted:
        for _ in range(3):
            machine.step(stdin)
            trace.append(machine.row())
    return None, trace


def _view(machine):
    return (
        machine.ptr,
        tuple(cell for chunk in machine.tape for cell in chunk),
        tuple(machine.lsrs),
        machine.ind,
        machine.jmp,
        machine.pos,
        machine._second_start,
        machine._dumped,
        machine._input_reads,
        machine._draws,
    )


def _check(factory, code, stdin="unused", heading=3, split=0):
    def build(source, io):
        return factory(source, io, _Draw(heading, split))

    assert observed(build, code, stdin, _view, cap=48) == _model(
        code, stdin, heading, split
    ), (code, stdin, heading, split)


def check_raw_laserfuck():
    for length in range(4):
        for commands, heading in product(product("+-<>#x, }", repeat=length), range(4)):
            _check(_Machine, ["o" + "".join(commands) + "x"], "A\nλ", heading)
    for command, heading, split in product("_()|/\\*^v{}", range(4), (0, 1)):
        _check(
            _Machine,
            [" xxx ", "x" + command + "+x", "x+o+x", "x+" + command + "x", " xxx "],
            heading=heading,
            split=split,
        )
        _check(_Machine, ["o+" + command + "x"], heading=heading, split=split)
    for source, stdin in product(
        (["o,x"], ["ÿo,>+x"], ["o+-x"], ["o-<+>x"]), ("", "A\n", "\x00", "λ")
    ):
        _check(_Machine, source, stdin)
    for source in ([], [""], ["oo"], ["nothing"], [" ", "o+x"]):
        _check(_Machine, source)

    class WrongHeading(_Machine):
        def __init__(self, code, io, _rng):
            super().__init__(code, io, _Draw(0, 0))

    class DoubleDump(_Machine):
        def dump(self):
            super().dump()
            super().dump()

    for factory in (stalled(_Machine), WrongHeading, DoubleDump):
        with pytest.raises(AssertionError):
            _check(factory, ["o+x"])
