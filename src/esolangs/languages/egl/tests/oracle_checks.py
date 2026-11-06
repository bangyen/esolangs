"""Revision 46755 EGL, using coordinate-keyed cells and captured loop positions."""

import itertools
import random
from decimal import Decimal

import pytest

from esolangs.languages.egl.interpreter import _Machine
from esolangs.runtime._state import WorkspaceModel
from tests.interpreters.oracle_support import observed
from tests.support.workspace_oracle import missing_workspace, workspace_view

_WORKSPACE = WorkspaceModel(
    "egl-v1",
    (
        "instruction",
        "row",
        "column",
        "cells",
        "loops",
        "input_cursor",
        "input_reads",
    ),
)


def _parse(source):
    header, colon, code = source.partition(":")
    width, comma, height = header.partition(",")
    if not colon or not comma or not width.isdecimal() or not height.isdecimal():
        raise ValueError
    width, height = int(Decimal(width)), int(Decimal(height))
    if min(width, height) < 1:
        raise ValueError
    depths = list(itertools.accumulate((c == "(") - (c == ")") for c in code))
    if min([0, *depths]) < 0 or (depths and depths[-1]):
        raise ValueError
    return width, height, code


def _closing(code, pc):
    depth = 1
    while depth:
        pc += 1
        depth += (code[pc] == "(") - (code[pc] == ")")
    return pc


def _model(source, stdin):
    try:
        width, height, code = _parse(source)
    except ValueError:
        return "syntax", [(None, False, "", 0, 0)]
    cells, position, loops, pc, consumed, output, error = {}, 0j, [], 0, 0, "", None

    def view():
        grid = tuple(
            cells.get(complex(col, row), 0)
            for row in range(height)
            for col in range(width)
        )
        frames = tuple((at, int(p.imag), int(p.real)) for at, p in loops)
        row, col = int(position.imag), int(position.real)
        return (
            (pc, row, col, grid, frames, grid, (row, col), consumed),
            pc == len(code),
            output,
            consumed,
            consumed,
        )

    trace = [view()]
    for _ in range(64):
        if pc == len(code):
            break
        command, next_pc, next_position = code[pc], pc + 1, position
        value = cells.get(position, 0)
        if command in "><v^":
            next_position += {">": 1, "<": -1, "v": 1j, "^": -1j}[command]
        elif command in "_|%":
            row, col = int(position.imag), int(position.real)
            next_position = complex(
                -col % width if command in "|%" else col,
                -row % height if command in "_%" else row,
            )
        elif command in "+-":
            cells[position] = value + (1 if command == "+" else -1)
        elif command == "x":
            if consumed == len(stdin):
                error = "input"
            else:
                cells[position] = ord(stdin[consumed])
                consumed += 1
        elif command == "=":
            output += str(value)
        elif command == "#":
            output += "".join(
                "|"
                + "|".join(str(cells.get(complex(c, r), 0)) for c in range(width))
                + "|\n"
                for r in range(height)
            )
        elif command == "(":
            if value:
                loops.append((pc, position))
            else:
                next_pc = _closing(code, pc) + 1
        elif command == ")":
            opening, original = loops[-1]
            if cells.get(original, 0):
                next_pc = opening + 1
            else:
                loops.pop()
        if not (0 <= next_position.real < width and 0 <= next_position.imag < height):
            error = "syntax"
        if not error:
            pc, position = next_pc, next_position
        trace.append(view())
        if error:
            break
    if not error and pc == len(code):
        trace.extend([view()] * 3)
    return error, trace


def _agrees(factory, source, stdin):
    expected = _model(source, stdin)
    checked = workspace_view(
        expected[1],
        _WORKSPACE,
        lambda row: (*row[0][:5], row[-1], row[0][-1]),
        lambda m: (*m.state, tuple(m.memory), m.ip, m.snapshot()[-1]),
    )
    assert observed(factory, source, stdin, checked) == expected, (source, stdin)
    return expected


def check_raw_egl():
    atoms = "><v^_|%+-x=#()z"
    bodies = ["".join(p) for n in range(3) for p in itertools.product(atoms, repeat=n)]
    corpus = [header + body for header in ("1,1:", "2,3:", "3,2:") for body in bodies]
    rng = random.Random(20261103)
    corpus += ["3,3:" + "".join(rng.choices(atoms, k=12)) for _ in range(128)]
    corpus += [
        "10,10:v>>_++#",
        "10,1:++(>+++++<-)",
        "2,1:+(>+<-)=",
        "2,1:+(>-)",
        "2,1:(x(>))",
        "2,1:+(>+(-)<-)",
        "2,2:>v%#",
        "1,1:(x)",
        "1,1:+()",
        "1,1:x=x",
        "1,1:" + "z" * 80,
        "\u0662,\u0661:+=",
        "1,1:λ\n",
    ]
    corpus.append("0" * 5000 + "1,1:+=")
    inputs = ("", "A\n", "λ")
    results = [_agrees(_Machine, code, stdin) for code in corpus for stdin in inputs]
    results.extend(
        _agrees(_Machine, code, "unread")
        for code in (
            "",
            "1,1",
            "0,1:",
            "1,0:",
            "-1,1:",
            "1, 1:",
            "1_0,1:",
            "1,1:(",
            "1,1:)",
            "1,1:)(",
            "1,1,1:",
        )
    )
    assert {error for error, _ in results} == {None, "syntax", "input"}
    assert any(not trace[-1][1] for error, trace in results if error is None)
    assert _model("10,1:++(>+++++<-)", "")[1][-1][0][3][1] == 10
    assert (
        _model("10,10:v>>_++#", "")[1][-1][2].splitlines()[-1]
        == "|0|0|2|0|0|0|0|0|0|0|"
    )
    controls = {
        "move": ("2,1:>", ""),
        "reflect": ("2,3:v_", ""),
        "add": ("1,1:+", ""),
        "loop": ("2,1:+(>+<-)", ""),
        "skip": ("1,1:(x)", ""),
        "input": ("1,1:x", "λ"),
        "eof": ("1,1:x", ""),
        "output": ("1,1:=", ""),
        "boundary": ("1,1:>", ""),
        "syntax": ("0,1:", ""),
        "posthalt": ("1,1:", ""),
    }
    for fault, (source, stdin) in controls.items():

        class Fault(_Machine):
            mode = fault

            def __init__(self, code, io):
                if self.mode == "eof":
                    io.input_char = lambda: 0
                super().__init__(
                    code.replace("0,1:", "1,1:") if self.mode == "syntax" else code, io
                )

            def step(self):
                if self.halted:
                    if self.mode == "posthalt":
                        self.io.print_str("extra")
                    return
                pc, row, col, grid, frames = self.state
                command = self.code[pc]
                try:
                    super().step()
                except ValueError:
                    if self.mode != "boundary":
                        raise
                    self.state = pc + 1, row, col, grid, frames
                    return
                at, r, c, values, loops = self.state
                if self.mode == "move" and command == ">":
                    c = col
                elif self.mode == "reflect" and command == "_":
                    r = self.height - 1 - row
                elif self.mode == "add" and command == "+":
                    values = grid
                elif self.mode == "loop" and command == "(":
                    loops = ((pc, row, col + 1),)
                elif self.mode == "skip" and command == "(":
                    at = pc + 1
                elif self.mode == "input" and command == "x":
                    self._input_reads -= 1
                elif self.mode == "output" and command == "=":
                    self.io.print_str("\n")
                self.state = at, r, c, values, loops

        with pytest.raises(AssertionError):
            _agrees(Fault, source, stdin)
    for component in _WORKSPACE.components:
        with pytest.raises(AssertionError):
            _agrees(missing_workspace(_Machine, component), "2,3:+", "")
    return len(results), len(controls) + 7
