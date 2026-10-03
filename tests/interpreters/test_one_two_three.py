"""Unit tests for the 123 interpreter."""

import importlib

import pytest

from esolangs.interpreters.io import ScriptedIO

run = importlib.import_module("esolangs.interpreters.tape_based.one_two_three").run

# The wiki's cat program: three 1s march the pointer to -3 (read), then the
# trailing 12121 flips the byte back and marches to -2 (write).
WIKI_CAT = "111212112"


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

    def test_state_cycle_detector_resolves_bounded_pointer_walk(self) -> None:
        """The walk repeats its complete state despite toggling bit 1."""
        from esolangs.interpreters.tape_based.one_two_three import _Machine
        from esolangs.vm import run_until_halt_or_cycle

        machine = _Machine("2131", ScriptedIO())
        assert run_until_halt_or_cycle(machine) is False

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


class TestStepMachine:
    def test_snapshot_carries_the_set_bits(self) -> None:
        """Snapshots carry signed set bits as well as the two cursors."""
        from esolangs.interpreters.tape_based.one_two_three import _Machine

        machine = _Machine("111", ScriptedIO())
        assert machine.snapshot() == (0, 0, frozenset(), 0)
        machine.step()
        assert machine.snapshot() == (1, -1, frozenset((0,)), 0)
        machine.step()
        assert machine.snapshot() == (2, -2, frozenset((-1, 0)), 0)
        machine.step()
        assert machine.snapshot() == (3, -3, frozenset((-2, -1, 0)), 0)
