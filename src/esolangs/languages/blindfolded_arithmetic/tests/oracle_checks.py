"""Revision 170630 arithmetic, using named registers and a statement scanner."""

import itertools
import random
from fractions import Fraction

import pytest

from esolangs.languages.blindfolded_arithmetic.interpreter import _Machine
from esolangs.runtime._state import WorkspaceModel
from tests.interpreters.oracle_support import observed
from tests.support.workspace_oracle import missing_workspace, workspace_view

_WORKSPACE = WorkspaceModel(
    "blindfolded-arithmetic-v1",
    ("configuration", "stopped", "input_cursor"),
)


def _parse(source):
    program, offsets, start = [], [], 0
    for end in range(len(source) + 1):
        if end != len(source) and source[end] not in ";\n":
            continue
        text = source[start:end].strip(" \t")
        if text:
            compact = text.replace(" ", "").replace("\t", "")
            if (
                len(compact) != 5
                or compact[1] != "="
                or compact[3] not in "+-*/"
                or any(compact[i] not in "abcdei" for i in (0, 2, 4))
            ):
                raise ValueError
            program.append((compact[0], compact[2], compact[3], compact[4]))
            offsets.append(
                start + len(source[start:end]) - len(source[start:end].lstrip(" \t"))
            )
        start = end + 1
    if not program:
        raise ValueError
    return program, offsets


def _read(stdin):
    at = 0
    while at < len(stdin) and stdin[at].isspace():
        at += 1
    start = at
    while at < len(stdin) and not stdin[at].isspace():
        at += 1
    token = stdin[start:at]
    if not token:
        return None, at, "input"
    digits = token[1:] if token[:1] in "+-" else token
    if not digits or any(c not in "0123456789" for c in digits):
        return None, at, "argument"
    value = int(token)
    return value, at, None if value > 0 else "argument"


def _model(source, stdin):
    try:
        program, offsets = _parse(source)
    except ValueError:
        return "syntax", [(None, False, "", 0, 0)]
    value, consumed, error = _read(stdin)
    if error:
        return error, [(None, False, "", consumed, consumed)]
    registers = dict.fromkeys("abcdei", 0)
    registers["i"] = value
    pc, halted, output = 0, False, ""

    def view():
        memory = tuple(registers.values())
        return ((memory, pc, memory, offsets[pc]), halted, output, consumed, consumed)

    trace = [view()]
    # Sixteen steps bound repeated squaring; 64 can exhaust memory.
    for _ in range(16):
        if halted:
            break
        target, left, op, right = program[pc]
        x, y = registers[left], registers[right]
        if op == "/" and not y:
            halted, output = True, str(registers["i"])
        else:
            operations = {
                "+": lambda a, b: a + b,
                "-": lambda a, b: a - b,
                "*": lambda a, b: a * b,
                "/": lambda a, b: int(Fraction(a, b)),
            }
            registers[target] = operations[op](x, y)
            pc = (pc + 1) % len(program)
        trace.append(view())
    if halted:
        trace.extend([view()] * 3)
    return None, trace


def _agrees(factory, source, stdin):
    expected = _model(source, stdin)
    configuration = None

    def parts(row):
        nonlocal configuration
        current = row[0][:2]
        # Equal immutable views retain the width oracle's identity memo.
        if current != configuration:
            configuration = current
        return configuration, row[1], row[-1]

    checked = workspace_view(
        expected[1],
        _WORKSPACE,
        parts,
        lambda m: (*m.state, tuple(m.memory), m.ip),
    )
    assert observed(factory, source, stdin, checked, cap=16) == expected, (
        source,
        stdin,
    )
    return expected


def check_raw_blindfolded_arithmetic():
    atoms = [
        f"{dest}={left}{op}{right}"
        for dest, left, right in itertools.product("abcdei", repeat=3)
        for op in "+-*/"
    ]
    prefix = "a=i+i;b=a+i;c=i-a;d=a+b;e=c-b;"
    corpus = atoms + [prefix + atom + ";a=a-a;a=a/a" for atom in atoms]
    rng = random.Random(20261103)
    corpus += ["; \n".join(rng.choices(atoms, k=12)) for _ in range(128)]
    corpus += [
        "b=i+i;c=a-i;i=c/b;a=a/a",
        " \t a = i / i ;\n i = i - a; a=a/i",
        "i=i/a",
        "a=i/i;i=i-a",
        "a=i/i;\t b=a+a\n i=i/b;a=a/a",
        "a=i+i;" * 20,
    ]
    results = [
        _agrees(_Machine, code, stdin)
        for code in corpus
        for stdin in ("1", " 3 trailing", "+17\n2")
    ]
    invalid = (
        "",
        " ; \n",
        "f=i+i",
        "A=i+i",
        "a=1+i",
        "a=i",
        "a==i+i",
        "a=i%i",
        "a=i+i#x",
        "a=i+i\r",
        "a=i+i\v",
        "a=i+i\u00a0",
    )
    results.extend(
        _agrees(_Machine, code, stdin)
        for code in (*invalid, "i=i/a")
        for stdin in ("", " \n", "0", "-1", "x", "1_0", "٣", "  +2 extra")
    )
    assert {error for error, _ in results} == {None, "syntax", "input", "argument"}
    assert _model("b=i+i;c=a-i;i=c/b;a=a/a", "3")[1][-1][2] == "0"
    assert any(not trace[-1][1] for error, trace in results if error is None)
    controls = {
        "divide": ("b=i+i;c=a-i;i=c/b;a=a/a", "3"),
        "operand": ("a=i-a", "3"),
        "multiply": ("i=i*i", "3"),
        "initial": ("a=i/a", "3"),
        "wrap": ("a=i+i", "3"),
        "zero": ("i=i/a", "3"),
        "syntax": ("f=i+i", "3"),
        "positive": ("i=i/a", "0"),
        "cursor": ("i=i/a", "3 4"),
        "repeat": ("i=i/a", "3"),
    }
    for fault, (source, stdin) in controls.items():

        class Fault(_Machine):
            mode = fault

            def __init__(self, code, io):
                if self.mode == "positive":
                    io.input_num = lambda: 1
                super().__init__(
                    code.replace("f", "a") if self.mode == "syntax" else code, io
                )
                if self.mode == "initial":
                    self.state = ((1, *self.state[0][1:]), self.state[1])

            def step(self):
                regs, pc = self.state
                target, op, left, right = self.program[pc]
                if self.mode == "cursor" and not self.halted:
                    self.io.input_char()
                if self.mode == "repeat" and self.halted:
                    self.io.print_num(regs[-1])
                if not self.halted and (
                    (self.mode == "divide" and op == "/" and regs[right])
                    or self.mode == "operand"
                    or self.mode == "multiply"
                ):
                    value = (
                        regs[left] // regs[right]
                        if self.mode == "divide"
                        else regs[right] - regs[left]
                        if self.mode == "operand"
                        else regs[left] + regs[right]
                    )
                    changed = list(regs)
                    changed[target] = value
                    self.state = tuple(changed), (pc + 1) % len(self.program)
                else:
                    super().step()
                    if self.mode == "wrap" and not self.halted:
                        self.halted = True
                    elif self.mode == "zero" and self.halted:
                        self.state = (0,) * 6, pc

        with pytest.raises(AssertionError):
            _agrees(Fault, source, stdin)
    for component in _WORKSPACE.components:
        with pytest.raises(AssertionError):
            _agrees(missing_workspace(_Machine, component), "i=i/i", "1")
    return len(results), len(controls) + 3
