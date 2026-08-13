"""Unit tests for the Painfuck interpreter."""

import importlib

import pytest

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import ScriptedIO

run = importlib.import_module("esolangs.interpreters.tape_based.painfuck").run

# The source text is translated through a position-dependent shift per cycle
# before execution.  _encode builds a source program whose translation is
# exactly ``targets`` (the inverse of the module's _translate), so the tests
# can express commands directly.
_CYCLES = ("pevkjzwr", "yuctsobqihald")


def _encode(targets: str) -> str:
    out: list[str] = []
    k = 0
    for tc in targets:
        for cycle in _CYCLES:
            if tc in cycle:
                out.append(cycle[(cycle.index(tc) - k) % len(cycle)])
                k += 1
                break
    return "".join(out)


def run_program(targets: str, stdin: str = "") -> str:
    io = ScriptedIO(stdin)
    run(_encode(targets), io)
    return io.getvalue()


class TestPainfuck:
    def test_increment_and_print(self) -> None:
        assert run_program("pue") == "\x02"
        assert run_program("ppue") == "\x04"

    def test_decrement(self) -> None:
        assert run_program("sue") == "\xff"  # -1 as a byte

    def test_zero(self) -> None:
        assert run_program("pzue") == "\x00"

    def test_square(self) -> None:
        assert run_program("pkue") == "\x04"  # 2*2
        assert run_program("ppkue") == "\x10"  # 4*4

    def test_half(self) -> None:
        assert run_program("pphue") == "\x02"  # 4 // 2 = 2

    def test_copy_neighbor(self) -> None:
        assert run_program("ppwue") == "\x00"  # copy 0 from the right neighbor
        assert run_program("ppwque") == "\x00"  # copy back

    def test_pointer_reset(self) -> None:
        # p at cell 0, r moves right, pp, then d resets and p adds again
        assert run_program("prppdpue") == "\x04"

    def test_read_byte(self) -> None:
        assert run_program("jue", "A\n") == "A"

    def test_read_number(self) -> None:
        assert run_program("jiue", "6\n65\n") == "A"

    def test_loop(self) -> None:
        # pp a (cell 2 nonzero, open), s b (0 -> close), u prints 0
        assert run_program("ppas b ue".replace(" ", "")) == "\x00"

    def test_repeat_next(self) -> None:
        # c repeats the next command 7 times; s subtracts 1 each -> -5
        assert run_program("pcsu") == "\xfb"
        # c repeating u prints 7 times
        assert run_program("pcue") == "\x02\x02\x02\x02\x02\x02\x02"

    def test_repeat_previous(self) -> None:
        # t repeats the previous command 3 times
        assert run_program("ptpue") == "\n"

    def test_halt(self) -> None:
        assert run_program("pe") == ""
        assert run_program("p") == ""

    def test_error(self) -> None:
        with pytest.raises(HaltError):
            run_program("b")  # loop close with an empty stack

    def test_empty_program(self) -> None:
        assert run_program("") == ""
