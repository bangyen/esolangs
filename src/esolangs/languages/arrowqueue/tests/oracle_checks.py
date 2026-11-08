"""Revision 201574 ArrowQueue, using complex headings and a list FIFO."""

import itertools
import random

import pytest

from esolangs.languages.arrowqueue.interpreter import _Machine
from tests.support import workspace_oracle as workspace

_WORKSPACE = workspace.workspace_model(
    "arrowqueue-v2", "row column direction queue stopped dumped input_cursor"
)


def _model(lines):
    width = max(map(len, lines), default=0)
    position, direction, queue, done, dumped, output = (
        0j,
        1 + 0j,
        [],
        not lines,
        False,
        "",
    )
    headings = {1: 0, 1j: 1, -1: 2, -1j: 3}

    def outside():
        return not (0 <= position.real < width and 0 <= position.imag < len(lines))

    def view():
        row, col, heading = int(position.imag), int(position.real), headings[direction]
        values = tuple(headings[d] for d in queue)
        return (
            (row, col, heading, values, done, dumped, (row, col, heading), values),
            done,
            output,
            0,
            0,
        )

    trace = [view()]
    for _ in range(64):
        if done:
            break
        if outside():
            done = True
        else:
            row, col = int(position.imag), int(position.real)
            command = lines[row][col] if col < len(lines[row]) else " "
            if command == "*":
                direction *= 1j
            elif command == "~":
                queue.append(direction)
            elif command == "+":
                if not queue:
                    done = True
                else:
                    direction = queue.pop(0)
            if not done:
                position += direction
                done = outside()
        trace.append(view())
    if done:
        for _ in range(3):
            if not dumped:
                output = " ".join(str(headings[d]) for d in queue)
                dumped = True
            trace.append(view())
    return None, trace


_agrees = workspace.source_checker(
    _model,
    (_WORKSPACE, lambda row: (*row[0][:6], row[-1])),
    lambda m: (*m.state, m.dumped, m.ip, tuple(m.stack)),
    "unused λ",
)


def check_raw_arrowqueue():
    atoms = "*~+ "
    corpus = [
        ["".join(p)] for n in range(4) for p in itertools.product(atoms, repeat=n)
    ]
    corpus += [
        ["".join(p[:2]), "".join(p[2:])] for p in itertools.product(atoms, repeat=4)
    ]
    rng = random.Random(20261103)
    corpus += [
        ["".join(rng.choices(atoms, k=rng.randrange(5))) for _ in range(4)]
        for _ in range(128)
    ]
    corpus += [
        [],
        ["", ""],
        ["λ\t\r"],
        ["~*", "**"],
        [" *", "", " ~"],
        ["~~*", "  ~", "  *"],
        ["~*  ", " ~  ", " +~~"],
        ["~" * 80],
        [" ~*", "+ *", "*~+"],
        [" ~*", "+~*", "*~+"],
    ]
    results = [_agrees(_Machine, lines) for lines in corpus]
    assert any(not trace[-1][1] for _, trace in results)
    assert _model(["~~"])[1][-1][2] == "0 0"
    assert _model(["~~*", "  ~", "  *"])[1][-1][2] == "0 0 1"
    controls = {
        "turn": ["*"],
        "enqueue": ["~"],
        "empty": ["+"],
        "fifo": ["~*  ", " ~  ", " +~~"],
        "padding": [" *", "", " ~"],
        "initial": [""],
        "input": ["~"],
        "early": ["~"],
        "format": ["~~"],
        "repeat": ["~"],
    }
    for fault, lines in controls.items():

        class Fault(_Machine):
            mode = fault

            def __init__(self, code, io):
                if self.mode == "turn":
                    code = [line.replace("*", " ") for line in code]
                super().__init__(code, io)
                if self.mode == "initial":
                    self.state = (*self.state[:4], True)

            def step(self):
                if self.halted:
                    super().step()
                    if self.mode == "repeat":
                        self.io.print_str("extra")
                    elif self.mode == "format":
                        self.io.print_str("\n")
                    return
                row, col, heading, queue, _ = self.state
                command = self.grid[row][col] if self.width else " "
                if self.mode == "input":
                    self.io.input_char()
                if self.mode == "fifo" and command == "+" and queue:
                    self.state = row, col, heading, tuple(reversed(queue)), False
                super().step()
                r, c, d, q, done = self.state
                if self.mode == "enqueue" and command == "~":
                    self.state = r, c, d, q[:-1], done
                elif self.mode == "empty" and command == "+":
                    self.state = row, col + 1, heading, q, True
                elif self.mode == "padding" and r == 1:
                    self.state = r, c, d, q, True
                elif self.mode == "early" and done:
                    self.io.print_str(" ".join(map(str, q)))
                    self._dumped = True

        with pytest.raises(AssertionError):
            _agrees(Fault, lines)
    workspace.check_erasures(_WORKSPACE, lambda f: _agrees(f, ["~~*"]), _Machine)
    return len(results), len(controls) + 7
