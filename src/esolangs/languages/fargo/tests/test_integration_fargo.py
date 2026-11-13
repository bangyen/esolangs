"""Fargo through the shared API, CLI and machinery."""

from unittest.mock import patch

import pytest

import esolangs
import esolangs.debugger as debugger_api
from esolangs import run
from esolangs.exceptions import ArgumentError
from tests.support.cli_support import call_both
from tests.support.reference import REFERENCE


def test_describe_leads_with_the_contract(capsys) -> None:
    output, _error = call_both(["describe", "Fargo"], capsys)
    assert output.startswith("Fargo\ninput: one decimal row index")
    assert output.index("input:") < output.index("input_shape")
    assert "proof_status" not in output
    assert "{'labels'" not in output
    assert "Interpreter for Fargo" not in output
    assert "esolangs describe --spec Fargo" in output


class TestAHugeRowIndexIsRefusedNotCrashed:
    """CPython caps int<->str at 4300 digits; both directions leaked it."""

    def test_encode_inputs_refuses_a_row_index_past_the_digit_cap(self) -> None:
        """Fargo reads a decimal row index, and 15000 bits name too many digits."""
        with pytest.raises(ArgumentError):
            esolangs.encode_inputs("Fargo", [1] * 15000)


@pytest.mark.parametrize("choices", ["[]", "no json", '{"eof":true}'])
def test_cli_invalid_settings_precede_io(choices, capsys) -> None:
    with (
        patch("esolangs.cli.run._read_program", side_effect=AssertionError("read")),
        pytest.raises(SystemExit) as caught,
    ):
        call_both(["run", "--settings", choices, "Fargo", "missing"], capsys)
    assert caught.value.code == 2


@pytest.mark.medium
def test_bounded_run_executes_generated_xor() -> None:
    program = esolangs.generate("Fargo", "0110")
    for row, expected in enumerate("0110"):
        stdin = esolangs.encode_inputs("Fargo", tuple(map(int, format(row, "02b"))))
        assert (
            run(
                "Fargo",
                program,
                stdin=stdin,
                limits=esolangs.ExecutionLimits(max_steps=1000),
            ).output
            == expected
        )

    from .oracle_checks import check_raw_fargo

    check_raw_fargo(0, 96)


class TestFargo:
    def test_frames_and_cursor(self) -> None:
        vm = debugger_api.make_vm("Fargo", "$", stdin="0\n")
        # `memory` is the whole state: the input read and the output built.
        assert (vm.ip, vm.memory, vm.stack) == (0, [0, 0], [])
        vm.step()  # the top-level line pushes its frame
        assert vm.ip == 1
        assert len(vm.stack) == 1
        frame = vm.stack[0]
        assert (frame.tokens, frame.pos, frame.fn_name) == (("$",), 0, "")
        vm.step()  # $ prints the number it was given
        assert vm.output == "0"
        vm.step()  # the frame pops, and the run is over
        assert (vm.stack, vm.halted) == ([], True)


class TestEncodeInputsCanCheckItsArity:
    """The one function whose purpose is to stop a silent mis-encoding."""

    def test_a_wrong_bit_count_is_refused_when_the_table_is_given(self) -> None:
        """Three bits at a four-row table encoded as cheerfully as two."""
        with pytest.raises(esolangs.ArgumentError, match="2 inputs, but 3 bits"):
            esolangs.encode_inputs("Fargo", [1, 0, 1], truth_table="0110")

    def test_the_right_count_passes(self) -> None:
        """And still encodes the shape it always did."""
        assert esolangs.encode_inputs("Fargo", [1, 0], truth_table="0110") == "2\n"

    def test_a_malformed_table_is_named_as_one(self) -> None:
        """Not reported as a bit-count mismatch against a nonsense arity."""
        with pytest.raises(esolangs.TruthTableError):
            esolangs.encode_inputs(REFERENCE, [1, 0], truth_table="011")


def test_the_input_is_a_row_index() -> None:
    """The claim the prose got wrong, stated as an executable fact."""
    assert esolangs.describe("Fargo").input_shape == "row_index"
    assert esolangs.encode_inputs("Fargo", [1, 1, 1, 1]) == "15\n"


def test_a_bit_per_line_input_is_the_wrong_row() -> None:
    """Only n>=4 shows it."""
    table = "0000000000000001"  # AND of four inputs
    program = esolangs.generate("Fargo", table)
    right = run(
        "Fargo",
        program,
        stdin=esolangs.encode_inputs("Fargo", [1, 1, 1, 1]),
        limits=esolangs.ExecutionLimits(execution_timeout=20),
    ).output
    wrong = run(
        "Fargo",
        program,
        stdin="1111\n",
        limits=esolangs.ExecutionLimits(execution_timeout=20),
    ).output
    assert esolangs.read_answer("Fargo", right) == "1"
    assert esolangs.read_answer("Fargo", wrong) == "0"


def test_missing_stdin_selects_row_zero() -> None:
    """Fargo answered row 0 -- the starkest case, since nothing was fed."""
    assert (
        run(
            "Fargo",
            esolangs.generate("Fargo", "10010110"),
            stdin="",
            limits=esolangs.ExecutionLimits(execution_timeout=10),
        ).output
        == "1"
    )


def test_inputs_are_one_number_indexed_by_bit() -> None:
    assert esolangs.describe("Fargo").input_shape == "row_index"
    assert esolangs.encode_inputs("Fargo", [1, 0, 1]) == "5\n"
