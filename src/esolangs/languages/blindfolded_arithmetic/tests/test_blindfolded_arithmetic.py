"""Tests for the Blindfolded Arithmetic interpreter."""

import pytest

from esolangs.languages.blindfolded_arithmetic.interpreter import _Machine
from esolangs.runtime.io import ScriptedIO
from esolangs.runtime.memory import trunc_div


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

    def rejected(_value):
        assert machine.halted
        raise EOFError("output rejected")

    io.print_num = rejected
    with pytest.raises(EOFError, match="output rejected"):
        machine.step()
    assert machine.halted
    assert io.getvalue() == ""
    captured = machine.workspace_snapshot()
    assert captured.parts == (((0, 0, 0, 0, 0, 1), 0), True, 1)
    machine.step()
    assert machine.workspace_snapshot() == captured
    assert io.input_char() == ord(" ")
    assert io.input_num() == 7

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


def test_ip_is_the_next_instructions_source_offset() -> None:
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
