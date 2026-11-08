"""Revision 82957 instructions; regex tokenization and a sparse logical tape."""

import itertools
import random
import re

import pytest

from esolangs.languages.six_five.interpreter import _Machine
from tests.support.workspace_oracle import check_erasures, workspace_model
from tests.support.workspace_oracle import checker as workspace_checker

_WORKSPACE = workspace_model("six-five-v1", "accumulator tape instruction input_cursor")

_TOKENS = re.compile(r"[78][\s\S]?|C[^\n]*(?:\n|$)|[\s\S]")


def _operand(token):
    if len(token) == 1:
        return 0
    char = token[1]
    if char.isdigit():
        return int(char)
    return ord(char.upper()) - ord("A") + 10


def _model(source, stdin):
    program = [m[0] for m in _TOKENS.finditer(source) if m[0][0] in "0123456789AB"]
    labels = [i + 1 for i, token in enumerate(program) if token == "4"]
    cells, position, low, high, pc, consumed, output, error = (
        {},
        0,
        0,
        0,
        0,
        0,
        "",
        None,
    )

    def view():
        tape = tuple(cells.get(i, 0) for i in range(low, high + 1))
        return (
            (pc, position - low, tape, tape, pc),
            pc >= len(program),
            output,
            consumed,
            consumed,
        )

    trace = [view()]
    for _ in range(64):
        if pc >= len(program):
            break
        token, next_pc = program[pc], pc + 1
        op, value = token[0], cells.get(position, 0)
        if op in "123569":
            if op in "13":
                position += 2 if op == "1" else -1
                low, high = min(low, position), max(high, position)
            else:
                cells[position] = value + {"5": 5, "6": 6, "2": -5, "9": -6}[op]
        elif op in "78":
            try:
                operand = _operand(token)
            except ValueError:
                error = "syntax"
            else:
                if op == "7" and operand == value:
                    next_pc += 1
                elif op == "8" and 1 <= operand <= len(labels):
                    next_pc = labels[operand - 1]
        elif op == "A":
            if not 0 <= value <= 0x10FFFF:
                error = "halt"
            else:
                output += chr(value)
        elif op == "B":
            if consumed == len(stdin):
                error = "input"
            else:
                cells[position] = ord(stdin[consumed])
                consumed += 1
        elif op == "0":
            next_pc = len(program)
        if not error:
            pc = next_pc
        trace.append(view())
        if error:
            break
    if pc >= len(program) and not error:
        trace.extend([view()] * 3)
    return error, trace


_agrees = workspace_checker(
    _model,
    (_WORKSPACE, lambda row: (row[0][1], row[0][2], row[0][0], row[-1])),
    lambda m: (*m.state, tuple(m.memory), m.ip),
)


def check_raw_six_five():
    atoms = ("1", "3", "5", "6", "2", "9", "A", "B", "70", "75", "81", "4")
    corpus = ["".join(p) for n in range(3) for p in itertools.product(atoms, repeat=n)]
    rng = random.Random(20261103)
    corpus += [" ".join(rng.choices(atoms, k=10)) for _ in range(128)]
    corpus += [
        "70 6A",
        "7 A",
        "7",
        "8",
        "481",
        "4824A",
        "804A",
        "8a",
        "78C555\nA",
        "7C555A",
        "C555\nA",
        "C555",
        "B6A",
        "B3A",
        "BBBA",
        "2A",
        "9A",
        "2" * 9 + "7\nA",
        "7\u00b2",
        "07\u00b2",
        "λ!\n",
        "1" * 80,
    ]
    inputs = ("", "\x00A\n", "λ", "\U0010ffff", "\r\n")
    results = [
        _agrees(_Machine, source, stdin) for source in corpus for stdin in inputs
    ]
    assert {error for error, _ in results} == {None, "syntax", "input", "halt"}
    assert any(not trace[-1][1] for error, trace in results if not error)
    assert _model("BA", "λ")[1][-1][2] == "λ"  # repo's character-input convention
    controls = {
        "right": ("1A", ""),
        "left": ("3A", ""),
        "skip": ("70 5", ""),
        "marker": ("481", ""),
        "eof": ("B", ""),
        "byte": ("BA", "λ"),
        "output": ("2A", ""),
        "stop": ("0A", ""),
        "comment": ("C5\nA", ""),
    }
    for fault, (source, stdin) in controls.items():

        class Fault(_Machine):
            mode = fault

            def __init__(self, code, io):
                if self.mode == "eof":
                    io.input_char = lambda: 0
                super().__init__(
                    code.replace("C", "") if self.mode == "comment" else code, io
                )

            def step(self):
                if self.halted:
                    super().step()
                    return
                pc, pointer, tape = self.state
                token = self.toks[pc]
                if self.mode == "right" and token == "1":
                    self.state = pc + 1, pointer + 1, (*tape, 0)
                elif (self.mode == "left" and token == "3") or (
                    self.mode == "skip" and token == "70"
                ):
                    self.state = pc + 1, pointer, tape
                elif self.mode == "marker" and token == "81":
                    self.state = self.markers[0], pointer, tape
                elif self.mode == "output" and token == "A":
                    self.state = pc + 1, pointer, tape
                    self.io.print_char("\x00")
                elif self.mode == "stop" and token == "0":
                    self.state = pc + 1, pointer, tape
                else:
                    super().step()
                    if self.mode == "byte" and token == "B":
                        at, pos, cells = self.state
                        self.state = (
                            at,
                            pos,
                            (*cells[:pos], cells[pos] % 256, *cells[pos + 1 :]),
                        )

        with pytest.raises(AssertionError):
            _agrees(Fault, source, stdin)
    check_erasures(_WORKSPACE, _agrees, _Machine, "B13B", "λA")
    return len(results), len(controls) + 4
