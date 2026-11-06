"""Revision 75747 Back, using complex reflections and marked tape coordinates."""

import itertools
import random

import pytest

from esolangs.languages.back.interpreter import _Machine
from esolangs.runtime._state import WorkspaceModel
from tests.interpreters.oracle_support import observed
from tests.support.workspace_oracle import missing_workspace, workspace_view

_WORKSPACE = WorkspaceModel(
    "back-v1",
    (
        "row",
        "column",
        "direction_row",
        "direction_column",
        "tape",
        "cell",
        "input_cursor",
    ),
)


def _model(lines):
    if not lines or not any(line.strip() for line in lines):
        return "syntax", [(None, False, "", 0, 0)]
    width, height = max(map(len, lines)), len(lines)
    position, direction, pointer, low, high, ones = 0j, 1 + 0j, 0, 0, 0, set()
    done, dumped, output = False, False, ""

    def view():
        row, col = int(position.imag), int(position.real)
        a, b = int(direction.imag), int(direction.real)
        tape = tuple(int(i in ones) for i in range(low, high + 1))
        return (
            (row, col, a, b, tape, pointer - low, done, dumped, tape, (row, col, a, b)),
            done,
            output,
            0,
            0,
        )

    trace = [view()]
    for _ in range(64):
        if done:
            break
        row, col = int(position.imag), int(position.real)
        command = lines[row][col] if col < len(lines[row]) else " "
        distance = 1
        if command in "\\/":
            direction = (1j if command == "\\" else -1j) * direction.conjugate()
        elif command in "<>":
            pointer += 1 if command == ">" else -1
            low, high = min(low, pointer), max(high, pointer)
        elif command == "-":
            ones.symmetric_difference_update({pointer})
        elif command == "+" and pointer not in ones:
            distance = 2
        elif command == "*":
            done = True
        if not done:
            position += distance * direction
            position = complex(int(position.real) % width, int(position.imag) % height)
        trace.append(view())
    if done:
        for _ in range(3):
            if not dumped:
                output = " ".join(str(int(i in ones)) for i in range(low, high + 1))
                dumped = True
            trace.append(view())
    return None, trace


def _agrees(factory, lines):
    expected = _model(lines)
    checked = workspace_view(
        expected[1],
        _WORKSPACE,
        lambda row: (*row[0][:6], row[-1]),
        lambda m: (*m.state, m.dumped, tuple(m.memory), m.ip),
    )
    assert observed(factory, lines, "unused λ", checked) == expected, lines
    return expected


def check_raw_back():
    atoms = "\\/<>-+*x"
    corpus = [
        ["".join(p)] for n in range(3) for p in itertools.product(atoms, repeat=n)
    ]
    corpus += [
        ["".join(p[:2]), "".join(p[2:])] for p in itertools.product("\\/+*", repeat=4)
    ]
    rng = random.Random(20261103)
    corpus += [
        ["".join(rng.choices(atoms, k=rng.randrange(5))) for _ in range(3)]
        for _ in range(64)
    ]
    corpus += [
        [],
        ["", " "],
        ["<-*"],
        [">-<*"],
        ["\\\\", " *"],
        ["//", " *"],
        ["+*x"],
        ["-+*"],
        ["*x", ""],
        ["λ"],
        [">" * 80],
    ]
    results = [_agrees(_Machine, lines) for lines in corpus]
    assert {error for error, _ in results} == {None, "syntax"}
    assert any(not trace[-1][1] for error, trace in results if error is None)
    assert _model(["<-*"])[1][-1][2] == "1 0"
    controls = {
        "mirror": ["\\", "*"],
        "skip": ["+*x"],
        "left": ["<-*"],
        "early": ["*"],
        "repeat": ["*"],
    }
    for fault, lines in controls.items():

        class Fault(_Machine):
            mode = fault

            def __init__(self, code, io):
                if self.mode == "mirror":
                    code = [line.replace("\\", "/") for line in code]
                elif self.mode == "skip":
                    code = [line.replace("+", "x") for line in code]
                super().__init__(code, io)

            def step(self):
                if self.halted:
                    super().step()
                    if self.mode == "repeat":
                        self.io.print_str("extra")
                    return
                before = self.state
                command = self.code[before[0]][before[1]]
                super().step()
                row, col, a, b, tape, _pointer, done = self.state
                if self.mode == "left" and command == "<":
                    self.state = row, col, a, b, before[4], before[5], done
                elif self.mode == "early" and done:
                    self.io.print_str(" ".join(map(str, tape)))
                    self._dumped = True

        with pytest.raises(AssertionError):
            _agrees(Fault, lines)
    for component in _WORKSPACE.components:
        with pytest.raises(AssertionError):
            _agrees(missing_workspace(_Machine, component), [">-* "])
    return len(results), len(controls) + 7
