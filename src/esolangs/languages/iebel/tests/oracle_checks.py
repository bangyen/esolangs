"""Revision 194369 IEBEL, using sparse named registers and scanned integers."""

import itertools
import random
import re

import pytest

from esolangs.languages.iebel.interpreter import _Machine
from tests.interpreters.oracle_support import observed
from tests.support import workspace_oracle as workspace

_WORKSPACE = workspace.workspace_model("iebel-v1", "instruction registers input_cursor")


def _integer(text):
    if re.fullmatch(r"[+-]?\d+(?:_\d+)*", text) is None:
        raise ValueError
    return int(text.replace("_", ""))


def _parse(source):
    ops = []
    for line, raw_text in enumerate(source.split("\n")):
        text = raw_text
        if not text.strip():
            continue
        if ":" in text:
            label, text = text.split(":", 1)
            if label.strip() != str(len(ops)):
                raise ValueError
        fields = text.split()
        if len(fields) != 3:
            raise ValueError
        a, b, c = map(_integer, fields)
        if not (0 <= a < 256 and 0 <= b < 256 and c >= -5):
            raise ValueError
        ops.append((a, b, c, line))
    return ops


def _model(source, stdin):
    try:
        ops = _parse(source)
    except ValueError:
        return "syntax", [(None, False, "", 0, 0)]
    pc, registers, consumed, output, error = 0, {}, 0, "", None

    # Reuse immutable views of equal maps; the full oracle took 1.34s.
    memories = {}

    def view():
        key = frozenset(registers.items())
        memory = memories.get(key)
        if memory is None:
            memory = memories[key] = tuple(registers.get(i, 0) for i in range(256))
        ip = (ops[pc][3],) if pc < len(ops) else (ops[-1][3] + 1 if ops else 0,)
        return ((pc, memory, ip), pc == len(ops), output, consumed, consumed)

    trace = [view()]
    for _ in range(64):
        if pc == len(ops):
            break
        a, b, control, _line = ops[pc]
        byte = None
        if control == -3:
            if consumed == len(stdin):
                error = "input"
            else:
                byte = ord(stdin[consumed]) % 256
                consumed += 1
        if not error:
            next_pc = pc + 1
            if registers.get(a, 0) == registers.get(b, 0):
                registers[a] = b
            elif control >= 0:
                next_pc = control
            if control in (-5, -4):
                registers[b] = (
                    registers.get(b, 0) + (1 if control == -5 else -1)
                ) % 256
            elif control == -3:
                registers[b] = byte
            elif control == -2:
                output += chr(registers.get(a, 0))
            elif control == -1:
                next_pc = len(ops)
            pc = min(len(ops), next_pc)
        trace.append(view())
        if error:
            break
    if pc == len(ops) and not error:
        trace.extend([view()] * 3)
    return error, trace


def _agrees(factory, source, stdin):
    expected = _model(source, stdin)
    checked = workspace.workspace_view(
        expected[1],
        _WORKSPACE,
        lambda row: (row[0][0], row[0][1], row[-1]),
        lambda m: (*m.state, m.ip),
    )
    assert observed(factory, source, stdin, checked) == expected, (source, stdin)
    return expected


def check_raw_iebel():
    atoms = [
        f"{a} {b} {c}"
        for a, b in itertools.product((0, 1, 2, 48, 255), repeat=2)
        for c in (-5, -4, -3, -2, -1, 0, 1, 99)
    ]
    corpus = atoms + ["0 0 -3\n" + atom + "\n0 0 -1" for atom in atoms]
    rng = random.Random(20261103)
    for _ in range(128):
        corpus.append(
            "\n\n".join(f"{i}: {op}" for i, op in enumerate(rng.choices(atoms, k=8)))
        )
    corpus += [
        "",
        "\n \n",
        "0 255 -2",
        "0 0 -4\n0 1 -2",
        "0 0 -5\n0 1 -2",
        "0 0 -3\n0 0 -2",
        "\n0 0 -1\n\n",
        "0 0 -5\n0 1 999",
        "0 0 -5\n0 0 -5",
        "0 0 -5\n" * 80,
        "+0 01 -1",
        "\u0660 \u0661 -\u0661",
        "0_0 0_1 -1",
    ]
    inputs = ("", "\x00A\n", "λ", "\U0010ffff", "\r\n")
    results = [_agrees(_Machine, code, stdin) for code in corpus for stdin in inputs]
    invalid = (
        "0 0",
        "0 0 -1 2",
        "0 0 -6",
        "-1 0 0",
        "0 256 0",
        "1: 0 0 -1",
        "00: 0 0 -1",
        "+0:0 0 -1",
        "0:0 0 -1\n0:0 0 -1",
        "0::0 0 -1",
        "0x0 0 -1",
        "0__0 0 -1",
        "² 0 -1",
        "0 0 -1#x",
    )
    results += [_agrees(_Machine, code, "unused") for code in invalid]
    assert {error for error, _ in results} == {None, "syntax", "input"}
    assert any(not trace[-1][1] for error, trace in results if error is None)
    assert _model("0 255 -2", "")[1][-1][2] == "ÿ"
    controls = {
        "load": ("0 1 -2", ""),
        "compare": ("0 0 -5\n0 1 0", ""),
        "increment": ("0 1 -5", ""),
        "decrement": ("0 1 -4", ""),
        "order": ("0 0 -5", ""),
        "input": ("0 0 -3", "λ"),
        "eof": ("0 1 -3", ""),
        "output": ("0 1 -2", ""),
        "jump": ("0 0 -5\n0 1 999", ""),
        "syntax": ("1:0 0 -1", ""),
        "offset": ("\n0 0 -1", ""),
        "posthalt": ("", ""),
    }
    for fault, (source, stdin) in controls.items():

        class Fault(_Machine):
            mode = fault

            def __init__(self, code, io):
                if self.mode == "eof":
                    io.input_char = lambda: ord("0")
                super().__init__(
                    code.replace("1:", "0:") if self.mode == "syntax" else code, io
                )
                if self.mode == "offset":
                    self.ops = tuple(type(op)(op.a, op.b, op.c, 0) for op in self.ops)

            def step(self):
                if self.halted:
                    if self.mode == "posthalt":
                        self.io.print_str("extra")
                    return
                pc, regs = self.state
                a, b, control, _ = self.ops[pc]
                super().step()
                at, values = self.state
                changed = list(values)
                if self.mode == "load":
                    changed[a] = regs[b]
                elif self.mode == "compare":
                    at = pc + 1
                elif self.mode == "increment":
                    changed[b] = (changed[b] - 1) % 256
                elif self.mode == "decrement":
                    changed[b] = 0
                elif self.mode == "order":
                    changed[a] = b
                elif self.mode == "input":
                    changed[b] = ord("λ")
                elif self.mode == "output":
                    self.io.print_str("\n")
                elif self.mode == "jump" and control >= 0:
                    at = control
                self.state = at, tuple(changed)

        with pytest.raises(AssertionError):
            _agrees(Fault, source, stdin)
    for component in _WORKSPACE.components:
        with pytest.raises(AssertionError):
            _agrees(workspace.missing_workspace(_Machine, component), "", "")
    return len(results), len(controls) + 3
