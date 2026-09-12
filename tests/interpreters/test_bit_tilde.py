r"""Unit tests for the bit~ interpreter."""

import io
from contextlib import redirect_stdout

import pytest

from esolangs.interpreters.io import IO, ScriptedIO
from esolangs.interpreters.tape_based.bit_tilde import run
from tests.interpreters.contract import (
    CycleContract,
    SnapshotContract,
    StateViewContract,
)
from tests.raises import raises_message


def run_and_capture(code: str) -> str:
    r"""Run ``code`` and return its output through a bare ``IO()``."""
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        run(code, IO())
    return buffer.getvalue()


def run_scripted(code: str, stdin: str = "") -> str:
    r"""Run ``code`` with ``stdin`` as input, returning the captured output."""
    io_obj = ScriptedIO(stdin)
    run(code, io_obj)
    return io_obj.getvalue()


class TestBitTilde:
    def test_single_toggle_prints_most_significant_bit(self) -> None:
        r"""Cell 0 is the MSB, so one toggle prints 0x80."""
        assert run_and_capture("~(") == "\x80"

    def test_least_significant_bit(self) -> None:
        r"""Moving to the 8th cell and back sets the LSB."""
        assert run_and_capture(">>>>>>>~<<<<<<<(") == "\x01"

    def test_two_bits(self) -> None:
        assert run_and_capture("~>>>>>>>~<<<<<<<(") == "\x81"

    def test_all_bits(self) -> None:
        assert run_and_capture("~>~>~>~>~>~>~>~<<<<<<<(") == "\xff"

    def test_left_pointer_clamps_at_cell_zero(self) -> None:
        r"""``<`` at cell 0 is a no-op, so the toggle hits the MSB."""
        assert run_and_capture("<<~(") == "\x80"

    def test_right_grows_the_pool(self) -> None:
        r"""After seven ``>`` the pool holds 14 cells; a toggle at the 8th cell."""
        assert run_and_capture(">>>>>>>~(") == "@"

    def test_unknown_characters_are_ignored(self) -> None:
        assert run_and_capture("~x(") == "\x80"

    def test_empty_window_prints_nul(self) -> None:
        assert run_and_capture(">(") == "\x00"
        assert run_and_capture(">>>(") == "\x00"

    def test_input_reads_first_character_of_a_line(self) -> None:
        assert run_scripted(")(", "hello") == "h"

    def test_input_writes_at_the_pointer(self) -> None:
        r"""``)`` writes the 8 bits starting at the pointer, so reading at cell."""
        assert run_scripted(">)(<", "A") == "A"

    def test_two_inputs_and_outputs(self) -> None:
        assert run_scripted(")()(", "hi\n!") == "h!"

    def test_input_grows_the_pool_to_fit_its_window(self) -> None:
        r"""``)`` past the first cell extends the pool to hold all eight bits."""
        assert run_scripted(">>)(", "A") == "A"
        assert run_scripted(">>>>)(", "A") == "A"

    def test_input_extends_the_pool_by_exactly_the_shortfall(self) -> None:
        r"""The pool grows to the end of the window and no further."""
        from esolangs.interpreters.tape_based.bit_tilde import _Machine

        machine = _Machine(">>)(", ScriptedIO("A"))
        while not machine.halted:
            machine.step()
        assert len(machine.tape) == 10  # two moves right, eight bits.

    def test_input_replaces_exactly_eight_cells(self) -> None:
        r"""``)`` overwrites the eight bits of its window and no more."""
        from esolangs.interpreters.tape_based.bit_tilde import _Machine

        machine = _Machine(">><<)", ScriptedIO("A"))
        while not machine.halted:
            machine.step()
        assert machine.tape == (0, 1, 0, 0, 0, 0, 0, 1, 0)

    def test_loop_skips_when_the_bit_is_zero(self) -> None:
        r"""``{`` jumps past its body when the current bit is zero."""
        assert run_and_capture("{(~}(") == "\x00"

    def test_loop_runs_while_the_bit_is_nonzero(self) -> None:
        r"""A body that builds and prints 'A' leaves bit 0 at zero so ``}``."""
        assert run_and_capture("~{~>~>>>>>>~<<<<<<<(}") == "A"

    def test_loop_repeats_until_the_bit_clears(self) -> None:
        r"""A counter in cell 1 lets the outer loop's body run twice: the first."""
        assert run_and_capture("~><{(>{<~>~}~<}") == "\x80\xc0"

    def test_nested_loops_match_by_depth(self) -> None:
        # the outer `{` at bit 0 skips.
        # outer `}`, printing the.
        assert run_and_capture("{{~~}~}(~") == "\x00"

    def test_output_bytes_round_trip_under_latin1(self) -> None:
        r"""The interpreter emits ``chr(byte)``, so each byte round-trips under."""
        assert run_scripted(")(", "\x80").encode("latin1") == b"\x80"
        assert run_scripted(")(", "\xe9").encode("latin1") == b"\xe9"

    def test_bit_flips_then_output_print_two_characters(self) -> None:
        r"""Set the bits of 'H', print, flip to 'i', print."""
        program = ">~>>>~>>><<<<<<<(>>~>>>>>~<<<<<<<("
        assert run_scripted(program) == "Hi"

    def test_exhausted_input_raises_eof(self) -> None:
        with pytest.raises(EOFError):
            run_scripted(")(")

    def test_unmatched_bracket_message_is_exact(self) -> None:
        r"""The message itself is pinned, not just a substring of it."""
        for code, message in (
            ("{~", "unmatched '{' at position 0"),
            ("~}", "unmatched '}' at position 1"),
        ):
            with raises_message(ValueError, message):
                run_and_capture(code)


class TestStepMachine:
    def test_step_tracks_pool_and_cursor(self) -> None:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.bit_tilde import _Machine

        machine = _Machine("~(", ScriptedIO())
        assert (machine.ind, list(machine.tape)) == (0, [0] * 8)
        machine.step()  # ~ flips the MSB.
        assert machine.tape[0] == 1
        machine.step()  # ( prints the byte.
        assert machine.io.getvalue() == "\x80"
        assert machine.halted
        machine.step()  # stepping a halted machine is.
        assert machine.ind == 2


def _machine(code: object) -> object:
    from esolangs.interpreters.io import ScriptedIO
    from esolangs.interpreters.tape_based.bit_tilde import _Machine

    return _Machine(code, ScriptedIO())


class TestContract(SnapshotContract, CycleContract, StateViewContract):
    r"""The shared shapes, with this language's own programs."""

    machine = staticmethod(_machine)
    stepping_program = "~("
    halting_program = "~("
    looping_program = "~{}"
    state_views = ("ind", "cell", "ip", "memory")
    # Walks out far enough to flip.
    # moves rather than only the.
    viewing_program = ">>>>>>>~<<<<<<<("


class TestStateViewValues:
    r"""The named views read the slots they claim, not one another."""

    def test_cell_is_the_data_pointer_not_the_code_cursor(self) -> None:
        r"""Nine steps in, the pointer has turned back and the cursor has not."""
        machine = _machine(">>>>>>>~<<<<<<<(")
        for _ in range(9):
            machine.step()
        assert machine.cell == 6  # walked out to 7 and back one.
        assert machine.ind == 9  # still counting forward.
