"""Unit tests for the Container interpreter."""

import io
from contextlib import redirect_stdout
from typing import ClassVar
from unittest.mock import patch

import pytest

from esolangs import ExecutionLimits, ExecutionResult, HaltError, Language
from esolangs import run as execute
from esolangs.languages.container.interpreter import Con, _Machine, run
from esolangs.runtime.io import IO, ScriptedIO
from esolangs.vm import run_until_halt_or_cycle
from tests.interpreters.contract import SnapshotContract, StateViewContract
from tests.support.fixtures import grid
from tests.support.raises import raises_message
from tests.support.vm_support import assert_rejected_output_retry

HELLO_WORLD = grid("container", "hello_world.txt")


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
        con = Con("A")
        con.add("-5 B>=1")
        assert con.update({"A": 2, "B": 1}) == 0
        assert con.update({"A": 2, "B": 0}) == 2

    def test_input_container(self) -> None:
        """An empty-named container going 0 -> 1 reads a character of input."""
        code = [":", "+1 A>=0", "", "A:", "+1 EXIT>=1", "", "EXIT=1:", "-1 A>=0"]
        with (
            patch("builtins.input", return_value="Z"),
            redirect_stdout(io.StringIO()),
        ):
            exit_code = run(code, IO())
        assert exit_code == 0

    def test_less_equal_takes_only_a_constant(self) -> None:
        """The page lists ``Container<=Constant``, never ``A<=B``."""
        with pytest.raises(ValueError, match="with a constant only"):
            run(["A:", "+1 A<=B", "B:"], IO())

    def test_rule_before_declaration_rejected(self) -> None:
        """``match=`` only looks for a substring, so pin the whole message."""
        with raises_message(ValueError, "rule line before any container declaration"):
            run(["+1 A>=0"], IO())

    def test_output_is_masked_to_seven_bits(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
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
        same_tick_source = "\n".join([*code, "", ":", "+1 PRINT<=0"])
        for source, stdin in (("\n".join(code), ""), (same_tick_source, "A")):
            assert_rejected_output_retry(
                "Container",
                source,
                "H",
                "H",
                prefix=0,
                stdin=stdin,
                monkeypatch=monkeypatch,
                unchanged_if_unwritten=True,
                following_writes=(),
            )
        self._check_interrupted_read(same_tick_source, monkeypatch)

    def _check_interrupted_read(
        self, source: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        api = Language("Container")
        limits = ExecutionLimits(max_steps=2)
        complete = api.run(source, stdin="A", limits=limits)
        assert (complete.output, complete.input_position, complete.input_reads) == (
            "H",
            1,
            1,
        )
        debug = api.make_debugger(source, stdin="A")
        boundary = debug.snapshot()
        read = ScriptedIO.input_char
        attempts = 0

        def refuse_first(io: ScriptedIO, prompt: str = "Input: ") -> int:
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                raise HaltError("transient input refusal")
            return read(io, prompt)

        monkeypatch.setattr(ScriptedIO, "input_char", refuse_first)
        with pytest.raises(HaltError, match="input refusal") as stopped:
            debug.run(limits=limits)
        assert stopped.value.observation == ExecutionResult("H", 0, 0, 0, steps=0)
        assert debug.snapshot() == (*boundary, 1)
        assert debug.run(limits=limits) == "halted"
        assert debug.observation == complete
        assert attempts == 2


class TestPublicAPI:
    def test_run_returns_output_instead_of_exiting(self) -> None:
        """EXIT is a normal halt, so the public API returns the output."""

        assert execute("Container", "\n".join(HELLO_WORLD)).output == "Hello, world!"


class TestStepMachine:
    def test_exit_sets_halted_and_exit_code(self) -> None:
        machine = _Machine(HELLO_WORLD, IO())
        while not machine.halted:
            machine.step()
        assert machine.exit_code == 0

    def test_tick_counts_the_steps_taken(self) -> None:
        machine = _Machine(HELLO_WORLD, IO())
        steps = 0
        while not machine.halted:
            machine.step()
            steps += 1
        assert machine.tick == steps

    def test_loop_is_detected_as_a_cycle(self) -> None:
        # A oscillates 0 -> 1 -> 0 forever with no EXIT rule: a genuine
        # state cycle since the containers' values repeat exactly.
        code = ["A=0:", "+1 A<=0", "-1 A>=1"]
        assert run_until_halt_or_cycle(_Machine(code, IO())) is False

    def test_the_read_container_takes_one_character_per_firing(self) -> None:
        """The empty-named container reads one character each time it turns on."""
        code = [":", "+1 <=0", "-1 >=1", "", "IN:"]
        machine = _Machine(code, ScriptedIO("AB"))
        seen = []
        for _ in range(4):
            machine.step()
            seen.append(machine.var["IN"])
        assert seen == [65, 65, 66, 66]

    def test_a_read_at_eof_sets_in_to_zero(self) -> None:
        """Wiki rev 135848: the read sets IN "with EOF returning 0"."""
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
        machine = _Machine(["A=1" + "0" * 5000 + ":"], IO())
        assert machine.var["A"] == 10**5000

        import sys

        from esolangs import ProgramArtifact
        from esolangs.debugger import make_debugger
        from esolangs.runtime._vm_adapter import _capture_workspace
        from esolangs.vm import make_vm

        cap = sys.get_int_max_str_digits()
        digits = "1" + "0" * max(5000, cap)
        program = ProgramArtifact("A=" + digits + ":\n", "Container")
        vm = make_vm("Container", program, stdin="")
        debug = make_debugger("Container", program, stdin="")
        for wrapped in (vm, debug.vm):
            before = wrapped.snapshot(), _capture_workspace(wrapped), wrapped.memory
            assert dict(wrapped.views)["var"] == ("{'A': " + digits + "}")[:57] + "..."
            assert (
                wrapped.snapshot(),
                _capture_workspace(wrapped),
                wrapped.memory,
            ) == before
        assert sys.get_int_max_str_digits() == cap


def _machine(code: object) -> object:
    return _Machine(code, IO())


class TestContract(SnapshotContract, StateViewContract):
    """The shared shapes, with this language's own programs."""

    machine = staticmethod(_machine)
    stepping_program: ClassVar[list[str]] = ["A=0:", "+1 A>=0"]
    # `memory` (the containers' values) is what the tick moves.
    state_views: ClassVar[tuple[str, ...]] = ("ip", "memory")
    viewing_program: ClassVar[list[str]] = ["A=0:", "+1 A>=0"]
