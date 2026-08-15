"""Unit tests for the AlbaBet interpreter."""

import io
from contextlib import redirect_stdout

from esolangs.interpreters.io import IO, ScriptedIO
from esolangs.interpreters.other.albabet import run


def run_scripted(code: str) -> str:
    """Run ``code`` through a ``ScriptedIO`` and return the captured output."""
    io_obj = ScriptedIO()
    run(code, io_obj)
    return io_obj.getvalue()


def run_and_capture(code: str) -> str:
    """Run ``code`` through a bare ``IO()`` and return the stdout."""
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        run(code, IO())
    return buffer.getvalue()


class TestAlbabet:
    def test_empty_program_prints_nothing(self) -> None:
        assert run_scripted("") == ""

    def test_unknown_characters_are_ignored(self) -> None:
        assert run_scripted("xyz 123\n@\x00\t") == ""

    def test_unicode_noops_are_ignored(self) -> None:
        assert run_scripted("\U0001f600a\U0001f600i") == "\x01"

    def test_a_increments_the_accumulator(self) -> None:
        assert run_scripted("a" * 65 + "i") == "A"

    def test_b_decrements_the_accumulator(self) -> None:
        assert run_scripted("a" * 65 + "b" + "i") == "@"  # 64

    def test_b_clamps_at_zero(self) -> None:
        """Natural-number subtraction never goes below 0."""
        assert run_scripted("b" * 5 + "i") == "\x00"

    def test_c_zeroes_the_accumulator(self) -> None:
        assert run_scripted("a" * 65 + "c" + "i") == "\x00"

    def test_d_zeroes_the_accumulator(self) -> None:
        """``d`` sets x to 0; ``h`` on 0 stays 0 (a swap would print SOH)."""
        assert run_scripted("adhi") == "\x00"

    def test_d_moves_the_accumulator_into_y(self) -> None:
        """``e`` copies x to y, ``d`` parks x, ``a`` restarts it, ``g``
        multiplies by the saved value (a swap would leave y at 0)."""
        assert run_scripted("aaedagi") == "\x02"

    def test_e_copies_x_into_y(self) -> None:
        """Without the copy, ``g`` would multiply by 0."""
        assert run_scripted("aaebgi") == "\x02"

    def test_f_clears_y(self) -> None:
        """Without the clear, ``g`` would multiply by the saved 2."""
        assert run_scripted("aaefbgi") == "\x00"

    def test_g_multiplies_x_by_y(self) -> None:
        assert run_scripted("aaaebgi") == "\x06"  # 3 * 2

    def test_j_adds_x_into_y(self) -> None:
        """j adds the accumulator into the multiplier (per the wiki)."""
        assert run_scripted("aeajgi") == "\x06"  # y = 1 + 2, x = 2 * 3
        assert run_scripted("aaaaae aajgi") == "T"  # y = 5 + 2, x = 7 * 12

    def test_h_squares_x(self) -> None:
        assert run_scripted("aahi") == "\x04"

    def test_printing_after_arithmetic(self) -> None:
        assert run_scripted("a" * 10 + "i" + "b" * 10 + "i") == "\n\x00"

    def test_printing_many_characters(self) -> None:
        assert run_scripted("a" * 65 + "i" + "a" * 33 + "i") == "Ab"

    def test_above_ascii_prints_utf8(self) -> None:
        assert run_scripted("a" * 256 + "i") == "Ā"  # U+0100
        assert run_scripted("a" * 0x10000 + "i") == "\U00010000"

    def test_valid_scalar_just_below_surrogates(self) -> None:
        assert run_scripted("a" * 0xD7FF + "i") == chr(0xD7FF)

    def test_surrogate_range_prints_nul(self) -> None:
        """Lean's ``Char.ofNat`` yields NUL for invalid scalar values."""
        assert run_scripted("a" * 0xD800 + "i") == "\x00"
        assert run_scripted("a" * 0xDFFF + "i") == "\x00"

    def test_just_above_surrogates(self) -> None:
        assert run_scripted("a" * 0xE000 + "i") == chr(0xE000)

    def test_above_unicode_max_prints_nul(self) -> None:
        assert run_scripted("a" * 0x10FFFF + "i") == "\U0010ffff"
        assert run_scripted("a" * 0x110000 + "i") == "\x00"

    def test_large_squaring_prints_nul(self) -> None:
        """``aahhhhhi`` squares to 2^32, not a valid code point."""
        assert run_scripted("aahhhhhi") == "\x00"

    def test_plain_io_path(self) -> None:
        assert run_and_capture("a" * 65 + "i") == "A"
        assert run_and_capture("") == ""

    def test_arbitrary_programs_never_raise(self) -> None:
        """Every character is a defined operation or a no-op, so the
        interpreter never raises (total semantics)."""
        for code in ("", "a", "b", "abcdefghij", "x", "a" * 10 + "h" + "i"):
            run_scripted(code)
