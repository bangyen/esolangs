"""Explicit source rewriting with a mutable byte tape."""

from itertools import product

import pytest

from esolangs.languages.rotfuck.interpreter import _Machine
from tests.interpreters.oracle_support import after_step
from tests.support import workspace_oracle as workspace
from tests.support.model_input import matching_delimiter

_COMMANDS = "+-><,.[]"
_WORKSPACE = workspace.workspace_model(
    "rotfuck-v1", "rotation tape pointer instruction input_cursor"
)


def _partner(code, pc):
    token = code[pc]
    indices = range(pc + 1, len(code)) if token == "[" else range(pc - 1, -1, -1)
    span = matching_delimiter(
        (code[index] for index in indices), token, "]" if token == "[" else "["
    )
    return None if span is None else pc + (span if token == "[" else -span)


def _model(source, stdin, direction):
    order = _COMMANDS if direction == "forward" else _COMMANDS[::-1]
    rewrite = str.maketrans(order, order[1:] + order[0])
    tape = bytearray(1)
    pc = ptr = cursor = 0
    output = ""
    trace = []
    for step in range(25):
        halted = pc >= len(source)
        snapshot = (pc, ptr, tuple(tape), source), halted, output, cursor, cursor
        trace.append(snapshot)
        if halted:
            return None, trace + [snapshot] * 3
        if step == 24:
            break
        token = source[pc]
        destination = pc + 1
        match token:
            case "+" | "-":
                tape[ptr] = (tape[ptr] + (1 if token == "+" else -1)) % 256
            case ">":
                ptr += 1
                if ptr == len(tape):
                    tape.append(0)
            case "<":
                if ptr:
                    ptr -= 1
                else:
                    tape.insert(0, 0)
            case ",":
                if cursor == len(stdin):
                    return "input", [*trace, snapshot]
                tape[ptr] = ord(stdin[cursor]) % 256
                cursor += 1
            case ".":
                output += chr(tape[ptr])
            case "[" | "]":
                if bool(tape[ptr]) == (token == "]"):
                    partner = _partner(source, pc)
                    if partner is None:
                        return "halt", [*trace, snapshot]
                    destination = partner + 1
        if token in _COMMANDS:
            source = source.translate(rewrite)
        pc = destination
    return None, trace


def _parts(expected):
    error, trace = expected
    rotation = 0
    for index, row in enumerate(trace):
        if (
            index
            and not trace[index - 1][1]
            and not (error and index == len(trace) - 1)
        ):
            state = trace[index - 1][0]
            rotation += state[3][state[0]] in _COMMANDS
        state = row[0]
        yield rotation, state[2], state[1], state[0], row[-1]


def _check(factory, source, stdin, direction):
    def machine(code, io):
        return factory(code, io, rotation=direction)

    def state(vm):
        effective = "".join(vm.prog.at(i) for i in range(len(source)))
        return vm.ind, vm.ptr, vm.tape, effective

    expected = _model(source, stdin, direction)
    parts = iter(_parts(expected))
    workspace.agrees(
        expected,
        (machine, source, stdin),
        (_WORKSPACE, lambda _row: next(parts)),
        state,
        cap=24,
        context=(source, stdin, direction),
    )


def check_raw_rotfuck():
    corpus = ["".join(chars) for chars in product(_COMMANDS + "x", repeat=3)]
    corpus += ["", ",[", "[[--]]", "+x +x +x +x +x +x +x +x +"]
    for source, stdin, direction in product(corpus, ("", "Ł"), ("forward", "backward")):
        _check(_Machine, source, stdin, direction)

    # Each effective command is +, including the ninth after a full rotation.
    _check(_Machine, "+][.,<>-+", "", "forward")

    no_rotation = after_step(_Machine, lambda self: self.prog.set_rotation(0))

    with pytest.raises(AssertionError):
        _check(no_rotation, "++", "", "forward")

    workspace.check_erasures(_WORKSPACE, _check, _Machine, ",-<+", "Ł", "forward")
