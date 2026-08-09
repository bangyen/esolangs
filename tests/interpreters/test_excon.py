"""Unit tests for the EXCON interpreter."""

import io
from contextlib import redirect_stdout

from esolangs.interpreters.io import IO
from esolangs.interpreters.tape_based.excon import run


def run_and_capture(code: str) -> str:
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        run(code, IO())
    return buffer.getvalue()


class TestEXCON:
    def test_single_bit(self) -> None:
        """Five toggles of the least significant bit leave it set."""
        assert run_and_capture("^^^^^!") == "\x01"

    def test_character_65(self) -> None:
        """Bits for value 64 and 1 combine to output 'A'."""
        assert run_and_capture("^<<<<<<^!") == "A"

    def test_most_significant_bit(self) -> None:
        assert run_and_capture("<<<<<<<^!") == "\x80"

    def test_reset(self) -> None:
        """: resets the pool, discarding previously set bits."""
        assert run_and_capture("^<^!") == "\x03"
        assert run_and_capture("^<:^!") == "\x01"

    def test_all_bits(self) -> None:
        assert run_and_capture("^<^<^<^<^<^<^<^!") == "\xff"
