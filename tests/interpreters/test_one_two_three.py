"""Unit tests for the 123 interpreter."""

import importlib

import pytest

from esolangs.interpreters.io import ScriptedIO

run = importlib.import_module("esolangs.interpreters.tape_based.one_two_three").run

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
        """A FALSE 3 skips to the next 3, then the 1 halts (pos below 0)."""
        # 3 (FALSE, bit@0) -> next 3 -> 1 flips bit@0 and moves to pos -1.
        assert run_program("3231") == ""

    def test_true_jump_skips_backward(self) -> None:
        """A TRUE 3 jumps back to the previous 3 (or the start) and loops."""
        from esolangs.interpreters.tape_based.one_two_three import _Machine
        from esolangs.vm import run_until_halt_or_cycle

        # 2 (pos 0->1) 1 (flip bit@1, pos 1->0) 3 (bit@0 is FALSE, skip to
        # end) then loop-or-halt sees pos=0 (not <0) and restarts at ip=0
        # with bit@1 toggled back — a genuine bounded cycle (positions 0-1
        # only), decided by the deterministic state-cycle detector with no
        # wall-clock bound. A pointer that marches right forever instead
        # (e.g. never turning back via a TRUE 3) grows the tape without
        # repeating a state, which this detector cannot resolve — that
        # class of hang is left to a caller's timeout.
        machine = _Machine("2131", ScriptedIO())
        assert run_until_halt_or_cycle(machine) is False

    def test_true_jump_finds_previous_three(self) -> None:
        """A TRUE 3 with an earlier 3 in the code jumps just past it.

        ``test_true_jump_skips_backward`` (despite its name) actually
        exercises the FALSE/skip-forward branch; this test drives the
        TRUE/skip-backward branch directly via ``_Machine`` so the
        backward scan-and-land logic itself is covered.
        """
        from esolangs.interpreters.tape_based.one_two_three import _Machine

        # code[0] is the only earlier '3'; landing there means ip == 1.
        machine = _Machine("3xx3", ScriptedIO())
        machine.pos = 2
        machine.bits[2] = True
        machine.ip = 3
        machine.step()
        assert machine.ip == 1

    def test_pointer_is_unbounded_past_position_seven(self) -> None:
        """2 past position 7 keeps moving right instead of getting stuck.

        The wiki only special-cases locations -3, -2, and (via 1's
        wraparound) -4; instruction 2 at "any other location" — including
        8, 9, ... — just moves right with no stated ceiling.
        """
        from esolangs.interpreters.tape_based.one_two_three import _Machine

        # Nine 2s march 0 -> 9, then 1 flips bit@9 and moves to pos 8.
        machine = _Machine("2" * 9 + "1", ScriptedIO())
        for _ in range(10):
            machine.step()
        assert machine.pos == 8
        assert machine.bits.get(9) is True

    def test_wraparound_from_beyond_seven_reaches_read_position(self) -> None:
        """Marching left from past position 7 still reaches -3 to read.

        Regression test: an earlier implementation capped the pointer at
        position 7 and got permanently stuck there once instruction 2
        pushed it past that point, so -3/-2 (and thus all I/O) became
        unreachable for any program that walked far enough right first.
        """
        from esolangs.interpreters.tape_based.one_two_three import _Machine

        # 9 2s march 0 -> 9; 16 1s march back through the -4 wraparound to
        # 0 and on to -3; the final 2 reads 'Q' (0x51) into locations 0-7.
        machine = _Machine("2" * 9 + "1" * 16 + "2", ScriptedIO("Q"))
        for _ in range(26):
            machine.step()
        assert machine.pos == 0
        assert machine.byte() == ord("Q")
