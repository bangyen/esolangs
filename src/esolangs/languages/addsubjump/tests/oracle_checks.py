"""Dense-memory reference for raw AddSubJump images."""

from itertools import product

import pytest

from esolangs.languages.addsubjump.interpreter import _Machine
from tests.interpreters.oracle_support import observed
from tests.support import workspace_oracle
from tests.support.workspace_oracle import missing_workspace, workspace_view

_WORKSPACE = workspace_oracle.workspace_model(
    "addsubjump-v1", "cells extent instruction zero negative flag_update input_cursor"
)


def _model(words, stdin):
    memory = list(words)
    flags = {-3: 0, -4: 0, -9: 0}
    pc = cursor = 0
    output = ""
    trace = []

    def load(address):
        nonlocal cursor
        if address == -1:
            if cursor == len(stdin):
                raise EOFError
            value = ord(stdin[cursor])
            cursor += 1
            return value
        if address >= 0:
            return memory[address] if address < len(memory) else 0
        return flags.get(address, {-6: 1, -8: -1}.get(address, 0))

    def view():
        return (
            (pc, tuple(memory), flags[-3], flags[-4], flags[-9]),
            not 0 <= pc < len(memory),
            output,
            cursor,
            cursor,
        )

    for step in range(17):
        row = view()
        trace.append(row)
        if row[1]:
            return None, trace + [row] * 3
        if step == 16:
            break
        a, b, target, mode = [load(pc + i) for i in range(4)]
        try:
            sign = -1 if load(mode) > 0 else 1
            operand = load(b)
        except EOFError:
            return "input", [*trace, view()]
        value = operand if a == -1 else load(a) + sign * operand
        if a == -1:
            output += chr(value % 256)
        elif a >= 0:
            memory.extend([0] * max(0, a + 1 - len(memory)))
            memory[a] = value
        elif a in flags:
            flags[a] = value
        if flags[-9]:
            flags[-3], flags[-4] = int(value == 0), int(value < 0)
        pc = target
    return None, trace


def check_raw_addsubjump():
    def state(vm):
        return vm.ip, tuple(vm.memory), vm.zf, vm.nf, vm.fum

    for a, b, mode, stdin in product(
        (-10, -9, -4, -3, -1, 0, 8, 12), (-8, -6, -1, 8), (-8, -6, -1), ("", "AΩ")
    ):
        words = [-9, -6, 4, -7, a, b, -1, mode, 3]
        code = " ".join(map(str, words))
        expected = _model(words, stdin)
        checked = _workspace_view(expected[1], state)
        assert observed(_Machine, code, stdin, checked, cap=16) == expected

    for component in _WORKSPACE.components:
        words = [-9, -6, 4, -7, -1, 8, -1, -8, 3]
        expected = _model(words, "A")
        with pytest.raises(AssertionError):
            observed(
                missing_workspace(_Machine, component),
                " ".join(map(str, words)),
                "A",
                _workspace_view(expected[1], state),
                cap=16,
            )

    class PhantomCell(_Machine):
        def step(self):
            super().step()
            (cells, length), *rest = self.state
            self.state = (({**cells, -10: 1}, length), *rest)

    words = [-10, -6, -1, -7]
    with pytest.raises(AssertionError):
        observed(
            PhantomCell,
            " ".join(map(str, words)),
            "",
            _workspace_view(_model(words, "")[1], state),
            cap=16,
        )


def _workspace_view(trace, view):
    return workspace_view(
        trace,
        _WORKSPACE,
        lambda row: (
            frozenset((i, value) for i, value in enumerate(row[0][1]) if value),
            len(row[0][1]),
            row[0][0],
            *row[0][2:],
            row[-1],
        ),
        view,
    )
