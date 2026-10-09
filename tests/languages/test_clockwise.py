"""Clockwise through the shared API, CLI and machinery."""

import pytest

import esolangs
from tests.stdin_check import _check_stdin


class TestPrivateStdinCheckSaysWhatItCanActuallyCheck:
    """Its help listed "the wrong number of lines" among what it catches
    without a table.  For most languages it cannot.
    """

    def test_a_line_per_bit_language_accepts_any_count(self) -> None:
        """Not a bug -- a count needs an arity, and only a table has one."""
        for stdin in ("", "1", "101"):
            _check_stdin("brainfuck", stdin)

    def test_the_table_is_what_catches_the_count(self) -> None:
        """The other half of the claim: with one, the count is checked."""
        with pytest.raises(esolangs.ArgumentError):
            _check_stdin("brainfuck", "1\n0\n1\n", "0110")

    def test_a_one_line_language_does_catch_a_stray_line(self) -> None:
        """Which is why the help can still claim a shape check at all."""
        with pytest.raises(esolangs.ArgumentError, match="unexpected character"):
            _check_stdin("Clockwise", "1\n0\n")


def test_clockwise_is_not_marked_because_it_never_reads_past_an_end() -> None:
    """Its underfed input is a shorter one-line string: no EOF happens."""
    assert esolangs.describe("Clockwise")["eof_is_a_value"] is False
    program = esolangs.generate("Clockwise", "10010110")
    short = esolangs.encode_inputs("Clockwise", [1, 0])
    output = esolangs.run("Clockwise", program, stdin=short, timeout=10)
    esolangs.read_answer("Clockwise", output)


def test_the_input_is_a_bit_string() -> None:
    assert esolangs.encode_inputs("Clockwise", [1, 1, 1, 1]) == "1111"


def test_a_one_line_language_has_its_bits_counted() -> None:
    """Clockwise's underfeed is a shorter string, not a missing line."""
    _check_stdin("Clockwise", "101", "00010111")
    with pytest.raises(esolangs.ArgumentError, match="reads 3 characters"):
        _check_stdin("Clockwise", "10", "00010111")


def test_inputs_are_seven_bits_per_character():
    assert esolangs.describe("Clockwise")["input_shape"] == "char_stream_cyclic"
    assert esolangs.encode_inputs("Clockwise", [1, 0, 1]) == "101"
