"""Mutable instruction rows rendered as labeled Crement source."""

from itertools import product

import pytest

from esolangs.languages.crement.interpreter import _Machine
from esolangs.runtime._state import WorkspaceModel
from tests.interpreters.oracle_support import observed
from tests.support.workspace_oracle import missing_workspace, workspace_view


def _source(program):
    return "\n".join(
        f":row{i} {'+' if sign > 0 else '-'}{op} @{target - i:+d} {data} * comment"
        for i, (op, sign, target, data) in enumerate(program)
    )


def _model(program):
    rows = [list(row) for row in program]
    pc = 0
    trace = []
    for step in range(17):
        halted = pc >= len(rows)
        snapshot = (pc, tuple(map(tuple, rows))), halted, "", 0, 0
        trace.append(snapshot)
        if halted:
            return None, trace + [snapshot] * 3
        if step == 16:
            break
        op, sign, target, data = rows[pc]
        if op == "J":
            destination = target if data and (data > 0) == (sign > 0) else pc + 1
            if destination < 0:
                return "halt", [*trace, snapshot]
            pc = destination
        else:
            if target < 0:
                return "halt", [*trace, snapshot]
            if target < len(rows):
                rows[target][2 if op == "A" else 3] = data + sign
            pc += 1
    return None, trace


def _check(factory, program):
    def state(machine):
        return machine.ip, tuple(
            (row.opcode, row.polarity, row.address, row.data) for row in machine.memory
        )

    expected = _model(program)
    checked = workspace_view(
        expected[1],
        WorkspaceModel("crement-v1", ("configuration", "input_cursor")),
        lambda row: (row[0], row[-1]),
        state,
    )
    assert observed(factory, _source(program), "unused", checked, cap=16) == expected


def check_raw_crement():
    instructions = tuple(product("ADJ", (-1, 1), (-1, 0, 1, 3), (-2, 0, 2)))
    for first, second in product(instructions, repeat=2):
        _check(_Machine, (first, second))
    _check(_Machine, ())

    class SkippedWrite(_Machine):
        def step(self):
            if not self.halted:
                self.state = type(self.state)(self.ip + 1, self.state.program)

    with pytest.raises(AssertionError):
        _check(SkippedWrite, (("D", 1, 0, 0),))

    for component in ("configuration", "input_cursor"):
        with pytest.raises(AssertionError):
            _check(missing_workspace(_Machine, component), (("D", 1, 0, 0),))
