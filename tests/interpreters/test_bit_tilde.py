"""Unit tests for the bit~ interpreter."""

import io
from contextlib import redirect_stdout

import pytest

from esolangs.interpreters.io import IO, ScriptedIO
from esolangs.interpreters.tape_based.bit_tilde import run
from esolangs.tools import text as gen
from tests.interpreters.contract import (
    CycleContract,
    SnapshotContract,
    StateViewContract,
)
from tests.raises import raises_message


def run_and_capture(code: str) -> str:
    """Run ``code`` and return its output through a bare ``IO()``."""
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        run(code, IO())
    return buffer.getvalue()


def run_scripted(code: str, stdin: str = "") -> str:
    """Run ``code`` with ``stdin`` as input, returning the captured output."""
    io_obj = ScriptedIO(stdin)
    run(code, io_obj)
    return io_obj.getvalue()


class TestBitTilde:
    def test_single_toggle_prints_most_significant_bit(self) -> None:
        """Cell 0 is the MSB, so one toggle prints 0x80."""
        assert run_and_capture("~(") == "\x80"

    def test_least_significant_bit(self) -> None:
        """Moving to the 8th cell and back sets the LSB."""
        assert run_and_capture(">>>>>>>~<<<<<<<(") == "\x01"

    def test_two_bits(self) -> None:
        assert run_and_capture("~>>>>>>>~<<<<<<<(") == "\x81"

    def test_all_bits(self) -> None:
        assert run_and_capture("~>~>~>~>~>~>~>~<<<<<<<(") == "\xff"

    def test_left_pointer_clamps_at_cell_zero(self) -> None:
        """``<`` at cell 0 is a no-op, so the toggle hits the MSB."""
        assert run_and_capture("<<~(") == "\x80"

    def test_right_grows_the_pool(self) -> None:
        """After seven ``>`` the pool holds 14 cells; a toggle at the 8th
        cell and a print at the same spot use only the available window."""
        assert run_and_capture(">>>>>>>~(") == "@"

    def test_unknown_characters_are_ignored(self) -> None:
        assert run_and_capture("~x(") == "\x80"

    def test_empty_window_prints_nul(self) -> None:
        assert run_and_capture(">(") == "\x00"
        assert run_and_capture(">>>(") == "\x00"

    def test_input_reads_first_character_of_a_line(self) -> None:
        assert run_scripted(")(", "hello") == "h"

    def test_input_writes_at_the_pointer(self) -> None:
        """``)`` writes the 8 bits starting at the pointer, so reading at
        cell 1 and printing there echoes the character."""
        assert run_scripted(">)(<", "A") == "A"

    def test_two_inputs_and_outputs(self) -> None:
        assert run_scripted(")()(", "hi\n!") == "h!"

    def test_input_grows_the_pool_to_fit_its_window(self) -> None:
        """``)`` past the first cell extends the pool to hold all eight bits.

        Input was only ever read at cells 0 and 1, where the window already
        fits inside the eight cells the pool starts with -- so the growth
        the read has to do, and how far, went unexercised.  Reading further
        right still round-trips the byte, which it cannot do unless the
        window was made to fit.
        """
        assert run_scripted(">>)(", "A") == "A"
        assert run_scripted(">>>>)(", "A") == "A"

    def test_input_extends_the_pool_by_exactly_the_shortfall(self) -> None:
        """The pool grows to the end of the window and no further.

        The byte prints the same however much slack is added past it, so
        the amount is only visible in the pool itself.
        """
        from esolangs.interpreters.tape_based.bit_tilde import _Machine

        machine = _Machine(">>)(", ScriptedIO("A"))
        while not machine.halted:
            machine.step()
        assert len(machine.tape) == 10  # two moves right, eight bits of window

    def test_input_replaces_exactly_eight_cells(self) -> None:
        """``)`` overwrites the eight bits of its window and no more.

        Coming back left leaves the pool longer than the window, so a
        wider write would swallow the spare cell instead of leaving it --
        which the printed byte, being the first eight bits, cannot show.
        """
        from esolangs.interpreters.tape_based.bit_tilde import _Machine

        machine = _Machine(">><<)", ScriptedIO("A"))
        while not machine.halted:
            machine.step()
        assert machine.tape == (0, 1, 0, 0, 0, 0, 0, 1, 0)

    def test_loop_skips_when_the_bit_is_zero(self) -> None:
        """``{`` jumps past its body when the current bit is zero."""
        assert run_and_capture("{(~}(") == "\x00"

    def test_loop_runs_while_the_bit_is_nonzero(self) -> None:
        """A body that builds and prints 'A' leaves bit 0 at zero so ``}``
        falls through; the loop runs exactly once."""
        assert run_and_capture("~{~>~>>>>>>~<<<<<<<(}") == "A"

    def test_loop_repeats_until_the_bit_clears(self) -> None:
        """A counter in cell 1 lets the outer loop's body run twice: the
        first pass skips the sentinel flip (bit 1 was 0) and loops, the
        second clears bit 0 and falls through.  Both passes print, and the
        second print sees the counter bit set, so it is 192."""
        assert run_and_capture("~><{(>{<~>~}~<}") == "\x80\xc0"

    def test_nested_loops_match_by_depth(self) -> None:
        # the outer `{` at bit 0 skips the nested brackets to the matching
        # outer `}`, printing the untouched (all-zero) pool
        assert run_and_capture("{{~~}~}(~") == "\x00"

    def test_output_bytes_round_trip_under_latin1(self) -> None:
        """The interpreter emits ``chr(byte)``, so each byte round-trips
        under latin1 (the cross-checks write raw bytes 0x00-0xFF)."""
        assert run_scripted(")(", "\x80").encode("latin1") == b"\x80"
        assert run_scripted(")(", "\xe9").encode("latin1") == b"\xe9"

    def test_generated_hi_round_trips(self) -> None:
        assert run_scripted(gen.bit_tilde("Hi")) == "Hi"

    def test_generated_hello_world_round_trips(self) -> None:
        text = "Hello, World!"
        assert run_scripted(gen.bit_tilde(text)) == text

    def test_generated_all_bytes_round_trip(self) -> None:
        for n in range(256):
            text = chr(n)
            assert run_scripted(gen.bit_tilde(text)) == text

    def test_exhausted_input_raises_eof(self) -> None:
        with pytest.raises(EOFError):
            run_scripted(")(")

    def test_unmatched_open_bracket_is_malformed(self) -> None:
        """A ``{`` that would jump to a missing ``}`` is malformed."""
        with pytest.raises(ValueError, match="unmatched"):
            run_and_capture("{~")

    def test_unmatched_close_bracket_is_malformed(self) -> None:
        """A ``}`` that would jump to a missing ``{`` is malformed."""
        with pytest.raises(ValueError, match="unmatched"):
            run_and_capture("~}")

    def test_unmatched_bracket_message_is_exact(self) -> None:
        """The message itself is pinned, not just a substring of it.

        Both cases above use ``match=``, which is a substring search, so
        the text could be rewritten around the word "unmatched" and still
        pass.  One scan raises for both directions, so asserting it once
        from each side covers the message wherever it comes from.
        """
        for code in ("{~", "~}"):
            with raises_message(ValueError, "unmatched bit~ bracket"):
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
    state_views = ("ind", "cell", "ip", "memory")
    viewing_program = "~("
