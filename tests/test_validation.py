"""Arguments that used to be accepted and then fail somewhere else."""

from __future__ import annotations

import pytest

import esolangs
import esolangs.debugger as debugger_api
from esolangs.debugger import STOP_REASONS
from tests.pick import languages


def _debugger() -> debugger_api.Debugger:
    return debugger_api.make_debugger("brainfuck", "+[]", stdin="")


class TestABoundMustBind:
    """``run``'s two budgets, which are the reason the class exists."""

    @pytest.mark.parametrize("max_steps", [-1, "x", 2.5])
    def test_a_bad_step_bound_is_refused(self, max_steps: object) -> None:
        """A negative one ran unbounded: the drive counts *up* to the limit."""
        with pytest.raises(esolangs.ArgumentError, match="max_steps"):
            _debugger().run(max_steps=max_steps)  # type: ignore[arg-type]

    @pytest.mark.parametrize("timeout", ["x", 0, -1])
    def test_a_bad_timeout_is_refused(self, timeout: object) -> None:
        """``timeout='x'`` reached the arithmetic and leaked a TypeError."""
        with pytest.raises(esolangs.ArgumentError, match="timeout"):
            _debugger().run(timeout=timeout)  # type: ignore[arg-type]

    def test_a_zero_step_bound_still_means_zero(self) -> None:
        """The refusal must not swallow the one legal edge."""
        assert _debugger().run(max_steps=0) == "max_steps"

    def test_the_stop_reasons_are_enumerable(self) -> None:
        """``StopReason`` is a Literal, so its members needed a data twin."""
        assert set(STOP_REASONS) == {"halted", "breakpoint", "max_steps", "timeout"}


class TestTheNamespaceIsTheSurface:
    def test_dir_matches_all(self) -> None:
        """``dir()`` also offered ``os``, ``re``, ``signal``, ``threading``."""
        assert dir(esolangs) == sorted(esolangs.__all__)

    def test_a_bad_table_names_the_bad_character(self) -> None:
        """``01a`` was answered with a complaint about its *length*."""
        with pytest.raises(esolangs.TruthTableError, match="only '0' and '1'"):
            esolangs.generate("brainfuck", "01a")


class TestTheChecksAreSymmetric:
    """Round seven's finding: every one of these was checked on one side."""

    @pytest.mark.parametrize("timeout", ["5", float("inf"), float("nan"), True, 0])
    def test_both_runs_refuse_the_same_timeout(self, timeout: object) -> None:
        with pytest.raises(esolangs.ArgumentError, match="timeout"):
            esolangs.run("brainfuck", "+.", timeout=timeout)  # type: ignore[arg-type]
        with pytest.raises(esolangs.ArgumentError, match="timeout"):
            _debugger().run(timeout=timeout)  # type: ignore[arg-type]

    @pytest.mark.parametrize(
        ("program", "stdin", "expected"),
        [
            (None, "", esolangs.ProgramError),
            (42, "", esolangs.ProgramError),
            # The stdin is not the program, so a bad one is an argument
            # fault.  The class is parameterized rather than shared because
            # what this asserts is that the *pair* agrees -- and it has to
            # agree on which fault it is, not merely that there was one.
            ("+", None, esolangs.ArgumentError),
            ("+", ["0"], esolangs.ArgumentError),
        ],
    )
    def test_both_entry_points_refuse_the_same_program(
        self, program: object, stdin: object, expected: type[Exception]
    ) -> None:
        with pytest.raises(expected):
            esolangs.run("brainfuck", program, stdin=stdin)  # type: ignore[arg-type]
        with pytest.raises(expected):
            debugger_api.make_debugger("brainfuck", program, stdin=stdin)  # type: ignore[arg-type]

    @pytest.mark.parametrize("text", [None, 5, b"x"])
    def test_break_on_output_refuses_a_non_string(self, text: object) -> None:
        """It raised ``'in <string>' requires string`` from the run loop."""
        with pytest.raises(esolangs.ArgumentError, match="text must be a string"):
            _debugger().break_on_output(text)  # type: ignore[arg-type]

    def test_break_when_refuses_a_non_callable(self) -> None:
        with pytest.raises(esolangs.ArgumentError, match="must be callable"):
            _debugger().break_when(42)  # type: ignore[arg-type]

    def test_break_when_refuses_the_wrong_arity(self) -> None:
        """A zero-argument lambda failed inside the loop, not at the setter."""
        with pytest.raises(esolangs.ArgumentError, match="one argument"):
            _debugger().break_when(lambda: True)  # type: ignore[arg-type,misc]

    def test_break_when_still_takes_a_real_predicate(self) -> None:
        dbg = debugger_api.make_debugger("brainfuck", "+++", stdin="")
        dbg.break_when(lambda vm: bool(vm.memory) and vm.memory[0] == 2)
        assert dbg.run(max_steps=10) == "breakpoint"


class TestTerminationPolarityIsData:
    """The one convention a zero-branch verifier still had to hardcode."""

    @pytest.mark.parametrize("name", languages(answer_mode="termination"))
    def test_the_polarity_is_reported(self, name: str) -> None:
        facts = esolangs.describe(name)
        assert facts["answer_mode"] == "termination"
        assert facts["answer_encoding"] == ("halts", "diverges")

    def test_a_printing_language_still_reports_digits(self) -> None:
        assert esolangs.describe("brainfuck")["answer_encoding"] == ("0", "1")


@pytest.mark.parametrize("method", ["break_at", "break_on_cell"])
def test_debugger_rejects_huge_invalid_arguments(method):
    from esolangs.debugger import make_debugger
    from esolangs.exceptions import ArgumentError

    debugger = make_debugger("brainfuck", "")
    huge = 10**5000
    call = (
        (lambda: debugger.break_at((huge,)))
        if method == "break_at"
        else lambda: debugger.break_on_cell(0, [huge])
    )
    with pytest.raises(ArgumentError):
        call()
