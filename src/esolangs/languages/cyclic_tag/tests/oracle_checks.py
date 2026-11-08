"""Revision 156412 cyclic productions, using a destructive FIFO."""

import itertools
import random
import re
from collections import deque

import pytest

from esolangs.languages.cyclic_tag.interpreter import _Machine
from tests.interpreters.oracle_support import observed
from tests.support import workspace_oracle as workspace

_WORKSPACE = workspace.workspace_model(
    "cyclic-tag-v1", "head live_bits answer_latch input_cursor"
)


def _model(source):
    if re.search(r"[^01;,\s]", source) or source.count(",") != 1:
        return "syntax", [(None, False, "", 0, 0)]
    rules_text, data = source.split(",")
    if ";" in data:
        return "syntax", [(None, False, "", 0, 0)]
    fields = rules_text.split(";")
    rules = ["".join(field.split()) for field in fields]
    offsets, start = [], 0
    for field in fields:
        at = start
        while source[at].isspace():
            at += 1
        offsets.append(at)
        start += len(field) + 1
    queue = deque("".join(data.split()))
    head, answer, printed, output = 0, None, False, ""

    def view():
        live = "".join(queue)
        return (
            (head, live, answer, printed, tuple(map(int, queue)), offsets[head]),
            not queue,
            output,
            0,
            0,
        )

    trace = [view()]
    for _ in range(64):
        if not queue:
            break
        answer = queue.popleft()
        if answer == "1":
            queue.extend(rules[head])
        head = (head + 1) % len(rules)
        trace.append(view())
    if not queue:
        for _ in range(3):
            if answer is not None and not printed:
                output, printed = answer, True
            trace.append(view())
    return None, trace


def _agrees(factory, source):
    expected = _model(source)
    checked = workspace.workspace_view(
        expected[1],
        _WORKSPACE,
        lambda row: (row[0][0], row[0][1], (row[0][2], row[0][3]), row[-1]),
        lambda m: (m.head, m.live, m.answer, m.printed, tuple(m.memory), m.ip),
    )
    assert observed(factory, source, "unused λ\n", checked) == expected, source
    return expected


def check_raw_cyclic_tag():
    bits = ["".join(p) for n in range(3) for p in itertools.product("01", repeat=n)]
    corpus = [f"{a};{b},{data}" for a in bits for b in bits for data in bits]
    rng = random.Random(20261103)
    for _ in range(128):
        fields = ["".join(rng.choices("01", k=rng.randrange(6))) for _ in range(3)]
        corpus.append(" \n".join(";".join(fields) + "," + rng.choice(bits)))
    corpus += [
        "",
        "1",
        "1,,0",
        "x,1",
        "1,0;1",
        ",",
        " ; , ",
        "011;10;101,1",
        "1,1",
        "," + "0" * 80,
    ]
    results = [_agrees(_Machine, code) for code in corpus]
    assert {error for error, _ in results} == {None, "syntax"}
    assert any(not trace[-1][1] for error, trace in results if error is None)
    assert [v[0][1] for v in _model("011;10;101,1")[1][:7]] == [
        "1",
        "011",
        "11",
        "1101",
        "101011",
        "0101110",
        "101110",
    ]
    controls = {
        "zero": "1,0",
        "schedule": "1;0,10",
        "front": ",01",
        "syntax": "1,0;1",
        "offset": " 1; 0,1",
        "input": ",1",
        "dump": ",1",
        "repeat": ",1",
    }
    for fault, source in controls.items():

        class Fault(_Machine):
            mode = fault

            def __init__(self, code, io):
                super().__init__(
                    code.replace(";", "") if self.mode == "syntax" else code, io
                )
                if self.mode == "offset":
                    self._starts = (0,) * len(self.program)

            def step(self):
                was_halted = self.halted
                if self.mode == "input" and not was_halted:
                    self.io.input_char()
                if self.mode == "front" and not was_halted:
                    self.data[self.read :] = reversed(self.data[self.read :])
                old_read = self.read
                super().step()
                if (
                    self.mode == "zero"
                    and not was_halted
                    and self.data[old_read] == "0"
                ):
                    self.data.extend(self.program[old_read % len(self.program)])
                elif self.mode == "schedule" and not was_halted:
                    self.program = self.program[1:] + self.program[:1]
                elif self.mode == "dump" and self.halted and not was_halted:
                    self.io.print_str(self.answer)
                    self.printed = True
                elif self.mode == "repeat" and was_halted:
                    self.io.print_str(self.answer or "")

        with pytest.raises(AssertionError):
            _agrees(Fault, source)
    workspace.check_erasures(_WORKSPACE, _agrees, _Machine, "1;0,1")
    return len(results), len(controls) + 4
