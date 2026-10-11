"""Unit tests for the Container interpreter."""

import io
from contextlib import redirect_stdout
from typing import ClassVar

import pytest

from esolangs.interpreters.io import IO
from esolangs.interpreters.other.container import run
from tests.fixtures import grid
from tests.interpreters.contract import SnapshotContract, StateViewContract
from tests.support.raises import raises_message

HELLO_WORLD = grid("container/hello_world.txt")


class TestContainer:
    def test_hello_world(self) -> None:
        """Hello, World! program from esolangs.org."""
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = run(HELLO_WORLD, io=IO())
        assert code == 0
        assert buffer.getvalue() == "Hello, world!"

    def test_container_update_clamps_at_zero(self) -> None:
        """Negative results are clamped to zero."""
        from esolangs.interpreters.other.container import Con

        con = Con("A")
        con.add("-5 B>=1")
        assert con.update({"A": 2, "B": 1}) == 0
        assert con.update({"A": 2, "B": 0}) == 2

    def test_input_container(self) -> None:
        """An empty-named container going 0 -> 1 reads a character of input."""
        from unittest.mock import patch

        code = [":", "+1 A>=0", "", "A:", "+1 EXIT>=1", "", "EXIT=1:", "-1 A>=0"]
        with (
            patch("builtins.input", return_value="Z"),
            redirect_stdout(io.StringIO()),
        ):
            exit_code = run(code, IO())
        assert exit_code == 0

    def test_rule_before_declaration_rejected(self) -> None:
        """A rule line before any container declaration is malformed."""
        with pytest.raises(ValueError, match="before any container"):
            run(["+1 A>=0"], IO())

    def test_less_equal_takes_only_a_constant(self) -> None:
        """The page lists ``Container<=Constant``, never ``A<=B``."""
        with pytest.raises(ValueError, match="with a constant only"):
            run(["A:", "+1 A<=B", "B:"], IO())

    def test_the_malformed_program_message_reads_exactly(self) -> None:
        """``match=`` only looks for a substring, so pin the whole message."""
        with raises_message(ValueError, "rule line before any container declaration"):
            run(["+1 A>=0"], IO())

    def test_output_is_masked_to_seven_bits(self) -> None:
        """OUT is printed modulo 128, so 200 comes out as 72."""
        code = [
            "PRINT:",
            "+1 PRINT<=0",
            "-1 PRINT>=1",
            "",
            "OUT=200:",
            "",
            "EXIT=1:",
            "-1 PRINT>=1",
        ]
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            exit_code = run(code, io=IO())
        assert exit_code == 0
        assert buffer.getvalue() == "H"


class TestPublicAPI:
    def test_run_returns_output_instead_of_exiting(self) -> None:
        """EXIT is a normal halt, so the public API returns the output."""
        import esolangs

        assert esolangs.run("Container", "\n".join(HELLO_WORLD)) == "Hello, world!"


class TestStepMachine:
    def test_exit_sets_halted_and_exit_code(self) -> None:
        from esolangs.interpreters.other.container import _Machine

        machine = _Machine(HELLO_WORLD, IO())
        while not machine.halted:
            machine.step()
        assert machine.exit_code == 0

    def test_tick_counts_the_steps_taken(self) -> None:
        from esolangs.interpreters.other.container import _Machine

        machine = _Machine(HELLO_WORLD, IO())
        steps = 0
        while not machine.halted:
            machine.step()
            steps += 1
        assert machine.tick == steps

    def test_loop_is_detected_as_a_cycle(self) -> None:
        # A oscillates 0 -> 1 -> 0 forever with no EXIT rule: a genuine
        # state cycle since the containers' values repeat exactly.
        from esolangs.interpreters.other.container import _Machine
        from esolangs.vm import run_until_halt_or_cycle

        code = ["A=0:", "+1 A<=0", "-1 A>=1"]
        assert run_until_halt_or_cycle(_Machine(code, IO())) is False

    def test_the_read_container_takes_one_character_per_firing(self) -> None:
        """The empty-named container reads one character each time it turns on."""
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.other.container import _Machine

        code = [":", "+1 <=0", "-1 >=1", "", "IN:"]
        machine = _Machine(code, ScriptedIO("AB"))
        seen = []
        for _ in range(4):
            machine.step()
            seen.append(machine.var["IN"])
        assert seen == [65, 65, 66, 66]

    def test_a_read_at_eof_sets_in_to_zero(self) -> None:
        """Wiki rev 135848: the read sets IN "with EOF returning 0"."""
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.other.container import _Machine

        machine = _Machine([":", "+1 <=0", "-1 >=1", "", "IN:"], ScriptedIO("A"))
        seen = []
        for _ in range(4):
            machine.step()
            seen.append(machine.var["IN"])
        assert seen == [65, 65, 0, 0]

    def test_a_negative_initial_value_is_rejected(self) -> None:
        """Wiki: the initial value "must be a nonnegative integer"."""
        with pytest.raises(ValueError, match="nonnegative"):
            run(["A=-1:"], IO())

    def test_an_initial_value_past_the_host_digit_cap_parses(self) -> None:
        """Python's int() refuses 4300+ digits; the language has no cap."""
        from esolangs.interpreters.other.container import _Machine

        machine = _Machine(["A=1" + "0" * 5000 + ":"], IO())
        assert machine.var["A"] == 10**5000


def _machine(code: object) -> object:
    from esolangs.interpreters.io import IO
    from esolangs.interpreters.other.container import _Machine

    return _Machine(code, IO())


class TestContract(SnapshotContract, StateViewContract):
    """The shared shapes, with this language's own programs."""

    machine = staticmethod(_machine)
    stepping_program: ClassVar[list[str]] = ["A=0:", "+1 A>=0"]
    # `queue` is the input read but not yet consumed, which this program
    # never fills -- it is read either side regardless, and `memory` (the
    # containers' values) is what the tick moves.
    state_views: ClassVar[tuple[str, ...]] = ("queue", "ip", "memory")
    viewing_program: ClassVar[list[str]] = ["A=0:", "+1 A>=0"]
    # No program in this file moves the queue view; it stays empty
    # for the whole run.
    constant_views: ClassVar[frozenset[str]] = frozenset({"queue"})
