"""Revision 192570 Unary, using octal sentinel decoding and a sparse BF tape."""

import gzip

import pytest

from esolangs.compressed import CompressedText
from esolangs.languages.unary.interpreter import _Machine
from tests.interpreters.oracle_support import observed
from tests.interpreters.semantic_oracles import bracket_pairs
from tests.support.workspace_oracle import (
    charged_bits,
    check_erasures,
    workspace_model,
    workspace_view,
)

_WORKSPACE = workspace_model("brainfuck-v1", "instruction pointer tape input_cursor")


def _decode(raw):
    digits = "".join(raw.split())
    if any(c != "0" for c in digits):
        raise ValueError
    if not digits:
        return ""
    octal = f"{len(digits):o}"
    if octal[0] != "1":
        raise ValueError
    program = "".join("><+-.,[]"[int(c)] for c in octal[1:])
    bracket_pairs(program)
    return program


def _model(raw, stdin, cap=64):
    try:
        program = _decode(raw)
        pairs = bracket_pairs(program)
    except ValueError:
        return "syntax", [(None, False, "", 0, 0)]
    pc, pointer, low, high, cells, consumed, output = 0, 0, 0, 0, {}, 0, ""

    def view():
        tape = tuple(cells.get(i, 0) for i in range(low, high + 1))
        state = pc, pointer - low, tape, tape, pc
        return state, pc == len(program), output, consumed, consumed

    trace = [view()]
    for _ in range(cap):
        if pc == len(program):
            break
        command, next_pc = program[pc], pc + 1
        value = cells.get(pointer, 0)
        if command in "+-":
            cells[pointer] = (value + (1 if command == "+" else -1)) % 256
        elif command in "><":
            pointer += 1 if command == ">" else -1
            low, high = min(low, pointer), max(high, pointer)
        elif command == ",":
            cells[pointer] = ord(stdin[consumed]) % 256 if consumed < len(stdin) else 0
            consumed = min(len(stdin), consumed + 1)
        elif command == ".":
            output += chr(value)
        elif (command == "[" and value == 0) or (command == "]" and value != 0):
            next_pc = pairs[pc] + 1
        pc = next_pc
        trace.append(view())
    if pc == len(program):
        trace.extend([view()] * 3)
    return None, trace


def _source(program):
    return "0" * int("1" + "".join(str("><+-.,[]".index(c)) for c in program), 8)


def _agrees(factory, raw, stdin, *, cap=64, compressed=False):
    source = CompressedText(gzip.compress(raw.encode(), mtime=0)) if compressed else raw
    expected = _model(raw, stdin, cap)
    checked = workspace_view(
        expected[1],
        _WORKSPACE,
        lambda row: (*row[0][:3], row[-1]),
        lambda machine: (*machine.state, tuple(machine.memory), machine.ip),
    )
    assert observed(factory, source, stdin, checked, cap=cap) == expected, (
        len(raw),
        stdin,
    )
    return expected


def check_raw_unary():
    corpus = ["0" * count for count in range(1025)]
    corpus += [
        _source(program)
        for program in (",[.,]", "-[-].", ",+.", "<+.", ">+.", "[[]]", "+[>+]")
    ]
    corpus += [
        " \n\t",
        "00x",
        "0☃",
        "\uff10",
        "O",
        "0\u00a00",
        "0\r\n",
        "0" * 108 + " \n",
    ]
    inputs = ("", "A\n", "λ", "\xff\x00", "\U0010ffff")
    results = [_agrees(_Machine, raw, stdin) for raw in corpus for stdin in inputs]
    for count in (0, 1, 8, 9, 10, 11, 12, 13, 14, 15, 63, 64, 108, 511, 512, 1024):
        raw = " \n".join(["0" * (count // 2), "0" * (count - count // 2)])
        results += [_agrees(_Machine, raw, stdin, compressed=True) for stdin in inputs]
    results.append(_agrees(_Machine, "00000000x", "", compressed=True))
    results.append(_agrees(_Machine, _source("-[-]."), "", cap=600))
    assert {error for error, _ in results} == {None, "syntax"}
    assert any(not trace[-1][1] for error, trace in results if error is None)
    assert _model("0" * 108, "Z")[1][-1][2] == "Z"
    assert _model(_source("-[-]."), "", 600)[1][-1][2] == "\x00"
    controls = {
        "sentinel": ("0", ""),
        "order": (_source(">+"), ""),
        "eof": (_source(","), ""),
        "wrap": (_source(",+."), "\xff"),
        "left": (_source("<"), ""),
        "read": (_source(","), "λ"),
        "jump": (_source("[+]"), ""),
        "syntax": ("00", ""),
        "output": (_source("."), ""),
        "posthalt": ("", ""),
    }
    for fault, (raw, stdin) in controls.items():

        class Fault(_Machine):
            mode = fault

            def __init__(self, code, io):
                if self.mode == "eof":
                    io.input_char = lambda: 255
                super().__init__(
                    "0" * 8
                    if self.mode == "sentinel"
                    else "0"
                    if self.mode == "syntax"
                    else code,
                    io,
                )
                if self.mode == "order":
                    self.code = self.code.translate(str.maketrans("><", "<>"))

            def step(self):
                if self.halted:
                    if self.mode == "posthalt":
                        self.io.print_str("extra")
                    return
                pc, pointer, tape = self.state
                command = self.code[pc]
                super().step()
                at, ptr, values = self.state
                if self.mode == "left" and command == "<":
                    self.state = at, pointer, tape
                elif (self.mode == "wrap" and command == "+") or (
                    self.mode == "read" and command == ","
                ):
                    changed = list(values)
                    changed[ptr] = 256 if self.mode == "wrap" else ord("λ")
                    self.state = at, ptr, tuple(changed)
                elif self.mode == "jump" and command == "[":
                    self.state = pc + 1, ptr, values
                elif self.mode == "output" and command == ".":
                    self.io.print_str("\n")

        with pytest.raises(AssertionError):
            _agrees(Fault, raw, stdin)
    check_erasures(_WORKSPACE, lambda f: _agrees(f, _source(">,+"), "A"), _Machine)
    rows = _agrees(_Machine, _source(">,+"), "A")[1]
    assert charged_bits(_WORKSPACE, ((*row[0][:3], row[-1]) for row in rows)) == 12
    return len(results) + 1, len(controls) + len(_WORKSPACE.components)
