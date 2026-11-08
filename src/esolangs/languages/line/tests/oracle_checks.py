"""Independent arithmetic/tape models for the wiki's two raw PNG examples.

https://esolangs.org/wiki/Line, Addition and Multiplication diagrams (190266).
Operands 0..5, two token reads, terminal tape, errors and halt within 1000
steps. Geometry outside these examples remains in the raw regression suite.
"""

import re
from functools import cache
from itertools import product
from pathlib import Path

import pytest

from esolangs.languages.line.interpreter import _execute, _Machine
from esolangs.raster import Raster
from esolangs.runtime.io import ScriptedIO
from tests.interpreters.oracle_support import observed, overread, stable_halt, stalled
from tests.support.model_input import token_span


def _read(stdin, cursor):
    start, cursor = token_span(stdin, cursor)
    if start == cursor:
        return None, cursor, "input"
    text = stdin[start:cursor]
    if not re.fullmatch(r"[+-]?[0-9]+", text):
        return None, cursor, "argument"
    value = int(text)
    assert 0 <= value <= 5, "example operand outside model domain"
    return value, cursor, None


def _model(example, stdin):
    cells, pointer, cursor = {}, 0, 0
    for pointer in (0, 1):
        value, cursor, error = _read(stdin, cursor)
        if error:
            state = pointer, tuple(sorted(cells.items()))
            return error, (state, False, "", cursor, cursor)
        cells[pointer] = value
    if example == "addition":
        cells[0] += cells[1]
        cells[1], pointer = 0, 0
    else:
        assert example == "multiplication"
        cells[2] = 0
        # Each outer pass traverses the restoring loop's scratch cell,
        # even when the multiplier is zero; no pass leaves it unvisited.
        for _ in range(cells[0]):
            cells[2] += cells[1]
            cells[3] = 0
        cells[0], pointer = 0, 2
    state = pointer, tuple(sorted(cells.items()))
    return None, (state, True, str(cells[pointer]), cursor, cursor)


def _view(machine):
    return machine.state[2], machine.state[3]


@cache
def _fixture(example):
    path = Path(__file__).parent / "fixtures" / (example + ".png")
    return Raster.from_png(path.read_bytes())


def _check(factory, example, stdin):
    error, trace = observed(
        factory, _fixture(example), stdin, stable_halt(_view), cap=1000
    )
    assert (error, trace[-1]) == _model(example, stdin), (example, stdin)
    assert trace[0] == ((0, ()), False, "", 0, 0)
    if factory is _Machine and error in (None, "input"):
        io = ScriptedIO(stdin)
        if error:
            with pytest.raises(EOFError):
                _execute(_fixture(example), io)
        else:
            _execute(_fixture(example), io)
            assert (io.getvalue(), io.position(), io.reads) == (*trace[-1][2:4], 2)


def check_raw_line():
    for example, left, right in product(
        ("addition", "multiplication"), range(6), range(6)
    ):
        _check(_Machine, example, f"{left}\n{right} 99")
    for example, stdin in product(
        ("addition", "multiplication"),
        ("", " \n", "1", "1\n", "bad", "1 bad", "1_0 2", "٣ 2", "0 0", " 5\t+5\r\n"),
    ):
        _check(_Machine, example, stdin)

    class WrongTape(_Machine):
        def step(self):
            super().step()
            if self.halted:
                node, at, pointer, tape = self.state
                cells = dict(tape)
                cells[pointer] = cells.get(pointer, 0) + 1
                self.state = node, at, pointer, tuple(sorted(cells.items()))

    for factory in (stalled(_Machine), WrongTape, overread(_Machine)):
        with pytest.raises(AssertionError):
            _check(factory, "addition", "2 3 99")
