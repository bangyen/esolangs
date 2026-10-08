"""Unit tests for Sophie interpreter."""

import io
from contextlib import redirect_stdout
from unittest.mock import patch

import pytest

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import IO
from esolangs.interpreters.register_based.sophie import run
from tests.interpreters.contract import CycleContract, SnapshotContract


class TestSophieBasicCommands:
    @pytest.mark.parametrize(
        ("code", "expected"),
        [
            pytest.param("#$42.&", "42", id="output_number"),
            pytest.param("#A,&", "A", id="output_char"),
            # Program halts before reaching output
            pytest.param("&.", "", id="halt_command"),
        ],
    )
    def test_output(self, code: str, expected: str) -> None:
        with redirect_stdout(io.StringIO()) as f:
            run(code, io=IO())
        assert f.getvalue() == expected

    def test_input_number(self) -> None:
        with (
            patch("builtins.input", return_value="123"),
            redirect_stdout(io.StringIO()) as f,
        ):
            run(":.&", io=IO())
        assert f.getvalue() == "123"

    def test_input_char(self) -> None:
        with (
            patch("builtins.input", return_value="X"),
            redirect_stdout(io.StringIO()) as f,
        ):
            run(";,&", io=IO())
        assert f.getvalue() == "X"


class TestSophieConditionals:
    @pytest.mark.parametrize(
        ("code", "expected"),
        [
            pytest.param("#A@A{,#C,}&", "AC", id="char_conditional_true"),
            pytest.param("#$65@$65{,#C,}&", "AC", id="number_conditional_true"),
            pytest.param("#A@A{,&}", "A", id="conditional_without_else"),
            pytest.param("#A@A{@$65{,#B,}}{#C,}&", "AB", id="nested_conditionals"),
        ],
    )
    def test_conditional_output(self, code: str, expected: str) -> None:
        with redirect_stdout(io.StringIO()) as f:
            run(code, io=IO())
        assert f.getvalue() == expected


class TestSophieLoops:
    @pytest.mark.parametrize(
        ("code", "expected"),
        [
            # Should print 3 then break
            pytest.param("#$3[.*]&", "3", id="simple_loop"),
            # `*` breaks only its own loop (wiki "break loop"; the author's
            # sophie.py pops one loop), so the outer loop needs its own break.
            pytest.param("#A[#B[.*]*]&", "66", id="nested_loops"),
            # Closing a loop pops one frame, not all but the outermost.
            pytest.param("#A[#B[#C[.*]*]*]&", "67", id="loops_nested_three_deep"),
        ],
    )
    def test_loop_output(self, code: str, expected: str) -> None:
        with redirect_stdout(io.StringIO()) as f:
            run(code, io=IO())
        assert f.getvalue() == expected


class TestSophieComments:
    def test_comment_block(self) -> None:
        with redirect_stdout(io.StringIO()) as f:
            run("{This is a comment}#A,&", io=IO())
        assert f.getvalue() == "A"

    def test_nested_comments(self) -> None:
        with redirect_stdout(io.StringIO()) as f:
            run("{Outer{Inner}comment}#A,&", io=IO())
        assert f.getvalue() == "A"


class TestSophieInputHandling:
    def test_invalid_number_input(self) -> None:
        with (
            patch("builtins.input", return_value="not_a_number"),
            redirect_stdout(io.StringIO()) as f,
        ):
            run("#$42:.&", io=IO())
        # A newline replaces the accumulator with character code 10.
        assert f.getvalue() == "42"

    def test_newline_char_input(self) -> None:
        with (
            patch("builtins.input", return_value=""),
            redirect_stdout(io.StringIO()) as f,
        ):
            run("#$42;.&", io=IO())
        # A newline replaces the accumulator with character code 10.
        assert f.getvalue() == "10"

    def test_multiple_inputs(self) -> None:
        with (
            patch("builtins.input", side_effect=["65 B"]),
            redirect_stdout(io.StringIO()) as f,
        ):
            run(":;,&", io=IO())
        assert f.getvalue() == " "


class TestSophieEdgeCases:
    @pytest.mark.parametrize(
        ("code", "expected"),
        [
            pytest.param("", "", id="empty_program"),
            # ``#[`` loads the ``[`` as data, so no loop is left unmatched.
            pytest.param("#[", "", id="a_bracket_loaded_by_a_marker_is_not_a_bracket"),
            # Validation already skipped ``#]``; the jump table did not.
            pytest.param(
                "[#]*]#A,&", "A", id="a_loaded_bracket_is_data_to_the_jumps_too"
            ),
            # A break used to set a flag that skipped the next loop entered.
            pytest.param(
                "[#A,[,*][#B,*]*]#C,&", "AABC", id="a_break_leaves_later_loops_running"
            ),
            # Brackets loaded as ``#`` data are not treated as structure.
            pytest.param("#{,", "{", id="braces_loaded_as_data"),
        ],
    )
    def test_edge_case_output(self, code: str, expected: str) -> None:
        with redirect_stdout(io.StringIO()) as f:
            run(code, io=IO())
        assert f.getvalue() == expected

    def test_a_program_ending_on_a_load_marker(self) -> None:
        """``#`` and ``#$`` may be the last thing in the program."""
        for code in ("#", "#$"):
            with redirect_stdout(io.StringIO()) as f:
                run(code, io=IO())
            assert f.getvalue() == "", code

    def test_a_dollar_without_a_number_is_the_loaded_character(self) -> None:
        """``#c`` with c ``$``: the ``[`` after ``#$`` is structure, not data."""
        with pytest.raises(ValueError, match="unmatched"):
            run("#$[", io=IO())
        with redirect_stdout(io.StringIO()) as f:
            run("#$#[,", io=IO())
        assert f.getvalue() == "["

    def test_a_digit_load_stops_at_the_first_non_digit(self) -> None:
        """``#$1[`` loads the digits only, leaving the bracket as structure."""
        for code in ("#$1[", "#$123["):
            with pytest.raises(ValueError, match="unmatched"):
                run(code, io=IO())

    def test_unmatched_brackets(self) -> None:
        with pytest.raises(ValueError, match="unmatched"):
            run("#A{&", io=IO())

    def test_break_outside_loop_halts(self) -> None:
        with pytest.raises(HaltError):
            run("*&", io=IO())

    def test_numbers_past_the_decimal_digit_cap(self) -> None:
        """A 5000-digit load prints back whole (CPython's str cap is 4300)."""
        digits = "9" * 5000
        with redirect_stdout(io.StringIO()) as f:
            run(f"#${digits}.&", io=IO())
        assert f.getvalue() == digits

    def test_unmatched_closing_brace(self) -> None:
        with pytest.raises(ValueError, match="unmatched"):
            run("#A}", io=IO())

    def test_unmatched_square_brackets(self) -> None:
        with pytest.raises(ValueError, match="unmatched"):
            run("#A[.*", io=IO())


class TestMiscCommands:
    def test_dollar_char_loaded_as_data(self) -> None:
        """``#$.`` loads ``$`` and prints it: the page has only ``#c`` and
        ``#$n``, and the clean-room reference agrees (``$`` was a marker).
        """
        with redirect_stdout(io.StringIO()) as f:
            run("#$.#$A,", io=IO())
        assert f.getvalue() == "36$"

    def test_invalid_commands_ignored(self) -> None:
        with redirect_stdout(io.StringIO()) as f:
            run("xyz#A,&", io=IO())
        # Only valid commands should execute
        assert f.getvalue() == "A"


class TestSophieExamples:
    def test_cat_program_stops_on_nul(self) -> None:
        from esolangs.interpreters.io import ScriptedIO

        source = ScriptedIO("\0")
        run("[;@$0{&}{,}]", io=source)
        assert source.getvalue() == ""

    def test_cat_program_halts_at_eof(self) -> None:
        from esolangs.interpreters.io import ScriptedIO

        source = ScriptedIO("ab")
        run("[;@$0{&}{,}]", io=source)
        assert source.getvalue() == "ab"

    @pytest.mark.parametrize("read", [";", ":"])
    def test_a_read_at_eof_is_zero(self, read: str) -> None:
        from esolangs.interpreters.io import ScriptedIO

        source = ScriptedIO("")
        run(f"#$42{read}.&", io=source)
        assert source.getvalue() == "0"

    def test_cat_program_with_input(self) -> None:
        with (
            patch("builtins.input", return_value="H"),
            redirect_stdout(io.StringIO()) as f,
        ):
            run(";@$0{&}{,}&", io=IO())
        assert f.getvalue() == "H"

    def test_xor_program_0_0(self) -> None:
        with (
            patch("builtins.input", side_effect=["0", "0"]),
            redirect_stdout(io.StringIO()) as f,
        ):
            run(":@$0{:@$0{#0,}{#1,}}{:@$0{#1,}{#0,}}&", io=IO())
        assert f.getvalue() == "0"


class TestStepMachine:
    def test_halt_command_sets_halted(self) -> None:
        from esolangs.interpreters.register_based.sophie import _Machine

        machine = _Machine("&", IO())
        assert not machine.halted
        machine.step()
        assert machine.halted

    def test_a_read_loop_is_not_a_cycle(self) -> None:
        """The snapshot holds the input cursor (a85db79a)."""
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.register_based.sophie import _Machine
        from esolangs.vm import run_until_halt_or_cycle

        io_ = ScriptedIO("AAB\x00")
        assert run_until_halt_or_cycle(_Machine("[;@$0{&}{,}]", io_), limit=100)
        assert io_.getvalue() == "AAB"


def _machine(code: object) -> object:
    from esolangs.interpreters.io import IO
    from esolangs.interpreters.register_based.sophie import _Machine

    return _Machine(code, IO())


class TestContract(SnapshotContract, CycleContract):
    """The shared shapes, with this language's own programs."""

    machine = staticmethod(_machine)
    stepping_program = "#$5"
    halting_program = "&"
    looping_program = "[]"


if __name__ == "__main__":
    pytest.main([__file__])
