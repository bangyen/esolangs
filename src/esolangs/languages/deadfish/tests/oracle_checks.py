"""Revision 196539 arithmetic; optional halt and line-separated decimal output."""

import itertools
import random

import pytest

from esolangs.languages.deadfish.interpreter import _Machine
from tests.interpreters.oracle_support import observed


def _model(source):
    position, value, stopped, output = 0, 0, False, ""
    arithmetic = {"i": lambda x: x + 1, "d": lambda x: x - 1, "s": lambda x: x**2}

    def view():
        return (
            (position, value, stopped, (value,), position),
            stopped or position == len(source),
            output,
            0,
            0,
        )

    trace = [view()]
    for _ in range(64):
        if stopped or position == len(source):
            break
        command = source[position]
        if command == "h":
            stopped = True
        else:
            value = arithmetic.get(command, lambda x: x)(value)
            if value in {-1, 256}:
                value = 0
            if command == "o":
                output += str(value) + "\n"
            position += 1
        trace.append(view())
    if stopped or position == len(source):
        trace.extend([view()] * 3)
    return None, trace


def _agrees(factory, source):
    def state(m):
        return (*m.state, tuple(m.memory), m.ip)

    expected = _model(source)
    assert observed(factory, source, "λ\nunused", state) == expected, source
    return expected


def check_raw_deadfish():
    atoms = "idsohx"
    corpus = ["".join(p) for n in range(5) for p in itertools.product(atoms, repeat=n)]
    rng = random.Random(20261103)
    # Twelve characters bound repeated squaring as well as the step count.
    corpus += ["".join(rng.choices(atoms, k=12)) for _ in range(256)]
    corpus += [
        "iissso",
        "diissisdo",
        "iissis" + "d" * 33 + "o",
        "iioiio",
        "ihio",
        "IDSOH",
        "λ\n",
        "iis",
        "diissisoxo",
        "i" * 80,
    ]
    for source in corpus:
        _agrees(_Machine, source)
    assert _model("iissso")[1][-1][2] == "0\n"
    assert _model("diissisdo")[1][-1][2] == "288\n"
    controls = {
        "underflow": "do",
        "overflow": "diissisdo",
        "square": "iiso",
        "halt": "hio",
        "newline": "io",
        "input": "io",
    }
    for fault, source in controls.items():

        class Fault(_Machine):
            mode = fault

            def __init__(self, code, io):
                if self.mode == "newline":
                    write = io.print_str
                    io.print_str = lambda text: write(text.rstrip("\n"))
                super().__init__(code, io)

            def step(self):
                if self.halted:
                    super().step()
                    return
                pc, value, _ = self.state
                command = self.code[pc]
                if self.mode == "halt" and command == "h":
                    self.state = pc + 1, value, False
                    return
                if self.mode == "input":
                    self.io.input_char()
                super().step()
                pc, current, stopped = self.state
                if self.mode == "underflow" and command == "d" and value == 0:
                    current = 255
                elif self.mode == "overflow" and current > 256:
                    current = 0
                elif self.mode == "square" and command == "s":
                    current += 1
                self.state = pc, current, stopped

        with pytest.raises(AssertionError):
            _agrees(Fault, source)
    return len(corpus), len(controls)
