"""Tests for the Bytemap interpreter."""

import pytest

from esolangs.exceptions import HaltError
from esolangs.languages.bytemap.interpreter import _Machine, run
from esolangs.runtime.io import ScriptedIO

_TRUTH = (
    "105201045202\nFFFFFFFFFFFF\n5201FFFF5404\n"
    "C3580200000452015202\n00540001FF\n005603015404"
)


def _out(code: str, stdin: str = "", steps: int | None = None) -> str:
    io = ScriptedIO(stdin)
    if steps is None:
        run(code, io)
    else:  # a program the page runs forever: take its first steps
        machine = _Machine(code, io)
        for _ in range(steps):
            machine.step()
    return io.getvalue()


def test_the_pages_examples_and_rulings() -> None:
    # The page's examples with stated output.
    assert _out("0A56050CFF48656C6C6F20576F726C6421") == "Hello World!"
    assert _out("005603015404", steps=6) == "111"
    assert _out("0F540005FF") == "0F540005FF"
    assert _out("0F540004") == "0F540004"
    assert _out(_TRUTH, "0") == "0"
    assert _out(_TRUTH, "7", steps=12) == "1111"
    # The row replicator copies itself one command ahead, forever.
    machine = _Machine("A000005400560808", ScriptedIO())
    for _ in range(3):
        machine.step()
    assert [machine.cell((0, c)) for c in range(24, 32)] == [
        0xA0,
        0,
        0,
        0x54,
        0,
        0x56,
        8,
        8,
    ]
    # Big-endian, signed; EOF writes FF; an invalid first jump reads 0 and
    # an invalid second 1, so A1 writes 0 - 1 over two bytes.
    assert _out("00560502FF0102") == "258"
    assert _out("1A56080100560401") == "-1"
    assert _out("A100000000560A0200560202") == "-1"
    for code, message in (("0g", "hex digit"), ("ABC", "odd")):
        with pytest.raises(ValueError, match=message):
            _out(code)
    for code, message in (("20", "not a command"), ("A30000560856090100", "zero")):
        with pytest.raises(HaltError, match=message):
            _out(code)
