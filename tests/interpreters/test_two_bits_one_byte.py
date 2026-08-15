"""Unit tests for the 2 Bits, 1 Byte interpreter."""

import os
import signal

import pytest

from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.other.two_bits_one_byte import run


def run_program(code: str, stdin: str = "") -> str:
    io = ScriptedIO(stdin)
    run(code, io)
    return io.getvalue()


class TestTwoBitsOneByte:
    def test_empty_program(self) -> None:
        """The empty program halts with no output."""
        assert run_program("") == ""

    def test_end_immediately(self) -> None:
        """0xff is four 11 fields, so the first field ENDs at once."""
        assert run_program("\xff") == "\xff"

    def test_don_then_end(self) -> None:
        """0x3f: field 0 is 00 (DON), field 1 is 11 (END)."""
        assert run_program("?") == "?"
        # 0x30: same shape, prints the byte as '0'
        assert run_program("0") == "0"

    def test_two_dons_then_end(self) -> None:
        """0x0c: fields 00 00 then 11; 0xfc: fields 11 11 11 00."""
        assert run_program("\x0c") == "\x0c"
        assert run_program("\xfc") == "\xfc"

    def test_extra_bytes_ignored(self) -> None:
        """Only the first byte of code is the program byte."""
        assert run_program("\x5cABC") == run_program("\x5c") == "l"

    def test_act_toggles_bit_pair(self) -> None:
        """ACT 01, X=1, Y=1: XOR bits 4-5 in, resume at field 2 = END."""
        # 0x5c = 01 01 11 00 -> 0x5c ^ 0x30 = 0x6c = 'l'
        assert run_program("\x5c") == "l"

    def test_act_toggles_second_pair(self) -> None:
        """ACT 01, X=2, Y=1: XOR bits 2-3 in, resume at field 3 = END."""
        # 0x67 = 01 10 01 11 -> 0x67 ^ 0x0c = 0x6b = 'k'
        assert run_program("\x67") == "k"

    def test_act_toggles_high_bit_only(self) -> None:
        """ACT with Y=2 XORs in just the selected pair's high bit."""
        # 0x6b = 01 10 10 11, X=2, Y=2 -> 0x6b ^ 0x08 = 0x63 = 'c'
        assert run_program("\x6b") == "c"
        # 0x7c = 01 11 11 00, X=3, Y=0 -> whole pair: 0x7c ^ 0x03 = 0x7f
        assert run_program("\x7c") == "\x7f"

    def test_act_x0_toggles_top_field(self) -> None:
        """ACT with X=0 targets the top field (bits 7-6), not a no-op."""
        # 0x41 = 01 00 00 01: the first ACT is X=0 and toggles bits 7-6,
        # yielding 0x8D before the later ACT at field 3.
        assert run_program("A") == "\x8d"

    def test_jump(self) -> None:
        """JMP X jumps the instruction pointer to field X."""
        # 0xac = 10 10 11 00: JMP 2 lands on the 11 field.
        assert run_program("\xac") == "\xac"
        # 0xb3 = 10 11 00 11: JMP 3 lands on the trailing 11 field.
        assert run_program("\xb3") == "\xb3"
        # 0x2f = 00 10 11 11: JMP 3 reads the last 11 field directly.
        assert run_program("/") == "/"

    def test_loop_never_halts(self) -> None:
        """Programs that never reach END loop forever, like the reference."""
        if os.name != "posix":
            pytest.skip("signal.alarm is POSIX-only")

        class _TimeoutError(Exception):
            pass

        def _alarm(_signum: int, _frame: object) -> None:
            raise _TimeoutError

        old_handler = signal.signal(signal.SIGALRM, _alarm)
        signal.alarm(1)
        try:
            run_program("\x00")  # all DON fields
        except _TimeoutError:
            pass
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old_handler)
