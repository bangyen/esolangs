"""Unit tests for the 123 interpreter."""

import importlib
from functools import partial

import pytest

from esolangs.interpreters.io import ScriptedIO
from tests.interpreters import runner

run = importlib.import_module("esolangs.interpreters.tape_based.one_two_three").run

# The wiki's cat program: three 1s march the pointer to -3 (read), then the
# trailing 12121 flips the byte back and marches to -2 (write).
WIKI_CAT = "111212112"


run_program = partial(runner.run_program, run, suppress_eof=False)


class Test123:
    def test_comment_only_program_loops(self) -> None:
        """Comments are NOPs; reaching their end restarts at position zero."""
        from esolangs.interpreters.tape_based.one_two_three import _Machine
        from esolangs.vm import run_until_halt_or_cycle

        assert run_until_halt_or_cycle(_Machine(" \n abc \n", ScriptedIO())) is False

    def test_wiki_cat_echoes(self) -> None:
        """The cat program echoes input, then EOF raises like the others."""
        io = ScriptedIO("h\ni")
        with pytest.raises(EOFError):
            run(WIKI_CAT, io)
        assert io.getvalue() == "h\ni"

    def test_false_jump_skips_forward(self) -> None:
        """A FALSE 3 skips to the next 3, then the 1 halts (pos below 0)."""
        # 3 (FALSE, bit@0) -> next 3 -> 1 flips bit@0 and moves to pos -1.
        assert run_program("3231") == ""

    def test_false_jump_starts_looking_at_the_next_command(self) -> None:
        """The forward scan begins one past the ``3``, so an adjacent ``3``
        is the one it finds.
        """
        assert run_program("331") == ""

    def test_forward_scan_stops_at_the_end_of_the_code(self) -> None:
        """The scan for the next ``3`` stops before running off the code."""
        assert run_program("132231") == ""

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
        """A TRUE 3 with an earlier 3 in the code jumps just past it."""
        from esolangs.interpreters.tape_based.one_two_three import _Machine

        # code[0] is the only earlier '3'; landing there means ip == 1.
        machine = _Machine("3xx3", ScriptedIO())
        machine.place(ip=3, pos=2, bits=frozenset((2,)))
        machine.step()
        assert machine.ip == 1

    def test_pointer_is_unbounded_past_position_seven(self) -> None:
        """2 past position 7 keeps moving right instead of getting stuck."""
        from esolangs.interpreters.tape_based.one_two_three import _Machine

        # Nine 2s march 0 -> 9, then 1 flips bit@9 and moves to pos 8.
        machine = _Machine("2" * 9 + "1", ScriptedIO())
        for _ in range(10):
            machine.step()
        assert machine.pos == 8
        assert 9 in machine.bits

    def test_wraparound_from_beyond_seven_reaches_read_position(self) -> None:
        """Marching left from past position 7 still reaches -3 to read."""
        from esolangs.interpreters.tape_based.one_two_three import _Machine

        # 9 2s march 0 -> 9; 16 1s march back through the -4 wraparound to
        # 0 and on to -3; the final 2 reads 'Q' (0x51) into locations 0-7.
        machine = _Machine("2" * 9 + "1" * 16 + "2", ScriptedIO("Q"))
        for _ in range(26):
            machine.step()
        assert machine.pos == 0
        assert machine.byte() == ord("Q")


class TestStepMachine:
    def test_reading_a_byte_keeps_bits_beyond_the_byte_window(self) -> None:
        """Input replaces locations 0-7 only; the tape remains unbounded."""
        from esolangs.interpreters.tape_based.one_two_three import _with_byte

        assert _with_byte(frozenset((8,)), 0) == frozenset((8,))

    def test_snapshot_carries_the_set_bits(self) -> None:
        """The tape is part of the state, not just the cursors."""
        from esolangs.interpreters.tape_based.one_two_three import _Machine

        machine = _Machine("111", ScriptedIO())
        assert machine.snapshot() == (0, 0, frozenset(), 0)
        machine.step()
        assert machine.snapshot() == (1, -1, frozenset((0,)), 0)
        machine.step()
        assert machine.snapshot() == (2, -2, frozenset((-1, 0)), 0)
        machine.step()
        assert machine.snapshot() == (3, -3, frozenset((-2, -1, 0)), 0)

    def test_backward_jump_stops_at_an_adjacent_three(self) -> None:
        """The backward scan starts at the character before the ``3``."""
        from esolangs.interpreters.tape_based.one_two_three import _Machine

        machine = _Machine("33112", ScriptedIO())
        for _ in range(20):
            if machine.halted:
                break
            machine.step()
        assert machine.io.getvalue() == "\x01"
