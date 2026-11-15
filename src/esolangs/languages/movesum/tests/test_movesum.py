"""Tests for the Movesum interpreter."""

import pytest

from esolangs import ExecutionCapError, ExecutionLimits, Language
from esolangs.exceptions import HaltError
from esolangs.languages.movesum.interpreter import _Machine, run
from esolangs.runtime.io import ScriptedIO
from esolangs.vm import complete_vm
from tests.interpreters.runner import native_runner

out = native_runner(run)


def test_unchanged_compares_values_not_keys() -> None:
    from esolangs.languages.movesum.tests.oracle_checks import check_raw_movesum

    check_raw_movesum()
    """Writing 0 to a fresh cell is no change: the truth machine halts on 0."""
    assert out("0=0\nmove 0 -1\nmove 0 7") == "0"
    assert out("0=42\nmove 0 -1\nmove 0 1\nmove 2 1", "0\n") == "0"


def test_a_change_resets_the_count() -> None:
    """Two quiet commands halt; a changing one between them keeps it going."""
    assert out("0=1\nmove 0 -1\nmove 0 2\nmove 0 -1\nmove 0 0") == "1 1"


def test_sum_adds_cells_one_to_four() -> None:
    code = "0=9 1=1 2=2 3=3 4=4 5=100\nsum\nmove 0 -1\nmove 0 0"
    assert out(code) == "10"


def test_both_negative_is_a_quiet_command() -> None:
    assert out("0=5\nmove -1 -1\nmove -2 -3\nmove 0 -1") == ""


def test_42_as_key_reads_before_the_value(monkeypatch) -> None:
    assert out("42=42\nmove 5 -1\nmove 0 0", "5\n7\n") == "7"
    from esolangs.languages.movesum import interpreter
    from tests.support.prepared_support import check_image_reuse

    check_image_reuse(
        "Movesum",
        "42=42\nmove 5 -1\nmove 0 0",
        interpreter,
        "_prepare_source",
        monkeypatch,
        cases=(("5\n7\n", "7"), ("5\n8\n", "8"), ("5\n9\n", "9")),
    )


def test_eof_reads_zero() -> None:
    assert out("1=42\nmove 1 -1\nmove 0 0") == "0"
    assert out("0=9\nmove -1 0\nmove 0 -1\nmove 0 0") == "0"


def test_no_separator_trails_and_blank_lines_are_skipped() -> None:
    assert out("0=1 1=2\n\nmove 0 -1\n\nmove 1 -1\nmove 0 0\n") == "1 2"


def test_the_array_is_unbounded_to_the_right() -> None:
    assert out("0=3\nmove 0 100000\nmove 100000 -1\nmove 0 0") == "3"


def test_a_negative_input_is_refused() -> None:
    with pytest.raises(HaltError, match="negative"):
        out("0=0\nmove -1 1\nmove 1 -1", "-1\n")


@pytest.mark.medium
def test_large_decimal_moves_and_output() -> None:
    api = Language("Movesum")
    number = "1" + "0" * 5000
    address = "2" + "0" * 5000
    source = f"{address}=42\nmove {address} -1"
    expected = number + " " + number
    assert api.run(f"{address}={number}\nmove {address} -1").output == expected
    limits = ExecutionLimits(max_steps=3)
    for isolated in (False, True):
        result = api.run(source, stdin=number, limits=limits, isolated=isolated)
        assert (
            result.output,
            result.input_position,
            result.input_reads,
            result.steps,
        ) == (
            expected,
            len(number),
            1,
            3,
        )
    assert complete_vm(api.make_vm(source, stdin=number), max_steps=3) == expected
    cap = len(number) + 3
    with pytest.raises(ExecutionCapError) as caught:
        api.run(source, stdin=number, limits=ExecutionLimits(max_output=cap))
    assert caught.value.bound == "max_output"
    assert caught.value.partial_output == expected[:cap]
    with pytest.raises(HaltError, match="negative input"):
        api.run(source, stdin="-" + number)


def test_failed_output_does_not_commit_a_quiet_step(monkeypatch) -> None:
    source = "0=1\nmove 0 -1"
    io = ScriptedIO("")
    machine = _Machine(source, io)
    machine.step()
    machine.step()
    before = machine.snapshot()

    def fail(_text):
        raise HaltError("write refused")

    with monkeypatch.context() as patch:
        patch.setattr(io, "print_str", fail)
        for _ in range(2):
            with pytest.raises(HaltError, match="write refused"):
                machine.step()
            assert not machine.halted
            assert machine.snapshot() == before
            assert io.getvalue() == "1"
    machine.step()
    assert machine.halted
    assert io.getvalue() == "1 1"
