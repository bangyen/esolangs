"""Revision 174732 BCT, modeled as bijective-base-two arithmetic."""

import itertools
import random
import re

import pytest

from esolangs.languages.bitwise_cyclic_tag.interpreter import _Machine
from esolangs.runtime._state import WorkspaceModel
from esolangs.runtime.io import ScriptedIO
from tests.support import workspace_oracle as workspace

_WORKSPACE = WorkspaceModel(
    "bitwise-cyclic-tag-v2",
    ("instruction", "live_bits", "answer", "completion_emitted", "input_cursor"),
)


def _word(number):
    bits = []
    while number:
        number, bit = divmod(number - 1, 2)
        bits.append(str(bit))
    return "".join(bits)


def _model(source, *, cap=64):
    text = "".join(source.split())
    if not re.fullmatch(r"[01]*(?:,[01]*)?", text):
        return "syntax", [(None, False, "", 0, 0)]
    program, _, data = text.partition(",")
    offsets = [i for i, char in enumerate(source.split(",", 1)[0]) if char in "01"]
    number = sum((int(bit) + 1) << i for i, bit in enumerate(data))
    head, deleted, answer, printed, output = 0, 0, None, False, ""

    def view():
        live = _word(number)
        ip = offsets[head] if program else None
        state = head, deleted, live, answer, printed, tuple(map(int, live)), ip
        return state, not program or not number, output, 0, 0

    trace = [view()]
    for _ in range(cap):
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


def _parts(row):
    return row[0][0], row[0][2], row[0][3], row[0][4], row[-1]


def _agrees(factory, source, *, cap=64):
    return workspace.agrees(
        _model(source, cap=cap),
        (factory, source, "unused λ"),
        (_WORKSPACE, _parts),
        lambda m: (m.head, m.read, m.live, m.answer, m.printed, tuple(m.memory), m.ip),
        cap=cap,
        context=source,
    )


def bitwise_cyclic_tag_cases():
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
    corpus.append("9" * 4400)
    return [(code, 64) for code in corpus] + [("0," + "0" * 80, 80)]


def check_raw_bitwise_cyclic_tag():
    results = [
        _agrees(_Machine, code, cap=cap) for code, cap in bitwise_cyclic_tag_cases()
    ]
    assert {error for error, _ in results} == {None, "syntax"}
    assert any(not trace[-1][1] for error, trace in results if error is None)
    assert _model("110100,10")[1][-1][2] == "0"
    live = [v[0][2] for v in _model("00111,101")[1][:7]]
    assert live == ["101", "01", "1", "11", "110", "10", "101"]
    for source, cap, bits in (
        (",1", 64, 1),
        ("0,1", 64, 17),
        ("00,1", 64, 18),
        ("0," + "0" * 80, 64, 648),
        ("0," + "0" * 80, 80, 649),
    ):
        trace = _model(source, cap=cap)[1]
        assert workspace.charged_bits(_WORKSPACE, map(_parts, trace)) == bits
    probe = _Machine("0,1", ScriptedIO("unused"))
    probe.step()
    cycle_key = probe.snapshot()
    assert probe.io.getvalue() == ""
    probe.step()
    assert (probe.snapshot(), probe.io.getvalue()) == (cycle_key, "1")
    probe.step()
    assert (probe.snapshot(), probe.io.getvalue()) == (cycle_key, "1")

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
            _agrees(workspace.missing_workspace(_Machine, component), "00,1")
