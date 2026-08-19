"""Tests for the step-and-inspect VM wrapper."""

import pytest

import esolangs
from esolangs.exceptions import UnknownLanguageError
from esolangs.vm import VM


def _run_all(vm: VM) -> str:
    while not vm.halted:
        vm.step()
    return vm.output


class TestProtocol:
    def test_implements_vm_protocol(self) -> None:
        assert isinstance(esolangs.make_vm("brainfuck", "+"), VM)


class TestBrainfuck:
    def test_tape_and_cursor_evolve(self) -> None:
        vm = esolangs.make_vm("brainfuck", "++.")
        assert (vm.ip, vm.memory, vm.output) == (0, [0], "")
        vm.step()
        assert (vm.ip, vm.memory) == (1, [1])
        vm.step()
        assert (vm.ip, vm.memory) == (2, [2])
        vm.step()
        assert vm.output == "\x02"
        assert vm.halted

    def test_run_matches_execute(self) -> None:
        assert _run_all(esolangs.make_vm("brainfuck", "+++[>+++<-]>.")) == esolangs.run(
            "brainfuck", "+++[>+++<-]>."
        )


class TestSbleq:
    def test_oisc_cells_and_ip(self) -> None:
        vm = esolangs.make_vm("S*bleq", "-3 11 3")
        assert (vm.ip, vm.memory, vm.stack) == (0, [-3, 11, 3], [])
        vm.step()
        assert (vm.ip, vm.halted, vm.output) == (3, True, "\x00")


class TestDimensional:
    def test_byte_value_exposed(self) -> None:
        vm = esolangs.make_vm("Dimensional", "++.")
        assert (vm.ip, vm.memory, vm.stack) == (0, [0], [])
        vm.step()
        assert vm.memory == [1]
        vm.step()
        assert vm.memory == [2]
        vm.step()
        assert vm.output == "\x02"


class TestGrapheme:
    def test_stack_exposed(self) -> None:
        vm = esolangs.make_vm("Grapheme", "FAFY")
        assert (vm.ip, vm.memory, vm.stack) == (0, [], [])
        vm.step()  # F starts int mode
        vm.step()  # A accumulates
        vm.step()  # F ends int mode, pushes 10
        assert vm.stack == [10]
        vm.step()  # Y prints
        assert vm.output == "10"
        assert vm.halted
        assert vm.ip == len("FAFY")  # frames are gone once halted
        assert vm.memory == []

    def test_rejects_non_uppercase(self) -> None:
        with pytest.raises(ValueError, match="uppercase"):
            esolangs.make_vm("Grapheme", "a")


class TestQoibl:
    def test_expression_cursor(self) -> None:
        vm = esolangs.make_vm("Qoibl", "et")
        assert vm.ip == 0
        assert not vm.halted
        assert vm.memory == [0] * 256
        assert vm.stack == []
        with pytest.raises(EOFError):
            vm.step()


class TestEval:
    def test_active_stack_exposed(self) -> None:
        vm = esolangs.make_vm("Eval", "0^")
        vm.step()
        assert vm.stack == [0]
        vm.step()
        assert vm.stack == [0, 0]


class TestModulous:
    def test_token_cursor_and_stack(self) -> None:
        vm = esolangs.make_vm("Modulous", "[PSH INT 5][PRT INT]")
        vm.step()
        assert (vm.ip, vm.stack) == (1, [5])
        assert vm.memory == []
        vm.step()
        assert vm.output == "5"
        assert vm.halted


class TestTemporaryStack:
    def test_word_pointer_and_stack(self) -> None:
        vm = esolangs.make_vm("The Temporary Stack", "v5 +")
        vm.step()
        assert (vm.ip, vm.stack) == (1, [5])
        assert vm.memory == []
        vm.step()
        assert vm.stack == [5, 5]


class TestLaserFuck:
    def test_ip_is_position_and_heading(self) -> None:
        # heading is fixed to 0 (up), so the laser at (2,4) moves up
        vm = esolangs.make_vm("LaserFuck", "\u00ff   x\n    +\n    o")
        assert vm.ip == (2, 4, 0)  # the laser's start position and heading
        vm.step()
        assert vm.ip == (1, 4, 0)  # moved up onto the '+'
        assert vm.memory == [1]
        vm.step()
        assert vm.ip == (0, 4, 0)  # moved up onto the 'x', died
        assert vm.halted
        assert vm.output == "\x01"
        assert vm.stack == []
        vm.step()  # stepping a halted VM is a no-op

    def test_dump_output_matches_interpreter(self) -> None:
        from esolangs.interpreters.grid_based.laserfuck import run as lf_run
        from esolangs.interpreters.io import ScriptedIO

        program = "\u00ff   x\n    +\n    o"
        io_obj = ScriptedIO()
        lf_run(program.splitlines(), io_obj, heading=0)
        vm = esolangs.make_vm("LaserFuck", program)
        assert _run_all(vm) == io_obj.getvalue()


class TestPointBreak:
    def test_statement_cursor_and_variables(self) -> None:
        vm = esolangs.make_vm(
            "Point Break",
            "LET x:=2+3\nPOINT loop\nIF x BREAK loop\nEND loop",
        )
        assert vm.ip == 0
        assert vm.memory == []
        vm.step()
        assert vm.ip == 1
        assert vm.memory == [5]
        vm.step()
        assert vm.ip == 2
        assert vm.stack == []
        vm.step()  # IF x BREAK loop fires (x=5) and exits past the END
        assert vm.halted
        assert vm.output == ""


class TestArrowQueue:
    def test_ip_is_position_and_heading(self) -> None:
        vm = esolangs.make_vm("ArrowQueue", "~+*")
        assert vm.ip == (0, 0, 0)
        vm.step()
        assert vm.ip == (1, 0, 0)
        assert vm.stack == [0]
        vm.step()  # + pops the queued direction (right) and keeps going
        assert vm.ip == (2, 0, 0)
        assert vm.stack == []
        vm.step()  # * turns down off the single row and halts
        assert vm.halted
        assert vm.memory == []
        vm.step()  # stepping a halted VM is a no-op


class Test123:
    def test_data_byte_and_cursor(self) -> None:
        vm = esolangs.make_vm("123", "121")
        assert vm.ip == 0
        assert vm.memory == [0]
        vm.step()  # 1 flips the bit at the pointer
        assert vm.ip == 1
        assert vm.memory == [128]
        vm.step()  # 2 at a data position moves the pointer right
        assert vm.ip == 2
        assert vm.memory == [128]
        vm.step()  # 1 flips bit 7 back; the cursor runs off the program
        assert vm.ip == 3
        assert vm.memory == [0]
        vm.step()  # the loop-or-halt check: pointer below 0 halts the run
        assert vm.halted
        assert vm.stack == []
        vm.step()  # stepping a halted VM is a no-op


class TestAPainterAnt:
    def test_ip_cursor_and_grid_memory(self) -> None:
        vm = esolangs.make_vm("A Painter Ant", "Pnn")
        assert vm.ip == 0
        vm.step()  # P whites the origin
        assert vm.ip == 1
        assert vm.memory == [1]
        vm.step()  # n moves north
        assert vm.ip == 2
        vm.step()  # n moves north
        assert vm.ip == 0  # the implicit loop wraps the cursor
        assert vm.halted is False  # the language never halts
        assert vm.stack == []


class TestTwoDFish:
    def test_ip_position_direction_and_accumulator(self) -> None:
        vm = esolangs.make_vm("2dFish", "/iio@")
        assert vm.ip == (1, 0, 0)  # after the initial direction step (heading right)
        vm.step()  # i increments the accumulator
        assert vm.memory == [1]
        assert vm.ip == (2, 0, 0)
        vm.step()  # i increments again
        assert vm.memory == [2]
        vm.step()  # o prints 2
        assert vm.output == "2"
        vm.step()  # @ halts
        assert vm.halted
        assert vm.stack == []


class TestDotlang:
    def test_ip_dot_position_and_value_stack(self) -> None:
        vm = esolangs.make_vm("Dotlang", "•#42#")
        assert vm.ip == (0, 0, 1)  # the starting dot, heading right
        vm.step()  # the • is a no-op and the dot steps right
        assert vm.ip == (0, 1, 1)
        vm.step()  # #42 stores 42 on the dot and steps past the literal
        assert vm.stack == [42]
        assert vm.ip == (0, 4, 1)
        vm.step()  # the trailing # prints 42, then the dot steps off the row
        assert vm.output == "42"
        assert vm.halted
        assert vm.ip is None  # the dot has been consumed
        assert vm.memory == []


class TestClockwise:
    def test_ip_position_heading_and_accumulator(self) -> None:
        vm = esolangs.make_vm("Clockwise", "+;S;S;S;S;S;+;R\nR             R")
        assert vm.ip == (0, 0, 0)  # the pointer starts at the origin heading right
        assert vm.memory == [0]
        vm.step()  # + at the origin increments the accumulator
        assert vm.ip == (1, 0, 0)
        assert vm.memory == [1]
        vm.step()  # ; queues a parity bit
        assert vm.ip == (2, 0, 0)
        assert vm.output == ""
        assert vm.stack == []

    def test_stepping_a_halted_vm_is_a_noop(self) -> None:
        vm = esolangs.make_vm("Clockwise", "+;S;S;S;S;S;+;R\nR             R")
        assert _run_all(vm) == "A"
        vm.step()  # no-op
        assert vm.output == "A"


class TestDig:
    def test_ip_mole_position_and_value(self) -> None:
        vm = esolangs.make_vm("Dig", ">$5:\n 2 ")
        assert vm.ip == (0, 0, 1)  # facing right
        assert vm.memory == [0]
        vm.step()  # > keeps facing right
        assert vm.ip == (0, 1, 1)
        vm.step()  # $ digs (reads the adjacent 5)
        vm.step()  # 5 loads the mole
        assert vm.memory == [5]
        assert vm.stack == []

    def test_stepping_a_halted_vm_is_a_noop(self) -> None:
        vm = esolangs.make_vm("Dig", ">$5:\n 2 ")
        assert _run_all(vm) == "5"
        vm.step()  # no-op
        assert vm.output == "5"


class TestWii2d:
    def test_ip_position_velocity_and_accumulator(self) -> None:
        vm = esolangs.make_vm("WII2D", ">~.\n!")
        assert vm.ip == (0, 0, 0)  # starts above the ! heading north
        assert vm.memory == [0]
        vm.step()  # > sets the heading east
        assert vm.ip == (0, 1, 3)
        vm.step()  # ~ prints the accumulator
        assert vm.output == "\x00"
        vm.step()  # . halts
        assert vm.halted
        assert vm.stack == []

    def test_stepping_a_halted_vm_is_a_noop(self) -> None:
        vm = esolangs.make_vm("WII2D", ">~.\n!")
        assert _run_all(vm) == "\x00"
        vm.step()  # no-op
        assert vm.output == "\x00"


class TestForth:
    def test_stack_and_active_frame_cursor(self) -> None:
        vm = esolangs.make_vm("Forþ", "65.")
        assert vm.ip == 0
        assert vm.stack == []
        vm.step()  # 6 pushes
        assert (vm.ip, vm.stack) == (1, [6])
        vm.step()  # 5 pushes
        assert vm.stack == [6, 5]
        vm.step()  # . pops and prints the low byte
        assert vm.output == "\x05"
        vm.step()  # finalizing the finished frame halts the machine
        assert vm.halted
        assert vm.ip == len("65.")  # frames are gone once halted
        assert vm.memory == []


class TestAddSubJump:
    def test_memory_and_instruction_pointer(self) -> None:
        vm = esolangs.make_vm("AddSubJump", "-1 1 0 -7")
        assert (vm.ip, vm.memory, vm.stack) == (0, [-1, 1, 0, -7], [])
        vm.step()  # write to -1 prints *b = cell 1
        assert vm.output == "\x01"
        assert vm.halted
        assert vm.ip == -1  # the jump off the special address halts
        vm.step()  # stepping a halted VM is a no-op


class TestBitdeque:
    def test_cursor_deque_and_register(self) -> None:
        vm = esolangs.make_vm("Bitdeque", "PUSH INVERT")
        assert (vm.ip, vm.memory, vm.stack) == (0, [], [0])
        vm.step()  # PUSH appends the register
        assert (vm.ip, vm.memory) == (1, [0])
        vm.step()  # INVERT flips the register, then the run renders
        assert vm.stack == [1]
        assert vm.halted
        assert vm.output == "0\n"
        vm.step()  # stepping a halted VM is a no-op
        assert vm.output == "0\n"


class TestTaglate:
    def test_queue_and_cursor(self) -> None:
        vm = esolangs.make_vm("Taglate", "abc\ni")
        assert (vm.ip, vm.memory, vm.stack) == (0, [97, 98, 99], [])
        vm.step()  # i pops the front and prints it
        assert vm.output == "a"
        assert vm.halted


class TestMinifuck:
    def test_tape_and_cursor(self) -> None:
        vm = esolangs.make_vm("Minifuck", ".")
        assert (vm.ip, vm.memory, vm.stack) == (0, [0] * 8, [])
        vm.step()  # . advances, flips the second cell, and prints the byte
        assert vm.output == "@"
        assert vm.halted
        assert vm.ip == 1


class TestBrainIf:
    def test_cells_and_cursor(self) -> None:
        vm = esolangs.make_vm("BrainIf", "if 0 output")
        assert (vm.ip, vm.memory, vm.stack) == (0, [0], [])
        vm.step()  # cell 0 is 0, so output prints it
        assert vm.output == "\x00"
        assert vm.halted


class TestROTFuck:
    def test_tape_and_cursor(self) -> None:
        vm = esolangs.make_vm("ROTfuck", ".")
        assert (vm.ip, vm.memory, vm.stack) == (0, [0], [])
        vm.step()  # . prints the current cell
        assert vm.output == "\x00"
        assert vm.halted


class TestCirclefuck:
    def test_cells_and_cursor(self) -> None:
        vm = esolangs.make_vm("Circlefuck", "+.@")
        assert (vm.ip, vm.memory) == (0, [43, 46, 64])
        vm.step()  # + sets the cell
        assert vm.memory == [44, 46, 64]
        vm.step()  # . prints it
        assert vm.output == ","
        vm.step()  # @ halts
        assert vm.halted
        assert vm.stack == []


class TestBFStack:
    def test_stack_and_cursor(self) -> None:
        vm = esolangs.make_vm("BFStack", ">+.")
        assert (vm.ip, vm.memory, vm.stack) == (0, [], [])
        vm.step()  # > pushes 0
        assert vm.stack == [0]
        vm.step()  # + increments the top
        assert vm.stack == [1]
        vm.step()  # . prints it
        assert vm.output == "\x01"
        assert vm.halted


class TestRunUntilHaltOrCycle:
    def test_halting_run_returns_true(self) -> None:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.register_based.point_break import _Machine
        from esolangs.vm import run_until_halt_or_cycle

        machine = _Machine("LET zero:=0", ScriptedIO())
        assert run_until_halt_or_cycle(machine) is True

    def test_looping_run_is_detected_as_a_cycle(self) -> None:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.register_based.point_break import _Machine
        from esolangs.vm import run_until_halt_or_cycle

        machine = _Machine(
            "LET zero:=0\nPOINT loop\nIF zero BREAK loop\nEND loop",
            ScriptedIO(),
        )
        assert run_until_halt_or_cycle(machine) is False

    def test_input_cursor_is_part_of_the_snapshot(self) -> None:
        """A loop that reads fresh input each pass is not a false cycle.

        The program re-reads ``n`` on every pass, so the cursor, variables,
        and frames repeat while the input cursor advances; were the input
        position absent from the snapshot, this would be misreported as a
        cycle before the program reached its nonzero input and halted.
        """
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.register_based.point_break import _Machine
        from esolangs.vm import run_until_halt_or_cycle

        program = "POINT loop\nLET n:=?\nIF n BREAK loop\nEND loop"
        machine = _Machine(program, ScriptedIO("0\n0\n1"))
        assert run_until_halt_or_cycle(machine) is True

    def test_snapshot_with_plain_io(self) -> None:
        """A source with no cursor reports position 0 in the snapshot."""
        from esolangs.interpreters.io import IO
        from esolangs.interpreters.register_based.point_break import _Machine

        machine = _Machine("LET zero:=0", IO())
        assert machine.snapshot() == (0, (), (), 0)


class TestFactory:
    def test_unknown_language_raises(self) -> None:
        from esolangs.vm import _VM_ADAPTERS

        with pytest.raises(UnknownLanguageError):
            esolangs.make_vm("NoSuchLanguage", "+")
        # a registry language that still lacks a step-capable interpreter
        not_step_capable = next(
            lang for lang in esolangs.list_languages() if lang not in _VM_ADAPTERS
        )
        with pytest.raises(UnknownLanguageError):
            esolangs.make_vm(not_step_capable, "+")


@pytest.mark.parametrize(
    ("language", "program"),
    [
        ("brainfuck", "+++[>+++<-]>."),
        ("S*bleq", "-3 11 3"),
        ("Dimensional", "+.+.+."),
        ("Grapheme", "FAFY"),
        ("Qoibl", "we y we yyeeee we\ntt qe y qe tt"),
        ("Eval", "0+."),
        ("Modulous", "[PSH INT 5][DUP][PRT INT]"),
        ("The Temporary Stack", "v5 *AB"),
        ("Point Break", "LET zero:=0"),
        ("ArrowQueue", "~*+"),
        ("123", "3231"),
        ("Clockwise", "+;S;S;S;S;S;+;R\nR             R"),
        ("Dig", ">$5:\n 2 "),
        ("WII2D", ">~.\n!"),
        ("Forþ", "65."),
        ("AddSubJump", "-1 1 0 -7"),
        ("Bitdeque", "PUSH INVERT"),
        ("BrainIf", "if 0 output"),
        ("Minifuck", "."),
        ("Taglate", "abc\ni"),
        ("ROTfuck", "."),
        ("Circlefuck", "+.@"),
        ("BFStack", ">+."),
    ],
)
def test_vm_output_matches_run(language: str, program: str) -> None:
    """Stepping a VM to completion matches running the interpreter directly."""
    try:
        expected = esolangs.run(language, program)
    except EOFError:
        pytest.skip(f"{language} needs input")
    vm = esolangs.make_vm(language, program)
    assert _run_all(vm) == expected
