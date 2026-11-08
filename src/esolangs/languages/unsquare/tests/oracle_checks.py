"""Mutable stack and forward scan for the matching loop closer."""

from itertools import product

import pytest

from esolangs.languages.unsquare.interpreter import _Machine
from tests.support import workspace_oracle as workspace
from tests.support.model_input import matching_delimiter

_WORKSPACE = workspace.workspace_model(
    "unsquare-v1", "instruction accumulator stack jumps input_cursor input_reads"
)


def _closer(code, pc):
    span = matching_delimiter(code[pc + 1 :], ">", "<")
    return None if span is None else pc + span


def _model(code, stdin):
    stack, loops = [], []
    pc = acc = cursor = 0
    output = ""
    trace = []
    failure = None
    for step in range(33):
        halted = pc == len(code)
        state = pc, acc, tuple(stack), tuple(opening - 1 for opening in loops)
        trace.append((state, halted, output, cursor, cursor))
        if failure:
            break
        if halted:
            trace.extend([trace[-1]] * 3)
            break
        if step == 32:
            break
        command = code[pc]
        destination = pc + 1
        if len(stack) < {"A": 1, "o": 1, "S": 2}.get(command, 0):
            failure = "halt"
            continue
        match command:
            case "O" | "I":
                stack.append(int(command == "I"))
            case "A":
                acc = stack.pop()
            case "S":
                stack[-2:] = reversed(stack[-2:])
            case "+" | "-" | "x":
                acc = {"+": acc + 2, "-": acc - 2, "x": acc + acc}[command]
            case "P":
                stack.append(acc)
            case "o":
                value = stack[-1]
                scalar = value % 2**32
                output += (
                    chr(scalar)
                    if scalar < 0x110000 and not 0xD800 <= scalar < 0xE000
                    else str(value)
                )
            case "i":
                if cursor == len(stdin):
                    failure = "input"
                    continue
                stack.append(ord(stdin[cursor]))
                cursor += 1
            case ">":
                closing = _closer(code, pc)
                if closing is None:
                    pc, failure = len(code), "halt"
                    continue
                if acc in (0, 1):
                    destination = closing + 1
                else:
                    loops.append(pc)
            case "<":
                if not loops:
                    failure = "halt"
                    continue
                opening = loops.pop()
                if acc not in (0, 1):
                    destination = opening
        pc = destination
    return failure, trace


def check_raw_unsquare():
    def check(factory, code, stdin):
        workspace.agrees(
            _model(code, stdin),
            (factory, code, stdin),
            (_WORKSPACE, lambda row: (*row[0], row[-1], row[-1])),
            lambda m: m.state,
            cap=32,
        )

    corpus = ["".join(chars) for chars in product("OIAS+-xPoi><?", repeat=3)]
    corpus += ["+>><-<", "+>-<Po", "++><", "OIA>i<o", "iAxxPo", "-Po", "io", "OOIS"]
    for code, stdin in product(corpus, ("", "😀\n", "\ud800")):
        check(_Machine, code, stdin)

    class LostLoop(_Machine):
        def step(self):
            super().step()
            if self.jumps:
                self.state = self.ind, self.acc, self.stack, ()

    with pytest.raises(AssertionError):
        check(LostLoop, "+>-<", "")

    workspace.check_erasures(_WORKSPACE, check, _Machine, "iA+>i<", "AA")
