"""Revision 188584 NOR rules, using list queues and arithmetic shifts."""

import itertools
import random

import pytest

from esolangs.exceptions import HaltError
from esolangs.languages.nor_machine.interpreter import _Machine
from tests.support import workspace_oracle as workspace

_WORKSPACE = workspace.workspace_model(
    "nor-machine-v1", "instruction queue stopped input_cursor"
)


def _parts(row):
    return *row[0], row[1], row[-1]


def _integers(text):
    numbers = []
    for token in text.split():
        digits = token[1:] if token[:1] in "+-" else token
        if not digits or any(c not in "0123456789" for c in digits):
            raise ValueError
        numbers.append(int(token))
    return numbers


def _model(source, stdin):
    program = "".join(source.split())
    if not program or any(c not in "IAXVLR" for c in program):
        return "syntax", [(None, False, "", 0, 0)]
    pc, queue, consumed, output, halted, error = 0, None, 0, "", False, None

    def view():
        return (
            (pc, None if queue is None else tuple(queue)),
            halted,
            output,
            consumed,
            consumed,
        )

    trace = [view()]
    for _ in range(64):
        if halted:
            break
        if queue is None:
            consumed = len(stdin)
            try:
                queue = _integers(stdin)
            except ValueError:
                error = "argument"
                trace.append(view())
                break
        command = program[pc]
        if command == "V" and len(queue) == 1:
            output, halted = str(queue[0]), True
        elif len(queue) < (2 if command in "XV" else 1):
            error = "halt"
        else:
            first = queue.pop(0)
            if command == "I":
                queue.append(first)
            elif command == "A":
                queue += [first, first]
            elif command == "X":
                queue += [queue.pop(0), first]
            elif command == "V":
                queue.append((~first) & (~queue.pop(0)))
            elif command == "L":
                queue.append(first * 2)
            else:
                queue.append(first // 2)
            pc = (pc + 1) % len(program)
        trace.append(view())
        if error:
            break
    if halted:
        trace.extend([view()] * 3)
    return error, trace


_agrees = workspace.checker(
    _model,
    (_WORKSPACE, _parts),
    lambda m: (m.ind, None if m.queue is None else tuple(m.queue)),
)


def check_raw_nor_machine():
    corpus = [
        "".join(p) for n in range(1, 4) for p in itertools.product("IAXVLR", repeat=n)
    ]
    rng = random.Random(20261103)
    corpus += [" \n".join(rng.choices("IAXVLR", k=12)) for _ in range(128)]
    corpus += ["", " \n", "rot", "A#", "v", "λ", "I" * 80, "V V", "XLRVV", "IRVV"]
    inputs = ("", "1", "-3", "0 1", "4 3 -2", " +1 \n -2 \t3 ", "1 x 3", "٣")
    results = [_agrees(_Machine, code, stdin) for code in corpus for stdin in inputs]
    results.extend(
        _agrees(_Machine, "V", stdin)
        for stdin in ("+", "1_0", "1.0", "--1", "0\x001", " ", "-0", str(1 << 80))
    )
    assert {error for error, _ in results} == {None, "syntax", "argument", "halt"}
    assert any(not trace[-1][1] for error, trace in results if error is None)
    assert _model("XLRVV", "4 3")[1][-1][2] == "-7"
    assert _model("IRVV", "8 1")[1][-1][2] == "-9"
    controls = {
        "rotate": ("I", "1 2"),
        "dup": ("A", "1"),
        "swap": ("X", "1 2 3"),
        "nor": ("V", "5 2"),
        "left": ("L", "3"),
        "right": ("R", "-3"),
        "single": ("V", "5"),
        "underflow": ("X", "1"),
        "syntax": ("v", "1"),
        "lazy": ("V", "1"),
        "cursor": ("V", " 1 "),
        "repeat": ("V", "1"),
    }
    for fault, (source, stdin) in controls.items():

        class Fault(_Machine):
            mode = fault

            def __init__(self, code, io):
                if self.mode == "cursor":
                    read_all = io.input_all
                    io.input_all = lambda: read_all()[:-1]
                    io.position = lambda: 0
                super().__init__(code.upper() if self.mode == "syntax" else code, io)
                if self.mode == "lazy":
                    from collections import deque

                    self.queue = deque([1])

            def step(self):
                if self.mode == "repeat" and self.done:
                    self.io.print_str("extra")
                before = None if self.queue is None else tuple(self.queue)
                try:
                    super().step()
                except HaltError:
                    if self.mode == "underflow" and self.queue:
                        self.queue.popleft()
                    raise
                queue = self.queue
                if queue is None:
                    return
                if self.mode == "rotate":
                    queue.rotate(1)
                elif self.mode == "dup":
                    queue.pop()
                elif self.mode == "swap":
                    if before is not None:
                        queue.clear()
                        queue.extend((*before[2:], *before[:2]))
                    else:
                        queue[-1], queue[-2] = queue[-2], queue[-1]
                elif self.mode == "nor" and not self.done:
                    queue[-1] += 1
                elif self.mode == "left":
                    queue[-1] //= 2
                elif self.mode == "right":
                    queue[-1] += int(queue[-1] < 0)
                elif self.mode == "single" and self.done:
                    self.io.print_str("wrong")

        with pytest.raises(AssertionError):
            _agrees(Fault, source, stdin)
    workspace.check_erasures(_WORKSPACE, _agrees, _Machine, "V", "5")
    return len(results), len(controls)
