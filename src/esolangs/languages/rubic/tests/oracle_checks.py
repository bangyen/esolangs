"""Sticker geometry computed with dot and cross products."""

import re
from itertools import product

import pytest

from esolangs.exceptions import HaltError
from esolangs.languages.rubic.interpreter import _Machine, prepare_machine
from esolangs.runtime.io import ScriptedIO
from tests.interpreters.oracle_support import decorate_io, reject_faults
from tests.support import workspace_oracle as workspace

_WORKSPACE = workspace.workspace_model(
    "rubic-v1", "instruction accumulator cube loop_frames input_cursor"
)

_NORMALS = {
    "w": (0, 1, 0),
    "w'": (0, -1, 0),
    "g": (0, 0, 1),
    "g'": (0, 0, -1),
    "o": (-1, 0, 0),
    "o'": (1, 0, 0),
}
_LAYERS = dict(
    zip("udfblrmes", ("w", "w'", "g", "g'", "o", "o'", "o'", "w", "g"), strict=True)
)


def _dot(a, b):
    return sum(x * y for x, y in zip(a, b, strict=True))


def _quarter(vector, axis):
    x, y, z = vector
    a, b, c = axis
    cross = (y * c - z * b, z * a - x * c, x * b - y * a)
    parallel = _dot(vector, axis)
    return tuple(
        component + parallel * normal
        for component, normal in zip(cross, axis, strict=True)
    )


def _model(turns):
    stickers = [
        (position, normal, colour)
        for position in product((-1, 0, 1), repeat=3)
        for colour, normal in _NORMALS.items()
        if _dot(position, normal) == 1
    ]
    for face, suffix in turns:
        axis = _NORMALS[_LAYERS[face]]
        layer = int(face not in "mes")
        for _ in range({"": 1, "2": 2, "'": 3}[suffix]):
            stickers = [
                (_quarter(p, axis), _quarter(n, axis), c)
                if _dot(p, axis) == layer
                else (p, n, c)
                for p, n, c in stickers
            ]
    centres = {colour: normal for p, normal, colour in stickers if p == normal}
    return "".join(
        chr(
            sum(
                n == centres[face] and p != n and colour == target
                for p, n, colour in stickers
            )
        )
        for face, target in product(_NORMALS, repeat=2)
    )


def _check(factory, turns):
    source = " ".join(
        [face.upper() + suffix for face, suffix in turns]
        + [f".{face}{target} !" for face, target in product(_NORMALS, repeat=2)]
    )
    io = ScriptedIO("unused")
    machine = factory(source, io)
    for _ in range(80):
        if machine.halted:
            break
        machine.step()
    assert machine.halted
    assert io.position() == 0
    assert io.getvalue() == _model(turns), turns
    _check_workspace(factory, source, "unused")


def check_raw_rubic():
    for turn in product(_LAYERS, ("", "2", "'")):
        _check(_Machine, (turn,))
        _check(_Machine, (("r", ""), turn, ("f", "'"), ("u", "2")))
    _check(_Machine, ())

    class InvertedTurn(_Machine):
        def __init__(self, code, io):
            super().__init__(code.replace("R ", "R' ", 1), io)

    with pytest.raises(AssertionError):
        _check(InvertedTurn, (("r", ""), ("f", "")))
    _extra_workspace()


def _stickers():
    return {
        (position, normal): colour
        for position in product((-1, 0, 1), repeat=3)
        for colour, normal in _NORMALS.items()
        if _dot(position, normal) == 1
    }


def _turn(stickers, token, *, backwards):
    axis = _NORMALS[_LAYERS[token[0]]]
    turns = 2 if token.endswith("2") else 3 if token.endswith("'") else 1
    if backwards:
        turns = (-turns) % 4
    for _ in range(turns):
        stickers = {
            (_quarter(p, axis), _quarter(n, axis))
            if _dot(p, axis) == int(token[0] not in "mes")
            else (p, n): colour
            for (p, n), colour in stickers.items()
        }
    return stickers


def _count(stickers, text):
    colours = re.findall(r"[wgo]'?", text)
    assert len(colours) == 2
    assert "".join(colours) == text
    face, target = colours
    middle = next(n for (p, n), colour in stickers.items() if p == n and colour == face)
    return sum(
        n == middle and p != n and colour == target
        for (p, n), colour in stickers.items()
    )


def _arithmetic(command, value, amount, *, backwards):
    if backwards:
        if command == ".":
            return -amount
        if command == "%":
            return value
        command = {"+": "-", "-": "+", "*": "/", "/": "*"}[command]
    if command == ".":
        return amount
    if command == "+":
        return value + amount
    if command == "-":
        return value - amount
    if command == "*":
        return value * amount
    if command == "/":
        return value // amount if amount else 0
    assert command == "%"
    return value % amount if amount else value


def _loop(tokens, pc, value, frames):
    backwards = bool(frames) and frames[-1][3]
    start, end = (pc, pc)
    if tokens[pc] == "(":
        depth = 1
        while depth:
            end += 1
            depth += (tokens[end] == "(") - (tokens[end] == ")")
    else:
        depth = 1
        while depth:
            start -= 1
            depth += (tokens[start] == ")") - (tokens[start] == "(")
    resume = start - 1 if backwards else end + 1
    if not value:
        return resume
    frames.append((start, end, abs(value), value < 0, resume))
    return end - 1 if value < 0 else start + 1


def _history(source, stdin, *, output_failure=False):
    tokens = source.lower().split()
    stickers, frames = _stickers(), []
    positions = sorted(stickers)
    pc = value = cursor = reads = past_end = 0
    output, failure, trace = "", None, []

    def row():
        cube = tuple(tuple(_NORMALS).index(stickers[slot]) for slot in positions)
        parts = pc, value, cube, tuple(frames), cursor
        return (
            (parts, reads, past_end),
            not frames and pc >= len(tokens),
            output,
            cursor,
            cursor,
        )

    trace.append(row())
    for _ in range(80):
        if not frames and pc >= len(tokens):
            trace.extend([row()] * 3)
            return failure, trace
        backwards = bool(frames) and frames[-1][3]
        token, nxt = tokens[pc], pc + (-1 if backwards else 1)
        if frames and pc == frames[-1][int(backwards is False)]:
            start, end, remaining, reverse, resume = frames.pop()
            if remaining > 1:
                frames.append((start, end, remaining - 1, reverse, resume))
                nxt = end - 1 if reverse else start + 1
            else:
                nxt = resume
        elif token in ("(", ")"):
            nxt = _loop(tokens, pc, value, frames)
        elif token[0] in _LAYERS:
            stickers = _turn(stickers, token, backwards=backwards)
        elif token == "!":
            if backwards:
                if cursor == len(stdin):
                    past_end += 1
                    failure = "input"
                else:
                    value = ord(stdin[cursor])
                    cursor, reads = cursor + 1, reads + 1
            else:
                output += chr(value % 128)
                if output_failure:
                    failure = "halt"
        else:
            value = _arithmetic(
                token[0], value, _count(stickers, token[1:]), backwards=backwards
            )
        if failure != "input":
            pc = nxt
        trace.append(row())
        if failure:
            return failure, trace
    if not frames and pc >= len(tokens):
        return None, trace + [row()] * 3
    raise AssertionError("finite Rubic corpus exceeded cap80")


def _view(machine):
    state = machine.state
    parts = (
        state.ind,
        state.v,
        tuple(state.cube),
        tuple(map(tuple, state.frames)),
        machine.io.progress(),
    )
    return parts, machine.io.reads, machine.io.past_end


def _check_workspace(factory, source, stdin="", *, output_failure=False):
    return workspace.agrees(
        _history(source, stdin, output_failure=output_failure),
        (factory, source, stdin),
        (_WORKSPACE, lambda row: row[0][0]),
        _view,
        cap=80,
    )


def _siblings(source, stdin):
    expected = _history(source, stdin)[1]
    build = prepare_machine(source, {})
    machines = (build(ScriptedIO(stdin)), build(ScriptedIO(stdin)))
    for machine, sibling in (machines, machines[::-1]):
        inactive = sibling.workspace_snapshot()
        checked = workspace.workspace_view(
            expected, _WORKSPACE, lambda row: row[0][0], _view
        )
        for index, reference in enumerate(expected):
            if index:
                machine.step()
            assert (
                checked(machine),
                machine.halted,
                machine.io.getvalue(),
                machine.io.position(),
                machine.io.progress(),
            ) == reference
            assert sibling.workspace_snapshot() == inactive


def _extra_workspace():
    source = "r b -og ( ! ) !"
    expected = _check_workspace(_Machine, source, "A")
    assert expected[1][-1][2] == "A"
    start = expected[1][0][0][0]
    assert all(
        any(row[0][0][index] != part for row in expected[1])
        for index, part in enumerate(start)
    )
    for code, stdin in (
        (source, ""),
        (source, "Ā"),
        ("r b .og ( ( +og ) ) !", ""),
        ("r b .og ( r +og *og /og %og ) !", ""),
        ("r b -og ( +og *og /og %og ) !", ""),
        ("", ""),
    ):
        _check_workspace(_Machine, code, stdin)
    workspace.check_erasures(_WORKSPACE, _check_workspace, _Machine, source, "A")
    reject_faults(
        _check_workspace,
        _Machine,
        workspace.missing_workspace(_Machine, "cube"),
        source,
        "A",
    )

    def refuse(write):
        def output(char):
            write(char)
            raise HaltError("Rubic witness writer refusal")

        return output

    _check_workspace(
        decorate_io(_Machine, "print_char", refuse), source, "A", output_failure=True
    )

    class ErasedCounts(_Machine):
        def step(self):
            try:
                super().step()
            finally:
                self.io._reads = self.io._past_end = 0

    for stdin in ("", "A"):
        with pytest.raises(AssertionError):
            _check_workspace(ErasedCounts, source, stdin)
    _siblings(source, "A")
