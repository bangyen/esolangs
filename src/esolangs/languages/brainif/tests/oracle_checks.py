"""Signed-coordinate byte tape with guards evaluated on each visit."""

from itertools import product

import pytest

from esolangs.languages.brainif.interpreter import _Machine
from esolangs.runtime._state import WorkspaceModel
from tests.interpreters.oracle_support import observed
from tests.support.workspace_oracle import check_erasures, workspace_view

_WORKSPACE = WorkspaceModel(
    "brainif-v1", ("cells", "instruction", "pointer", "input_cursor")
)


def _parse(line):
    guard, value, *words = line.split()
    if guard != "if":
        raise ValueError
    command = " ".join(words)
    if words[:1] == ["goto"] and len(words) == 2 and int(words[1]) > 0:
        return int(value), int(words[1]) - 1
    aliases = {"inc": "increment", "move left": "left", "move right": "right"}
    command = aliases.get(command, command)
    if command not in {"increment", "left", "right", "input", "output"}:
        raise ValueError
    return int(value), command


def _model(lines, stdin):
    tape = {}
    pc = head = left = right = cursor = 0
    output = ""
    trace = []
    failure = None
    for step in range(33):
        halted = pc >= len(lines)
        cells = tuple(tape.get(i, 0) for i in range(left, right + 1))
        trace.append(((pc, head - left, cells), halted, output, cursor, cursor))
        if failure:
            break
        if halted:
            trace.extend([trace[-1]] * 3)
            break
        if step == 32:
            break
        if not lines[pc].strip():
            pc += 1
            continue
        try:
            value, command = _parse(lines[pc])
        except ValueError:
            failure = "syntax"
            continue
        if tape.get(head, 0) == value:
            match command:
                case int(target):
                    pc = target
                    continue
                case "left":
                    head -= 1
                    left = min(left, head)
                case "right":
                    head += 1
                    right = max(right, head)
                case "increment":
                    tape[head] = (value + 1) % 256
                case "input":
                    if cursor == len(stdin):
                        failure = "input"
                        continue
                    tape[head] = ord(stdin[cursor]) % 256
                    cursor += 1
                case "output":
                    output += chr(value)
        pc += 1
    return failure, trace


def _check(factory, lines, stdin):
    expected = _model(lines, stdin)

    checked = workspace_view(
        expected[1],
        _WORKSPACE,
        lambda row: (row[0][2], row[0][0], row[0][1], row[-1]),
        lambda machine: (machine.ind, machine.ptr, machine.cells),
    )
    assert observed(factory, lines, stdin, checked, cap=32) == expected, lines


def check_raw_brainif():
    commands = ("inc", "move left", "right", "goto 1", "input", "output")
    lines = [f"if {value} {op}" for value, op in product((0, 1, 255), commands)]
    cases = [list(pair) for pair in product(lines, repeat=2)]
    cases += [
        ["if 0 left", "", "if 0 inc", "if 1 output", "if 1 goto 8"],
        ["if 0 input", "if 255 increment", "if 0 output"],
        ["if 9 goto 0"],
        ["if 9 move up"],
        ["if 9 increment extra"],
        ["if 0"],
        [],
    ]
    for code, stdin in product(cases, ("", "ÿ", "Ł")):
        _check(_Machine, code, stdin)

    class StaleGuard(_Machine):
        def step(self):
            super().step()
            if self.ind == 1:
                self.code = [self.code[0], "if 0 output"]

    with pytest.raises(AssertionError):
        _check(StaleGuard, ["if 0 inc", "if 1 output"], "")
    check_erasures(
        _WORKSPACE, lambda f: _check(f, ["if 0 inc", "if 1 right"], ""), _Machine
    )
