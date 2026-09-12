r"""Unit tests for the 123 interpreter."""

import importlib

import pytest

from esolangs.interpreters.io import ScriptedIO
from tests.interpreters.contract import EmptyProgramContract

run = importlib.import_module("esolangs.interpreters.tape_based.one_two_three").run

# The wiki's cat program: three.
# trailing 12121 flips the byte.
WIKI_CAT = "111212112"


def run_program(code: str, stdin: str = "") -> str:
    io = ScriptedIO(stdin)
    run(code, io)
    return io.getvalue()


class Test123:
    def test_nops_only(self) -> None:
        r"""Characters other than 1/2/3 are NOPs and are skipped."""
        assert run_program(" \n abc \n") == ""

    def test_generated_letter(self) -> None:
        r"""The generator's program for 'A' outputs 'A' and halts."""
        assert run_program("212222222112112112112112112112112\n1") == "A"

    def test_unknown_chars_are_nops(self) -> None:
        r"""Comments scattered through the program do not change it."""
        prog = "212222222112112112112112112112112\n1"
        assert run_program("hello " + prog) == "A"

    def test_wiki_cat_echoes(self) -> None:
        r"""The cat program echoes input, then EOF raises like the others."""
        io = ScriptedIO("h\ni")
        with pytest.raises(EOFError):
            run(WIKI_CAT, io)
        assert io.getvalue() == "hi"

    def test_false_jump_skips_forward(self) -> None:
        r"""A FALSE 3 skips to the next 3, then the 1 halts (pos below 0)."""
        # 3 (FALSE, bit@0) -> next 3 ->.
        assert run_program("3231") == ""

    def test_false_jump_starts_looking_at_the_next_command(self) -> None:
        r"""The forward scan begins one past the ``3``, so an adjacent ``3`` is."""
        assert run_program("331") == ""

    def test_forward_scan_stops_at_the_end_of_the_code(self) -> None:
        r"""The scan for the next ``3`` stops before running off the code."""
        assert run_program("132231") == ""

    def test_unwritten_bits_are_zero(self) -> None:
        r"""Bits never assigned read as 0 when the byte is assembled."""
        assert run_program("1121") == "\x80"

    def test_true_jump_skips_backward(self) -> None:
        r"""A TRUE 3 jumps back to the previous 3 (or the start) and loops."""
        from esolangs.interpreters.tape_based.one_two_three import _Machine
        from esolangs.vm import run_until_halt_or_cycle

        # 2 (pos 0->1) 1 (flip bit@1,.
        # end) then loop-or-halt sees.
        # with bit@1 toggled back — a.
        # only), decided by the.
        # wall-clock bound.
        # (e.g.
        # repeating a state, which this.
        # class of hang is left to a.
        machine = _Machine("2131", ScriptedIO())
        assert run_until_halt_or_cycle(machine) is False

    def test_true_jump_finds_previous_three(self) -> None:
        r"""A TRUE 3 with an earlier 3 in the code jumps just past it."""
        from esolangs.interpreters.tape_based.one_two_three import _Machine

        # code[0] is the only earlier.
        machine = _Machine("3xx3", ScriptedIO())
        machine.place(ip=3, pos=2, bits=frozenset((2,)))
        machine.step()
        assert machine.ip == 1

    def test_pointer_is_unbounded_past_position_seven(self) -> None:
        r"""2 past position 7 keeps moving right instead of getting stuck."""
        from esolangs.interpreters.tape_based.one_two_three import _Machine

        # Nine 2s march 0 -> 9, then 1.
        machine = _Machine("2" * 9 + "1", ScriptedIO())
        for _ in range(10):
            machine.step()
        assert machine.pos == 8
        assert 9 in machine.bits

    def test_wraparound_from_beyond_seven_reaches_read_position(self) -> None:
        r"""Marching left from past position 7 still reaches -3 to read."""
        from esolangs.interpreters.tape_based.one_two_three import _Machine

        # 9 2s march 0 -> 9; 16 1s.
        # 0 and on to -3; the final 2.
        machine = _Machine("2" * 9 + "1" * 16 + "2", ScriptedIO("Q"))
        for _ in range(26):
            machine.step()
        assert machine.pos == 0
        assert machine.byte() == ord("Q")


class TestStepMachine:
    def test_reading_a_byte_keeps_bits_beyond_the_byte_window(self) -> None:
        r"""Input replaces locations 0-7 only; the tape remains unbounded."""
        from esolangs.interpreters.tape_based.one_two_three import _with_byte

        assert _with_byte(frozenset((8,)), 0) == frozenset((8,))

    def test_snapshot_carries_the_set_bits(self) -> None:
        r"""The tape is part of the state, not just the cursors."""
        from esolangs.interpreters.tape_based.one_two_three import _Machine

        machine = _Machine("111", ScriptedIO())
        assert machine.snapshot() == (0, 0, (), 0)
        machine.step()
        assert machine.snapshot() == (1, -1, (0,), 0)
        machine.step()
        assert machine.snapshot() == (2, -2, (-1, 0), 0)
        machine.step()
        assert machine.snapshot() == (3, -3, (-2, -1, 0), 0)

    def test_backward_jump_stops_at_an_adjacent_three(self) -> None:
        r"""The backward scan starts at the character before the ``3``."""
        from esolangs.interpreters.tape_based.one_two_three import _Machine

        machine = _Machine("33112", ScriptedIO())
        for _ in range(20):
            if machine.halted:
                break
            machine.step()
        assert machine.io.getvalue() == "\x80"


class TestContract(EmptyProgramContract):
    r"""The shared empty-program shape, with this language's data."""

    run = staticmethod(run_program)
