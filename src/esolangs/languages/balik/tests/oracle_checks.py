"""Revision 196949 Balik, using complex coordinates and sparse trit cells."""

import itertools
import random

import pytest

from esolangs.languages.balik.interpreter import _Machine
from esolangs.languages.balik.tests.source_fixtures import _page_loop
from tests.support import workspace_oracle as workspace

_WORKSPACE = workspace.workspace_model(
    "balik-v1", "row column heading pointer tape input_cursor"
)


def _model(source, stdin):
    lines = source.split("\n")
    if any(char not in "+<>*@., \n" for char in source):
        return "syntax", [(None, False, "", 0, 0)]
    width = max(map(len, lines))
    position, direction, pointer, extent, cells = 0j, 1 + 0j, 0, 1, {}
    consumed, output, error = 0, "", None

    def view():
        col, row = int(position.real), int(position.imag)
        heading = {1: 0, 1j: 1, -1: 2, -1j: 3}[direction]
        memory = tuple(cells.get(i, 0) for i in range(extent))
        return (
            (row, col, heading, pointer, memory, (row, col, heading)),
            not (0 <= row < len(lines) and 0 <= col < width),
            output,
            consumed,
            consumed,
        )

    trace = [view()]
    for _ in range(64):
        if trace[-1][1]:
            break
        col, row = int(position.real), int(position.imag)
        command = lines[row][col] if col < len(lines[row]) else " "
        value = cells.get(pointer, 0)
        if command == "+":
            cells[pointer] = (value + 1) % 3
        elif command == ">":
            pointer += 1
            extent = max(extent, pointer + 1)
        elif command == "<":
            if pointer == 0:
                error = "halt"
            else:
                pointer -= 1
        elif command == "*":
            direction *= 1j
        elif command == "@" and value == 0:
            direction = -direction
        elif command == ".":
            output += str(value)
        elif command == ",":
            while consumed < len(stdin) and stdin[consumed].isspace():
                consumed += 1
            if consumed == len(stdin):
                error = "input"
            else:
                char = stdin[consumed]
                consumed += 1
                if char not in "012":
                    error = "argument"
                else:
                    cells[pointer] = (value + int(char)) % 3
        if error is None:
            position += direction
        trace.append(view())
        if error:
            break
    if not error and trace[-1][1]:
        trace.extend([view()] * 3)
    return error, trace


_agrees = workspace.checker(
    _model,
    (_WORKSPACE, lambda row: (*row[0][:5], row[-1])),
    lambda m: (*m.state, tuple(m.memory), m.ip),
)


def check_raw_balik():
    atoms = "+<>*@., "
    corpus = ["".join(p) for n in range(3) for p in itertools.product(atoms, repeat=n)]
    rng = random.Random(20261103)
    corpus += [
        "\n".join("".join(rng.choices(atoms, k=rng.randrange(5))) for _ in range(4))
        for _ in range(128)
    ]
    corpus += [
        "+.+.+.",
        ",>,.<.",
        "  *\n\n  .",
        "*\n*",
        "* *\n* *",
        ">>+<<.>>.",
        "+,.",
        "+@.",
        "@.",
        _page_loop("   ", "+. ", "   "),
        _page_loop("+  ", "+. ", ".  "),
        " " * 80,
        "\t",
        "\r\n",
        "λ",
        "#",
        "x",
    ]
    inputs = ("", "012", " 2\n1\n", "x", " \n", "٣", "\x00", "2x")
    results = [
        _agrees(_Machine, source, stdin) for source in corpus for stdin in inputs
    ]
    assert {error for error, _ in results} == {
        None,
        "syntax",
        "input",
        "argument",
        "halt",
    }
    assert any(not trace[-1][1] for error, trace in results if error is None)
    assert _model(_page_loop("   ", "+. ", "   "), "")[1][-1][2] == "120"
    assert _model(_page_loop("+  ", "+. ", ".  "), "")[1][-1][2] == "1"
    controls = {
        "wrap": ("++", ""),
        "turn": ("*\n.", ""),
        "reverse": ("@.", ""),
        "left": ("<", ""),
        "move": (">", ""),
        "input": ("+,.", "2"),
        "eof": (",", ""),
        "space": (",", " 2"),
        "output": (".", ""),
        "padding": ("  *\n\n  .", ""),
        "syntax": ("x", ""),
        "posthalt": ("", ""),
    }
    for fault, (source, stdin) in controls.items():

        class Fault(_Machine):
            mode = fault

            def __init__(self, code, io):
                if self.mode == "eof":
                    io.input_char = lambda: ord("0")
                elif self.mode == "space":
                    io.input_char = lambda: ord("2")
                super().__init__(
                    code.replace("x", " ") if self.mode == "syntax" else code, io
                )
                if self.mode in ("turn", "reverse"):
                    char = "*" if self.mode == "turn" else "@"
                    self.grid = tuple(line.replace(char, " ") for line in self.grid)

            def step(self):
                if self.halted:
                    super().step()
                    if self.mode == "posthalt":
                        self.io.print_str("extra")
                    return
                row, col, heading, pointer = self.state
                command = self.grid[row][col]
                if self.mode == "left" and command == "<":
                    self.state = row, col + 1, heading, pointer
                    return
                super().step()
                if self.mode == "wrap" and command == "+":
                    self.tape[pointer] %= 2
                elif self.mode == "move" and command == ">":
                    self.state = (*self.state[:3], pointer)
                    self.tape.pop()
                elif self.mode == "input" and command == ",":
                    self.tape[pointer] = 2
                elif self.mode == "output" and command == ".":
                    self.io.print_str("\n")
                elif self.mode == "padding" and command == "*":
                    self.state = len(self.grid), col, heading, pointer

        with pytest.raises(AssertionError):
            _agrees(Fault, source, stdin)
    workspace.check_erasures(_WORKSPACE, _agrees, _Machine, "+>+", "")
    return len(results), len(controls) + 6
