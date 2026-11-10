"""Integer instruction oracle for the shared code and stack array."""

from itertools import product
from operator import add, eq, mul, sub

import pytest

from esolangs.languages.chicken.interpreter import _Machine
from esolangs.runtime._state import WorkspaceModel
from esolangs.runtime.io import ScriptedIO
from tests.support.workspace_oracle import WorkspaceWitness, missing_workspace

_OPERATIONS = {2: add, 3: sub, 4: mul, 5: eq}


def check_raw_chicken():
    for left, right, opcode in product((0, 1, 7, 65, 255), (0, 1, 2, 66), _OPERATIONS):
        counts = (left + 10, right + 10, opcode)
        source = "\n".join(" ".join(["chicken"] * count) for count in counts)
        io = ScriptedIO("unused")
        machine = _Machine(source, io)
        expected = _OPERATIONS[opcode](left, right)
        for offset, operands in enumerate(([left], [left, right], [expected]), 3):
            machine.step()
            assert machine.ip == offset
            assert machine.stack[6:] == operands
            assert not machine.halted
            assert io.getvalue() == ""
        machine.step()
        assert machine.halted
        output = str(expected).lower()
        assert io.getvalue() == output
        machine.step()
        assert io.getvalue() == output

    # Load from input and the shared array, then exercise a write into code.
    for index, stdin in product(range(4), ("", "aΩz", "0123")):
        expected = stdin[index] if index < len(stdin) else "undefined"
        _output_case((10 + index, 6, 1), stdin, expected)
    for scalar in (0, 65, 937):
        _output_case((10 + scalar, 9), "", chr(scalar))
    for condition, offset in product((0, 1), (0, 1)):
        expected = "0" if condition and offset else "chicken"
        _output_case((10 + condition, 10 + offset, 8, 1), "", expected)
    # Jump over the output arm, then jump back to it with offset -7.
    _output_case((11, 12, 8, 1, 0, 11, 10, 17, 3, 8), "", "chicken")
    _output_case((11, 15, 7, 10), "", "chicken")
    _output_case((12, 6, 0, 10, 2), "", "12")
    _latch_witness(_Machine)
    with pytest.raises(AssertionError):
        _latch_witness(missing_workspace(_Machine, "stopped"))

    from .reference_checks import check_raw_chicken_reference

    check_raw_chicken_reference()


def _output_case(counts, stdin, expected):
    source = "\n".join(" ".join(["chicken"] * count) for count in counts)
    io = ScriptedIO(stdin)
    machine = _Machine(source, io)
    for _ in range(12):
        if machine.halted:
            break
        machine.step()
    assert machine.halted, counts
    assert io.position() == len(stdin)
    assert io.getvalue() == expected, (counts, stdin)


def _latch_witness(factory):
    io = ScriptedIO()
    machine = factory("chicken", io)
    model = WorkspaceModel(
        "chicken-v2", ("instruction", "cells", "stopped", "input_cursor")
    )
    witness = WorkspaceWitness(model)
    cells = ((), "", 1, 0)
    final = (4, cells, True, "chicken")
    rows = [
        (2, cells, False, ""),
        (3, (*cells, "chicken"), False, ""),
        final,
        *[final] * 3,
    ]
    for index, (pointer, expected_cells, stopped, output) in enumerate(rows):
        witness.sample(
            machine.workspace_snapshot(), (pointer, expected_cells, stopped, 0)
        )
        assert (machine.ip, machine.halted, io.getvalue()) == (pointer, stopped, output)
        assert (io.reads, io.past_end, io.position(), io.progress()) == (1, 0, 0, 0)
        if index + 1 < len(rows):
            machine.step()
    witness.finish()
    assert witness.expected.written[2]
    assert witness.measured.bits == witness.expected.bits == 62
