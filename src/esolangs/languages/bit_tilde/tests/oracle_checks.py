"""Revision 137987 bit windows; sparse logical tape with independent pool bounds."""

import itertools
import random

import pytest

from esolangs.languages.bit_tilde.interpreter import _Machine
from esolangs.runtime._state import WorkspaceModel
from tests.interpreters.oracle_support import observed
from tests.support.workspace_oracle import missing_workspace, workspace_view

_WORKSPACE = WorkspaceModel(
    "bit-tilde-v1", ("tape", "pointer", "instruction", "input_cursor")
)


def _model(source, stdin):
    cells, position, low, high, pc, consumed, output, error = (
        {},
        0,
        0,
        7,
        0,
        0,
        "",
        None,
    )

    def view():
        pool = tuple(cells.get(i, 0) for i in range(low, high + 1))
        return (
            (pc, position - low, pool, pool),
            pc == len(source),
            output,
            consumed,
            consumed,
        )

    trace = [view()]
    for _ in range(64):
        if pc == len(source):
            break
        command, next_pc = source[pc], pc + 1
        if command == "~":
            cells[position] = 1 - cells.get(position, 0)
        elif command in "<>":
            position += 1 if command == ">" else -1
            low, high = min(low, position), max(high, position + 7)
        elif command == ")":
            if consumed == len(stdin):
                error = "input"
            else:
                byte = ord(stdin[consumed]) % 256
                consumed += 1
                for i in range(8):
                    if byte & (128 >> i):
                        at = position + i
                        cells[at] = 1 - cells.get(at, 0)
        elif command == "(":
            output += chr(
                sum(cells.get(position + i, 0) * 2 ** (7 - i) for i in range(8))
            )
        elif (command == "{" and not cells.get(position, 0)) or (
            command == "}" and cells.get(position, 0)
        ):
            direction, nesting, at = (1 if command == "{" else -1), 1, pc
            while nesting:
                at += direction
                if not 0 <= at < len(source):
                    error = "syntax"
                    break
                nesting += (source[at] == command) - (
                    source[at] in "{}" and source[at] != command
                )
            next_pc = at + 1
        if not error:
            pc = next_pc
        trace.append(view())
        if error:
            break
    if pc == len(source) and not error:
        trace.extend([view()] * 3)
    return error, trace


def _agrees(factory, source, stdin):
    expected = _model(source, stdin)
    checked = workspace_view(
        expected[1],
        _WORKSPACE,
        lambda row: (row[0][2], row[0][1], row[0][0], row[-1]),
        lambda m: (*m.state, tuple(m.memory)),
    )
    assert observed(factory, source, stdin, checked) == expected, (source, stdin)
    return expected


def check_raw_bit_tilde():
    atoms = "~><)({}x"
    corpus = ["".join(p) for n in range(4) for p in itertools.product(atoms, repeat=n)]
    rng = random.Random(20261103)
    corpus += [
        "".join(rng.choices(("~", ">", "<", ")", "(", "{}", "{~}", "{>}"), k=10))
        for _ in range(128)
    ]
    corpus += [
        "))(",
        "<~>(<(",
        "~{",
        "}",
        "~}",
        "{~}",
        "~{>}",
        "){~}{(}",
        "~(~(",
        ">" * 80,
        "λ\n)(",
        "{{}}",
    ]
    inputs = ("", "\x81\x81", "λ\n")
    results = [
        _agrees(_Machine, source, stdin) for source in corpus for stdin in inputs
    ]
    assert {error for error, _ in results} == {None, "syntax", "input"}
    assert any(not trace[-1][1] for error, trace in results if not error)
    assert _model("))(", "\x81\x81")[1][-1][2] == "\x00"
    assert _model("~{", "")[0] is None  # an untaken jump has no syntax error
    controls = {
        "store": ("))(", "\x81\x81"),
        "left": ("<~(", ""),
        "eager": ("~{", ""),
        "close": ("}", ""),
        "eof": (")", ""),
        "order": (")(", "\x01"),
        "output": ("~(", ""),
        "posthalt": ("", ""),
    }
    for fault, (source, stdin) in controls.items():

        class Fault(_Machine):
            mode = fault

            def __init__(self, code, io):
                if self.mode == "eager" and code.count("{") != code.count("}"):
                    raise ValueError("eager braces")
                if self.mode == "eof":
                    io.input_char = lambda: 0
                elif self.mode == "order":
                    read = io.input_char
                    io.input_char = lambda: int(f"{read() % 256:08b}"[::-1], 2)
                elif self.mode == "output":
                    write = io.print_char
                    io.print_char = lambda text: write(chr(ord(text) & 127))
                super().__init__(code, io)

            def step(self):
                if self.halted:
                    super().step()
                    if self.mode == "posthalt":
                        self.io.print_str("extra")
                    return
                pc, pointer, tape = self.state
                command = self.code[pc]
                if self.mode == "store" and command == ")":
                    byte = self.io.input_char() % 256
                    values = list(tape)
                    values[pointer : pointer + 8] = [int(b) for b in f"{byte:08b}"]
                    self.state = pc + 1, pointer, tuple(values)
                elif self.mode == "left" and command == "<" and not pointer:
                    self.state = pc + 1, pointer, tape
                elif self.mode == "close" and command == "}":
                    raise ValueError("unconditional close")
                else:
                    super().step()

        with pytest.raises(AssertionError):
            _agrees(Fault, source, stdin)
    for component in _WORKSPACE.components:
        with pytest.raises(AssertionError):
            _agrees(missing_workspace(_Machine, component), "~>~", "")
    return len(results), len(controls) + 4
