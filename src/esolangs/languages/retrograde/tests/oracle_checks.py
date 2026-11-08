"""Revision 198201 Retrograde, using a set of marked tape coordinates."""

import itertools
import random

import pytest

from esolangs.languages.retrograde.interpreter import _Machine
from tests.support import workspace_oracle as workspace

_WORKSPACE = workspace.workspace_model(
    "retrograde-v1", "instruction pointer direction left right printed input_cursor"
)


def _model(source):
    offsets = [i for i, c in enumerate(source) if not c.isspace()]
    program = [source[i] for i in offsets]
    level = 0
    for char in program:
        if char not in "*<>{}/\\":
            return "syntax", [(None, False, "", 0, 0)]
        level += (char == "{") - (char == "}")
        if level < 0:
            return "syntax", [(None, False, "", 0, 0)]
    if level:
        return "syntax", [(None, False, "", 0, 0)]
    pc, pointer, direction, ones, printed, output = 0, 0, 1, set(), False, ""

    def view():
        low, high = min(ones | {0, pointer}), max(ones | {0, pointer})
        memory = tuple(int(i in ones) for i in range(low, high + 1))
        ip = offsets[pc] if 0 <= pc < len(program) else None
        return ((pc, pointer, direction, memory, printed, ip), printed, output, 0, 0)

    trace = [view()]
    for _ in range(64):
        if printed:
            break
        if not 0 <= pc < len(program):
            printed, output = True, str(int(pointer in ones))
        else:
            command = program[pc]
            if (
                command == "*"
                or (command == "/" and direction > 0)
                or (command == "\\" and direction < 0)
            ):
                ones.symmetric_difference_update({pointer})
            elif command in "<>":
                pointer += direction * (1 if command == ">" else -1)
            elif command in "{}" and pointer in ones:
                scan = 1 if command == "{" else -1
                depth = 1
                while depth:
                    pc += scan
                    depth += (program[pc] == command) - (
                        program[pc] == ("}" if command == "{" else "{")
                    )
                direction = -direction
            pc += direction
        trace.append(view())
    if printed:
        trace.extend([view()] * 3)
    return None, trace


def _agrees(factory, source):
    expected = _model(source)
    ones, previous = set(), 0

    def parts(row):
        nonlocal previous
        pc, pointer, direction, memory, printed, _ = row[0]
        change = sum(memory) - len(ones)
        if change:
            assert abs(change) == 1
            assert pointer == previous
            assert (previous in ones) == (change < 0)
            ones.symmetric_difference_update({previous})
        assert sum(memory) == len(ones)
        previous = pointer
        left = sum(1 << (-cell - 1) for cell in ones if cell < 0)
        right = sum(1 << cell for cell in ones if cell >= 0)
        return pc, pointer, direction, left, right, printed, row[-1]

    return workspace.agrees(
        expected,
        (factory, source, "unused λ"),
        (_WORKSPACE, parts),
        lambda m: (*m.state[:3], tuple(m.memory), m.printed, m.ip),
        context=source,
    )


def check_raw_retrograde():
    atoms = "*<>{}/\\"
    corpus = ["".join(p) for n in range(4) for p in itertools.product(atoms, repeat=n)]
    rng = random.Random(20261103)
    for _ in range(128):
        body = "".join(rng.choices("*<>/\\", k=8))
        before, after = rng.choice((("*{", "}"), ("{", "}"), ("*{{*", "}{*}}")))
        corpus.append(" \n".join(before + body + after))
    corpus += [
        "*{>}",
        "*{<}",
        "*{\\}",
        "*{/}",
        "*{{*>}{*}}",
        "{*{*>*}*}",
        "/{*}/",
        "<*>>*<*",
        "<**",
        "{*}",
        " ",
        "λ",
        "{}x",
        "}{",
        "*" * 80,
    ]
    results = [_agrees(_Machine, source) for source in corpus]
    assert {error for error, _ in results} == {None, "syntax"}
    assert any(not trace[-1][1] for error, trace in results if error is None)
    assert _model("*")[1][-1][2] == "1"
    assert _model("<**")[1][-1][0][3] == (0, 0)
    controls = {
        "toggle": "*",
        "forward": "/",
        "backward": "*{\\}",
        "movement": "*{>}",
        "turn": "*{>}",
        "left": "<*",
        "syntax": "{",
        "offset": " * ",
        "input": "*",
        "repeat": "",
    }
    for fault, source in controls.items():

        class Fault(_Machine):
            mode = fault

            def __init__(self, code, io):
                edits = {
                    "toggle": ("*", "\\"),
                    "forward": ("/", "\\"),
                    "backward": ("\\", "/"),
                    "syntax": ("{", " "),
                }
                if self.mode in edits:
                    code = code.replace(*edits[self.mode])
                super().__init__(code, io)
                if self.mode == "offset":
                    self.offsets = (0,) * len(self.offsets)

            def step(self):
                if self.mode == "repeat" and self.halted:
                    self.io.print_str("extra")
                if self.mode == "input" and not self.halted:
                    self.io.input_char()
                before = self.state
                super().step()
                pc, pointer, direction, left, right = self.state
                if (
                    self.mode == "movement"
                    and before.direction < 0
                    and self.ip is not None
                ):
                    self.state = type(self.state)(pc, -pointer, direction, left, right)
                elif self.mode == "turn" and direction != before.direction:
                    self.state = type(self.state)(
                        pc, pointer, before.direction, left, right
                    )
                elif self.mode == "left" and pointer < 0:
                    self.state = type(self.state)(pc, 0, direction, left, right)

        with pytest.raises(AssertionError):
            _agrees(Fault, source)
    workspace.check_erasures(_WORKSPACE, _agrees, _Machine, "*<*>{*}")
    return len(results), len(controls)
