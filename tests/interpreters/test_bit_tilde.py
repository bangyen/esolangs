"""Unit tests for the bit~ interpreter."""

import io
from contextlib import redirect_stdout
from functools import partial

import pytest

from esolangs.interpreters.io import IO, ScriptedIO
from esolangs.interpreters.tape_based.bit_tilde import run
from tests.interpreters.contract import (
    CycleContract,
    SnapshotContract,
    StateViewContract,
)
from tests.interpreters.runner import run_program
from tests.raises import raises_message


def run_and_capture(code: str) -> str:
    """Run ``code`` and return its output through a bare ``IO()``."""
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        run(code, IO())
    return buffer.getvalue()


run_scripted = partial(run_program, run, suppress_eof=False)


_BIT_TILDE_RESULTS = {
    # Cell 0 is the MSB, so one toggle prints 0x80.
    "single_toggle_prints_most_significant_bit": ("~(", "\x80"),
    # ``<`` at cell 0 is a no-op, so the toggle hits the MSB.
    "left_pointer_clamps_at_cell_zero": ("<<~(", "\x80"),
    # After seven ``>`` the pool holds 14 cells; a toggle at the 8th cell and a print
    # at the same spot use only the available window.
    "right_grows_the_pool": (">>>>>>>~(", "@"),
    # A body that builds and prints 'A' leaves bit 0 at zero so ``}`` falls through;
    # the loop runs exactly once.
    "loop_runs_while_the_bit_is_nonzero": ("~{~>~>>>>>>~<<<<<<<(}", "A"),
    # A counter in cell 1 lets the outer loop's body run twice: the first pass skips
    # the sentinel flip (bit 1 was 0) and loops, the second clears bit 0 and falls
    # through. Both passes print, and the second print sees the counter bit set, so it
    # is 192.
    "loop_repeats_until_the_bit_clears": ("~><{(>{<~>~}~<}", "\x80\xc0"),
    # the outer `{` at bit 0 skips the nested brackets to the matching
    # outer `}`, printing the untouched (all-zero) pool
    "nested_loops_match_by_depth": ("{{~~}~}(~", "\x00"),
}


class TestBitTilde:
    @pytest.mark.parametrize(
        ("code", "expected"), _BIT_TILDE_RESULTS.values(), ids=list(_BIT_TILDE_RESULTS)
    )
    def test_result(self, code, expected) -> None:
        assert run_and_capture(code) == expected

    def test_input_reads_first_character_of_a_line(self) -> None:
        assert run_scripted(")(", "hello") == "h"

    def test_input_writes_at_the_pointer(self) -> None:
        """``)`` writes the 8 bits starting at the pointer, so reading at
        cell 1 and printing there echoes the character.
        """
        assert run_scripted(">)(<", "A") == "A"

    def test_input_grows_the_pool_to_fit_its_window(self) -> None:
        """``)`` past the first cell extends the pool to hold all eight bits."""
        assert run_scripted(">>)(", "A") == "A"
        assert run_scripted(">>>>)(", "A") == "A"

    def test_input_extends_the_pool_by_exactly_the_shortfall(self) -> None:
        """The pool grows to the end of the window and no further."""
        from esolangs.interpreters.tape_based.bit_tilde import _Machine

        machine = _Machine(">>)(", ScriptedIO("A"))
        while not machine.halted:
            machine.step()
        assert len(machine.tape) == 10  # two moves right, eight bits of window

    def test_input_flips_rather_than_overwrites(self) -> None:
        """The spec says ``)`` flips its window by the code: ``A ^ B`` is 3."""
        assert run_scripted("))(", "AB") == "\x03"

    def test_input_replaces_exactly_eight_cells(self) -> None:
        """``)`` on a clear window writes its eight bits and no more."""
        from esolangs.interpreters.tape_based.bit_tilde import _Machine

        machine = _Machine(">><<)", ScriptedIO("A"))
        while not machine.halted:
            machine.step()
        assert machine.tape == (0, 1, 0, 0, 0, 0, 0, 1, 0)

    def test_output_bytes_round_trip_under_latin1(self) -> None:
        """The interpreter emits ``chr(byte)``, so each byte round-trips
        under latin1 (the cross-checks write raw bytes 0x00-0xFF).
        """
        assert run_scripted(")(", "\x80").encode("latin1") == b"\x80"
        assert run_scripted(")(", "\xe9").encode("latin1") == b"\xe9"

    def test_exhausted_input_raises_eof(self) -> None:
        with pytest.raises(EOFError):
            run_scripted(")(")

    def test_unmatched_bracket_message_is_exact(self) -> None:
        """The message itself is pinned, not just a substring of it."""
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
        machine.step()  # ~ flips the MSB
        assert machine.tape[0] == 1
        machine.step()  # ( prints the byte
        assert machine.io.getvalue() == "\x80"
        assert machine.halted
        machine.step()  # stepping a halted machine is a no-op
        assert machine.ind == 2


def _machine(code: object) -> object:
    from esolangs.interpreters.io import ScriptedIO
    from esolangs.interpreters.tape_based.bit_tilde import _Machine

    return _Machine(code, ScriptedIO())


class TestContract(SnapshotContract, CycleContract, StateViewContract):
    """The shared shapes, with this language's own programs."""

    machine = staticmethod(_machine)
    stepping_program = "~("
    halting_program = "~("
    looping_program = "~{}"
    state_views = ("ind", "cell", "memory")
    # Walks out far enough to flip a cell and come back, so `cell`
    # moves rather than only the cursor.
    viewing_program = ">>>>>>>~<<<<<<<("


class TestStateViewValues:
    """The named views read the slots they claim, not one another."""

    def test_cell_is_the_data_pointer_not_the_code_cursor(self) -> None:
        """Nine steps in, the pointer has turned back and the cursor has not."""
        machine = _machine(">>>>>>>~<<<<<<<(")
        for _ in range(9):
            machine.step()
        assert machine.cell == 6  # walked out to 7 and back one
        assert machine.ind == 9  # still counting forward
