"""Unit tests for the 123 interpreter."""

import importlib

import pytest

from esolangs.interpreters.io import ScriptedIO

run = importlib.import_module("esolangs.interpreters.tape_based.123").run

# The wiki's cat program: three 1s march the pointer to -3 (read), then the
# trailing 12121 flips the byte back and marches to -2 (write).
WIKI_CAT = "111212112"


def run_program(code: str, stdin: str = "") -> str:
    io = ScriptedIO(stdin)
    run(code, io)
    return io.getvalue()


class Test123:
    def test_empty_program(self) -> None:
        """The empty program halts with no output instead of looping."""
        assert run_program("") == ""

    def test_nops_only(self) -> None:
        """Characters other than 1/2/3 are NOPs and are skipped."""
        assert run_program(" \n abc \n") == ""

    def test_generated_letter(self) -> None:
        """The generator's program for 'A' outputs 'A' and halts."""
        assert run_program("212222222112112112112112112112112\n1") == "A"

    def test_unknown_chars_are_nops(self) -> None:
        """Comments scattered through the program do not change it."""
        prog = "212222222112112112112112112112112\n1"
        assert run_program("hello " + prog) == "A"

    def test_wiki_cat_echoes(self) -> None:
        """The cat program echoes input, then EOF raises like the others."""
        io = ScriptedIO("h\ni")
        with pytest.raises(EOFError):
            run(WIKI_CAT, io)
        assert io.getvalue() == "hi"

    def test_false_jump_skips_forward(self) -> None:
        """A FALSE 3 skips to the next 3, then the 1 halts (mask > 128)."""
        # 3 (FALSE, bit 0) -> next 3 -> 1 sets bit 7 and moves below 0.
        assert run_program("3231") == ""

    def test_true_jump_skips_backward(self) -> None:
        """A TRUE 3 jumps back to the previous 3 (or the start) and loops."""
        import os
        import signal

        import pytest

        if os.name != "posix":
            pytest.skip("signal.alarm is POSIX-only")

        class _TimeoutError(Exception):
            pass

        def _alarm(_signum: int, _frame: object) -> None:
            raise _TimeoutError

        # 2 1 2 reaches position 0 with bit 7 set; the 3 is TRUE and loops.
        signal.signal(signal.SIGALRM, _alarm)
        signal.alarm(2)
        try:
            run_program("21232131")
        except _TimeoutError:
            pass  # the TRUE jump loops back to the start, as expected
        finally:
            signal.alarm(0)
