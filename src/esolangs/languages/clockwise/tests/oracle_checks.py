"""Revision 190264 Clockwise, using complex headings and mutable bit queues."""

import itertools
import random

import pytest

from esolangs.languages.clockwise.interpreter import _Machine
from tests.support import workspace_oracle as workspace

_WORKSPACE = workspace.workspace_model(
    "clockwise-v1",
    "row column direction accumulator output_bits input_bits input_cursor",
)


def _model(lines, stdin):
    if not lines:
        return "syntax", [(None, False, "", 0, 0)]
    width = max(map(len, lines))
    reads = any("." in line for line in lines)
    incoming = list("".join(f"{ord(c):07b}" for c in stdin)) if reads else []
    consumed = len(stdin) if reads else 0
    position, direction, acc, pending, output, error = 0j, 1 + 0j, 0, [], "", None

    def view():
        row, col = int(position.imag), int(position.real)
        heading = {1: 0, 1j: 1, -1: 2, -1j: 3}[direction]
        return (
            (
                row,
                col,
                heading,
                acc,
                tuple(pending),
                tuple(incoming),
                (acc,),
                (row, col, heading),
            ),
            position == 0 and direction != 1,
            output,
            consumed,
            consumed,
        )

    trace = [view()]
    for _ in range(64):
        if trace[-1][1]:
            break
        row, col = int(position.imag), int(position.real)
        if not (0 <= row < len(lines) and 0 <= col < width):
            error = "syntax"
        else:
            command = lines[row][col] if col < len(lines[row]) else " "
            if command == "." and not incoming:
                error = "input"
            else:
                if (
                    command == "R"
                    or (command == "?" and acc != 0)
                    or (command == "!" and acc == 0)
                ):
                    direction *= 1j
                if command in "+-":
                    acc += 1 if command == "+" else -1
                elif command == "S":
                    acc = 0
                elif command == ".":
                    bit = incoming.pop(0)
                    incoming.append(bit)
                    acc = acc - acc % 2 + int(bit)
                elif command == ";":
                    pending.append(str(acc % 2))
                    if len(pending) == 7:
                        output += chr(
                            sum(int(b) * 2 ** (6 - i) for i, b in enumerate(pending))
                        )
                        pending.clear()
                position += direction
        trace.append(view())
        if error:
            break
    if not error and trace[-1][1]:
        trace.extend([view()] * 3)
    return error, trace


_agrees = workspace.checker(
    _model,
    (_WORKSPACE, lambda row: (*row[0][:6], row[-1])),
    lambda m: (*m.state, tuple(m.memory), m.ip),
)


def _ring(body):
    return [body + "R", "R" + " " * (len(body) - 1) + "R"]


def check_raw_clockwise():
    atoms = "R?!+-.;Sx"
    corpus = [
        ["".join(p)] for n in range(3) for p in itertools.product(atoms, repeat=n)
    ]
    rng = random.Random(20261103)
    corpus += [
        ["".join(rng.choices(atoms, k=rng.randrange(5))) for _ in range(3)]
        for _ in range(96)
    ]
    corpus += [
        [],
        ["", ""],
        [" R", "RR"],
        [" R", "R."],
        [" R", "", "R R"],
        _ring(".;" * 7),
        _ring(".;" * 14),
        _ring("-;S;" * 4),
        _ring("+;" * 3),
        _ring("-."),
        ["x" * 80],
        ["λ\t"],
    ]
    inputs = ("", "A", "\x02\n", "λ", "\U0010ffff")
    results = [_agrees(_Machine, lines, stdin) for lines in corpus for stdin in inputs]
    assert {error for error, _ in results} == {None, "syntax", "input"}
    assert any(not trace[-1][1] for error, trace in results if error is None)
    assert _model(_ring(".;" * 14), "A")[1][-1][2] == "AA"
    assert _model(_ring("+;" * 3), "")[1][-1][2] == ""
    controls = {
        "turn": ([" R", "RR"], ""),
        "input": (_ring(".;" * 7), "\x02"),
        "flush": (_ring(";"), ""),
        "eof": (["."], ""),
        "halt": ([" R", "RR"], ""),
    }
    for fault, (lines, stdin) in controls.items():

        class Fault(_Machine):
            mode = fault

            def __init__(self, code, io):
                if self.mode == "turn":
                    code = [line.replace("R", " ") for line in code]
                super().__init__(code, io)
                if self.mode == "input":
                    self.state = (*self.state[:5], tuple(reversed(self.state[5])))
                elif self.mode == "eof":
                    self.state = (*self.state[:5], ("0",))

            @property
            def halted(self):
                return False if self.mode == "halt" else super().halted

            def step(self):
                if self.halted:
                    super().step()
                    return
                row, col = self.state[:2]
                command = (
                    self.code[row][col]
                    if 0 <= row < len(self.code) and 0 <= col < len(self.code[row])
                    else ""
                )
                super().step()
                if self.mode == "flush" and command == ";":
                    self.io.print_char("\x00")

        with pytest.raises(AssertionError):
            _agrees(Fault, lines, stdin)
    for component in _WORKSPACE.components:
        with pytest.raises(AssertionError):
            _agrees(workspace.missing_workspace(_Machine, component), ["+S"], "x")
    return len(results), len(controls) + 7
