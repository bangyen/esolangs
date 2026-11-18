"""Tests for the Bytemap interpreter."""

import random

import pytest

from esolangs import ExecutionLimits, Language, ProgramError
from esolangs.exceptions import HaltError
from esolangs.languages.bytemap.interpreter import _Machine, run
from esolangs.runtime.io import ScriptedIO
from tests.support.vm_support import assert_rejected_output_retry

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


def test_the_pages_examples_and_rulings(monkeypatch: pytest.MonkeyPatch) -> None:
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
    _check_retry_and_line_endings(monkeypatch)


def _check_retry_and_line_endings(monkeypatch: pytest.MonkeyPatch) -> None:
    api = Language("Bytemap")
    limits = ExecutionLimits(max_steps=8)
    assert_rejected_output_retry(
        api.name, "0A560502FF4142", "AB", "AB", prefix=0, monkeypatch=monkeypatch
    )
    for source in ("FF\n", "FF\r\n"):
        assert api.run(source, limits=limits, isolated=True).steps == 1
    for source in ("FF\r", "FF\r\r\n"):
        with pytest.raises(ProgramError, match="uppercase hex digit"):
            api.run(source, limits=limits, isolated=True)

    read = ScriptedIO.input_char
    for command, stdin in (("1A", "ABC"), ("1F", "414243")):
        source = command + "5609020A560502FF0000"
        expected = api.run(source, stdin=stdin, limits=limits, isolated=True)
        assert expected.output == "AB"

        def refuse(io, prompt="Input: "):
            if io.position() == 1:
                raise HaltError("temporary input refusal")
            return read(io, prompt)

        debugger = api.make_debugger(source, stdin=stdin)
        before = debugger.snapshot()
        with monkeypatch.context() as patch:
            patch.setattr(ScriptedIO, "input_char", refuse)
            with pytest.raises(HaltError, match="temporary input refusal"):
                debugger.step()
        assert debugger.ip == (0, 0)
        assert (debugger.observation.input_position, debugger.observation.steps) == (
            1,
            0,
        )
        assert debugger.snapshot() != before
        assert debugger.run(limits=limits) == "halted"
        assert debugger.observation == expected

    for command, prefix in (("1A", "A"), ("1F", "41")):
        source = command + "5609020A560502FF0000"
        stdin = prefix + "\ud800BC"
        expected = api.execute(source, stdin=stdin, limits=limits, isolated=True)
        assert isinstance(expected.error, ProgramError)
        cause = expected.error.__cause__
        assert isinstance(cause, UnicodeEncodeError)
        debugger = api.make_debugger(source, stdin=stdin)
        for _ in range(2):
            with pytest.raises(ProgramError, match="surrogates not allowed") as caught:
                debugger.step()
            actual = caught.value.__cause__
            assert isinstance(actual, UnicodeEncodeError)
            assert actual.args == cause.args
            assert debugger.ip == (0, 0)
            assert debugger.observation == expected.observation
        assert debugger.observation.input_position == len(prefix) + 1


@pytest.mark.medium
def test_sixteen_essential_inputs_split_row_zero_and_page_the_return() -> None:
    # Reading code needs two row-0 segments from 13 essential inputs and a
    # paged return along row 1 from 16, where it spans 266 cells against a
    # jump's 255; the weekly deadcode scan found both unreached.  16 sampled
    # rows of 65,536.
    rng = random.Random(16)
    n = 16
    table = "".join(rng.choice("01") for _ in range(2**n))
    api = Language("Bytemap")
    program = api.generate(table)
    for row in [0, 2**n - 1, *rng.sample(range(2**n), 14)]:
        bits = [int(bit) for bit in f"{row:0{n}b}"]
        output = api.run(program, stdin=api.encode_inputs(bits)).output
        assert api.read_answer(output) == table[row], row
