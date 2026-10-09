"""Fargo through the shared API, CLI and machinery."""

import warnings
from unittest.mock import patch

import pytest

import esolangs
import esolangs.debugger as debugger_api
from esolangs.exceptions import ArgumentError
from tests.cli_support import call_both
from tests.stdin_check import _check_stdin


class TestALeadingZeroIndexNeverCrashes:
    """The message explaining a leading zero crashed on one."""

    @pytest.mark.parametrize("value", ["02", "089"])
    def test_a_non_binary_leading_zero_is_refused_cleanly(self, value: str) -> None:
        """`int('02', 2)` raises, so the friendly message threw a traceback."""
        with pytest.raises(esolangs.ArgumentError, match="leading zero"):
            _check_stdin("Fargo", f"{value}\n")

    @pytest.mark.parametrize("value", ["01", "010"])
    def test_a_binary_one_still_offers_the_index(self, value: str) -> None:
        """The helpful half must survive the fix to the crashing half."""
        with pytest.raises(esolangs.ArgumentError, match="if those are the input bits"):
            _check_stdin("Fargo", f"{value}\n")

    def test_the_suggested_index_is_right(self) -> None:
        """`010` as bits is row 2, and the message says so."""
        with pytest.raises(esolangs.ArgumentError, match="the index is 2"):
            _check_stdin("Fargo", "010\n")

    def test_a_large_binary_index_is_refused_without_rendering_it(self) -> None:
        with pytest.raises(esolangs.ArgumentError, match="15001 input bits") as caught:
            _check_stdin("Fargo", "0" + "1" * 15000)
        assert "leading zero" in str(caught.value)
        assert len(str(caught.value)) < 200


def test_describe_leads_with_the_contract(capsys):
    output, _error = call_both(["describe", "Fargo"], capsys)
    assert output.startswith("Fargo\ninput: one decimal row index")
    assert output.index("input:") < output.index("input_shape")
    assert "proof_status" not in output
    assert "{'labels'" not in output
    assert "Interpreter for Fargo" not in output
    assert "esolangs describe --spec Fargo" in output


class TestARowIndexNeverHasALeadingZero:
    """`0010` fed to a 16-row program parses as ten and answers row 10."""

    def test_a_bit_string_typed_as_an_index_is_caught(self) -> None:
        """No table needed; the message gives the index the bits meant."""
        with pytest.raises(esolangs.ArgumentError, match=r"leading zero.*index is 2"):
            _check_stdin("Fargo", "0010\n")

    def test_a_real_index_passes(self) -> None:
        """Including a single zero, which has no *leading* zero to speak of."""
        _check_stdin("Fargo", "0\n")
        _check_stdin("Fargo", "15\n")


class TestAHugeRowIndexIsRefusedNotCrashed:
    """CPython caps int<->str at 4300 digits; both directions leaked it."""

    def test_check_stdin_refuses_a_row_index_past_the_digit_cap(self) -> None:
        """``isdecimal`` passes for 4301 nines; ``int`` is what refuses them."""
        with pytest.raises(ArgumentError):
            _check_stdin("Fargo", "9" * 4301, "01")

    def test_encode_inputs_refuses_a_row_index_past_the_digit_cap(self) -> None:
        """Fargo reads a decimal row index, and 15000 bits name too many digits."""
        with pytest.raises(ArgumentError):
            esolangs.encode_inputs("Fargo", [1] * 15000)


@pytest.mark.parametrize("choices", ["[]", "no json", '{"eof":true}'])
def test_cli_invalid_settings_precede_io(choices, capsys):
    with (
        patch("esolangs.cli_run._read_program", side_effect=AssertionError("read")),
        pytest.raises(SystemExit) as caught,
    ):
        call_both(["run", "--settings", choices, "Fargo", "missing"], capsys)
    assert caught.value.code == 2


@pytest.mark.medium
def test_bounded_run_executes_generated_xor() -> None:
    program = esolangs.generate("Fargo", "0110")
    for row, expected in enumerate("0110"):
        stdin = esolangs.encode_inputs("Fargo", tuple(map(int, format(row, "02b"))))
        assert esolangs.run("Fargo", program, stdin=stdin, max_steps=1000) == expected


class TestFargo:
    def test_frames_and_cursor(self) -> None:
        vm = debugger_api.make_vm("Fargo", "$", stdin="0\n")
        # `memory` is the whole state: the input read and the output built.
        assert (vm.ip, vm.memory, vm.stack) == (0, [0, 0], [])
        vm.step()  # the top-level line pushes its frame
        assert vm.ip == 1
        assert len(vm.stack) == 1
        frame = vm.stack[0]
        assert (frame.tokens, frame.pos, frame.fn_name) == (("$",), 0, "")  # type: ignore[attr-defined]
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
            esolangs.encode_inputs("brainfuck", [1, 0], truth_table="011")


def test_the_input_is_a_row_index() -> None:
    """The claim the prose got wrong, stated as an executable fact."""
    assert esolangs.describe("Fargo")["input_shape"] == "row_index"
    assert esolangs.encode_inputs("Fargo", [1, 1, 1, 1]) == "15\n"


def test_a_bit_per_line_input_is_the_wrong_row() -> None:
    """Only n>=4 shows it."""
    table = "0000000000000001"  # AND of four inputs
    program = esolangs.generate("Fargo", table)
    right = esolangs.run(
        "Fargo",
        program,
        stdin=esolangs.encode_inputs("Fargo", [1, 1, 1, 1]),
        timeout=20,
    )
    wrong = esolangs.run("Fargo", program, stdin="1111\n", timeout=20)
    assert esolangs.read_answer("Fargo", right) == "1"
    assert esolangs.read_answer("Fargo", wrong) == "0"


def test_forgetting_stdin_entirely_is_warned_about() -> None:
    """Fargo answered row 0 -- the starkest case, since nothing was fed."""
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        esolangs.run(
            "Fargo", esolangs.generate("Fargo", "10010110"), stdin="", timeout=10
        )
