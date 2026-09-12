r"""Unit tests for the AddSubJump interpreter."""

import pytest

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.register_based.addsubjump import run
from tests.interpreters.contract import (
    CycleContract,
    EmptyProgramContract,
)
from tests.interpreters.oisc import memory, run_program


def _run(code, stdin=""):
    return run_program(run, code, stdin=stdin)


class TestInstruction:
    def test_output_a_memory_cell(self) -> None:
        # The wiki's example: -1 1 0 -7.
        # value cell is at address 4.
        assert _run("-1 4 0 -7 65") == "A"

    def test_adds_through_the_constant_one(self) -> None:
        # memory[12] += 1 twice (d = -7.
        # then output and halt (c = -8.
        # address).
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
        # d = -6 is the constant 1, so.
        code = memory([[12, -6, 13, -6], [-1, 12, -8, -7]], {13: 4})
        assert _run(code) == "\xff"

    def test_jumps_via_a_data_cell(self) -> None:
        # The increment's *c =.
        code = memory([[12, -6, 13, -7], [-1, 12, -8, -7]], {13: 4})
        assert _run(code) == "\x01"


class TestSpecialAddresses:
    def test_constants(self) -> None:
        # -6 = 1, -7 = 0, -8 = -1:.
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

    def test_writing_a_reserved_address_is_discarded(self) -> None:
        r"""Of the special addresses only ``-1`` and ``-9`` accept a write."""
        code = memory([[-5, -6, 20, -7], [-1, -7, -8, -7]], {20: 4})
        assert _run(code) == "\x00"

    def test_input_byte_is_added_to_the_target(self) -> None:
        # memory[12] starts 0, so.
        code = memory([[12, -1, 13, -7], [-1, 12, -8, -7]], {13: 4})
        assert _run(code, "X") == "X"

    def test_input_running_out_raises_eof(self) -> None:
        code = memory([[12, -1, 4, -7], [-1, 12, -8, -7]])
        io = ScriptedIO("")
        with pytest.raises(EOFError):
            run(code, io)

    def test_flags_only_update_while_flag_mode_is_set(self) -> None:
        # Without touching -9 the zero.
        code = memory(
            [
                [12, -7, 13, -7],
                [-1, 12, -8, -7],
            ],
            {13: 4},
        )
        assert _run(code) == "\x00"

    def test_zero_flag_is_set_under_flag_mode(self) -> None:
        # Enable flag mode (-9 += 1),.
        # flag (-3) into a cell, and.
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
        # Under flag mode, 0 - 1 = -1.
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


class TestTruncatedInstruction:
    r"""An instruction running off the end of memory reads zeros for the."""

    def test_a_missing_operand_reads_as_zero(self) -> None:
        # One cell: b, c and d are all.
        # the instruction prints *b =.
        assert _run("-1") == "\xff"

    def test_the_second_operand_is_the_first_that_can_be_present(self) -> None:
        # Two cells: b exists (address.
        # d do not.
        assert _run("-1 4") == "\x00"
        # .
        assert _run("-1 -6") == "\x01"

    def test_a_present_third_operand_still_ends_the_run(self) -> None:
        # Three cells: c exists and.
        # = -1, a special address,.
        assert _run("-1 4 0") == "\x00"


class TestFlags:
    r"""The flag update mode and the four flags it refreshes."""

    @staticmethod
    def _flag(op: int, flag: int) -> str:
        r"""Turn the mode on, apply ``op`` to cell 12, then print ``flag``."""
        return memory(
            [[-9, -6, 13, -7], [12, op, 14, -6], [-1, flag, 15, -7]],
            {13: 4, 14: 8, 15: -1},
        )

    def test_negative_flag_follows_the_sign_of_the_result(self) -> None:
        r"""``NF`` is set when the result is below zero, and only then."""
        assert _run(self._flag(-6, -4)) == "\x01"  # 0 - 1 = -1.
        assert _run(self._flag(-7, -4)) == "\x00"  # 0 - 0 = 0.

    def test_zero_flag_follows_the_result_being_zero(self) -> None:
        r"""``ZF`` is set when the result is exactly zero, and only then."""
        assert _run(self._flag(-7, -3)) == "\x01"  # 0 - 0 = 0.
        assert _run(self._flag(-6, -3)) == "\x00"  # 0 - 1 = -1.

    def test_carry_and_overflow_stay_zero(self) -> None:
        r"""Cells are unbounded, so neither flag has anything to report."""
        assert _run(self._flag(-6, -2)) == "\x00"
        assert _run(self._flag(-6, -5)) == "\x00"

    def test_flags_do_not_update_while_the_mode_is_off(self) -> None:
        r"""The mode starts at zero, so a negative result leaves ``NF`` clear."""
        code = memory([[12, -6, 13, -6], [-1, -4, 14, -7]], {13: 4, 14: -1})
        assert _run(code) == "\x00"


class TestHaltAndErrors:
    def test_jump_off_the_end_halts(self) -> None:
        # The jump target (a data cell).
        code = memory([[12, -6, 13, -7]], {13: 1000})
        assert _run(code) == ""

    def test_malformed_token(self) -> None:
        with pytest.raises(ValueError, match="malformed memory token"):
            _run("12 -6 x -7")

    def test_growing_the_memory_zeroes_the_cells_it_skips(self) -> None:
        r"""A write past the end pads with zeros, and pads exactly far enough."""
        code = memory([[20, -6, 13, -7], [-1, 19, 14, -7]], {13: 4, 14: -1})
        assert _run(code) == "\x00"

    def test_a_write_at_the_first_absent_address_still_grows(self) -> None:
        r"""The growth fires when the address equals the length, not past it."""
        code = memory([[15, -6, 13, -7], [-1, 15, 14, -7]], {13: 4, 14: -1})
        assert _run(code) == "\x01"

    def test_the_largest_allocatable_address_is_the_last_one_that_works(
        self,
    ) -> None:
        r"""A write halts only once the address is past the memory ceiling."""
        ceiling = 1 << 24
        assert _run(memory([[ceiling - 1, -6, 13, -7]], {13: -1})) == ""

        with pytest.raises(HaltError) as caught:
            _run(memory([[ceiling, -6, 13, -7]], {13: -1}))
        assert str(caught.value) == f"memory address {ceiling} is too large"

    def test_carry_and_overflow_flags_read_as_zero(self) -> None:
        # The carry (-2) and overflow.
        # interpreter, so copying them.
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
        r"""Cell values are unbounded; the list holding them is not."""
        with pytest.raises(HaltError, match="too large"):
            _run("9" * 40)


class TestStepMachine:
    def test_step_tracks_ip_and_memory(self) -> None:
        from esolangs.interpreters.register_based.addsubjump import _Machine

        machine = _Machine("-1 1 0 -7", ScriptedIO())
        assert (machine.ip, list(machine.memory)) == (0, [-1, 1, 0, -7])
        machine.step()  # writes *b to I/O and jumps.
        assert machine.io.getvalue() == "\x01"
        assert machine.ip == -1
        assert machine.halted
        machine.step()  # stepping a halted machine is.
        assert machine.ip == -1

    def test_snapshot_includes_the_input_cursor(self) -> None:
        from esolangs.interpreters.register_based.addsubjump import _Machine

        machine = _Machine("0 0 0 0", ScriptedIO("one\n"))
        before = machine.snapshot()
        machine.io.input_str()
        assert machine.snapshot() != before

    def test_a_cell_written_to_zero_matches_one_never_written(self) -> None:
        r"""The sparse store must not distinguish a stored zero from no key."""
        from esolangs.interpreters.register_based.addsubjump import (
            _pack,
            _store,
        )

        state = (_pack([5, 0, 0]), 0, 0, 0, 0, 0, 0)
        # Write a non-zero and then.
        written = _store(_store(state, 1, 7), 1, 0)
        assert written[0] == state[0], "a zeroed cell left a key behind"

        # And a parsed zero is already.
        cells, length = _pack([5, 0, 0])
        assert cells == {0: 5}
        assert length == 3

    def test_snapshot_is_independent_of_write_order(self) -> None:
        r"""Equal memories must snapshot equal however they were reached."""
        from esolangs.interpreters.register_based.addsubjump import (
            _Machine,
            _store,
        )

        one = _Machine("0 0 0 0", ScriptedIO())
        other = _Machine("0 0 0 0", ScriptedIO())
        one.state = _store(_store(one.state, 1, 4), 2, 9)
        other.state = _store(_store(other.state, 2, 9), 1, 4)
        assert one.snapshot() == other.snapshot()
        assert hash(one.snapshot()) == hash(other.snapshot())

    def test_the_flag_registers_are_readable_off_the_machine(self) -> None:
        r"""The five flag names report the state fields they are named for."""
        from esolangs.interpreters.register_based.addsubjump import _Machine

        code = memory(
            [
                [-9, -6, 40, -7],
                [30, -7, 41, -7],
                [31, -3, 42, -7],
                [-1, 31, -8, -7],
            ],
            {40: 4, 41: 8, 42: 12},
        )
        machine = _Machine(code, ScriptedIO())
        assert (machine.cf, machine.zf, machine.nf, machine.vf, machine.fum) == (
            0,
            0,
            0,
            0,
            0,
        )
        seen = set()
        while not machine.halted:
            machine.step()
            seen.add((machine.fum, machine.zf))
        assert machine.fum == 1  # -9 turned the mode on and it.
        assert (1, 1) in seen  # and the zero result set ZF.
        # The three flags this program.
        # accessors are not all reading.
        assert (machine.cf, machine.nf, machine.vf) == (0, 0, 0)
        # AddSubJump has no stack, and.
        # empty one rather than by.
        assert machine.stack == []


def _machine(code: object) -> object:
    from esolangs.interpreters.io import ScriptedIO
    from esolangs.interpreters.register_based.addsubjump import _Machine

    return _Machine(code, ScriptedIO())


class TestContract(EmptyProgramContract, CycleContract):
    r"""The shared empty-program shape, with this language's data."""

    run = staticmethod(_run)
    machine = staticmethod(_machine)
    halting_program = "-1 1 0 -7"
    looping_program = "0 0 0 0"
