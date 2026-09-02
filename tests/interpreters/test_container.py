"""Unit tests for the Container interpreter."""

import io
from contextlib import redirect_stdout
from typing import ClassVar

import pytest

from esolangs.interpreters.io import IO
from esolangs.interpreters.other.container import run
from tests.interpreters.contract import SnapshotContract, StateViewContract
from tests.raises import raises_message

HELLO_WORLD = [
    "A:",
    "+1 EXIT>=1",
    "",
    "PRINT:",
    "+1 PRINT<=0",
    "-1 PRINT>=1",
    "",
    "OUT:",
    "+72 A>=0",
    "-115 A>=2",
    "+93 A>=4",
    "-100 A>=6",
    "+103 A>=8",
    "-173 A>=10",
    "+114 A>=11",
    "+0 A>=12",
    "+99 A>=14",
    "-194 A>=16",
    "+205 A>=18",
    "-214 A>=20",
    "+106 A>=21",
    "+0 A>=22",
    "-59 A>=24",
    "",
    "EXIT=1:",
    "-1 A>=24",
]


class TestContainer:
    def test_hello_world(self) -> None:
        """Hello, World! program from esolangs.org."""
        buffer = io.StringIO()
        with pytest.raises(SystemExit) as exc, redirect_stdout(buffer):
            run(HELLO_WORLD, io=IO())
        assert exc.value.code == 0
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
            pytest.raises(SystemExit) as exc,
            redirect_stdout(io.StringIO()),
        ):
            run(code, IO())
        assert exc.value.code == 0

    def test_rule_before_declaration_rejected(self) -> None:
        """A rule line before any container declaration is malformed."""
        with pytest.raises(ValueError, match="before any container"):
            run(["+1 A>=0"], IO())

    def test_the_malformed_program_message_reads_exactly(self) -> None:
        """``match=`` only looks for a substring, so pin the whole message."""
        with raises_message(ValueError, "rule line before any container declaration"):
            run(["+1 A>=0"], IO())

    def test_output_is_masked_to_seven_bits(self) -> None:
        """OUT is printed modulo 128, so 200 comes out as 72.

        Hello, World! never drives OUT past 127, which leaves the width of
        the mask free -- 200 is the smallest round value above it.
        """
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
        with pytest.raises(SystemExit) as exc, redirect_stdout(buffer):
            run(code, io=IO())
        assert exc.value.code == 0
        assert buffer.getvalue() == "H"

    def test_empty_program_halts(self) -> None:
        """An empty program halts immediately with no output."""
        run([], IO())


class TestStepMachine:
    def test_exit_sets_halted_and_exit_code(self) -> None:
        from esolangs.interpreters.other.container import _Machine

        machine = _Machine(HELLO_WORLD, IO())
        while not machine.halted:
            machine.step()
        assert machine.exit_code == 0

    def test_empty_program_is_halted(self) -> None:
        from esolangs.interpreters.other.container import _Machine

        assert _Machine([], IO()).halted is True

    def test_loop_is_detected_as_a_cycle(self) -> None:
        # A oscillates 0 -> 1 -> 0 forever with no EXIT rule: a genuine
        # state cycle since the containers' values repeat exactly.
        from esolangs.interpreters.other.container import _Machine
        from esolangs.vm import run_until_halt_or_cycle

        code = ["A=0:", "+1 A<=0", "-1 A>=1"]
        assert run_until_halt_or_cycle(_Machine(code, IO())) is False

    def test_step_after_halt_is_a_noop(self) -> None:
        from esolangs.interpreters.other.container import _Machine

        machine = _Machine([], IO())
        assert machine.halted
        machine.step()  # stepping a halted machine is a no-op
        assert machine.tick == 0

    def test_each_tick_counts_once(self) -> None:
        """``tick`` advances by one per step, from zero."""
        from esolangs.interpreters.other.container import _Machine

        machine = _Machine(["A=0:", "+1 A>=0"], IO())
        machine.step()
        machine.step()
        assert machine.tick == 2

    def test_the_read_container_takes_one_character_per_firing(self) -> None:
        """The empty-named container reads one character each time it turns on.

        It oscillates 0 -> 1 -> 0, so it fires on every other tick, and the
        line it read stays queued for the next firing -- one input line
        feeds two reads, and IN holds the character until then.  Watching
        the exit code alone would not show which character landed, nor
        that the second one came from the queue rather than a fresh line.
        """
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.other.container import _Machine

        code = [":", "+1 <=0", "-1 >=1", "", "IN:"]
        machine = _Machine(code, ScriptedIO("AB"))
        seen = []
        for _ in range(4):
            machine.step()
            seen.append(machine.var["IN"])
        assert seen == [65, 65, 66, 66]


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
