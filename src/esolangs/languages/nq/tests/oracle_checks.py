"""Revision 156166 commands; regex/tree parser and list queue, both guard readings."""

import itertools
import random
import re
from functools import partial

import pytest

from esolangs.languages.nq.interpreter import _Machine
from tests.interpreters.oracle_support import observed

_LEX = re.compile(
    r"(?P<load>[+l])\s*(?P<data>[012]|\([^)]*\))"
    r"|(?P<guard>>)\s*(?P<trit>[012])\s*(?P<group>\()?"
    r"|(?P<single>[-rRWH])|(?P<bad>[+l>])|(?P<close>\))"
)


def _instructions(source, binding):
    if binding not in ("opcode", "recursive"):
        raise ValueError("binding")
    tree = []
    stack = [tree]
    for match in _LEX.finditer(source):
        parts = match.groupdict()
        if parts["bad"]:
            raise ValueError("operand")
        if parts["close"]:
            if len(stack) > 1:
                stack.pop()
            continue
        word = parts["load"] or parts["guard"] or parts["single"]
        payload = parts["data"] or parts["trit"] or ""
        if payload.startswith("("):
            payload = payload[1:-1]
        if any(c not in "012" and not c.isspace() for c in payload):
            raise ValueError("trits")
        node = {
            "word": word,
            "values": [int(c) for c in payload if not c.isspace()],
            "at": match.start(),
            "body": [] if parts["group"] else None,
        }
        stack[-1].append(node)
        if node["body"] is not None:
            stack.append(node["body"])
    if len(stack) != 1:
        raise ValueError("group")
    flat = []

    def flatten(nodes):
        for node in nodes:
            flat.append(node)
            if node["body"] is not None:
                flatten(node["body"])
            node["end"] = len(flat)
            node["span"] = len(flat)
        if binding == "recursive":
            for i in range(len(nodes) - 1, -1, -1):
                node = nodes[i]
                if node["word"] == ">" and node["body"] is None:
                    if i + 1 == len(nodes):
                        raise ValueError("guard target")
                    node["span"] = nodes[i + 1]["span"]

    flatten(tree)
    return flat


def _input(word, stdin, consumed):
    if word == "R":
        text, consumed = stdin[consumed:], len(stdin)
    else:
        while consumed < len(stdin) and stdin[consumed].isspace():
            consumed += 1
        if consumed == len(stdin):
            return [], consumed, "input"
        text, consumed = stdin[consumed], consumed + 1
    if any(c not in "012" and not c.isspace() for c in text):
        return [], consumed, "argument"
    return [int(c) for c in text if not c.isspace()], consumed, None


def _model(source, stdin, binding):
    try:
        program = _instructions(source, binding)
    except ValueError:
        return "syntax", [(None, False, "", 0, 0)]
    cursor = flag = consumed = 0
    first, stopped, queue, output, error = True, not program, [], "", None

    def view():
        state = (
            cursor,
            flag,
            first,
            stopped,
            tuple(queue),
            None if stopped else program[cursor]["at"],
        )
        return state, stopped, output, consumed, consumed

    trace = [view()]
    for _ in range(64):
        if stopped:
            break
        node, next_cursor = program[cursor], cursor + 1
        word = node["word"]
        if word == "+" or (word == "l" and first):
            queue.extend(node["values"])
        elif word == ">" and flag != node["values"][0]:
            if node["body"] is not None:
                next_cursor = node["end"]
            elif cursor + 1 == len(program):
                next_cursor = len(program) + program[0]["end"]
            else:
                next_cursor = program[cursor + 1]["span"]
        elif word in "-W":
            if not queue:
                error = "halt"
            elif word == "-":
                flag = queue.pop(0)
            else:
                output += " \n#"[queue[0]]
        elif word in "rR":
            values, consumed, error = _input(word, stdin, consumed)
            if not error:
                queue.extend(values)
        elif word == "H":
            stopped = True
        if not error:
            if next_cursor >= len(program):
                first = False
            cursor = next_cursor % len(program)
        trace.append(view())
        if error:
            break
    if stopped and not error:
        trace.extend([view()] * 3)
    return error, trace


def _state(machine):
    return (*machine.state, tuple(machine.memory), machine.ip)


def _agrees(factory, source, stdin, binding):
    expected = _model(source, stdin, binding)
    assert (
        observed(partial(factory, guard_binding=binding), source, stdin, _state)
        == expected
    ), (source, stdin, binding)
    return expected


def check_raw_nq():
    atoms = ("+0", "+2", "l1", "-", "W", "H", "r", "R", ">0", ">1(+2)")
    corpus = ["".join(p) for n in range(3) for p in itertools.product(atoms, repeat=n)]
    rng = random.Random(20261103)
    corpus += [" ".join(rng.choices(atoms, k=8)) for _ in range(128)]
    corpus += [
        "+0->1>0+2WH",
        "+0->1>0+2+0WH",
        ">0(+2)W>1",
        "l2W-",
        ">0(>1)>2H",
        ">1(>0)H",
        ">1>0",
        ">1",
        "+",
        "+3",
        "+(01x)",
        "+(01",
        ">3",
        ">0(",
        "l(0 1\n2)W-W-WH",
        "+()H",
        "xyz 9 ?",
        ")H",
        ">0a(+2)WH",
        ">0(>1(+1)H)+2WH",
        "RWH",
        "rr-WH",
        ">0(>2)H",
    ]
    results = [
        _agrees(_Machine, source, stdin, binding)
        for source in corpus
        for stdin in ("", "0 1\n2", "x 2")
        for binding in ("opcode", "recursive")
    ]
    results.append(_agrees(_Machine, "H", "", "bogus"))
    assert {error for error, _ in results} == {
        None,
        "syntax",
        "halt",
        "input",
        "argument",
    }
    assert any(not trace[-1][1] for error, trace in results if not error)
    assert _model("+(012)W-W-WH", "", "opcode")[1][-1][2] == " \n#"
    assert _model("+0->1>0+2WH", "", "recursive")[0] == "halt"
    controls = {
        "pop": ("+(12)-WH", ""),
        "flag": ("+1->1(+2)WH", ""),
        "first": ("l2-", ""),
        "wrap": ("+1", ""),
        "peek": ("+2WWH", ""),
        "read": ("rH", "2"),
        "syntax": ("+3", ""),
        "constructor": ("+", "2"),
    }
    for fault, (source, stdin) in controls.items():

        class Fault(_Machine):
            mode = fault

            def __init__(self, code, io, **kwargs):
                if self.mode == "constructor":
                    io.input_char()
                super().__init__(
                    code.replace("+3", "+2") if self.mode == "syntax" else code,
                    io,
                    **kwargs,
                )

            def step(self):
                if self.halted:
                    super().step()
                    return
                command = self.code[self.state.cursor].opcode
                super().step()
                if self.mode == "pop" and command == "-":
                    self.queue.appendleft(1)
                elif self.mode == "flag" and command == "-":
                    self.state = self.state._replace(flag=0)
                elif self.mode == "first":
                    self.state = self.state._replace(first=True)
                elif self.mode == "wrap":
                    self.state = self.state._replace(stopped=True)
                elif self.mode == "peek" and command == "W":
                    self.queue.popleft()
                elif self.mode == "read" and command == "r":
                    self.queue.clear()

        with pytest.raises(AssertionError):
            _agrees(Fault, source, stdin, "opcode")
    return len(results), len(controls)
