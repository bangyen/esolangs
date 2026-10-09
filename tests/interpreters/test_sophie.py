"""Unit tests for Sophie interpreter."""

import io
from contextlib import redirect_stdout
from unittest.mock import patch

import pytest

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import IO
from esolangs.interpreters.register_based.sophie import run
from tests.interpreters.contract import (
    CycleContract,
    EmptyProgramContract,
    SnapshotContract,
)
from tests.interpreters.runner import run_printing
from tests.raises import assert_rejected_with_hint


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        pytest.param("#$42.&", "42", id="output_number"),
        pytest.param("#A,&", "A", id="output_char"),
        # Program halts before reaching output
        pytest.param("&.", "", id="halt_command"),
        pytest.param("#A@A{,#C,}&", "AC", id="char_conditional_true"),
        pytest.param("#$65@$65{,#C,}&", "AC", id="number_conditional_true"),
        pytest.param("#A@A{,&}", "A", id="conditional_without_else"),
        pytest.param("#A@A{@$65{,#B,}}{#C,}&", "AB", id="nested_conditionals"),
        pytest.param("#$3[.*]&", "3", id="simple_loop"),
        # `*` breaks only its own loop (wiki "break loop"; the author's
        # sophie.py pops one loop), so the outer loop needs its own break.
        pytest.param("#A[#B[.*]*]&", "66", id="nested_loops"),
        # Closing a loop pops one frame, not all but the outermost.
        pytest.param("#A[#B[#C[.*]*]*]&", "67", id="loops_nested_three_deep"),
        pytest.param("{This is a comment}#A,&", "A", id="comment_block"),
        pytest.param("{Outer{Inner}comment}#A,&", "A", id="nested_comments"),
        # ``#[`` loads the ``[`` as data, so no loop is left unmatched.
        pytest.param("#[", "", id="a_bracket_loaded_by_a_marker_is_not_a_bracket"),
        # Validation already skipped ``#]``; the jump table did not.
        pytest.param("[#]*]#A,&", "A", id="a_loaded_bracket_is_data_to_the_jumps_too"),
        # A break used to set a flag that skipped the next loop entered.
        pytest.param(
            "[#A,[,*][#B,*]*]#C,&", "AABC", id="a_break_leaves_later_loops_running"
        ),
        # Brackets loaded as ``#`` data are not treated as structure.
        pytest.param("#{,", "{", id="braces_loaded_as_data"),
        # ``#`` and ``#$`` may be the last thing in the program.
        pytest.param("#", "", id="ends_on_load_marker"),
        pytest.param("#$", "", id="ends_on_number_marker"),
        # ``#c`` with c ``$``: the ``[`` after ``#$`` is structure, not data.
        pytest.param("#$#[,", "[", id="dollar_without_number_is_the_character"),
        # A 5000-digit load prints back whole (CPython's str cap is 4300).
        pytest.param(f"#${'9' * 5000}.&", "9" * 5000, id="past_the_digit_cap"),
        # ``#$.`` loads ``$`` and prints it: the page has only ``#c`` and
        # ``#$n``, and the clean-room reference agrees (``$`` was a marker).
        pytest.param("#$.#$A,", "36$", id="dollar_char_loaded_as_data"),
        pytest.param("xyz#A,&", "A", id="invalid_commands_ignored"),
    ],
)
def test_output(code: str, expected: str) -> None:
    assert run_printing(run, code) == expected


# ``#$[`` and ``#$1[``: a ``$`` load stops at the first non-digit, leaving
# the bracket as structure.
@pytest.mark.parametrize("code", ["#$[", "#$1[", "#$123[", "#A{&", "#A}", "#A[.*"])
def test_unmatched_brackets(code: str) -> None:
    with pytest.raises(ValueError, match="unmatched"):
        run(code, io=IO())


def test_break_outside_loop_halts() -> None:
    with pytest.raises(HaltError):
        run("*&", io=IO())


@pytest.mark.parametrize(
    ("code", "line", "expected"),
    [
        (":.&", "123", "123"),
        (";,&", "X", "X"),
        # A non-number leaves the accumulator alone.
        ("#$42:.&", "not_a_number", "42"),
        # A newline replaces the accumulator with character code 10.
        ("#$42;.&", "", "10"),
        (":;,&", "65 B", " "),
    ],
)
def test_console_input(code: str, line: str, expected: str) -> None:
    with (
        patch("builtins.input", return_value=line),
        redirect_stdout(io.StringIO()) as f,
    ):
        run(code, io=IO())
    assert f.getvalue() == expected


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


class TestContract(EmptyProgramContract, SnapshotContract, CycleContract):
    """The shared shapes, with this language's own programs."""

    run = staticmethod(lambda code: run_printing(run, code))
    machine = staticmethod(_machine)
    stepping_program = "#$5"
    halting_program = "&"
    looping_program = "[]"


if __name__ == "__main__":
    pytest.main([__file__])


@pytest.mark.medium
def test_malformed_source_carries_a_repair_hint() -> None:
    assert_rejected_with_hint("Sophie", "#$[", "matching partner")
