"""Revision 189085 Home Row, using a 5x5 matrix and ordered loop delimiters."""

import itertools
import random

import pytest

from esolangs.languages.home_row.interpreter import _Machine
from tests.interpreters.oracle_support import observed
from tests.support import workspace_oracle as workspace

_WORKSPACE = workspace.workspace_model("home-row-v1", "instruction pointer grid")


def _model(source, cap=64):
    program = [c for c in source if c in "asdfjkl;"]
    loops = [i for i, c in enumerate(program) if c == "l"]
    if len(loops) % 2:
        return "syntax", [(None, False, "", 0, 0)]
    matrix, row, col, pc, output = [[0] * 5 for _ in range(5)], 0, 0, 0, ""

    def view():
        grid = tuple(itertools.chain.from_iterable(matrix))
        halted = pc >= len(program) or program[pc] == ";"
        return ((pc, row * 5 + col, grid, pc), halted, output, 0, 0)

    trace = [view()]
    for _ in range(cap):
        if trace[-1][1]:
            break
        command, value = program[pc], matrix[row][col]
        if command in "as":
            matrix[row][col] += 1 if command == "a" else -1
        elif command == "d":
            row = (row + 1) % 5
        elif command == "f":
            col = (col + 1) % 5
        elif command == "j" and value == 0:
            pc += 1
        elif command == "k":
            output += chr(value % 256)
            matrix[row][col] = 0
        elif command == "l":
            ordinal = loops.index(pc)
            if (ordinal % 2 == 0 and value == 0) or (ordinal % 2 == 1 and value != 0):
                pc = loops[ordinal ^ 1]
        pc += 1
        trace.append(view())
    if trace[-1][1]:
        trace.extend([view()] * 3)
    return None, trace


def _agrees(factory, source, *, cap=64):
    expected = _model(source, cap)
    checked = workspace.workspace_view(
        expected[1], _WORKSPACE, lambda row: row[0][:3], lambda m: (*m.state, m.ip)
    )
    assert observed(factory, source, "unused λ", checked, cap=cap) == expected, source
    return expected


def check_raw_home_row():
    corpus = [
        "".join(p) for n in range(4) for p in itertools.product("asdfjkl;", repeat=n)
    ]
    rng = random.Random(20261103)
    corpus += [" \n".join(rng.choices("asdfjkl;", k=16)) for _ in range(128)]
    corpus += [
        "a" + "f" * 5 + "k",
        "a" + "d" * 5 + "k",
        "adaffffk",
        "skk",
        "aalskl",
        "lall",
        "l;",
        "j x a k",
        "λ",
        "a" * 80,
        ";l",
    ]
    results = [_agrees(_Machine, source) for source in corpus]
    results.append(_agrees(_Machine, "a" * 256 + "kk", cap=300))
    assert {error for error, _ in results} == {None, "syntax"}
    assert any(not trace[-1][1] for error, trace in results if error is None)
    assert _model("skk")[1][-1][2] == "\xff\x00"
    assert _model("a" * 256 + "kk", 300)[1][-1][2] == "\x00\x00"
    controls = {
        "add": "a",
        "subtract": "s",
        "down": "d",
        "forward": "f",
        "skip": "j a k",
        "clear": "akk",
        "loop": "l a l",
        "stop": ";a",
        "syntax": "l",
        "input": "a",
        "posthalt": "",
    }
    for fault, source in controls.items():

        class Fault(_Machine):
            mode = fault

            def __init__(self, code, io):
                edits = {
                    "down": ("d", "f"),
                    "forward": ("f", "d"),
                    "skip": ("j", ""),
                    "loop": ("l", ""),
                    "stop": (";", ""),
                    "syntax": ("l", ""),
                }
                if self.mode in edits:
                    code = code.replace(*edits[self.mode])
                super().__init__(code, io)

            def step(self):
                if self.halted:
                    if self.mode == "posthalt":
                        self.io.print_str("extra")
                    return
                pc, _pointer, grid = self.state
                command = self.code[pc]
                if self.mode == "input":
                    self.io.input_char()
                super().step()
                at, ptr, _values = self.state
                if (
                    (self.mode == "add" and command == "a")
                    or (self.mode == "subtract" and command == "s")
                    or (self.mode == "clear" and command == "k")
                ):
                    self.state = at, ptr, grid

        with pytest.raises(AssertionError):
            _agrees(Fault, source)
    workspace.check_erasures(_WORKSPACE, _agrees, _Machine, "asdf;")
    return len(results), len(controls) + 3
