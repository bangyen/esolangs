"""Unit tests for the bit~ interpreter."""

import io
from contextlib import redirect_stdout

import pytest

from esolangs.interpreters.io import IO, ScriptedIO
from esolangs.interpreters.tape_based.bit_tilde import run
from esolangs.tools import text as gen


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
