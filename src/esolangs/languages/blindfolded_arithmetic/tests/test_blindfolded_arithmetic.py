"""Tests for the Blindfolded Arithmetic interpreter."""

from pathlib import Path

import pytest

from esolangs import (
    ArgumentError,
    ExecutionCapError,
    ExecutionLimits,
    Language,
    ProgramError,
)
from esolangs.languages.blindfolded_arithmetic.interpreter import _Machine
from esolangs.runtime.io import ScriptedIO
from esolangs.runtime.memory import trunc_div
from esolangs.vm import complete_vm
from tests.support.cli_support import run_cli
from tests.support.vm_support import assert_rejected_output_retry


@pytest.mark.parametrize(
    ("dividend", "divisor", "quotient"),
    [(7, 2, 3), (-7, 2, -3), (7, -2, -3), (-7, -2, 3), (6, 3, 2)],
)
def test_division_truncates_toward_zero(
    dividend: int, divisor: int, quotient: int
) -> None:
    assert trunc_div(dividend, divisor) == quotient


def test_constructor_and_output_failures_preserve_native_phase(monkeypatch) -> None:
    """Constructor and output failures retain their input and halt boundaries."""
    io = ScriptedIO("")
    with pytest.raises(ValueError, match="at least one instruction"):
        _Machine("\n;  \n", io)
    for source, stdin, kind, expected in (
        ("", "7", ValueError, (0, 0, 0, 0)),
        ("i=i/a", "", EOFError, (0, 0, 0, 1)),
        ("i=i/a", "x 7", ValueError, (1, 1, 1, 0)),
    ):
        io = ScriptedIO(stdin)
        with pytest.raises(kind):
            _Machine(source, io)
        assert (io.position(), io.progress(), io.reads, io.past_end) == expected
        assert io.getvalue() == ""
    io = ScriptedIO("1 7")
    machine = _Machine("i=i/a", io)
    assert (io.position(), io.progress(), io.reads) == (1, 1, 1)
    original_write = io.print_num

    def rejected(_value):
        assert not machine.halted
        raise EOFError("output rejected")

    io.print_num = rejected
    captured = machine.workspace_snapshot()
    assert captured.parts == (((0, 0, 0, 0, 0, 1), 0), False, 1)
    for _ in range(2):
        with pytest.raises(EOFError, match="output rejected"):
            machine.step()
        assert machine.workspace_snapshot() == captured
        assert io.getvalue() == ""
    io.print_num = original_write
    machine.step()
    assert machine.halted
    machine.step()
    assert io.getvalue() == "1"
    assert io.input_char() == ord(" ")
    assert io.input_num() == 7
    assert_rejected_output_retry(
        "Blindfolded Arithmetic",
        "i=i/a",
        123,
        "123",
        prefix=0,
        stdin="123 9",
        monkeypatch=monkeypatch,
        unchanged_if_unwritten=True,
        following_writes=(),
    )

    from esolangs.languages.blindfolded_arithmetic import interpreter
    from tests.support.prepared_support import check_image_reuse

    check_image_reuse(
        "Blindfolded Arithmetic",
        "i=i/a",
        interpreter,
        "_parse",
        monkeypatch,
        cases=(("1", "1"), ("2", "2"), ("7", "7")),
    )


@pytest.mark.medium
def test_large_integer_output_matches_across_execution_routes() -> None:
    api = Language("Blindfolded Arithmetic")
    source = "i=i/a"
    text = "1" + "0" * 5000
    limits = ExecutionLimits(max_steps=1)
    for options in ({}, {"limits": limits}, {"limits": limits, "isolated": True}):
        result = api.run(source, stdin=text, **options)
        assert (result.output, result.input_position, result.input_reads) == (
            text,
            len(text),
            1,
        )
    assert complete_vm(api.make_vm(source, stdin=text), max_steps=1) == text
    with pytest.raises(ExecutionCapError) as caught:
        api.run(source, stdin=text, limits=ExecutionLimits(max_output=17))
    assert caught.value.bound == "max_output"
    assert caught.value.partial_output == text[:17]
    with pytest.raises(ArgumentError, match="input must be positive"):
        api.run(source, stdin="-" + text)


def test_ip_is_the_next_instructions_source_offset(tmp_path: Path) -> None:
    from esolangs.languages.blindfolded_arithmetic.tests.oracle_checks import (
        _agrees,
        check_raw_blindfolded_arithmetic,
    )

    check_raw_blindfolded_arithmetic()
    _agrees(_Machine, "i=i/i;i=i/a", "1" + "0" * 4400)
    machine = _Machine("a=i/i;  b=a+a", ScriptedIO("1\n"))
    assert machine.ip == 0
    machine.step()
    assert machine.ip == 8
    machine.step()
    assert machine.ip == 0
    assert machine.memory == [1, 2, 0, 0, 0, 1]

    api = Language("Blindfolded Arithmetic")
    path = tmp_path / "source"
    limits = ExecutionLimits(max_steps=4)
    for newline in ("\n", "\r\n"):
        source = newline.join(("i=i+i;", "", "  i=i/a", ""))
        path.write_bytes(source.encode())
        vm = api.make_vm(path, stdin="3\n")
        assert vm.ip == 0
        vm.step()
        assert vm.ip == source.index("i=i/a")
        assert api.run(path, stdin="3\n").output == "6"
        bounded = api.run(path, stdin="3\n", limits=limits)
        assert (bounded.output, bounded.steps) == ("6", 2)
        assert api.run(path, stdin="3\n", limits=limits, isolated=True) == bounded
        cli = run_cli("run", api.name, str(path), stdin="3\n")
        assert (cli.returncode, cli.stdout, cli.stderr) == (0, "6", "")
    with pytest.raises(ProgramError, match="not a Blindfolded Arithmetic instruction"):
        api.run("i=i+i\ri=i/a", stdin="3\n")
