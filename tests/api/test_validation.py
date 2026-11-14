"""Arguments that used to be accepted and then fail somewhere else."""

from __future__ import annotations

from pathlib import Path

import pytest

import esolangs
import esolangs.debugger as debugger_api
from esolangs.debugger import STOP_REASONS
from tests.support.pick import first, languages
from tests.support.reference import REFERENCE
from tests.support.vm_support import _debugger


class TestABoundMustBind:
    """``run``'s two budgets, which are the reason the class exists."""

    @pytest.mark.parametrize("max_steps", [-1, "x", 2.5])
    def test_a_bad_step_bound_is_refused(self, max_steps: object) -> None:
        """A negative one ran unbounded: the drive counts *up* to the limit."""
        with pytest.raises(esolangs.ArgumentError, match="max_steps"):
            _debugger().run(limits=esolangs.ExecutionLimits(max_steps=max_steps))

    @pytest.mark.parametrize("timeout", ["x", 0, -1])
    def test_a_bad_timeout_is_refused(self, timeout: object) -> None:
        """``timeout='x'`` reached the arithmetic and leaked a TypeError."""
        with pytest.raises(esolangs.ArgumentError, match="timeout"):
            _debugger().run(limits=esolangs.ExecutionLimits(execution_timeout=timeout))

    def test_a_zero_step_bound_still_means_zero(self) -> None:
        """The refusal must not swallow the one legal edge."""
        assert (
            _debugger().run(limits=esolangs.ExecutionLimits(max_steps=0)) == "max_steps"
        )

    def test_the_stop_reasons_are_enumerable(self) -> None:
        """``StopReason`` is a Literal, so its members needed a data twin."""
        assert set(STOP_REASONS) == {
            "halted",
            "breakpoint",
            "max_steps",
            "execution_timeout",
        }


class TestTheNamespaceIsTheSurface:
    def test_dir_matches_all(self) -> None:
        """``dir()`` also offered ``os``, ``re``, ``signal``, ``threading``."""
        assert dir(esolangs) == sorted(esolangs.__all__)

    def test_a_bad_table_names_the_bad_character(self) -> None:
        """``01a`` was answered with a complaint about its *length*."""
        with pytest.raises(esolangs.TruthTableError, match="only '0' and '1'"):
            esolangs.generate(REFERENCE, "01a")


class TestTheChecksAreSymmetric:
    """Round seven's finding: every one of these was checked on one side."""

    @pytest.mark.parametrize("timeout", ["5", float("inf"), float("nan"), True, 0])
    def test_both_runs_refuse_the_same_timeout(self, timeout: object) -> None:
        with pytest.raises(esolangs.ArgumentError, match="timeout"):
            esolangs.run(
                REFERENCE,
                "+.",
                limits=esolangs.ExecutionLimits(execution_timeout=timeout),
            )
        with pytest.raises(esolangs.ArgumentError, match="timeout"):
            _debugger().run(limits=esolangs.ExecutionLimits(execution_timeout=timeout))

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
            esolangs.run(REFERENCE, program, stdin=stdin)
        with pytest.raises(expected):
            debugger_api.make_debugger(REFERENCE, program, stdin=stdin)

    @pytest.mark.parametrize("text", [5, b"x", ""])
    def test_break_on_output_refuses_a_non_string(self, text: object) -> None:
        """It raised ``'in <string>' requires string`` from the run loop; ``""``
        stopped before the first step."""
        with pytest.raises(esolangs.ArgumentError, match="text must be a"):
            _debugger().break_on_output(text)

    def test_break_when_refuses_a_non_callable(self) -> None:
        with pytest.raises(esolangs.ArgumentError, match="must be callable"):
            _debugger().break_when(42)

    def test_break_when_refuses_the_wrong_arity(self) -> None:
        """A zero-argument lambda failed inside the loop, not at the setter."""
        with pytest.raises(esolangs.ArgumentError, match="one argument"):
            _debugger().break_when(lambda: True)

    def test_break_when_still_takes_a_real_predicate(self) -> None:
        dbg = debugger_api.make_debugger(REFERENCE, "+++", stdin="")
        dbg.break_when(lambda vm: bool(vm.memory) and vm.memory[0] == 2)
        assert dbg.run(limits=esolangs.ExecutionLimits(max_steps=10)) == "breakpoint"


class TestTerminationPolarityIsData:
    """The one convention a zero-branch verifier still had to hardcode."""

    @pytest.mark.parametrize("name", languages(answer_mode="termination"))
    def test_the_polarity_is_reported(self, name: str) -> None:
        facts = esolangs.describe(name)
        assert facts.answer_mode == "termination"
        assert facts.answer_encoding == ("halts", "diverges")

    def test_a_printing_language_still_reports_digits(self) -> None:
        assert esolangs.describe(REFERENCE).answer_encoding == ("0", "1")


@pytest.mark.parametrize("method", ["break_at", "break_on_cell"])
def test_debugger_rejects_huge_invalid_arguments(method) -> None:
    from esolangs.debugger import make_debugger
    from esolangs.exceptions import ArgumentError

    debugger = make_debugger(REFERENCE, "")
    huge = 10**5000
    call = (
        (lambda: debugger.break_at((huge,)))
        if method == "break_at"
        else lambda: debugger.break_on_cell(0, [huge])
    )
    with pytest.raises(ArgumentError):
        call()


class TestOneOperationOneSpelling:
    """Each operation is a module function and a bound method, spelled alike."""

    def test_a_debugger_refuses_a_limit_it_cannot_enforce(self) -> None:
        """Output, memory and whole-invocation budgets need a worker."""
        for limit in (
            {"max_output": 1},
            {"max_memory": 1},
            {"total_timeout": 1},
            {"preparation_timeout": 1},
        ):
            with pytest.raises(esolangs.ArgumentError, match=next(iter(limit))):
                _debugger().run(limits=esolangs.ExecutionLimits(**limit))
        with pytest.raises(esolangs.ArgumentError, match="ExecutionLimits"):
            _debugger().run(limits=5)  # type: ignore[arg-type]

    def test_every_language_function_is_a_method(self) -> None:
        """``to_file`` had no ``from_file``; five methods had no function."""
        import inspect

        import esolangs.debugger as debugger_api

        functions = {
            name: getattr(module, name)
            for module in (esolangs, debugger_api)
            for name in module.__all__
            if inspect.isfunction(getattr(module, name))
        }
        del functions["list_languages"]
        methods = {
            name
            for name, member in vars(esolangs.Language).items()
            if inspect.isfunction(member) and not name.startswith("_")
        }
        assert methods == {*functions, "settings"}
        for name, function in functions.items():
            unbound = list(inspect.signature(function).parameters.values())
            bound = list(
                inspect.signature(getattr(esolangs.Language, name)).parameters.values()
            )
            assert (unbound[0].name, unbound[-1].name) == ("language", "catalog")
            assert [(p.name, p.kind, p.default) for p in unbound[1:-1]] == [
                (p.name, p.kind, p.default) for p in bound[1:]
            ], name

    def test_the_bound_and_unbound_spellings_agree(self, tmp_path: Path) -> None:
        bound = esolangs.Language(REFERENCE)
        path = tmp_path / "program"
        esolangs.to_file(REFERENCE, "+.", path)
        assert esolangs.from_file(REFERENCE, path) == bound.from_file(path)
        assert esolangs.from_source(REFERENCE, "+.") == bound.from_source("+.")
        assert esolangs.execute(REFERENCE, "+.") == bound.execute("+.")
        assert esolangs.prepare(REFERENCE, "+.").run() == bound.run("+.")
        artifact = esolangs.generate(REFERENCE, "0110")
        assert esolangs.evaluate(REFERENCE, artifact, [0, 1]).answer == "1"
        assert bound.make_vm("+.").ip == bound.prepare("+.").make_vm().ip
        for debugger in (
            bound.make_debugger("+."),
            bound.prepare("+.").make_debugger(),
        ):
            assert debugger.run() == "halted"
            assert debugger.output == "\x01"

    def test_to_file_takes_settings_as_every_program_reader_does(
        self, tmp_path: Path
    ) -> None:
        """A bare raster's PNG could not record the dialect it was written in."""
        name = first(source_kind="raster", boolean_generator=True)
        bound = esolangs.Language(name)
        raster = bound.generate("01").source
        bound.to_file(raster, tmp_path / "bare.png")
        bound.to_file(raster, tmp_path / "kept.png", settings=bound.settings())
        assert bound.from_file(tmp_path / "bare.png").settings is None
        assert bound.from_file(tmp_path / "kept.png").settings == bound.settings()
        with pytest.raises(esolangs.ArgumentError, match="belong to"):
            esolangs.to_file(
                REFERENCE, "+.", tmp_path / "refused", settings=bound.settings()
            )

    def test_an_absent_scale_is_none_everywhere(self) -> None:
        """``generate`` alone defaulted to 1; a text language refused only 2."""
        name = first(source_kind="raster", boolean_generator=True)
        assert esolangs.generate(name, "01") == esolangs.generate(name, "01", scale=1)
        assert esolangs.generate(REFERENCE, "01", scale=1).scale is None
