"""Unit tests for the AddSubJump interpreter.

Tests cover the self-modifying memory model, the add/sub OISC instruction,
the special addresses (I/O, flags, constants, flag update mode), the jump,
and the documented halt/limit conventions.
"""

import pytest

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.register_based.addsubjump import run
from tests.interpreters.contract import (
    CycleContract,
    EmptyProgramContract,
)
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

    def test_writing_a_reserved_address_is_discarded(self) -> None:
        """Of the special addresses only ``-1`` and ``-9`` accept a write.

        ``-1`` prints and ``-9`` sets the flag-update mode; the constants at
        ``-6``..``-8`` and the flags between are read-only, so a write aimed
        at one is dropped rather than landing in memory or raising.  The
        program then prints, so the run is observed to continue.
        """
        code = memory([[-5, -6, 20, -7], [-1, -7, -8, -7]], {20: 4})
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


class TestTruncatedInstruction:
    """An instruction running off the end of memory reads zeros for the rest.

    Every other program holds whole four-cell instructions, so the guards
    that decide whether each operand exists were never false and the zero
    they fall back to was never used.  These programs stop mid-instruction,
    one cell shorter each time.
    """

    def test_a_missing_operand_reads_as_zero(self) -> None:
        # One cell: b, c and d are all absent, so each reads 0. a is -1, so
        # the instruction prints *b = memory[0] = -1, a byte of 0xff.
        assert _run("-1") == "\xff"

    def test_the_second_operand_is_the_first_that_can_be_present(self) -> None:
        # Two cells: b exists (address 4, an absent cell, so 0) while c and
        # d do not. Printing *b gives NUL rather than the -1 above.
        assert _run("-1 4") == "\x00"
        # ... and b really is read, not defaulted: -6 is the constant 1.
        assert _run("-1 -6") == "\x01"

    def test_a_present_third_operand_still_ends_the_run(self) -> None:
        # Three cells: c exists and holds 0, so the jump goes to memory[0]
        # = -1, a special address, which halts.
        assert _run("-1 4 0") == "\x00"


class TestFlags:
    """The flag update mode and the four flags it refreshes.

    Nothing exercised these: the mode starts off, so a suite that never
    writes ``-9`` leaves the whole update block unreached, and the flags it
    would have set unread.  Each program here turns the mode on, performs
    one arithmetic step whose result is known, and prints one flag.
    """

    @staticmethod
    def _flag(op: int, flag: int) -> str:
        """Turn the mode on, apply ``op`` to cell 12, then print ``flag``."""
        return memory(
            [[-9, -6, 13, -7], [12, op, 14, -6], [-1, flag, 15, -7]],
            {13: 4, 14: 8, 15: -1},
        )

    def test_negative_flag_follows_the_sign_of_the_result(self) -> None:
        """``NF`` is set when the result is below zero, and only then."""
        assert _run(self._flag(-6, -4)) == "\x01"  # 0 - 1 = -1
        assert _run(self._flag(-7, -4)) == "\x00"  # 0 - 0 =  0

    def test_zero_flag_follows_the_result_being_zero(self) -> None:
        """``ZF`` is set when the result is exactly zero, and only then."""
        assert _run(self._flag(-7, -3)) == "\x01"  # 0 - 0 =  0
        assert _run(self._flag(-6, -3)) == "\x00"  # 0 - 1 = -1

    def test_carry_and_overflow_stay_zero(self) -> None:
        """Cells are unbounded, so neither flag has anything to report.

        They are still cleared on every update, which is what keeps them
        from holding a stale value; a mode that set them instead would be
        reporting a carry that cannot happen.
        """
        assert _run(self._flag(-6, -2)) == "\x00"
        assert _run(self._flag(-6, -5)) == "\x00"

    def test_flags_do_not_update_while_the_mode_is_off(self) -> None:
        """The mode starts at zero, so a negative result leaves ``NF`` clear."""
        code = memory([[12, -6, 13, -6], [-1, -4, 14, -7]], {13: 4, 14: -1})
        assert _run(code) == "\x00"


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

    def test_growing_the_memory_zeroes_the_cells_it_skips(self) -> None:
        """A write past the end pads with zeros, and pads exactly far enough.

        Writing beyond the memory grows it to reach the address, and every
        cell in between is created by that growth -- so their value is the
        padding's, and nothing read one.  Cell 19 here is skipped over on
        the way to 20: it must read as zero, and the memory must stop at
        21 cells rather than run one over.
        """
        code = memory([[20, -6, 13, -7], [-1, 19, 14, -7]], {13: 4, 14: -1})
        assert _run(code) == "\x00"

    def test_a_write_at_the_first_absent_address_still_grows(self) -> None:
        """The growth fires when the address equals the length, not past it.

        Fifteen cells make address 15 the first that does not exist, and it
        is exactly the edge the comparison sits on: a check that waited for
        the address to exceed the length would index off the end here.
        """
        code = memory([[15, -6, 13, -7], [-1, 15, 14, -7]], {13: 4, 14: -1})
        assert _run(code) == "\x01"

    def test_the_largest_allocatable_address_is_the_last_one_that_works(
        self,
    ) -> None:
        """A write halts only once the address is past the memory ceiling.

        The ceiling itself was never approached, so the comparison deciding
        it was free to sit a cell either side, and the padding that grows
        the memory to reach the address was free to be one cell short or
        long.  Writing to the last legal address succeeds; the next one up
        halts, and says so.
        """
        ceiling = 1 << 24
        assert _run(memory([[ceiling - 1, -6, 13, -7]], {13: -1})) == ""

        with pytest.raises(HaltError) as caught:
            _run(memory([[ceiling, -6, 13, -7]], {13: -1}))
        assert str(caught.value) == f"memory address {ceiling} is too large"

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

    def test_the_flag_registers_are_readable_off_the_machine(self) -> None:
        """The five flag names report the state fields they are named for.

        ``TestFlags`` above proves the flags through *programs*, which read
        them back out of memory at ``-3``..``-5``; nothing read them off the
        machine object.  They are the language's own names on the stepped
        surface, and ``of`` in particular is load-bearing elsewhere: the VM
        looks up ``of`` on a state class to find an alternative constructor
        and only accepts it when callable, precisely because AddSubJump
        spells its overflow flag that way.

        The program enables flag-update mode and then produces a zero
        result, so ``fum`` and ``zf`` both have to move -- a property wired
        to a neighbouring tuple slot would stay put.
        """
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
        assert (machine.cf, machine.zf, machine.nf, machine.of, machine.fum) == (
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
        assert machine.fum == 1  # -9 turned the mode on and it stayed on
        assert (1, 1) in seen  # and the zero result set ZF while it was on
        # The three flags this program never disturbs stay clear, so the
        # accessors are not all reading one field.
        assert (machine.cf, machine.nf, machine.of) == (0, 0, 0)
        # AddSubJump has no stack, and the shared VM view says so with an
        # empty one rather than by omitting the name.
        assert machine.stack == []


def _machine(code: object) -> object:
    from esolangs.interpreters.io import ScriptedIO
    from esolangs.interpreters.register_based.addsubjump import _Machine

    return _Machine(code, ScriptedIO())


class TestContract(EmptyProgramContract, CycleContract):
    """The shared empty-program shape, with this language's data."""

    run = staticmethod(_run)
    machine = staticmethod(_machine)
    halting_program = "-1 1 0 -7"
    looping_program = "0 0 0 0"
