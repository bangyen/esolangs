"""Unit tests for the AddSubJump interpreter."""

import pytest

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.register_based.addsubjump import _assembly, run
from tests.interpreters.contract import (
    CycleContract,
    EmptyProgramContract,
)
from tests.interpreters.oisc import memory, run_program


def _run(code, stdin=""):
    return run_program(run, code, stdin=stdin)


class TestAssembly:
    def test_labels_offsets_and_question_mark(self) -> None:
        code = """
        -1 @A -1 @A+1
        @A:65 0 @A-1
        """
        assert _assembly(code) == [-1, 4, -1, 5, 65, 0, 3, -7]

    def test_sugar_and_data_directive(self) -> None:
        code = """
        IO A
        IO B
        IO C
        IO D
        IO E IO
        .data A:65 B:66 C:67 D:68 E:69
        """
        assert _assembly(code) == [
            -1,
            20,
            4,
            -7,
            -1,
            21,
            8,
            -7,
            -1,
            22,
            12,
            -7,
            -1,
            23,
            16,
            -7,
            -1,
            24,
            -1,
            -7,
            65,
            66,
            67,
            68,
            69,
        ]

    def test_macro_example(self) -> None:
        code = """
        def macro A {
          IO A
        }
        macro H
        @0 @0 @0
        H:.data 72
        """
        assert _assembly(code) == [-1, 8, 4, -7, -7, -7, -7, -7, 72]

    def test_comments_and_explicit_asj(self) -> None:
        code = """
        /* block */ ASJ IO value end @0 // line
        value:.data 65 # tail
        end:
        """
        assert _assembly(code) == [-1, 4, 5, -7, 65]

    def test_macro_local_labels_are_private_per_expansion(self) -> None:
        code = """
        def skip A {
          local: @0 @0 A
        }
        skip done
        skip done
        done:.data 0
        """
        assert _assembly(code) == [-7, -7, 8, -7, -7, -7, 8, -7, 0]

    def test_a_label_can_prefix_an_empty_macro(self) -> None:
        code = """
        def nop {
        }
        start: nop
        .data start
        """
        assert _assembly(code) == [0]

    def test_a_label_can_prefix_a_macro_with_a_body(self) -> None:
        code = """
        def one {
        .data 7
        }
        start: one
        .data start
        """
        assert _assembly(code) == [7, 0]

    def test_inline_data_label_can_precede_a_separate_value(self) -> None:
        assert _assembly(".data A: 1") == [1]


class TestAssemblyErrors:
    @pytest.mark.parametrize(
        ("code", "message"),
        [
            ("def", "malformed .*macro"),
            ("def bad {\n{\n}\n", "nested"),
            ("def bad {", "missing"),
            ("def bad A { 1 2\n}", "malformed .*macro"),
            (".data :1", "empty AddSubJump label"),
            ("def bad {\n}\ndef bad {\n}", "duplicate macro"),
            ("def loop {\nloop\n}\nloop", "recursive macro"),
            ("def one A {\n.data A\n}\none", "takes 1 arguments"),
            ("def bad {\n:label 1 2\n}\nbad", "empty AddSubJump label"),
            ("IO: 1 2", "duplicate label"),
            (".data A:1 A:2", "duplicate label"),
            ("1", "needs 2 to 4 operands"),
            (".data $", "invalid AddSubJump operand"),
        ],
    )
    def test_malformed_assembly_is_rejected(self, code: str, message: str) -> None:
        with pytest.raises(ValueError, match=message):
            _assembly(code)


class TestInstruction:
    def test_output_a_memory_cell(self) -> None:
        # The wiki's example -1 1 0 -7 outputs memory address 1 and then
        # jumps to the *literal* address 0, which loops; here the value cell
        # is at address 4 and c = -1 is a special address, so the run ends.
        assert _run("-1 4 -1 -7 65") == "A"

    def test_adds_through_the_constant_one(self) -> None:
        # memory[12] += 1 twice (d = -7 is the constant 0, so the += branch),
        # then output and halt (c = -8 is a special address).
        code = memory(
            [
                [12, -6, 4, -7],
                [12, -6, 8, -7],
                [-1, 12, -8, -7],
            ]
        )
        assert _run(code) == "\x02"

    def test_subtracts_when_the_selector_is_positive(self) -> None:
        # d = -6 is the constant 1, so the -= branch fires: 0 - 1 = -1.
        code = memory([[12, -6, 4, -6], [-1, 12, -8, -7]])
        assert _run(code) == "\xff"

    def test_the_jump_target_is_literal(self) -> None:
        """``c`` is the destination itself, not a cell holding it."""
        code = memory([[12, -6, 8, -7], [-1, -8, -1, -7], [-1, 12, -8, -7]])
        assert _run(code) == "\x01"


class TestSpecialAddresses:
    def test_constants(self) -> None:
        # -6 = 1, -7 = 0, -8 = -1: memory[30] = 1 + 0 + (-1) = 0.
        code = memory(
            [
                [30, -6, 4, -7],
                [30, -7, 8, -7],
                [30, -8, 12, -7],
                [-1, 30, -8, -7],
            ]
        )
        assert _run(code) == "\x00"

    def test_writing_a_reserved_address_is_discarded(self) -> None:
        """Of the special addresses only ``-1`` and ``-9`` accept a write."""
        code = memory([[-5, -6, 4, -7], [-1, -7, -8, -7]])
        assert _run(code) == "\x00"

    def test_input_byte_is_added_to_the_target(self) -> None:
        # memory[12] starts 0, so reading -1 (as *b) adds the input byte.
        code = memory([[12, -1, 4, -7], [-1, 12, -8, -7]])
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
                [12, -7, 4, -7],
                [-1, 12, -8, -7],
            ]
        )
        assert _run(code) == "\x00"


class TestTruncatedInstruction:
    """An instruction running off the end of memory reads zeros for the rest."""

    @staticmethod
    def _once(code: str) -> tuple[str, int]:
        """Run one instruction and return its output and the new pointer."""
        from esolangs.interpreters.register_based.addsubjump import _Machine

        machine = _Machine(code, ScriptedIO())
        machine.step()
        return machine.io.getvalue(), machine.ip

    def test_a_missing_operand_reads_as_zero(self) -> None:
        # One cell: b, c and d are all absent, so each reads 0. a is -1, so
        # the instruction prints *b = memory[0] = -1, a byte of 0xff, and
        # the absent c sends the pointer to 0.
        assert self._once("-1") == ("\xff", 0)

    def test_the_second_operand_is_the_first_that_can_be_present(self) -> None:
        # Two cells: b exists (address 4, an absent cell, so 0) while c and
        # d do not. Printing *b gives NUL rather than the -1 above.
        assert self._once("-1 4") == ("\x00", 0)
        # ... and b really is read, not defaulted: -6 is the constant 1.
        assert self._once("-1 -6") == ("\x01", 0)

    def test_a_present_third_operand_is_the_literal_target(self) -> None:
        # Three cells: c exists and holds -1, a special address, which
        # halts. d is still absent and reads 0, so the += branch runs.
        assert _run("-1 4 -1") == "\x00"


class TestFlags:
    """The flag update mode and the four flags it refreshes."""

    @staticmethod
    def _flag(op: int, flag: int) -> str:
        """Turn the mode on, apply ``op`` to cell 12, then print ``flag``."""
        return memory([[-9, -6, 4, -7], [12, op, 8, -6], [-1, flag, -1, -7]])

    def test_negative_flag_follows_the_sign_of_the_result(self) -> None:
        """``NF`` is set when the result is below zero, and only then."""
        assert _run(self._flag(-6, -4)) == "\x01"  # 0 - 1 = -1
        assert _run(self._flag(-7, -4)) == "\x00"  # 0 - 0 =  0

    def test_zero_flag_follows_the_result_being_zero(self) -> None:
        """``ZF`` is set when the result is exactly zero, and only then."""
        assert _run(self._flag(-7, -3)) == "\x01"  # 0 - 0 =  0
        assert _run(self._flag(-6, -3)) == "\x00"  # 0 - 1 = -1

    def test_carry_and_overflow_stay_zero(self) -> None:
        """Cells are unbounded, so neither flag has anything to report."""
        assert _run(self._flag(-6, -2)) == "\x00"
        assert _run(self._flag(-6, -5)) == "\x00"

    def test_flags_do_not_update_while_the_mode_is_off(self) -> None:
        """The mode starts at zero, so a negative result leaves ``NF`` clear."""
        code = memory([[12, -6, 4, -6], [-1, -4, -1, -7]])
        assert _run(code) == "\x00"


class TestHaltAndErrors:
    def test_jump_off_the_end_halts(self) -> None:
        # The jump target is huge, past the memory.
        code = memory([[12, -6, 1000, -7]])
        assert _run(code) == ""

    def test_malformed_token(self) -> None:
        with pytest.raises(ValueError, match="undefined label 'x'"):
            _run("12 -6 x -7")

    def test_growing_the_memory_zeroes_the_cells_it_skips(self) -> None:
        """A write past the end pads with zeros, and pads exactly far enough."""
        code = memory([[20, -6, 4, -7], [-1, 19, -1, -7]])
        assert _run(code) == "\x00"

    def test_the_largest_allocatable_address_is_the_last_one_that_works(
        self,
    ) -> None:
        """A write halts only once the address is past the memory ceiling."""
        ceiling = 1 << 24
        assert _run(memory([[ceiling - 1, -6, -1, -7]])) == ""

        with pytest.raises(HaltError) as caught:
            _run(memory([[ceiling, -6, -1, -7]]))
        assert str(caught.value) == f"memory address {ceiling} is too large"

    def test_unallocatable_address_halts(self) -> None:
        """Cell values are unbounded; the list holding them is not."""
        with pytest.raises(HaltError, match="too large"):
            _run("9" * 40)

    def test_operands_past_the_decimal_digit_cap_parse(self) -> None:
        """A 5000-digit operand is a number, past CPython's 4300-digit cap."""
        digits = "9" * 5000
        with pytest.raises(HaltError, match=f"^memory address {digits} is too large"):
            _run(digits)


class TestStepMachine:
    def test_flag_views_report_the_mode_and_flags(self) -> None:
        """After 0 - 1 with the mode on, only ``NF`` and ``FUM`` read 1."""
        machine = _machine(TestFlags._flag(-6, -4))  # noqa: SLF001
        machine.step()
        machine.step()
        assert (machine.cf, machine.zf, machine.nf, machine.vf, machine.fum) == (
            0,
            0,
            1,
            0,
            1,
        )

    def test_step_tracks_ip_and_memory(self) -> None:
        from esolangs.interpreters.register_based.addsubjump import _Machine

        machine = _Machine("-1 1 -1 -7", ScriptedIO())
        assert (machine.ip, list(machine.memory)) == (0, [-1, 1, -1, -7])
        machine.step()  # writes *b to I/O and jumps to c, a special address
        assert machine.io.getvalue() == "\x01"
        assert machine.ip == -1
        assert machine.halted
        machine.step()  # stepping a halted machine is a no-op
        assert machine.ip == -1

    def test_snapshot_includes_the_input_cursor(self) -> None:
        from esolangs.interpreters.register_based.addsubjump import _Machine

        machine = _Machine("0 0 0 0", ScriptedIO("one\n"))
        before = machine.snapshot()
        machine.io.input_str()
        assert machine.snapshot() != before

    def test_a_cell_written_to_zero_matches_one_never_written(self) -> None:
        """The sparse store must not distinguish a stored zero from no key."""
        from esolangs.interpreters.register_based.addsubjump import (
            _pack,
            _store,
        )

        state = (_pack([5, 0, 0]), 0, 0, 0, 0, 0, 0)
        # Write a non-zero and then zero it again: back to the start.
        written = _store(_store(state, 1, 7), 1, 0)
        assert written[0] == state[0], "a zeroed cell left a key behind"

        # And a parsed zero is already absent, so the two agree.
        cells, length = _pack([5, 0, 0])
        assert cells == {0: 5}
        assert length == 3

    def test_snapshot_is_independent_of_write_order(self) -> None:
        """Equal memories must snapshot equal however they were reached."""
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


# The wiki's assembler ships an ``IFZ`` macro; this repo's dialect has the
# ``def`` blocks but no macro library, so the two wiki programs below carry
# their own.  ``IFZ X Z P`` is "goto Z if *X == 0, else goto P": it copies
# ``*X`` under flag-update mode so ZF answers the test, then adds or
# subtracts 4 from a goto's own ``c`` cell to pick one of two trampolines
# four cells either side of its resting value.  Each trampoline undoes the
# move before jumping, so the macro is re-entrant -- the hello-world loop
# runs it thirteen times.
_IFZ = """
def IFZ X Z P {
  T2 T2 ? @1
  T2 X ?
  g+2 D4 ? ZF
  g: @0 @0 g+8
  g+2 D4 ?
  @0 @0 Z
  g+2 D4 ? @1
  @0 @0 P
  D4:.data 4
  T2:.data 0
}
"""

_CMP = """
def CMP A B {
  temp temp ? @1
  temp A ?
  temp B ? @1
}
"""

# The wiki's truth machine, verbatim but for two things: the ``FUM`` line
# that arms IFZ's zero test, and cell B, which holds -48 so that the
# comparison sees the digit and not its ASCII byte (this repo's port reads
# bytes; the wiki program assumes a numeric read).  The jump structure --
# ``loop:`` naming itself as ``c``, ``end:`` halting on the literal -1 -- is
# the wiki's and is exactly what the literal semantics buys.
_TRUTH_MACHINE = (
    _IFZ
    + """
FUM @1
A IO
B A
IFZ B end loop
loop: IO A loop
end: IO A -1
A:.data 0
B:.data -48
"""
)

# The wiki's hello world.  ``start+1`` replaces the wiki's literal ``1``
# (the ``FUM`` line shifts every address by one instruction) and ``temp``
# is declared in the program because macro-local labels are private per
# expansion, so CMP's result has to be a shared name.
_HELLO_WORLD = (
    _IFZ
    + _CMP
    + """
FUM @1
start: IO H
start+1 @1
CMP start+1 E
IFZ temp IO start
.data H: 72 101 108 108 111 44 32 119 111 114 108 100 33 E:E
temp:.data 0
"""
)


def _capped(code: str, stdin: str, cap: int) -> tuple[str, bool, int]:
    """Run at most ``cap`` instructions; return output, halted, steps taken."""
    from esolangs.interpreters.register_based.addsubjump import _Machine

    machine = _Machine(code, ScriptedIO(stdin))
    steps = 0
    while not machine.halted and steps < cap:
        machine.step()
        steps += 1
    return machine.io.getvalue(), machine.halted, steps


class TestWikiPrograms:
    """The wiki's own two programs, which only run under ``goto c``."""

    def test_truth_machine_prints_zero_and_halts(self) -> None:
        assert _capped(_TRUTH_MACHINE, "0", 100) == ("0", True, 10)

    def test_truth_machine_loops_on_one(self) -> None:
        # Capped rather than waited out: the loop is one instruction, so a
        # thousand steps is a thousand ones and no halt.
        output, halted, steps = _capped(_TRUTH_MACHINE, "1", 1000)
        assert (output, halted, steps) == ("1" * 991, False, 1000)

    def test_hello_world(self) -> None:
        assert _capped(_HELLO_WORLD, "", 10_000) == ("Hello, world!", True, 144)


def _machine(code: object) -> object:
    from esolangs.interpreters.io import ScriptedIO
    from esolangs.interpreters.register_based.addsubjump import _Machine

    return _Machine(code, ScriptedIO())


class TestContract(EmptyProgramContract, CycleContract):
    """The shared empty-program shape, with this language's data."""

    run = staticmethod(_run)
    machine = staticmethod(_machine)
    halting_program = "-1 1 -1 -7"
    looping_program = "0 0 0 0"
