"""Contracts the public API owes a caller who has only read the docs.

Each test here pins a behaviour that a blind usability pass found missing:
a template that ran as a program and answered wrong, a language name that
differed from the one the CLI printed, a breakpoint that could not be
resumed past.  They are grouped by the promise they keep rather than by the
function they call, because that is how the caller met them.
"""

import pathlib

import pytest

import esolangs
from esolangs.exceptions import (
    EsolangError,
    InputExhaustedError,
    ProgramError,
    TemplateError,
    TruthTableError,
    UnknownLanguageError,
)
from esolangs.registry import LANGUAGES, parameterized_ids

XOR = "0110"
ROOT = pathlib.Path(__file__).parents[1]


class TestNameResolution:
    """A language name is matched however the caller spells it."""

    @pytest.mark.parametrize("spelling", ["brainfuck", "Brainfuck", "BRAINFUCK"])
    def test_case_is_ignored(self, spelling: str) -> None:
        """The registry mixes conventions, so a caller cannot guess one."""
        assert esolangs.run(spelling, "+.", timeout=5) == "\x01"

    def test_a_near_miss_is_named(self) -> None:
        """A misspelling is a spelling problem; answer it with the spelling."""
        with pytest.raises(UnknownLanguageError) as exc:
            esolangs.generate("Sophi", XOR)
        assert "did you mean Sophie" in str(exc.value)

    def test_a_wild_miss_still_raises_plainly(self) -> None:
        with pytest.raises(UnknownLanguageError, match="unknown language: zzzz"):
            esolangs.generate("zzzz", XOR)

    def test_every_entry_point_resolves(self) -> None:
        """One helper backs them all, so none can drift out of step."""
        assert esolangs.describe("BRAINFUCK")["name"] == "brainfuck"
        assert esolangs.make_vm("BRAINFUCK", "+").ip == 0
        assert esolangs.make_debugger("BRAINFUCK", "+").ip == 0


class TestParameterizedTemplates:
    """A template is never mistaken for a runnable program."""

    def test_describe_says_so_in_advance(self) -> None:
        facts = esolangs.describe("Minifuck")
        assert facts["parameterized"] is True
        assert facts["reads_input"] is False
        assert esolangs.describe("brainfuck")["parameterized"] is False

    def test_running_one_unfilled_is_refused(self) -> None:
        """Minifuck ignored its slots and reported a constant as the answer."""
        template = esolangs.generate("Minifuck", XOR)
        with pytest.raises(TemplateError) as exc:
            esolangs.run("Minifuck", template)
        assert "{X0}" in str(exc.value)
        assert "instantiate" in str(exc.value)

    def test_instantiating_gives_the_right_answer(self) -> None:
        """The whole point: all four rows, executed."""
        template = esolangs.generate("Minifuck", XOR)
        got = "".join(
            esolangs.run("Minifuck", esolangs.instantiate("Minifuck", template, [a, b]))
            for a in (0, 1)
            for b in (0, 1)
        )
        assert got == XOR

    def test_a_reader_has_nothing_to_instantiate(self) -> None:
        with pytest.raises(TemplateError, match="reads its inputs"):
            esolangs.instantiate("brainfuck", esolangs.generate("brainfuck", XOR), [0])

    def test_the_set_matches_what_the_generators_emit(self) -> None:
        """The definition is behavioural, so nothing can quietly leave it.

        The same set taken from ``parameterized.__all__`` omits Home Row,
        and three documents each named a different subset.
        """
        emits = {
            lang.id
            for lang in LANGUAGES.values()
            if lang.boolean is not None and "{X0}" in str(lang.boolean(XOR))
        }
        assert emits == set(parameterized_ids())


class TestErrorsAreCatchable:
    """``except EsolangError`` is the one handler a caller needs."""

    @pytest.mark.parametrize(
        ("call", "expected"),
        [
            (lambda: esolangs.run("brainfuck", ",.", stdin=""), InputExhaustedError),
            (lambda: esolangs.generate("brainfuck", "011"), TruthTableError),
            (lambda: esolangs.generate("brainfuck", "0121"), TruthTableError),
            (lambda: esolangs.generate("brainfuck", 6), TruthTableError),
            (lambda: esolangs.run("brainfuck", 42), ProgramError),
            (lambda: esolangs.run("brainfuck", ",.", stdin=["0"]), ProgramError),
            (lambda: esolangs.run("Nope", "+"), UnknownLanguageError),
        ],
    )
    def test_it_derives_from_the_base(self, call: object, expected: type) -> None:
        with pytest.raises(expected) as exc:
            call()  # type: ignore[operator]
        assert isinstance(exc.value, EsolangError)
        assert str(exc.value), "an error with no message cannot be acted on"

    def test_exhausted_input_says_how_much_there_was(self) -> None:
        """A bare ``EOFError()`` reached the caller as the empty string."""
        with pytest.raises(InputExhaustedError, match="1 line supplied"):
            esolangs.run("brainfuck", ",,.", stdin="0\n")

    def test_it_is_still_an_eoferror(self) -> None:
        """The repo-wide convention every interpreter documents is unchanged."""
        with pytest.raises(EOFError):
            esolangs.run("brainfuck", ",.", stdin="")


class TestRunTakesSource:
    """``run`` takes a program, and says so when it is handed a path."""

    def test_a_path_string_is_refused(self) -> None:
        """It used to execute the filename and print a null byte."""
        with pytest.raises(ProgramError, match="looks like a path"):
            esolangs.run("brainfuck", "examples/boolean/brainfuck.txt")

    def test_a_path_object_is_read(self) -> None:
        path = ROOT / "examples" / "boolean" / "brainfuck.txt"
        assert esolangs.run("brainfuck", path, stdin="0\n1\n", timeout=30) == "0"

    def test_a_real_program_is_never_mistaken_for_one(self) -> None:
        """The guard needs an existing file, so ordinary source is exempt."""
        assert esolangs.run("brainfuck", "+.", timeout=5) == "\x01"


class TestDebuggerResume:
    """A stopped debugger can be resumed, and says why it stopped."""

    def _debugger(self) -> esolangs.Debugger:
        return esolangs.make_debugger(
            "brainfuck", esolangs.generate("brainfuck", XOR), stdin="1\n0\n"
        )

    def test_output_breakpoint_does_not_deadlock(self) -> None:
        """Output only accumulates, so the condition is true forever after."""
        dbg = self._debugger()
        dbg.break_on_output("1")
        assert dbg.run(max_steps=100000) == "breakpoint"
        assert dbg.run(max_steps=100000) == "halted"
        assert dbg.halted

    def test_the_stop_reason_separates_all_three(self) -> None:
        dbg = esolangs.make_debugger("brainfuck", "++>+<.", stdin="")
        assert dbg.run(max_steps=2) == "max_steps"
        assert dbg.run() == "halted"

    def test_a_position_breakpoint_still_fires_before_its_step(self) -> None:
        """The documented contract: ``break_at`` does not execute that ip."""
        dbg = esolangs.make_debugger("brainfuck", "++>+<.", stdin="")
        dbg.break_at(0)
        assert dbg.run() == "breakpoint"
        assert dbg.ip == 0
        assert dbg.output == ""

    def test_clear_breakpoints_releases_the_run(self) -> None:
        dbg = esolangs.make_debugger("brainfuck", "++>+<.", stdin="")
        dbg.break_at(0)
        dbg.run()
        dbg.clear_breakpoints()
        assert dbg.run() == "halted"

    def test_timeout_bounds_an_unbounded_run(self) -> None:
        """``run()`` with no budget hangs on a program that never halts."""
        dbg = esolangs.make_debugger("brainfuck", "+[]", stdin="")
        with pytest.raises(esolangs.HaltError, match="timeout"):
            dbg.run(timeout=1)


class TestDescribe:
    """``describe`` answers what a caller would otherwise read code for."""

    def test_every_language_finds_its_examples(self) -> None:
        """19 of 69 reported none: the id and the stem are spelled apart."""
        missing = [
            name
            for name in esolangs.list_languages()
            if not esolangs.describe(name)["examples"]
        ]
        assert missing == []

    def test_width_aware_names_the_generators_that_lay_themselves_out(self) -> None:
        """It answered False for all 69: it takes a generator, not a name."""
        aware = [
            name
            for name in esolangs.list_languages()
            if esolangs.describe(name)["width_aware"]
        ]
        assert aware == ["LaserFuck", "Streetcode"]


class TestPackageSurface:
    """What ``dir(esolangs)`` advertises is what the package supports."""

    def test_all_is_declared_and_importable(self) -> None:
        assert esolangs.__all__
        for name in esolangs.__all__:
            assert hasattr(esolangs, name), name

    def test_stdlib_imports_are_not_advertised(self) -> None:
        for leaked in ("importlib", "pathlib", "signal", "threading", "Any"):
            assert leaked not in esolangs.__all__

    def test_version_is_present(self) -> None:
        assert esolangs.__version__
