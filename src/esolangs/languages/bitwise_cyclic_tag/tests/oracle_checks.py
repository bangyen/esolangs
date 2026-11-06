"""Revision 174732 BCT, modeled as bijective-base-two arithmetic."""

import itertools
import random
import re

import pytest

from esolangs.languages.bitwise_cyclic_tag.interpreter import _Machine
from esolangs.runtime._state import WorkspaceModel
from tests.interpreters.oracle_support import observed
from tests.support.workspace_oracle import missing_workspace, workspace_view

_WORKSPACE = WorkspaceModel(
    "bitwise-cyclic-tag-v1",
    ("instruction", "live_bits", "answer", "input_cursor"),
)


def _word(number):
    bits = []
    while number:
        number, bit = divmod(number - 1, 2)
        bits.append(str(bit))
    return "".join(bits)


def _model(source):
    text = "".join(source.split())
    if not re.fullmatch(r"[01]*(?:,[01]*)?", text):
        return "syntax", [(None, False, "", 0, 0)]
    program, _, data = text.partition(",")
    offsets = [i for i, char in enumerate(source.split(",", 1)[0]) if char in "01"]
    number = sum((int(bit) + 1) << i for i, bit in enumerate(data))
    head, deleted, answer, printed, output = 0, 0, None, False, ""

    def view():
        live = _word(number)
        return (
            (
                head,
                deleted,
                live,
                answer,
                printed,
                tuple(map(int, live)),
                offsets[head] if program else None,
            ),
            not program or not number,
            output,
            0,
            0,
        )

    trace = [view()]
    for _ in range(64):
        if not program or not number:
            break
        if program[head] == "0":
            number, front = divmod(number - 1, 2)
            answer, deleted = str(front), deleted + 1
            head = (head + 1) % len(program)
        else:
            operand = int(program[(head + 1) % len(program)])
            if number % 2 == 0:
                number += (operand + 1) << ((number + 1).bit_length() - 1)
            head = (head + 2) % len(program)
        trace.append(view())
    if not program or not number:
        for _ in range(3):
            if not printed and answer is not None:
                output = answer
            printed = True
            trace.append(view())
    return None, trace


def _agrees(factory, source):
    expected = _model(source)
    checked = workspace_view(
        expected[1],
        _WORKSPACE,
        lambda row: (row[0][0], row[0][2], row[0][3], row[-1]),
        lambda m: (m.head, m.read, m.live, m.answer, m.printed, tuple(m.memory), m.ip),
    )
    assert observed(factory, source, "unused λ", checked) == expected, source
    return expected


def check_raw_bitwise_cyclic_tag():
    words = ["".join(p) for n in range(5) for p in itertools.product("01", repeat=n)]
    corpus = [f"{program},{data}" for program in words for data in words[:15]]
    rng = random.Random(20261103)
    corpus += [
        " \n".join(
            "".join(rng.choices("01", k=9)) + "," + "".join(rng.choices("01", k=6))
        )
        for _ in range(128)
    ]
    corpus += [
        "",
        "0",
        "1",
        ",",
        ",1",
        "00111,101",
        "110100,10",
        "11,1",
        "1,0",
        "1,1",
        "0," + "0" * 80,
        "x,1",
        "0,,1",
        "0;1,1",
    ]
    results = [_agrees(_Machine, code) for code in corpus]
    assert {error for error, _ in results} == {None, "syntax"}
    assert any(not trace[-1][1] for error, trace in results if error is None)
    assert _model("110100,10")[1][-1][2] == "0"
    assert [v[0][2] for v in _model("00111,101")[1][:7]] == [
        "101",
        "01",
        "1",
        "11",
        "110",
        "10",
        "101",
    ]
    controls = {
        "conditional": "11,0",
        "operand": "10,1",
        "wrap": "1,1",
        "delete": "0,01",
        "head": "110,1",
        "syntax": "x,1",
        "offset": " 0 ,1",
        "input": "0,1",
        "early": "0,1",
        "repeat": "0,1",
    }
    for fault, source in controls.items():

        class Fault(_Machine):
            mode = fault

            def __init__(self, code, io):
                super().__init__(
                    code.replace("x", "0") if self.mode == "syntax" else code, io
                )
                if self.mode == "offset":
                    self.offsets = (0,) * len(self.offsets)

            def step(self):
                if self.halted:
                    super().step()
                    if self.mode == "repeat":
                        self.io.print_str(self.answer or "")
                    return
                head, read = self.state
                if self.mode == "input":
                    self.io.input_char()
                if self.mode == "delete":
                    self.data[read:] = reversed(self.data[read:])
                super().step()
                if self.mode == "conditional":
                    self.data.append("1")
                elif self.mode == "operand":
                    self.data[-1] = "1"
                elif self.mode == "wrap":
                    self.data.pop()
                elif self.mode == "head":
                    self.state = (head + 1) % len(self.program), self.read
                elif self.mode == "early" and self.halted:
                    self.io.print_str(self.answer)
                    self.printed = True

        with pytest.raises(AssertionError):
            _agrees(Fault, source)
    for component in _WORKSPACE.components:
        with pytest.raises(AssertionError):
            _agrees(missing_workspace(_Machine, component), "00,1")
    return len(results), len(controls) + 4
