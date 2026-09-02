"""Tests for the step-and-inspect VM wrapper."""

import contextlib

import pytest

import esolangs
from esolangs.exceptions import UnknownLanguageError
from esolangs.vm import VM

# These four programs are the sweep's samples for their languages, so they
# live in the table rather than being spelled twice.
from .samples import (
    CIRCUIT_PRIME_TESTER,
    DUMPS_ON_THE_POST_HALT_STEP,
    FLOWCHART_CAT,
    FLOWCHART_TRUTH_MACHINE,
    SAMPLES,
    STREETCODE,
    STREETCODE_GAP,
    bits_of,
)


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
        assert (vm.ip, vm.memory, vm.stack) == ((0,), [], [])
        vm.step()  # F starts int mode
        vm.step()  # A accumulates
        vm.step()  # F ends int mode, pushes 10
        assert vm.stack == [10]
        vm.step()  # Y prints
        assert vm.output == "10"
        assert vm.halted
        assert vm.ip == (len("FAFY"),)  # frames are gone once halted
        assert vm.memory == []

    def test_rejects_non_uppercase(self) -> None:
        with pytest.raises(ValueError, match="uppercase"):
            esolangs.make_vm("Grapheme", "a")

    def test_ip_exposes_the_call_stack(self) -> None:
        # FAF pushes 10, EKE pushes the string "K"; G calls it as a nested
        # frame (K dups the shared stack's top), so ip grows to (caller pc,
        # callee pc) while that frame is active instead of folding it into
        # one cursor.
        vm = esolangs.make_vm("Grapheme", "FAFEKEG")
        for _ in range(7):
            vm.step()
        assert vm.ip == (7, 0)  # caller's pc past G, callee's pc at its start
        assert vm.stack == [10]
        vm.step()  # the callee's K command runs, then the frame finishes
        assert vm.halted
        assert vm.ip == (7,)  # the callee frame is gone once it returns
        assert vm.stack == [10, 10]

    def test_caller_resumes_after_the_callee_returns(self) -> None:
        # Y after G still has to run once the callee pops, proving the
        # halted-``ip`` sentinel is the top-level frame's own end position,
        # not an artifact of the callee finishing on the caller's last pc.
        vm = esolangs.make_vm("Grapheme", "FAFEKEGY")
        for _ in range(9):
            vm.step()
        assert vm.halted
        assert vm.output == "10"  # Y printed the duplicated int 10
        assert vm.ip == (len("FAFEKEGY"),)


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


class TestLaserFuck:
    def test_ip_is_position_and_heading(self) -> None:
        # the adapter's generator is seeded so its first draw is 0 (up), so
        # the laser at (2,4) moves up
        vm = esolangs.make_vm("LaserFuck", "\u00ff   x\n    +\n    o")
        assert vm.ip == (2, 4, 0)  # the laser's start position and heading
        vm.step()
        assert vm.ip == (1, 4, 0)  # moved up onto the '+'
        assert vm.memory == [1]
        vm.step()
        assert vm.ip == (0, 4, 0)  # moved up onto the 'x', died
        assert vm.halted
        assert vm.output == ""  # the tape is not dumped until the next step
        assert vm.stack == []
        vm.step()  # the post-halt step dumps it, as run's own last step does
        assert vm.output == "\x01"
        vm.step()  # and the dump happens once, not once per step past the halt
        assert vm.output == "\x01"

    def test_dump_output_matches_interpreter(self) -> None:
        from esolangs.interpreters.grid_based.laserfuck import run as lf_run
        from esolangs.interpreters.io import ScriptedIO

        program = "\u00ff   x\n    +\n    o"
        io_obj = ScriptedIO()
        lf_run(program.splitlines(), io_obj, heading=0)
        vm = esolangs.make_vm("LaserFuck", program)
        _run_all(vm)
        vm.step()  # the dump, which run performs as its own last step
        assert vm.output == io_obj.getvalue()


class TestCOD:
    def test_ip_memory_and_output(self) -> None:
        # ')' increments twice, then '---' on the right edge prints and
        # removes the cod; ip is the single cod's (row, col, heading, value).
        vm = esolangs.make_vm("COD", "~~~~~\n~>))---")
        assert vm.ip == (1, 1, 2, 0)  # heading 2 == E
        assert vm.memory == [0]
        assert vm.stack == []
        vm.step()
        assert vm.ip == (1, 2, 2, 1)
        assert vm.memory == [1]
        vm.step()
        assert vm.ip == (1, 3, 2, 2)
        vm.step()
        assert vm.halted
        assert vm.output == "2"
        vm.step()  # stepping a halted VM is a no-op

    def test_random_junction_is_deterministic(self) -> None:
        # forward blocked, East and West both open: the adapter's generator
        # is seeded so the draw lands on 'E' every run, unlike the
        # interpreter's default secrets-backed draw.
        code = "\n".join(["~~~~~~~", "~     ~", "~ ~ ~ ~", "~~~>~~~"])
        vm = esolangs.make_vm("COD", code)
        vm.step()  # (3,3,N) -> (2,3,N)
        vm.step()  # (2,3,N) -> (1,3,N): enters the junction cell
        vm.step()  # forward (N) blocked: resolves to 'E'
        assert vm.ip == (1, 4, 2, 0)  # heading 2 == E


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
        assert vm.ip == (0, 1, 0)
        assert vm.stack == [0]
        vm.step()  # + pops the queued direction (right) and keeps going
        assert vm.ip == (0, 2, 0)
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


class TestClockwise:
    def test_ip_position_heading_and_accumulator(self) -> None:
        vm = esolangs.make_vm("Clockwise", "+;S;S;S;S;S;+;R\nR             R")
        assert vm.ip == (0, 0, 0)  # the pointer starts at the origin heading right
        assert vm.memory == [0]
        vm.step()  # + at the origin increments the accumulator
        assert vm.ip == (0, 1, 0)
        assert vm.memory == [1]
        vm.step()  # ; queues a parity bit
        assert vm.ip == (0, 2, 0)
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


class TestStreetcode:
    def test_car_position_heading_and_cells(self) -> None:
        vm = esolangs.make_vm("Streetcode", STREETCODE)
        assert vm.ip == (2, 1, 1)  # on the C, heading east
        assert vm.memory == []
        vm.step()  # drives onto the first ^
        assert vm.ip == (2, 2, 1)
        vm.step()  # ^ increments the cell under CP
        assert vm.memory == [1]
        vm.step()  # ^ again
        assert vm.memory == [2]
        vm.step()  # O prints it
        assert vm.output == "\x02"
        assert vm.stack == []

    def test_memory_fills_the_gaps_between_written_cells(self) -> None:
        """The tape is a sparse dict, so a skipped cell still reads as zero.

        ``=`` moves CP right without writing, so incrementing either side of
        two of them leaves cell 1 untouched between two written cells.
        """
        vm = esolangs.make_vm("Streetcode", STREETCODE_GAP)
        assert _run_all(vm) == ""
        assert vm.memory == [1, 0, 1]

    def test_run_matches_execute(self) -> None:
        assert _run_all(esolangs.make_vm("Streetcode", STREETCODE)) == esolangs.run(
            "Streetcode", STREETCODE
        )

    def test_stepping_a_halted_vm_is_a_noop(self) -> None:
        vm = esolangs.make_vm("Streetcode", STREETCODE)
        assert _run_all(vm) == "\x02"
        vm.step()  # no-op
        assert vm.output == "\x02"


class TestFlowchart:
    def test_live_pointer_position_and_heading(self) -> None:
        vm = esolangs.make_vm("Flowchart", FLOWCHART_TRUTH_MACHINE, "0\n")
        assert vm.ip == (0, 10, 0, 1)  # on the opening ( ), heading east
        assert vm.stack == []
        vm.step()
        assert vm.ip == (0, 11, 0, 1)  # moved on, still travelling east

    def test_ip_is_none_once_every_pointer_has_stopped(self) -> None:
        """``ip`` reports the first live pointer, so a finished run has none."""
        vm = esolangs.make_vm("Flowchart", FLOWCHART_TRUTH_MACHINE, "0\n")
        assert _run_all(vm) == "0"
        assert vm.ip is None

    def test_the_deque_holds_what_the_pointers_read(self) -> None:
        """The cat reads its bits onto the shared tape before printing them."""
        vm = esolangs.make_vm("Flowchart", FLOWCHART_CAT, "1\n")
        while not vm.halted and not vm.memory:
            vm.step()
        assert vm.memory == [1]

    def test_run_matches_execute(self) -> None:
        vm = esolangs.make_vm("Flowchart", FLOWCHART_TRUTH_MACHINE, "0\n")
        assert _run_all(vm) == esolangs.run("Flowchart", FLOWCHART_TRUTH_MACHINE, "0\n")

    def test_stepping_a_halted_vm_is_a_noop(self) -> None:
        vm = esolangs.make_vm("Flowchart", FLOWCHART_TRUTH_MACHINE, "0\n")
        assert _run_all(vm) == "0"
        vm.step()  # no-op
        assert vm.output == "0"


class TestCircuitDiagram:
    def test_wire_values_are_per_generation_events(self) -> None:
        vm = esolangs.make_vm("Circuit Diagram", CIRCUIT_PRIME_TESTER, bits_of(3))
        assert vm.ip is None  # nothing moves through a circuit
        assert vm.stack == []
        vm.step()
        assert vm.memory == [0, 0, 1, 1]  # the input port, most significant first
        assert _run_all(vm) == "1"

    def test_stepping_detects_exactly_the_primes(self) -> None:
        """The page's worked example, replayed a generation at a time."""
        detected = {
            n
            for n in range(16)
            if _run_all(
                esolangs.make_vm("Circuit Diagram", CIRCUIT_PRIME_TESTER, bits_of(n))
            )
            == "1"
        }
        assert detected == {2, 3, 5, 7, 11, 13}

    def test_run_matches_execute(self) -> None:
        vm = esolangs.make_vm("Circuit Diagram", CIRCUIT_PRIME_TESTER, bits_of(7))
        assert _run_all(vm) == esolangs.run(
            "Circuit Diagram", CIRCUIT_PRIME_TESTER, bits_of(7)
        )

    def test_stepping_a_halted_vm_is_a_noop(self) -> None:
        vm = esolangs.make_vm("Circuit Diagram", CIRCUIT_PRIME_TESTER, bits_of(7))
        assert _run_all(vm) == "1"
        vm.step()  # no-op
        assert vm.output == "1"


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
        assert vm.ip == (0,)
        assert vm.stack == []
        vm.step()  # 6 pushes
        assert (vm.ip, vm.stack) == ((1,), [6])
        vm.step()  # 5 pushes
        assert vm.stack == [6, 5]
        vm.step()  # . pops and prints the low byte
        assert vm.output == "\x05"
        vm.step()  # finalizing the finished frame halts the machine
        assert vm.halted
        assert vm.ip == (len("65."),)  # frames are gone once halted
        assert vm.memory == []

    def test_ip_exposes_the_call_stack(self) -> None:
        # '1{:}1;' stores the scope ':' under key 1, then calls it; ip
        # grows to (caller pc, callee pc) while the scope is active instead
        # of folding it into one cursor.
        vm = esolangs.make_vm("Forþ", "1{:}1;")
        for _ in range(4):
            vm.step()
        assert vm.ip == (6, 0)  # caller's pc past ';', callee's pc at start
        assert vm.stack == [1]
        vm.step()  # the callee's ':' command runs (dup)
        assert vm.ip == (6, 1)
        assert vm.stack == [1, 1]
        vm.step()  # finalizing the finished callee frame halts the machine
        assert vm.halted
        assert vm.ip == (6,)  # the callee frame is gone once it returns


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
        vm.step()  # INVERT flips the register
        assert vm.stack == [1]
        assert vm.halted
        assert vm.output == ""  # the deque is not rendered until the next step
        vm.step()  # the post-halt step renders it, as run's own last step does
        assert vm.output == "0"
        vm.step()  # and rendering happens once, not once per step past the halt
        assert vm.output == "0"


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


class TestDecleq:
    def test_memory_and_pointer(self) -> None:
        vm = esolangs.make_vm("Decleq", "-2 5 9 9 9 65 0 0")
        assert (vm.ip, vm.memory, vm.stack) == (0, [-2, 5, 9, 9, 9, 65, 0, 0], [])
        vm.step()  # a=-2 outputs memory[5]
        assert vm.output == "A"
        assert vm.ip == 3
        vm.step()  # the countdown then jumps off the end of memory
        assert vm.halted
        assert vm.ip == 65


class TestSixFive:
    def test_tape_and_cursor(self) -> None:
        vm = esolangs.make_vm("6-5", "55A")
        assert (vm.ip, vm.memory, vm.stack) == (0, [0], [])
        vm.step()  # 5 adds 5 to the cell
        assert vm.memory == [5]
        vm.step()  # 5 adds 5 more
        assert vm.memory == [10]
        vm.step()  # A prints the cell
        assert vm.output == "\n"
        assert vm.halted


class TestBack:
    def test_beam_tape_and_direction(self) -> None:
        vm = esolangs.make_vm("Back", "-*")
        assert (vm.ip, vm.memory, vm.stack) == ((0, 0, 0, 1), [0], [])
        vm.step()  # - flips the current bit
        assert vm.memory == [1]
        assert vm.ip == (0, 1, 0, 1)
        vm.step()  # * prints the tape and halts
        assert vm.output == "1"
        assert vm.halted

    def test_halt_prints_tape(self) -> None:
        vm = esolangs.make_vm("Back", ">--*")
        _run_all(vm)
        assert vm.output == "0 0"


class TestBIO:
    def test_registers_and_loop_stack(self) -> None:
        vm = esolangs.make_vm("BIO", "0ox;0ix{1ox;};1ix;")
        assert (vm.ip, vm.memory, vm.stack) == (0, [0, 0, 0], [])
        vm.step()  # 0ox sets x to 1
        assert vm.memory == [1, 0, 0]
        vm.step()  # 0ix sees x nonzero and pushes the loop
        assert vm.stack == [1]
        vm.step()  # 1ox decrements x
        assert vm.memory == [0, 0, 0]
        vm.step()  # } pops the loop and lands back on the 0ix
        assert vm.stack == []
        assert vm.ip == 1
        vm.step()  # 0ix sees x zero and skips the body
        assert vm.ip == 4
        vm.step()  # 1ix outputs the zero x
        assert vm.output == "\x00"
        assert vm.halted


class TestNoComment:
    def test_tape_stack_and_cursor(self) -> None:
        vm = esolangs.make_vm("NoComment", "ciio")
        assert (vm.ip, vm.memory[0], vm.stack) == (0, 0, [])
        vm.step()  # c clears the cell
        vm.step()  # i increments
        vm.step()  # i increments
        vm.step()  # o prints the cell
        assert vm.output == "\x02"
        assert vm.halted

    def test_stack_is_exposed(self) -> None:
        vm = esolangs.make_vm("NoComment", "cinf")
        vm.step()  # c clears
        vm.step()  # i increments to 1
        vm.step()  # n pushes the cell
        assert vm.stack == [1]
        vm.step()  # f pops into the cell
        assert vm.stack == []
        assert vm.halted


class TestThreeDBrainfuck:
    def test_pointer_and_cells(self) -> None:
        vm = esolangs.make_vm("3D Brainfuck", "+.")
        assert (vm.ip, vm.memory, vm.stack) == ((0, 0, 0, 1, 0, 0), [], [])
        vm.step()  # + sets the origin cell to 1
        assert vm.memory == [1]
        vm.step()  # . prints it
        assert vm.output == "\x01"
        assert vm.halted


class TestFactor:
    def test_decoded_machine(self) -> None:
        vm = esolangs.make_vm("Factor", "15")
        assert (vm.ip, vm.memory, vm.stack) == (0, [0], [])
        vm.step()  # + increments the cell
        assert vm.memory == [1]
        vm.step()  # . prints it
        assert vm.output == "\x01"
        assert vm.halted


class TestBasicfuck:
    def test_tape_and_cursor(self) -> None:
        prog = "#basicfuck t=1 r=0~255 o=nearest\n#allocate a\n"
        vm = esolangs.make_vm("Basicfuck", prog + "a += 65;\nwrite <- a ;")
        assert (vm.ip, vm.memory, vm.stack) == (0, [0], [])
        vm.step()  # a += 65
        assert vm.memory == [65]
        vm.step()  # write prints a
        assert vm.output == "A"
        vm.step()  # the finished frame is finalized
        assert vm.halted

    def test_while_loop_restarts_the_body(self) -> None:
        prog = "#basicfuck t=unbounded r=0~255 o=wrap\n#allocate a\n"
        vm = esolangs.make_vm("Basicfuck", prog + "a += 3;\nwhile (a) { a -= 1; }")
        for _ in range(8):
            vm.step()
        assert vm.memory == [0]
        assert vm.halted


class TestPainfuck:
    def test_tape_and_cursor(self) -> None:
        vm = esolangs.make_vm("Painfuck", "pp")
        assert (vm.ip, vm.memory, vm.stack) == (0, [0], [])
        vm.step()  # p adds 2
        assert vm.memory == [2]
        vm.step()  # e halts
        assert vm.halted


class TestBitTilde:
    def test_pool_and_cursor(self) -> None:
        vm = esolangs.make_vm("bit~", "~(")
        assert (vm.ip, vm.memory, vm.stack) == (0, [0] * 8, [])
        vm.step()  # ~ flips the MSB
        assert vm.memory[0] == 1
        vm.step()  # ( prints the byte
        assert vm.output == "\x80"
        assert vm.halted


class TestCollatzMultiverse:
    def test_line_pointer_and_registers(self) -> None:
        vm = esolangs.make_vm(
            "Collatz Multiverse", "x = negativeOne x + negativeOne, DO PRINT."
        )
        assert (vm.ip, vm.memory, vm.stack) == (1, [-1], [])
        vm.step()  # x = 0*(-1)+(-1) = -1, printed as a byte
        assert vm.output == "\xff"
        assert vm.halted


class TestPolynomial:
    def test_register_and_cursor(self) -> None:
        vm = esolangs.make_vm("Polynomial", "f(x) = x^2+4")
        assert (vm.ip, vm.memory, vm.stack) == (0, [0], [])
        vm.step()  # the [0, 1] instruction prints the register
        assert vm.output == "\x00"
        assert vm.halted


class TestRAM0:
    def test_registers_and_cursor(self) -> None:
        vm = esolangs.make_vm("RAM0", "ZA")
        assert (vm.ip, vm.memory, vm.stack) == (0, [0, 0], [])
        vm.step()  # Z zeroes z
        assert vm.ip == 1
        vm.step()  # A increments z; the cursor runs off the end
        assert (vm.ip, vm.memory, vm.halted) == (2, [1, 0], True)
        assert vm.output == ""  # the dump happens on the next step
        vm.step()
        assert vm.output == "z: 1\nn: 0\nram: {}"


class TestMinskySwap:
    def test_registers_and_cursor(self) -> None:
        vm = esolangs.make_vm("Minsky Swap", "+")
        assert (vm.ip, vm.memory, vm.stack) == (0, [0, 0], [])
        vm.step()  # + increments the active register; the cursor runs off
        assert (vm.ip, vm.memory, vm.halted) == (1, [1, 0], True)
        assert vm.output == ""  # the dump happens on the next step
        vm.step()
        assert vm.output == "1 0"


class TestHomeRow:
    def test_grid_and_cursor(self) -> None:
        vm = esolangs.make_vm("Home Row", "ak;")
        assert (vm.ip, vm.memory[:3], vm.stack) == (0, [0, 0, 0], [])
        vm.step()  # a increments the current cell
        assert (vm.ip, vm.memory[:3]) == (1, [1, 0, 0])
        vm.step()  # k prints the cell and resets it; the cursor lands on ';'
        assert vm.memory[:3] == [0, 0, 0]
        assert vm.output == "\x01"
        assert vm.halted


class TestUnsquare:
    def test_stack_accumulator_and_cursor(self) -> None:
        vm = esolangs.make_vm("Unsquare", "Io")
        assert (vm.ip, vm.memory, vm.stack) == (0, [0], [])
        vm.step()  # I pushes 1
        assert (vm.ip, vm.stack) == (1, [1])
        vm.step()  # o prints the top of stack without popping
        assert vm.halted
        assert vm.output == "\x01"
        assert vm.stack == [1]


class TestPctSquaredMinusOne:
    def test_accumulator_and_cursor(self) -> None:
        vm = esolangs.make_vm("%^2^-1", "ie")
        assert (vm.ip, vm.memory, vm.stack) == (0, [0], [])
        vm.step()  # i subtracts 3 from the accumulator
        assert (vm.ip, vm.memory) == (1, [-3])
        vm.step()  # e prints the low byte of the accumulator
        assert vm.halted
        assert vm.output == "\xfd"


class TestSuffolk:
    def test_tape_and_cursor(self) -> None:
        vm = esolangs.make_vm("Suffolk", "!" * 66 + "<.")
        assert (vm.ip, vm.memory, vm.stack) == (0, [0], [])
        for _ in range(66):
            vm.step()  # each ! sets the cell to the accumulator-derived value
        assert vm.memory == [66]
        assert vm.stack == []
        assert vm.halted is False
        vm.step()  # < sums the cell into the accumulator
        vm.step()  # . prints the accumulator minus one
        assert vm.output == "A"


class TestContainer:
    def test_named_values_and_tick(self) -> None:
        vm = esolangs.make_vm("Container", "A=0:\n+1 A>=0")
        assert (vm.ip, vm.memory, vm.stack) == (0, [0], [])
        vm.step()  # A>=0 always holds, so A increments every tick
        assert (vm.ip, vm.memory) == (1, [1])
        assert not vm.halted


class TestNevermind:
    def test_named_variables_and_cursor(self) -> None:
        vm = esolangs.make_vm("Nevermind", "make,x,5\nprint,$x")
        assert (vm.ip, vm.memory, vm.stack) == (0, [], [])
        vm.step()  # make,x,5 stores x = 5
        assert (vm.ip, vm.memory) == (1, [5])
        vm.step()  # print,$x resolves $x and prints it
        assert vm.halted
        assert vm.output == "5"


class TestBFPDA:
    def test_bit_stack_and_cursor(self) -> None:
        vm = esolangs.make_vm("BF-PDA", "<@.")
        assert (vm.ip, vm.memory, vm.stack) == (0, [], [])
        vm.step()  # < pushes a zero
        assert (vm.ip, vm.stack) == (1, [0])
        vm.step()  # @ flips the top bit
        assert vm.stack == [1]
        vm.step()  # . prints the top bit
        assert vm.halted
        assert vm.output == "1"


class TestThreeX:
    def test_rational_stack_and_cursor(self) -> None:
        vm = esolangs.make_vm("3x", "3!")
        assert (vm.ip, vm.memory, vm.stack) == (0, [], [])
        vm.step()  # 3 pushes the rational 3
        assert (vm.ip, vm.stack) == (1, [3])
        vm.step()  # ! pops and prints the top
        assert vm.halted
        assert vm.output == "3"


class TestSophie:
    def test_accumulator_and_cursor(self) -> None:
        vm = esolangs.make_vm("Sophie", "#$5.")
        assert (vm.ip, vm.memory, vm.stack) == (0, [0], [])
        vm.step()  # #$5 loads 5 into the accumulator
        assert (vm.ip, vm.memory) == (3, [5])
        vm.step()  # . prints the accumulator
        assert vm.halted
        assert vm.output == "5"


class TestJaune:
    def test_cells_hold_and_cursor(self) -> None:
        vm = esolangs.make_vm("Jaune", "++^")
        assert (vm.ip, vm.memory, vm.stack) == (0, [0], [])
        vm.step()  # ++ increments the cell twice (a counted command)
        assert (vm.ip, vm.memory) == (1, [2])
        vm.step()  # ^ prints the cell as a decimal number
        assert vm.halted
        assert vm.output == "2"


class TestSlowAcvMammalian:
    def test_arrays_pointer_and_cursor(self) -> None:
        vm = esolangs.make_vm("SLOW ACV MAMMALIAN", "SEED SEED SEED CONSUME PRONOUNCE")
        assert vm.ip == 0
        assert vm.memory == [0]
        assert vm.stack == [0] * 23  # all 23 arrays flattened, each a single 0
        for _ in range(3):
            vm.step()
        assert vm.memory == [3]  # three SEEDs add 1 to lst[0]'s head each time
        vm.step()  # CONSUME pops the array's middle element into the accumulator
        assert vm.memory == []
        vm.step()
        assert vm.halted
        assert vm.output == "\x03"


class TestZtoalcL:
    def test_pointer_and_variables(self) -> None:
        vm = esolangs.make_vm("ZTOALC L", "\n".join(["10", "print 65"]))
        assert vm.ip == 10
        assert vm.memory == []
        assert vm.stack == []
        while not vm.halted:
            vm.step()
        assert vm.output == "A"


class TestBetween:
    def test_counter_and_variables(self) -> None:
        vm = esolangs.make_vm("Between", "'a'v.\n[a]s|3|\n[a]p.\n.x.")
        assert (vm.ip, vm.memory) == (0, [])
        assert vm.stack == []
        vm.step()  # declares variable 'a' = 0
        assert vm.memory == [0]
        vm.step()  # [a]s|3| stores 3 into a
        assert (vm.ip, vm.memory) == (2, [3])
        vm.step()  # prints a
        assert vm.output == "3"
        vm.step()  # .x. exits
        assert vm.halted


class TestMyScript:
    def test_frame_position_and_scope(self) -> None:
        vm = esolangs.make_vm("MyScript", "var a is 5\nsay a")
        assert vm.ip == (1, 0)
        assert vm.memory == []
        assert vm.stack == []
        vm.step()  # declares a = 5
        assert vm.ip == (1, 1)
        assert vm.memory == [5]
        vm.step()  # say a
        assert vm.output == "5"
        vm.step()  # the root frame's statements are exhausted; it pops
        assert vm.halted
        assert vm.ip is None  # the frame stack has emptied
        assert vm.memory == []


class TestLamfunc:
    def test_token_cursor_and_variables(self) -> None:
        vm = esolangs.make_vm("Lamfunc", "p 5")
        assert vm.ip == 0
        assert vm.memory == []
        assert vm.stack == []
        while not vm.halted:
            vm.step()
        assert vm.output == "101"


class TestForbin:
    def test_locals_and_cursor(self) -> None:
        vm = esolangs.make_vm("Forbin", "main { x = 1; }")
        assert vm.ip == (0,)
        assert vm.memory == []
        assert vm.stack == []
        vm.step()
        assert vm.ip == (1,)
        assert vm.memory == [1]
        vm.step()  # main's body is exhausted; the frame pops
        assert vm.halted
        assert vm.memory == []  # the frame stack has emptied

    def test_ip_exposes_the_call_stack(self) -> None:
        # a statement-position call pushes a new frame, deepening ip
        vm = esolangs.make_vm("Forbin", "main { f 0; }\nf x { y = 1; }")
        assert vm.ip == (0,)
        vm.step()  # f 0; pushes a frame for f, advancing main's own cursor
        assert vm.ip == (1, 0)
        vm.step()  # y = 1; inside f
        assert vm.ip == (1, 1)
        vm.step()  # f's body is exhausted; the frame pops
        assert vm.ip == (1,)
        vm.step()  # main's body is exhausted; the frame pops
        assert vm.halted


class TestSuptiftam:
    def test_globals_and_cursor(self) -> None:
        vm = esolangs.make_vm("Suptiftam", "x=7")
        assert vm.ip == 0
        assert vm.memory == []
        assert vm.stack == []
        vm.step()
        assert vm.ip == 1
        assert vm.memory == [7]
        assert vm.halted


class TestCvnc:
    def test_accumulator_deque_and_cursor(self) -> None:
        # The wiki's truth machine, whose "0" branch halts.  The program is
        # IPA, so it comes from the sample table rather than being spelled
        # here: this module carries no confusable-character exemption.
        program, stdin = SAMPLES["CV(N)(C)"]
        vm = esolangs.make_vm("CV(N)(C)", program, stdin)
        assert (vm.ip, vm.memory, vm.stack) == (0, [0], [])
        vm.step()
        vm.step()
        vm.step()  # the read-and-print syllable emits the input digit
        assert (vm.ip, vm.output) == (3, "0")
        _run_all(vm)
        # The accumulator leads `memory`, ahead of the (still empty) deque.
        assert (vm.memory, vm.stack) == ([1], [])
        assert vm.halted


class TestFargo:
    def test_frames_and_cursor(self) -> None:
        vm = esolangs.make_vm("Fargo", "$", "0\n")
        # `memory` is the whole state: the input read and the output built.
        assert (vm.ip, vm.memory, vm.stack) == (0, [0, 0], [])
        vm.step()  # the top-level line pushes its frame
        assert vm.ip == 1
        assert len(vm.stack) == 1
        frame = vm.stack[0]
        assert (frame.tokens, frame.pos, frame.fn_name) == (("$",), 0, "")  # type: ignore[attr-defined]
        vm.step()  # $ prints the number it was given
        assert vm.output == "0"
        vm.step()  # the frame pops, and the run is over
        assert (vm.stack, vm.halted) == ([], True)


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

    def test_sbleq_halting_run_returns_true(self) -> None:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.sbleq import _Machine
        from esolangs.vm import run_until_halt_or_cycle

        # a=0 b=0 c=3: diff (0-0=0) jumps to mem[3], which is negative -> halts
        machine = _Machine(io=ScriptedIO(), mem=[0, 0, 3, -1], store="a")
        assert run_until_halt_or_cycle(machine) is True

    def test_sbleq_looping_run_is_detected_as_a_cycle(self) -> None:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.sbleq import _Machine
        from esolangs.vm import run_until_halt_or_cycle

        # a=0 b=0 c=2: diff is always 0, so it jumps to mem[2] (address 0) forever
        machine = _Machine(io=ScriptedIO(), mem=[0, 0, 0], store="a")
        assert run_until_halt_or_cycle(machine) is False

    def test_dimensional_halting_run_returns_true(self) -> None:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.dimensional import _Machine
        from esolangs.vm import run_until_halt_or_cycle

        machine = _Machine("+.", ScriptedIO())
        assert run_until_halt_or_cycle(machine) is True

    def test_dimensional_looping_run_is_detected_as_a_cycle(self) -> None:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.dimensional import _Machine
        from esolangs.vm import run_until_halt_or_cycle

        # cell starts nonzero and the loop body never changes it, so it never exits
        machine = _Machine("+[]", ScriptedIO())
        assert run_until_halt_or_cycle(machine) is False

    def test_modulous_halting_run_returns_true(self) -> None:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.stack_based.modulous import State
        from esolangs.vm import run_until_halt_or_cycle

        state = State(var={f"VAR{k}": 0 for k in range(1, 5)}, io=ScriptedIO())
        state.tokens = ["END"]
        assert run_until_halt_or_cycle(state) is True

    def test_modulous_looping_run_is_detected_as_a_cycle(self) -> None:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.stack_based.modulous import State
        from esolangs.vm import run_until_halt_or_cycle

        # RST resets the pointer to the start of the program on every pass
        state = State(var={f"VAR{k}": 0 for k in range(1, 5)}, io=ScriptedIO())
        state.tokens = ["RST"]
        assert run_until_halt_or_cycle(state) is False

    def test_laserfuck_halting_run_returns_true(self) -> None:
        from esolangs.interpreters.grid_based.laserfuck import _Machine
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.vm import run_until_halt_or_cycle

        machine = _Machine(["o"], ScriptedIO(), heading=0)
        assert run_until_halt_or_cycle(machine) is True

    def test_laserfuck_looping_run_is_detected_as_a_cycle(self) -> None:
        from esolangs.interpreters.grid_based.laserfuck import _Machine
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.vm import run_until_halt_or_cycle

        # a closed ring of mirrors the laser circles forever
        grid = ["/ \\", "\\o/", "//\\"]
        machine = _Machine(grid, ScriptedIO(), heading=2)
        assert run_until_halt_or_cycle(machine) is False

    def test_slow_acv_mammalian_halting_run_returns_true(self) -> None:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.slow_acv_mammalian import _Machine
        from esolangs.vm import run_until_halt_or_cycle

        machine = _Machine("PRONOUNCE", ScriptedIO())
        assert run_until_halt_or_cycle(machine) is True

    def test_slow_acv_mammalian_looping_run_is_detected_as_a_cycle(self) -> None:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.slow_acv_mammalian import _Machine
        from esolangs.vm import run_until_halt_or_cycle

        # LEAPFROG jumps back to a point that reproduces the exact same state
        machine = _Machine(
            "CONFLAGRATE SEED SEED DIGEST FISSION LEAPFROG", ScriptedIO()
        )
        assert run_until_halt_or_cycle(machine) is False

    def test_ztoalc_l_halting_run_returns_true(self) -> None:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.other.ztoalc_l import _Machine
        from esolangs.vm import run_until_halt_or_cycle

        machine = _Machine(["2"], ScriptedIO())
        assert run_until_halt_or_cycle(machine) is True

    def test_ztoalc_l_looping_run_is_detected_as_a_cycle(self) -> None:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.other.ztoalc_l import _Machine
        from esolangs.vm import run_until_halt_or_cycle

        # each "jump x 1" bumps the pointer past the 2-line program and back
        # via a Collatz step, tracing 2 -> 3 -> 4 -> 2 forever
        machine = _Machine(["2", "jump x 1", "jump x 1"], ScriptedIO())
        assert run_until_halt_or_cycle(machine) is False

    def test_between_halting_run_returns_true(self) -> None:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.register_based.between import _Machine
        from esolangs.vm import run_until_halt_or_cycle

        machine = _Machine([".x."], ScriptedIO())
        assert run_until_halt_or_cycle(machine) is True

    def test_between_looping_run_is_detected_as_a_cycle(self) -> None:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.register_based.between import _Machine
        from esolangs.vm import run_until_halt_or_cycle

        # |0|f. is an unconditional goto back to line 0
        machine = _Machine(["|0|f."], ScriptedIO())
        assert run_until_halt_or_cycle(machine) is False

    def test_myscript_halting_run_returns_true(self) -> None:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.register_based.myscript import _Machine
        from esolangs.vm import run_until_halt_or_cycle

        machine = _Machine("say 5", ScriptedIO())
        assert run_until_halt_or_cycle(machine) is True

    def test_myscript_looping_run_is_detected_as_a_cycle(self) -> None:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.register_based.myscript import _Machine
        from esolangs.vm import run_until_halt_or_cycle

        # while yes never becomes false; the body's own state never changes
        machine = _Machine("while yes,\n  var x is 1", ScriptedIO())
        assert run_until_halt_or_cycle(machine) is False

    def test_lamfunc_halting_run_returns_true(self) -> None:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.other.lamfunc import _Machine
        from esolangs.vm import run_until_halt_or_cycle

        machine = _Machine("p 5", ScriptedIO())
        assert run_until_halt_or_cycle(machine) is True

    def test_lamfunc_recursive_halting_run_returns_true(self) -> None:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.other.lamfunc import _Machine
        from esolangs.vm import run_until_halt_or_cycle

        # loop halves x each call until it reaches 0; a real, terminating
        # recursion whose call sits inside i's lazy branch, not just a flat
        # top-level program
        code = "F loop x - i x loop fb x 0\nloop 0b1000"
        machine = _Machine(code, ScriptedIO())
        assert run_until_halt_or_cycle(machine) is True

    def test_forbin_halting_run_returns_true(self) -> None:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.other.forbin import _Machine
        from esolangs.vm import run_until_halt_or_cycle

        machine = _Machine("main { x = 1; }", ScriptedIO())
        assert run_until_halt_or_cycle(machine) is True

    def test_forbin_for_loop_halts_without_a_false_cycle(self) -> None:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.other.forbin import _Machine
        from esolangs.vm import run_until_halt_or_cycle

        # each row sets the same local to the same value, so only the loop's
        # own row index (part of the snapshot) keeps this from reading as a
        # repeat before the finite range is exhausted
        machine = _Machine("main { for i:0..1 { x = 0; } }", ScriptedIO())
        assert run_until_halt_or_cycle(machine) is True

    def test_suptiftam_halting_run_returns_true(self) -> None:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.other.suptiftam import _Machine
        from esolangs.vm import run_until_halt_or_cycle

        machine = _Machine("x=7", ScriptedIO())
        assert run_until_halt_or_cycle(machine) is True


class TestFactory:
    def test_unknown_language_raises(self) -> None:
        with pytest.raises(UnknownLanguageError):
            esolangs.make_vm("NoSuchLanguage", "+")

    def test_registered_language_without_an_adapter_raises(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A registry language missing from ``_VM_ADAPTERS`` also raises.

        Every current registry language has an adapter, so this exercises
        ``make_vm``'s defensive fallback (not just the unregistered-name
        check) by removing one adapter for the duration of the test.
        """
        from esolangs.vm import _VM_ADAPTERS

        monkeypatch.delitem(_VM_ADAPTERS, "brainfuck")
        with pytest.raises(UnknownLanguageError):
            esolangs.make_vm("brainfuck", "+")


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
        ("Decleq", "-2 5 9 9 9 65 0 0"),
        ("6-5", "55A"),
        ("Back", "-*"),
        ("BIO", "0ox;0ix{1ox;};1ix;"),
        ("NoComment", "ciio"),
        ("3D Brainfuck", "+."),
        ("Factor", "15"),
        (
            "Basicfuck",
            "#basicfuck t=1 r=0~255 o=nearest\n#allocate a\na += 65;\nwrite <- a ;",
        ),
        ("Painfuck", "pp"),
        ("bit~", "~("),
        ("Collatz Multiverse", "x = negativeOne x + negativeOne, DO PRINT."),
        ("Polynomial", "f(x) = x^2+4"),
        ("Streetcode", STREETCODE),
    ],
)
def test_vm_output_matches_run(language: str, program: str) -> None:
    """Stepping a VM to completion matches running the interpreter directly."""
    try:
        expected = esolangs.run(language, program)
    except EOFError:
        pytest.skip(f"{language} needs input")
    vm = esolangs.make_vm(language, program)
    _run_all(vm)
    if language in DUMPS_ON_THE_POST_HALT_STEP:
        vm.step()  # the dump, which run performs after its own loop
    assert vm.output == expected


class TestEveryLanguageIsSteppable:
    """The two whole-registry invariants, as tests rather than prose.

    Both were true by habit before they were true by test: a new language
    could land with a runner and no adapter, or with a state object whose
    ``snapshot()`` nobody had written, and only a reader comparing two
    lists would notice.
    """

    def test_every_registry_language_is_step_capable(self) -> None:
        """Every language can be wrapped, which is why the table is derived.

        The adapters are built from ``RUNNERS`` itself, so "every language
        has an adapter" is now true by construction and worth nothing as an
        assertion.  What is *not* automatic is the fact that made deriving
        them safe: that every registered interpreter actually exposes a
        step-capable state object.  A new language that ran only as a whole
        program would still get an adapter built for it, and would fail on
        the first ``step()`` rather than here -- so that is what is checked.
        """
        import importlib

        from esolangs.registry import RUNNERS

        without: list[str] = []
        for language, (module_path, _split, _kwargs) in sorted(RUNNERS.items()):
            module = importlib.import_module(f"esolangs.interpreters.{module_path}")
            state = getattr(module, "_Machine", None) or getattr(module, "State", None)
            if state is None or not hasattr(state, "step"):
                without.append(language)
        assert without == []

    def test_every_adapter_wraps_a_state_object_with_a_snapshot(self) -> None:
        """``run_until_halt_or_cycle`` needs ``snapshot()`` on the machine.

        A machine without ``snapshot()`` cannot have a hang proven, which is
        the cycle detector's real precondition.  The check reads the module
        each language names in ``RUNNERS`` rather than the adapter's source:
        most adapters are now derived from that entry and have no import to
        read back, and the registry is where the association actually lives.

        This deliberately does not build the machines -- that would need a
        valid program for every language -- so it checks the class each
        module exposes as its state object.
        """
        import importlib

        from esolangs.registry import RUNNERS
        from esolangs.vm import _VM_ADAPTERS

        without: list[str] = []
        for name in sorted(_VM_ADAPTERS):
            module = importlib.import_module(
                f"esolangs.interpreters.{RUNNERS[name][0]}"
            )
            # A couple of modules call their state object ``State``.
            state = getattr(module, "_Machine", None) or getattr(module, "State", None)
            if state is None or not hasattr(state, "snapshot"):
                without.append(name)
        assert without == []

    def test_memory_and_stack_are_copies_not_the_live_store(self) -> None:
        """A caller must not be able to write into a running machine.

        An interpreter may hand back its store directly -- several hold the
        list under exactly the VM's name, which is why the shape protocol
        asks only for a ``Sequence`` -- so the copy that keeps the boundary
        honest is ``_DelegatingVM``'s, made once rather than in every
        interpreter.  Nothing else covers it: every other test reads these
        properties without writing to them.
        """
        from esolangs.vm import _VM_ADAPTERS, _DelegatingVM

        checked = 0
        for name, adapter in sorted(_VM_ADAPTERS.items()):
            if not issubclass(adapter, _DelegatingVM):
                continue
            program, stdin = SAMPLES[name]
            vm = esolangs.make_vm(name, program, stdin)
            with contextlib.suppress(Exception):
                vm.step()
            before_mem, before_stk = list(vm.memory), list(vm.stack)
            vm.memory.append(12345)
            vm.stack.append("scribble")
            assert list(vm.memory) == before_mem, f"{name}: memory is live"
            assert list(vm.stack) == before_stk, f"{name}: stack is live"
            checked += 1
        assert checked > 30, f"only {checked} adapters exercised"

    def test_stepping_is_reproducible_for_the_random_languages(self) -> None:
        """Five languages have a random instruction; the VM pins every one.

        ``?`` (WII2D), ``y`` (Painfuck), ``RND`` (Modulous), a COD junction
        and LaserFuck's ``*`` beam splitter all draw at *runtime*, so two
        runs of the same program could disagree -- which would make a
        stepped VM unusable and ``run_until_halt_or_cycle``'s argument
        ("a deterministic machine that revisits a state has looped") false.
        Each adapter passes a seeded generator to fix that.

        The programs below were chosen because the draw actually fires for
        them.  Asserting determinism on a program that never reaches its
        random instruction would pass whatever the adapters did, so the
        first half of this test proves the instruction executes and the
        second proves it lands the same way twice.
        """
        from esolangs.interpreters import randomness

        cases = {
            "WII2D": ">?.\n!",
            "Painfuck": "y",
            "Modulous": "[RND 9][PRT INT]",
            "COD": "~~~~~~~\n~     ~\n~ ~ ~ ~\n~~~>~~~",
            "LaserFuck": "*\no",
        }

        def trace(language: str, program: str) -> list[object]:
            vm = esolangs.make_vm(language, program)
            seen: list[object] = []
            for _ in range(40):
                if vm.halted:
                    break
                with contextlib.suppress(Exception):
                    vm.step()
                ip = vm.ip
                seen.append(
                    (tuple(ip) if isinstance(ip, tuple) else ip, tuple(vm.memory))
                )
            return seen

        original = randomness.Seeded.randbelow
        for language, program in cases.items():
            drawn = []

            def counted(self, upper, _o=original, _d=drawn):
                _d.append(upper)
                return _o(self, upper)

            randomness.Seeded.randbelow = counted
            try:
                first = trace(language, program)
            finally:
                randomness.Seeded.randbelow = original
            assert drawn, f"{language}: the random instruction never ran"
            assert trace(language, program) == first, f"{language} is not reproducible"

    def test_the_seeded_source_rejects_an_empty_range(self) -> None:
        """``randbelow`` checks its bound instead of ignoring it.

        A stub that never read its argument would answer an impossible
        request -- choosing among no options -- as readily as a real one,
        and the mistake would surface somewhere far from its cause.
        ``secrets.randbelow``, the default source, raises here too, so the
        seeded stand-in agrees with what it replaces.
        """
        from esolangs.interpreters.randomness import Seeded

        source = Seeded(0)
        for bad in (0, -1):
            with pytest.raises(ValueError, match=f"must be positive, got {bad}"):
                source.randbelow(bad)

        assert source.randbelow(1) == 0
