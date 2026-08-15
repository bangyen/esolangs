"""Unit tests for the %^2^-1 interpreter."""

import importlib

from esolangs.interpreters.io import ScriptedIO

run = importlib.import_module(
    "esolangs.interpreters.register_based.pct_squared_minus_one"
).run


def run_program(code: str, stdin: str = "") -> str:
    io = ScriptedIO(stdin)
    run(code, io)
    return io.getvalue()


class TestPct:
    def test_reset_sets_zero(self) -> None:
        assert run_program("'e") == "\x00"
        assert run_program("'pe") == "\x00"
        assert run_program("'me") == "\x00"  # 0 * 2 is still 0

    def test_divide(self) -> None:
        # 'i -> -3, p -> 3, s -> 1: the fixed three-op path for byte 1
        assert run_program("'ipse") == "\x01"
        assert run_program("'ipe") == "\x03"
        assert run_program("'mse") == "\xfe"  # 0, *2, -2 -> -2 as a byte

    def test_square_and_negate(self) -> None:
        assert run_program("'ie") == "\xfd"  # -3 as a byte

    def test_print_decimal(self) -> None:
        assert run_program("'l") == "0"
        assert run_program("'sl") == "-2"
        assert run_program("'me'l") == "\x000"

    def test_read(self) -> None:
        assert run_program("ne", "X\n") == "X"
        assert run_program("ne", "0\n") == "0"
        assert run_program("nl", "A\n") == "65"

    def test_read_reset(self) -> None:
        # n reads 'a', ' resets, n reads 'c', e prints it
        assert run_program("n'ne", "ab\ncd\n") == "c"

    def test_rewind_noop_when_zero(self) -> None:
        assert run_program("'te") == "\x00"

    def test_rewind_loop_terminates_on_zero(self) -> None:
        # t rewinds while the magnitude is nonzero; reading a 0 byte stops it
        assert run_program("nt", "A\n\x00\n") == ""
        assert run_program("nt", "\x00\n") == ""

    def test_reset_above_3003(self) -> None:
        # 12 doublings reach 4096 > 3003, which resets to 0 before the l
        assert run_program("'m" * 12 + "l") == "0"

    def test_empty_program(self) -> None:
        assert run_program("") == ""
