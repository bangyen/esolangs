"""Revision 198202 bidirectional search, using exact Fraction arithmetic."""

import itertools
import random
from fractions import Fraction

import pytest

from esolangs.languages.refractran.interpreter import _Machine
from tests.support import workspace_oracle as workspace

_WORKSPACE = workspace.workspace_model(
    "refractran-v1", "instruction integer direction printed input_cursor"
)


def _tokens(source):
    words, at = [], 0
    while at < len(source):
        if source[at] == "#":
            end = source.find("\n", at)
            at = len(source) if end < 0 else end
        elif source[at].isspace():
            at += 1
        else:
            start = at
            while at < len(source) and not source[at].isspace() and source[at] != "#":
                at += 1
            words.append((source[start:at], start))
    return words


def _decimal(text):
    if not text or any(c not in "0123456789" for c in text):
        raise ValueError
    return int(text)


def _parse(source):
    words = _tokens(source)
    if not words:
        raise ValueError
    initial = 1
    for factor in words[0][0].split("*"):
        base, caret, exponent = factor.partition("^")
        number = _decimal(base)
        if not number:
            raise ValueError
        initial *= number ** (_decimal(exponent) if caret else 1)
    fractions, offsets = [], []
    for token, offset in words[1:]:
        numerator, slash, denominator = token.partition("/")
        if not slash:
            raise ValueError
        a, b = _decimal(numerator), _decimal(denominator)
        if not a or not b:
            raise ValueError
        fractions.append(Fraction(a, b))
        offsets.append(offset)
    return initial, fractions, offsets


def _model(source):
    try:
        value, fractions, offsets = _parse(source)
    except ValueError:
        return "syntax", [(None, False, "", 0, 0)]
    index, direction, printed, output = 0, 1, False, ""

    def view():
        ip = offsets[index] if 0 <= index < len(offsets) else None
        return (
            (index, value, direction, printed, (value, direction), ip),
            printed,
            output,
            0,
            0,
        )

    trace = [view()]
    for _ in range(64):
        if printed:
            break
        if index < 0 or index >= len(fractions):
            output, printed = bin(value)[2:], True
        else:
            candidate = value * fractions[index] ** direction
            if candidate.denominator == 1:
                value, direction = candidate.numerator, -direction
            index += direction
        trace.append(view())
    if printed:
        trace.extend([view()] * 3)
    return None, trace


def _agrees(factory, source):
    return workspace.agrees(
        _model(source),
        (factory, source, "unused λ"),
        (_WORKSPACE, lambda r: (*r[0][:4], r[-1])),
        lambda m: (*m.state, m.printed, tuple(m.memory), m.ip),
        context=source,
    )


def check_raw_refractran():
    atoms = ("1/1", "2/3", "3/2", "3/5", "5/3", "6/4")
    corpus = [
        str(initial) + " " + " ".join(p)
        for initial in range(1, 7)
        for n in range(3)
        for p in itertools.product(atoms, repeat=n)
    ]
    rng = random.Random(20261103)
    corpus += [
        f"{rng.randrange(1, 33)} # initial\n "
        + " # fraction\n ".join(rng.choices(atoms, k=8))
        for _ in range(128)
    ]
    corpus += [
        "",
        "0",
        "-1",
        "2^-1",
        "2^",
        "2**3",
        "2 0/3",
        "2 3/0",
        "2 3/2/1",
        "2 abc",
        "٢ 3/2",
        "2 ٣/2",
        "2^0*3^2",
        "2#initial\n 3/2",
        "2 7/5 3/2",
        "1 " + "2/3 " * 80,
    ]
    results = [_agrees(_Machine, code) for code in corpus]
    assert {error for error, _ in results} == {None, "syntax"}
    assert any(not trace[-1][1] for error, trace in results if error is None)
    assert _model("2 3/5 3/2")[1][-1][2] == "101"
    workspace.check_erasures(_WORKSPACE, _agrees, _Machine, "2 3/2")
    controls = {
        "turn": "2 3/2",
        "inverse": "2 3/5 3/2",
        "failure": "2 3/5 3/2",
        "reduce": "2 6/4",
        "power": "2^3*3",
        "syntax": "0",
        "offset": "2 \n 3/2",
        "binary": "2",
        "repeat": "2",
        "input": "2 3/2",
    }
    for fault, source in controls.items():

        class Fault(_Machine):
            mode = fault

            def __init__(self, code, io):
                if self.mode == "syntax":
                    code = "1"
                elif self.mode == "power":
                    code = "2*3"
                elif self.mode == "reduce":
                    code = code.replace("6/4", "6/1")
                super().__init__(code, io)
                if self.mode == "offset":
                    self.offsets = (0,) * len(self.offsets)

            def step(self):
                index, value, direction = self.state
                if self.mode == "input" and not self.halted:
                    self.io.input_char()
                if self.mode == "repeat" and self.halted:
                    self.io.print_str("extra")
                if self.mode == "binary" and not self.halted and self.ip is None:
                    self.io.print_str(str(value))
                    self.printed = True
                elif self.mode == "inverse" and direction < 0 and self.ip is not None:
                    a, b = self.fractions[index]
                    self.state = type(self.state)(index - 1, value * a // b, direction)
                else:
                    super().step()
                    _at, got, heading = self.state
                    if self.mode == "turn" and heading != direction:
                        self.state = type(self.state)(index + direction, got, direction)
                    elif (
                        self.mode == "failure" and got == value and self.ip is not None
                    ):
                        self.state = type(self.state)(
                            index - direction, got, -direction
                        )

        with pytest.raises(AssertionError):
            _agrees(Fault, source)
    return len(results), len(controls)
