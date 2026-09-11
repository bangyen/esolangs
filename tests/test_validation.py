"""Arguments that used to be accepted and then fail somewhere else.

A bound that does not bind, a breakpoint that never fires, a width that is
silently ignored: each of these was taken without complaint and went wrong
later, in a place that named neither the value nor the call that supplied
it.  ``max_steps=-1`` is the sharpest -- it disabled the bound entirely, in
the one tool whose job is stopping a runaway.
"""

from __future__ import annotations

import pytest

import esolangs
from esolangs.debugger import STOP_REASONS


def _debugger() -> esolangs.Debugger:
    return esolangs.make_debugger("brainfuck", "+[]", stdin="")


class TestABoundMustBind:
    """``run``'s two budgets, which are the reason the class exists."""

    @pytest.mark.parametrize("max_steps", [-1, -100, "x", 2.5])
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


class TestABreakpointMustBeAbleToFire:
    """A breakpoint that can never match is worse than a refused one."""

    @pytest.mark.parametrize("ip", ["x", 1.5, None])
    def test_a_non_position_is_refused(self, ip: object) -> None:
        with pytest.raises(esolangs.ArgumentError, match="ip must be"):
            _debugger().break_at(ip)  # type: ignore[arg-type]

    def test_a_grid_coordinate_is_still_accepted(self) -> None:
        """A 2D language's ``ip`` is a tuple, so that spelling must pass.

        Checked against Streetcode, whose ``ip`` really is a coordinate,
        rather than against a tape language where a tuple could never match
        and the test would pass for the wrong reason.
        """
        program = esolangs.generate("Streetcode", "0110")
        dbg = esolangs.make_debugger(
            "Streetcode", program, stdin=esolangs.encode_inputs("Streetcode", [0, 1])
        )
        assert isinstance(dbg.ip, tuple)
        dbg.break_at(dbg.ip)
        assert dbg.run(max_steps=5) == "breakpoint"

    def test_a_non_integer_cell_value_is_refused(self) -> None:
        with pytest.raises(esolangs.ArgumentError, match="value must be"):
            _debugger().break_on_cell(0, "x")  # type: ignore[arg-type]

    @pytest.mark.parametrize("index", [-5, "x"])
    def test_a_bad_watch_index_is_refused(self, index: object) -> None:
        """``watch_cell(-5)`` raised a bare IndexError from a later run."""
        with pytest.raises(esolangs.ArgumentError, match="index"):
            _debugger().watch_cell(index)  # type: ignore[arg-type]


class TestWidthIsCheckedWhereverItIsTaken:
    """``generate`` refused these and ``instantiate`` ignored them."""

    @pytest.mark.parametrize("width", [0, -2, "8", 2.5])
    def test_instantiate_refuses_what_generate_refuses(self, width: object) -> None:
        template = esolangs.generate("Minifuck", "0110")
        with pytest.raises(esolangs.ArgumentError, match="width"):
            esolangs.instantiate("Minifuck", template, [1, 0], width)  # type: ignore[arg-type]

    @pytest.mark.parametrize("width", [0, -2, "8", 2.5])
    def test_generate_still_refuses_them(self, width: object) -> None:
        with pytest.raises(esolangs.ArgumentError, match="width"):
            esolangs.generate("brainfuck", "0110", width)  # type: ignore[arg-type]


class TestTheEncodersRefuseWhatTheyCannotAnswer:
    """Each says so rather than returning something plausible."""

    def test_encode_inputs_refuses_a_language_that_reads_nothing(self) -> None:
        """It returned stdin for a program with no input command."""
        with pytest.raises(esolangs.ArgumentError, match="reads no stdin"):
            esolangs.encode_inputs("123", [0, 1])

    def test_read_answer_refuses_a_non_string(self) -> None:
        with pytest.raises(esolangs.ProgramError, match="output must be a string"):
            esolangs.read_answer("brainfuck", None)  # type: ignore[arg-type]


class TestTheNamespaceIsTheSurface:
    def test_dir_matches_all(self) -> None:
        """``dir()`` also offered ``os``, ``re``, ``signal``, ``threading``."""
        assert dir(esolangs) == sorted(esolangs.__all__)

    def test_a_bad_table_names_the_bad_character(self) -> None:
        """``01a`` was answered with a complaint about its *length*."""
        with pytest.raises(esolangs.TruthTableError, match="only '0' and '1'"):
            esolangs.generate("brainfuck", "01a")


class TestTheChecksAreSymmetric:
    """Round seven's finding: every one of these was checked on one side.

    ``Debugger.run`` validated its timeout and ``run`` did not; three
    breakpoint setters validated and two did not; ``run`` checked its
    program and ``make_vm`` did not.  So these assert the *pair*, not the
    single call -- a check added to one side again would fail here.
    """

    @pytest.mark.parametrize("timeout", ["5", float("inf"), float("nan"), True, 0, -1])
    def test_both_runs_refuse_the_same_timeout(self, timeout: object) -> None:
        with pytest.raises(esolangs.ArgumentError, match="timeout"):
            esolangs.run("brainfuck", "+.", timeout=timeout)  # type: ignore[arg-type]
        with pytest.raises(esolangs.ArgumentError, match="timeout"):
            _debugger().run(timeout=timeout)  # type: ignore[arg-type]

    @pytest.mark.parametrize(
        ("program", "stdin"), [(None, ""), (42, ""), ("+", None), ("+", ["0"])]
    )
    def test_both_entry_points_refuse_the_same_program(
        self, program: object, stdin: object
    ) -> None:
        with pytest.raises(esolangs.ProgramError):
            esolangs.run("brainfuck", program, stdin)  # type: ignore[arg-type]
        with pytest.raises(esolangs.ProgramError):
            esolangs.make_debugger("brainfuck", program, stdin)  # type: ignore[arg-type]

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
        dbg = esolangs.make_debugger("brainfuck", "+++", stdin="")
        dbg.break_when(lambda vm: bool(vm.memory) and vm.memory[0] == 2)
        assert dbg.run(max_steps=10) == "breakpoint"


class TestBitsAreBits:
    """The container as well as the elements."""

    @pytest.mark.parametrize("bits", [None, "10", {0: 1, 1: 0}, [], [1.0, 0.0]])
    def test_both_encoders_refuse_the_same_bits(self, bits: object) -> None:
        """A dict was iterated as its *keys*, answering a different row."""
        with pytest.raises(esolangs.ArgumentError, match="bits"):
            esolangs.encode_inputs("brainfuck", bits)  # type: ignore[arg-type]
        template = esolangs.generate("Minifuck", "0110")
        with pytest.raises(esolangs.ArgumentError, match="bits"):
            esolangs.instantiate("Minifuck", template, bits)  # type: ignore[arg-type]

    def test_a_non_string_template_is_refused(self) -> None:
        with pytest.raises(esolangs.TemplateError, match="template must be"):
            esolangs.instantiate("Minifuck", None, [1, 0])  # type: ignore[arg-type]


class TestTerminationPolarityIsData:
    """The one convention a zero-branch verifier still had to hardcode."""

    @pytest.mark.parametrize("name", ["123", "ArrowQueue", "Point Break"])
    def test_the_polarity_is_reported(self, name: str) -> None:
        facts = esolangs.describe(name)
        assert facts["answer_mode"] == "termination"
        assert facts["answer_encoding"] == ("halts", "diverges")

    def test_a_printing_language_still_reports_digits(self) -> None:
        assert esolangs.describe("brainfuck")["answer_encoding"] == ("0", "1")


class TestNameResolutionIsTrulyCaseInsensitive:
    """The usage text promises it for every name, including the odd ones."""

    @pytest.mark.parametrize(
        "spelling", ["CV(N)(C)", "cv(n)(c)", "CV(n)(c)", "cvnc", "CVNC"]
    )
    def test_the_overridden_name_folds_too(self, spelling: str) -> None:
        """Its id came from an exact-key override, so only one case matched."""
        assert esolangs.describe(spelling)["name"] == "CV(N)(C)"

    def test_every_display_name_resolves_from_any_case(self) -> None:
        for name in esolangs.list_languages():
            assert esolangs.describe(name.upper())["name"] == name
            assert esolangs.describe(name.lower())["name"] == name
