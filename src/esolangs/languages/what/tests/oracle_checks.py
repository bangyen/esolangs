"""Closed-form checks for arithmetic, counted loops, and dual-slot guards."""

from itertools import product
from operator import add, floordiv, mul, sub

import pytest

from esolangs.exceptions import HaltError
from esolangs.languages.what.interpreter import _Machine
from esolangs.runtime.io import ScriptedIO


def _output(factory, source, stdin=""):
    io = ScriptedIO(stdin)
    machine = factory(source, io)
    for _ in range(128):
        if machine.halted:
            break
        machine.step()
    assert machine.halted, source
    assert io.position() == len(stdin)
    return io.getvalue()


def _arithmetic(factory, left, right, token, operation):
    source = f'{left}."tag"{right}{token}!!"!"!!!'
    if token == "/" and not left:
        with pytest.raises(HaltError, match="division by zero"):
            _output(factory, source)
        return
    assert _output(factory, source) == f"{operation(right, left) % 65536}tag!"


def check_raw_what():
    for left, right, (token, operation) in product(
        (0, 1, 11, 65535),
        (0, 2, 10, 65534),
        zip("+-*/", (add, sub, mul, floordiv), strict=True),
    ):
        _arithmetic(_Machine, left, right, token, operation)
    for count, value in product(range(1, 9), ("A", "Ω", "\n")):
        source = f'1.{count}("x"-)!!!.?!!'
        assert _output(_Machine, source, value) == "x" * count + str(ord(value))
    for literal, current, op in product(
        (0, 2, 9), (0, 3, 9), (":", "<", ">", ":;", "<>")
    ):
        tests = {
            ":": literal == current,
            "<": literal < current,
            ">": literal > current,
        }
        holds = any(tests[t] for t in op if t != ";") != (";" in op)
        source = f'{current}[{literal}{op}"yes"]"end"!!!'
        assert _output(_Machine, source) == ("yes" if holds else "") + "end"

    class ReversedSubtraction(_Machine):
        def __init__(self, code, io):
            super().__init__(code.replace("-", "+"), io)

    with pytest.raises(AssertionError):
        _arithmetic(ReversedSubtraction, 2, 7, "-", sub)
