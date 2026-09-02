"""Unit tests for the %^2^-1 interpreter."""

import importlib

from esolangs.interpreters.io import ScriptedIO
from tests.interpreters.contract import (
    CycleContract,
    EmptyProgramContract,
    StateViewContract,
)

run = importlib.import_module(
    "esolangs.interpreters.register_based.pct_squared_minus_one"
).run


def run_program(code: str, stdin: str = "") -> str:
    io = ScriptedIO(stdin)
    run(code, io)
    return io.getvalue()


class TestPct:
    def test_reset_sets_zero(self) -> None:
        assert run_program("'e") == "\x00"
        assert run_program("'pe") == "\x00"
        assert run_program("'me") == "\x00"  # 0 * 2 is still 0

    def test_divide(self) -> None:
        # 'i -> -3, p -> 3, s -> 1: the fixed three-op path for byte 1
        assert run_program("'ipse") == "\x01"
        assert run_program("'ipe") == "\x03"
        assert run_program("'mse") == "\xfe"  # 0, *2, -2 -> -2 as a byte

    def test_square_and_negate(self) -> None:
        assert run_program("'ie") == "\xfd"  # -3 as a byte

    def test_print_decimal(self) -> None:
        assert run_program("'l") == "0"
        assert run_program("'sl") == "-2"
        assert run_program("'me'l") == "\x000"

    def test_read(self) -> None:
        assert run_program("ne", "X\n") == "X"
        assert run_program("ne", "0\n") == "0"
        assert run_program("nl", "A\n") == "65"

    def test_read_reset(self) -> None:
        # n reads 'a', ' resets, n reads 'c', e prints it
        assert run_program("n'ne", "ab\ncd\n") == "c"

    def test_rewind_noop_when_zero(self) -> None:
        assert run_program("'te") == "\x00"

    def test_rewind_loop_terminates_on_zero(self) -> None:
        # t rewinds while the magnitude is nonzero; reading a 0 byte stops it
        assert run_program("nt", "A\n\x00\n") == ""
        assert run_program("nt", "\x00\n") == ""

    def test_reset_above_3003(self) -> None:
        # ip -> 3, ten doublings -> 3072 > 3003, which resets to 0 before the l
        assert run_program("ip" + "m" * 10 + "l") == "0"
        # just under the threshold: 3 * 2^9 = 1536 prints normally
        assert run_program("ip" + "m" * 9 + "l") == "1536"

    def test_unknown_characters_are_no_ops(self) -> None:
        """Characters outside the command set do nothing at all.

        Every other program here is built purely from commands, so the tail
        of the dispatch chain was never reached by a character it does not
        handle: inverting ``char == "'"`` or ``char == "t"`` there changed
        nothing the suite could see.  A no-op between two commands has to
        leave both the accumulator and the cursor alone -- ``ixe`` prints
        exactly what ``ie`` does.
        """
        assert run_program("ixe") == run_program("ie") == "\xfd"
        assert run_program("i.l") == "-3"
        # an uppercase T is not the rewind command, so it changes nothing
        assert run_program("iTl") == "-3"

    def test_rewind_sends_the_cursor_back_to_the_start(self) -> None:
        """``t`` restarts the program while the accumulator is nonzero.

        The suite covers the characters that are *not* the rewind -- an
        uppercase ``T`` above -- but never the one that is, so the branch
        could stop matching entirely and every program would still finish.
        Testing it needs a loop that ends: ``t`` rewinds to the start, so
        the accumulator has to reach zero on its own.  It does, through the
        cap -- ``s`` then ``p`` makes it positive and ``m`` doubles it
        until it passes 3003, which the next step resets to 0.  Then ``t``
        falls through and ``l`` prints the zero.  Without the rewind the
        run is a single pass and prints 4 instead.
        """
        assert run_program("sptml") == "0"

    def test_reset_clears_an_accumulated_value(self) -> None:
        """' zeroes a magnitude that is already nonzero.

        The reset was only ever run first, on the zero it starts at, where
        setting the accumulator to 0 and leaving it alone look the same.
        """
        assert run_program("i'l") == "0"
        assert run_program("i'e") == "\x00"

    def test_reset_boundary_is_exclusive(self) -> None:
        """3003 itself survives; the reset needs the magnitude to exceed it.

        ``test_reset_above_3003`` jumps from 1536 to 3072, so every value in
        between -- 3003 included -- went unchecked.  1001 subtractions of 3
        then a negation land on the boundary exactly.
        """
        assert run_program("i" * 1001 + "pl") == "3003"
        assert run_program("i" * 1002 + "pl") == "0"
        # 3004 is the first magnitude that resets, so it pins the threshold
        # from the other side: one higher and the reset would let it through
        assert run_program("s" * 1502 + "pl") == "0"


class TestStepMachine:
    def test_snapshot_changes_after_a_step(self) -> None:
        from esolangs.interpreters.register_based.pct_squared_minus_one import (
            _Machine,
        )

        machine = _Machine("i", ScriptedIO(""))
        before = machine.snapshot()
        machine.step()  # i subtracts 3 from the accumulator
        assert machine.snapshot() != before
        assert machine.acc == -3

    def test_step_after_halt_is_a_noop(self) -> None:
        from esolangs.interpreters.register_based.pct_squared_minus_one import (
            _Machine,
        )

        machine = _Machine("", ScriptedIO(""))
        assert machine.halted
        machine.step()  # stepping a halted machine is a no-op
        assert machine.acc == 0


def _machine(code: object) -> object:
    from esolangs.interpreters.register_based.pct_squared_minus_one import _Machine

    return _Machine(code, ScriptedIO(""))


class TestContract(EmptyProgramContract, CycleContract, StateViewContract):
    """The shared shapes.

    ``mipt`` settles into a genuine 4-state cycle: (0,3) -> (1,6) -> (2,3)
    -> (3,-3) -> back to (0,3), so the accumulator never grows without
    bound and the state repeats exactly.
    """

    run = staticmethod(run_program)
    machine = staticmethod(_machine)
    halting_program = "i"
    looping_program = "mipt"
    state_views = ("ind", "acc", "ip", "memory")
    viewing_program = "pl"  # `p` raises the accumulator, `l` prints it
