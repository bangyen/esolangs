"""Revision 200833 Pilas, using mutable per-line stacks and scanned braces."""

import itertools
import random

import pytest

from esolangs.exceptions import HaltError
from esolangs.languages.pilas.interpreter import _Machine
from tests.interpreters.oracle_support import observed
from tests.support.workspace_oracle import (
    charged_bits,
    missing_workspace,
    workspace_model,
    workspace_view,
)

_WORKSPACE = workspace_model(
    "pilas-v1", "instruction_pointers stacks turn input_cursor"
)


def _partner(line, at, step):
    opening, closing = ("{", "}") if step > 0 else ("}", "{")
    depth = 1
    while depth:
        at += step
        depth += (line[at] == opening) - (line[at] == closing)
    return at


def _lines(source):
    lines = source.split("\n")
    if len(lines) > 2:
        raise ValueError
    lines += [""] * (2 - len(lines))
    for line in lines:
        levels = list(itertools.accumulate((c == "{") - (c == "}") for c in line))
        if min([0, *levels]) < 0 or (levels and levels[-1]):
            raise ValueError
    return lines


def _model(source, stdin):
    try:
        lines = _lines(source)
    except ValueError:
        return "syntax", [(None, False, "", 0, 0)]
    ips, stacks, turn, consumed, output, error = [0, 0], [[], []], 0, 0, "", None

    def view():
        state = tuple(ips), tuple(tuple(s) for s in stacks), turn
        halted = any(ips[i] >= len(lines[i]) for i in (0, 1))
        return (*state, tuple(ips)), halted, output, consumed, consumed

    trace = [view()]
    for _ in range(64):
        if trace[-1][1]:
            break
        pc, stack = ips[turn], stacks[turn]
        command = lines[turn][pc]
        need = 2 if command in "+-" else 1 if command in ":~{." else 0
        next_pc = pc + 1
        if len(stack) < need or (command == "." and not 0 <= stack[-1] <= 0x10FFFF):
            error = "halt"
        elif command in "0123456789":
            stack.append(int(command))
        elif command in "+-":
            a, b = stack.pop(), stack.pop()
            stack.append(b + a if command == "+" else b - a)
        elif command == ":":
            stack.append(stack[-1])
        elif command == "~":
            stacks[1 - turn].append(stack.pop())
        elif command == "{":
            if stack.pop():
                next_pc = _partner(lines[turn], pc, 1) + 1
        elif command == "}":
            next_pc = _partner(lines[turn], pc, -1)
        elif command == ",":
            if consumed == len(stdin):
                error = "input"
            else:
                stack.append(ord(stdin[consumed]))
                consumed += 1
        elif command == ".":
            output += chr(stack.pop())
        if not error:
            ips[turn] = next_pc
            turn = 1 - turn
        trace.append(view())
        if error:
            break
    if not error and trace[-1][1]:
        trace.extend([view()] * 3)
    return error, trace


def _agrees(factory, source, stdin):
    expected = _model(source, stdin)
    checked = workspace_view(
        expected[1],
        _WORKSPACE,
        lambda row: (*row[0][:3], row[-1]),
        lambda m: (*m.state, m.ip),
    )

    assert observed(factory, source, stdin, checked) == expected, (source, stdin)
    return expected


def check_raw_pilas():
    words = ("", "0", "1", "9", "+", "-", ":", "~", "{", "}", ",", ".", "x")
    corpus = [a + "\n" + b for a, b in itertools.product(words, repeat=2)]
    rng = random.Random(20261103)
    atoms = "019+-:~{},.x"
    corpus += [
        "\n".join("".join(rng.choices(atoms, k=12)) for _ in range(2))
        for _ in range(128)
    ]
    corpus += [
        "12+.\nxxxx",
        "12-.\nxxxx",
        "1~x\nx.x",
        ",.\n,.x",
        "0{0}\n" + "x" * 80,
        "1{0}.\nxxxxxx",
        "0{1{2}}\nxxxxxxxx",
        "12:.\nxxxxx",
        "\u0663.\nxx",
        "λ\n\r",
        "0\n,",
        "0\n0\n",
        "0",
        "12~+\n0~xx",
        ",:+.\nxxxxx",
    ]
    inputs = ("", "AB\n", "λ", "\x00\xff", "\U0010ffff")
    results = [_agrees(_Machine, code, stdin) for code in corpus for stdin in inputs]
    assert {error for error, _ in results} == {None, "syntax", "halt", "input"}
    assert any(not trace[-1][1] for error, trace in results if error is None)
    assert _model("12+.\nxxxx", "")[1][-1][2] == "\x03"
    assert _model("1~x\nx.x", "")[1][-1][2] == "\x01"
    controls = {
        "turn": ("1x\n2x", ""),
        "transfer": ("1~x\nx.x", ""),
        "subtract": ("12-x\nxxxx", ""),
        "duplicate": ("1:x\nxxx", ""),
        "halt": ("0\n,", ""),
        "loop": ("1{0}x\nxxxxx", ""),
        "eof": (",x\nxx", ""),
        "output": ("1.x\nxxx", ""),
        "syntax": ("{\nx", ""),
        "posthalt": ("", ""),
        "character": (",:+.\nxxxxx", "\U0010ffff"),
    }
    for fault, (code, stdin) in controls.items():

        class Fault(_Machine):
            mode = fault

            def __init__(self, source, io):
                if self.mode == "eof":
                    io.input_char = lambda: 0
                if self.mode == "halt":
                    source = source.replace("0\n", "0x\n")
                super().__init__(
                    source.replace("{", "x") if self.mode == "syntax" else source, io
                )

            def step(self):
                if self.halted:
                    if self.mode == "posthalt":
                        self.io.print_str("extra")
                    return
                ips, stacks, turn = self.state
                command = self.lines[turn][ips[turn]]
                try:
                    super().step()
                except HaltError:
                    if self.mode == "character":
                        changed = [list(s) for s in stacks]
                        changed[turn].pop()
                        self.state = type(self.state)(
                            ips, tuple(tuple(s) for s in changed), turn
                        )
                    raise
                after_ips, after_stacks, after_turn = self.state
                changed = [list(s) for s in after_stacks]
                if self.mode == "turn":
                    after_turn = turn
                elif self.mode == "transfer" and command == "~":
                    changed = [list(s) for s in stacks]
                elif self.mode == "subtract" and command == "-":
                    changed[turn][-1] *= -1
                elif self.mode == "duplicate" and command == ":":
                    changed[turn].pop()
                elif self.mode == "loop" and command == "{":
                    after_ips = tuple(
                        ips[i] + 1 if i == turn else ips[i] for i in (0, 1)
                    )
                elif self.mode == "output" and command == ".":
                    self.io.print_str("\n")
                self.state = type(self.state)(
                    after_ips, tuple(tuple(s) for s in changed), after_turn
                )

        with pytest.raises(AssertionError):
            _agrees(Fault, code, stdin)
    for component in _WORKSPACE.components:
        with pytest.raises(AssertionError):
            _agrees(missing_workspace(_Machine, component), ",x\nxx", "A")
    for code, stdin, bits in (
        ("", "", 0),
        ("x\nx", "", 3),
        ("9x\nxx", "", 8),
        (",x\nxx", "A", 12),
    ):
        rows = _agrees(_Machine, code, stdin)[1]
        assert (
            charged_bits(_WORKSPACE, ((*row[0][:3], row[-1]) for row in rows)) == bits
        )
    return len(results), len(controls)
