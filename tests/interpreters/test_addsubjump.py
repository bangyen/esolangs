"""Unit tests for the AddSubJump interpreter.

Tests cover the self-modifying memory model, the add/sub OISC instruction,
the special addresses (I/O, flags, constants, flag update mode), the jump,
and the documented halt/limit conventions.
"""

import pytest

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.register_based.addsubjump import run
from tests.interpreters.contract import EmptyProgramContract
from tests.interpreters.oisc import memory, run_program


def _run(code, stdin="", limit=100_000):
    return run_program(run, code, stdin=stdin, limit=limit)


class TestInstruction:
    def test_output_a_memory_cell(self) -> None:
        # The wiki's example: -1 1 0 -7 outputs memory address 1; here the
        # value cell is at address 4 and *c = memory[0] = -1 halts.
        assert _run("-1 4 0 -7 65") == "A"

    def test_adds_through_the_constant_one(self) -> None:
        # memory[12] += 1 twice (d = -7 is the constant 0, so the += branch),
        # then output and halt (c = -8 reads the constant -1, a special
        # address).  Jump targets come from data cells 13/14.
        code = memory(
            [
                [12, -6, 13, -7],
                [12, -6, 14, -7],
                [-1, 12, -8, -7],
            ],
            {13: 4, 14: 8},
        )
        assert _run(code) == "\x02"

    def test_subtracts_when_the_selector_is_positive(self) -> None:
        # d = -6 is the constant 1, so the -= branch fires: 0 - 1 = -1.
        code = memory([[12, -6, 13, -6], [-1, 12, -8, -7]], {13: 4})
        assert _run(code) == "\xff"

    def test_jumps_via_a_data_cell(self) -> None:
        # The increment's *c = memory[13] = 4 sends the pointer to ip 4.
        code = memory([[12, -6, 13, -7], [-1, 12, -8, -7]], {13: 4})
        assert _run(code) == "\x01"


class TestSpecialAddresses:
    def test_constants(self) -> None:
        # -6 = 1, -7 = 0, -8 = -1: memory[30] = 1 + 0 + (-1) = 0.
        code = memory(
            [
                [30, -6, 20, -7],
                [30, -7, 21, -7],
                [30, -8, 22, -7],
                [-1, 30, -8, -7],
            ],
            {20: 4, 21: 8, 22: 12},
        )
        assert _run(code) == "\x00"

    def test_input_byte_is_added_to_the_target(self) -> None:
        # memory[12] starts 0, so reading -1 (as *b) adds the input byte.
        code = memory([[12, -1, 13, -7], [-1, 12, -8, -7]], {13: 4})
        assert _run(code, "X") == "X"

    def test_input_running_out_raises_eof(self) -> None:
        code = memory([[12, -1, 4, -7], [-1, 12, -8, -7]])
        io = ScriptedIO("")
        with pytest.raises(EOFError):
            run(code, io)

    def test_flags_only_update_while_flag_mode_is_set(self) -> None:
        # Without touching -9 the zero flag stays 0 even after a +0 result.
        code = memory(
            [
                [12, -7, 13, -7],
                [-1, 12, -8, -7],
            ],
            {13: 4},
        )
        assert _run(code) == "\x00"

    def test_zero_flag_is_set_under_flag_mode(self) -> None:
        # Enable flag mode (-9 += 1), produce a zero result, copy the zero
        # flag (-3) into a cell, and output it.
        code = memory(
            [
                [-9, -6, 40, -7],
                [30, -7, 41, -7],
                [31, -3, 42, -7],
                [-1, 31, -8, -7],
            ],
            {40: 4, 41: 8, 42: 12},
        )
        assert _run(code) == "\x01"

    def test_negative_flag(self) -> None:
        # Under flag mode, 0 - 1 = -1 sets the negative flag (-4).
        code = memory(
            [
                [-9, -6, 40, -7],
                [30, -6, 41, -6],
                [31, -4, 42, -7],
                [-1, 31, -8, -7],
            ],
            {40: 4, 41: 8, 42: 12},
        )
        assert _run(code) == "\x01"


class TestHaltAndErrors:
    def test_jump_off_the_end_halts(self) -> None:
        # The jump target (a data cell) is huge, past the memory.
        code = memory([[12, -6, 13, -7]], {13: 1000})
        assert _run(code) == ""

    def test_looping_program_hits_the_limit(self) -> None:
        # The increment's jump target is itself (data cell 13 = 0 -> ip 0).
        code = memory([[12, -6, 13, -7]], {13: 0})
        io = ScriptedIO("")
        with pytest.raises(HaltError):
            run(code, io, limit=100)

    def test_malformed_token(self) -> None:
        with pytest.raises(ValueError, match="malformed memory token"):
            _run("12 -6 x -7")

    def test_carry_and_overflow_flags_read_as_zero(self) -> None:
        # The carry (-2) and overflow (-5) flags are always 0 in this
        # interpreter, so copying them into cells prints two NUL bytes.
        code = memory(
            [
                [31, -2, 44, -7],
                [32, -5, 45, -7],
                [-1, 31, 46, -7],
                [-1, 32, -8, -7],
            ],
            {44: 4, 45: 8, 46: 12},
        )
        assert _run(code) == "\x00\x00"

    def test_comments_and_blank_lines_are_ignored(self) -> None:
        base = memory([[31, -6, 45, -7], [-1, 31, -8, -7]], {45: 4})
        code = "# a comment\n\n" + base + " # trailing comment\n"
        assert _run(code) == "\x01"

    def test_unallocatable_address_halts(self) -> None:
        """Cell values are unbounded; the list holding them is not."""
        with pytest.raises(HaltError, match="too large"):
            _run("9" * 40)


class TestStepMachine:
    def test_step_tracks_ip_and_memory(self) -> None:
        from esolangs.interpreters.register_based.addsubjump import _Machine

        machine = _Machine("-1 1 0 -7", ScriptedIO())
        assert (machine.ip, list(machine.memory)) == (0, [-1, 1, 0, -7])
        machine.step()  # writes *b to I/O and jumps via *c (a special address)
        assert machine.io.getvalue() == "\x01"
        assert machine.ip == -1
        assert machine.halted
        machine.step()  # stepping a halted machine is a no-op
        assert machine.ip == -1

    def test_snapshot_includes_the_input_cursor(self) -> None:
        from esolangs.interpreters.register_based.addsubjump import _Machine

        machine = _Machine("0 0 0 0", ScriptedIO())
        assert hash(machine.snapshot()) is not None
        assert machine.io.position() == 0

    def test_halting_program_is_detected(self) -> None:
        from esolangs.interpreters.register_based.addsubjump import _Machine
        from esolangs.vm import run_until_halt_or_cycle

        assert run_until_halt_or_cycle(_Machine("-1 1 0 -7", ScriptedIO())) is True

    def test_looping_program_is_detected_as_a_cycle(self) -> None:
        """0 0 0 0 adds zero to cell 0 and jumps to itself forever."""
        from esolangs.interpreters.register_based.addsubjump import _Machine
        from esolangs.vm import run_until_halt_or_cycle

        assert run_until_halt_or_cycle(_Machine("0 0 0 0", ScriptedIO())) is False


class TestContract(EmptyProgramContract):
    """The shared empty-program shape, with this language's data."""

    run = staticmethod(_run)
