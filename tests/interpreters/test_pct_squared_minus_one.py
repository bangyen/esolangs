r"""Unit tests for the %^2^-1 interpreter."""

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
        assert run_program("'me") == "\x00"  # 0 * 2 is still 0.

    def test_divide(self) -> None:
        # 'i -> -3, p -> 3, s -> 1: the.
        assert run_program("'ipse") == "\x01"
        assert run_program("'ipe") == "\x03"
        assert run_program("'mse") == "\xfe"  # 0, *2, -2 -> -2 as a byte.

    def test_square_and_negate(self) -> None:
        assert run_program("'ie") == "\xfd"  # -3 as a byte.

    def test_print_decimal(self) -> None:
        assert run_program("'l") == "0"
        assert run_program("'sl") == "-2"
        assert run_program("'me'l") == "\x000"

    def test_read(self) -> None:
        assert run_program("ne", "X\n") == "X"
        assert run_program("ne", "0\n") == "0"
        assert run_program("nl", "A\n") == "65"

    def test_read_reset(self) -> None:
        # n reads 'a', ' resets, n.
        assert run_program("n'ne", "ab\ncd\n") == "c"

    def test_rewind_noop_when_zero(self) -> None:
        assert run_program("'te") == "\x00"

    def test_rewind_loop_terminates_on_zero(self) -> None:
        # t rewinds while the magnitude.
        assert run_program("nt", "A\n\x00\n") == ""
        assert run_program("nt", "\x00\n") == ""

    def test_reset_above_3003(self) -> None:
        # ip -> 3, ten doublings ->.
        assert run_program("ip" + "m" * 10 + "l") == "0"
        # just under the threshold: 3 *.
        assert run_program("ip" + "m" * 9 + "l") == "1536"

    def test_unknown_characters_are_no_ops(self) -> None:
        r"""Characters outside the command set do nothing at all."""
        assert run_program("ixe") == run_program("ie") == "\xfd"
        assert run_program("i.l") == "-3"
        # an uppercase T is not the.
        assert run_program("iTl") == "-3"

    def test_rewind_sends_the_cursor_back_to_the_start(self) -> None:
        r"""``t`` restarts the program while the accumulator is nonzero."""
        assert run_program("sptml") == "0"

    def test_reset_clears_an_accumulated_value(self) -> None:
        r"""' zeroes a magnitude that is already nonzero."""
        assert run_program("i'l") == "0"
        assert run_program("i'e") == "\x00"

    def test_reset_boundary_is_exclusive(self) -> None:
        r"""3003 itself survives; the reset needs the magnitude to exceed it."""
        assert run_program("i" * 1001 + "pl") == "3003"
        assert run_program("i" * 1002 + "pl") == "0"
        # 3004 is the first magnitude.
        # from the other side: one.
        assert run_program("s" * 1502 + "pl") == "0"


class TestStepMachine:
    def test_snapshot_changes_after_a_step(self) -> None:
        from esolangs.interpreters.register_based.pct_squared_minus_one import (
            _Machine,
        )

        machine = _Machine("i", ScriptedIO(""))
        before = machine.snapshot()
        machine.step()  # i subtracts 3 from the.
        assert machine.snapshot() != before
        assert machine.acc == -3

    def test_step_after_halt_is_a_noop(self) -> None:
        from esolangs.interpreters.register_based.pct_squared_minus_one import (
            _Machine,
        )

        machine = _Machine("", ScriptedIO(""))
        assert machine.halted
        machine.step()  # stepping a halted machine is.
        assert machine.acc == 0


def _machine(code: object) -> object:
    from esolangs.interpreters.register_based.pct_squared_minus_one import _Machine

    return _Machine(code, ScriptedIO(""))


class TestContract(EmptyProgramContract, CycleContract, StateViewContract):
    r"""The shared shapes."""

    run = staticmethod(run_program)
    machine = staticmethod(_machine)
    halting_program = "i"
    looping_program = "mipt"
    state_views = ("ind", "acc", "ip", "memory")
    # `m`/`i`/`p`/`t` between them.
    # not just the cursor.
    viewing_program = "mipt"
