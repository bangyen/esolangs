"""Independent arithmetic/tape models for the wiki's two raw PNG examples.

https://esolangs.org/wiki/Line, Addition and Multiplication diagrams (190266).
Operands 0..5, two token reads, terminal tape, errors and halt within 1000
steps. Geometry outside these examples remains in the raw regression suite.
"""

import re
from functools import cache
from itertools import product

import pytest

from esolangs.languages.line.interpreter import _execute, _Machine
from esolangs.languages.line.tests import fixture_image
from esolangs.raster import Raster
from esolangs.runtime.io import ScriptedIO
from tests.interpreters.oracle_support import observed, reject_faults, stable_halt
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


def arithmetic_terminal(example, stdin):
    """Predict the terminal tape and IO directly from fixture arithmetic."""
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
    return Raster.from_png(fixture_image(f"{example}.png").read_bytes())


def _check(factory, example, stdin):
    error, trace = observed(
        factory, _fixture(example), stdin, stable_halt(_view), cap=1000
    )
    assert (error, trace[-1]) == arithmetic_terminal(example, stdin), (example, stdin)
    assert trace[0] == ((0, ()), False, "", 0, 0)


def fixture_cases():
    """Yield the common arithmetic and full-trace corpus."""
    examples = ("addition", "multiplication")
    for example, left, right in product(examples, range(6), range(6)):
        yield example, f"{left}\n{right} 99"
    yield from product(
        examples,
        ("", " \n", "1", "1\n", "bad", "1 bad", "1_0 2", "٣ 2", "0 0", " 5\t+5\r\n"),
    )


def check_raw_line():
    for example, stdin in fixture_cases():
        error, (_, _, output, cursor, _) = arithmetic_terminal(example, stdin)
        io = ScriptedIO(stdin)
        if error == "input":
            with pytest.raises(EOFError):
                _execute(_fixture(example), io)
        elif error is None:
            _execute(_fixture(example), io)
            assert (io.getvalue(), io.position(), io.reads) == (output, cursor, 2)
    for example in ("addition", "multiplication"):
        _check(_Machine, example, "2 3 99")

    class WrongTape(_Machine):
        def step(self):
            super().step()
            if self.halted:
                node, at, pointer, tape = self.state
                cells = dict(tape)
                cells[pointer] = cells.get(pointer, 0) + 1
                self.state = node, at, pointer, tuple(sorted(cells.items()))

    reject_faults(_check, _Machine, WrongTape, "addition", "2 3 99")
