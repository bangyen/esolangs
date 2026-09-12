"""Contracts the public API owes a caller who has only read the docs.

Each test here pins a behaviour that a blind usability pass found missing:
a template that ran as a program and answered wrong, a language name that
differed from the one the CLI printed, a breakpoint that could not be
resumed past.  They are grouped by the promise they keep rather than by the
function they call, because that is how the caller met them.
"""

import importlib
import inspect
import pathlib
from pathlib import Path

import pytest

import esolangs
from esolangs.exceptions import (
    ArgumentError,
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
            # A bad stdin is an ArgumentError, not a ProgramError: the stdin
            # is not the program.  Either way it is an EsolangError, which is
            # what this class is about.
            (lambda: esolangs.run("brainfuck", ",.", stdin=["0"]), ArgumentError),
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
        """``run()`` with no budget hangs on a program that never halts.

        Both bounds report through the return value.  A timeout used to
        raise while ``max_steps`` returned, so a caller bounding a runaway
        both ways needed a ``try`` around a call whose stated job is to say
        why it stopped.
        """
        dbg = esolangs.make_debugger("brainfuck", "+[]", stdin="")
        assert dbg.run(timeout=1) == "timeout"
        assert not dbg.halted


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


class TestConventionsAreDiscoverable:
    """How to feed a language, and how to read its answer, are askable."""

    def test_grapheme_names_its_input_alphabet(self) -> None:
        """Digits are read as truthy, so 0/1 lines answer the wrong row."""
        assert esolangs.describe("Grapheme")["input_encoding"] == ("%", "A")
        assert esolangs.describe("brainfuck")["input_encoding"] == ("0", "1")

    def test_the_named_alphabet_is_the_one_that_works(self) -> None:
        """The point of the key: using it reproduces the truth table."""
        zero, one = esolangs.describe("Grapheme")["input_encoding"]  # type: ignore[misc]
        program = esolangs.generate("Grapheme", XOR)
        got = "".join(
            esolangs.run(
                "Grapheme", program, stdin=f"{[zero, one][a]}\n{[zero, one][b]}\n"
            )
            for a in (0, 1)
            for b in (0, 1)
        )
        assert got == XOR

    @pytest.mark.parametrize("name", ["123", "ArrowQueue", "Point Break", "Fargo"])
    def test_a_language_that_needs_explaining_explains_itself(self, name: str) -> None:
        """Termination-as-answer and Fargo's row index are not guessable."""
        assert esolangs.describe(name)["answer_convention"]

    def test_a_plain_printer_needs_no_note(self) -> None:
        assert esolangs.describe("brainfuck")["answer_convention"] is None


class TestEveryDeliberateErrorIsCatchable:
    """The package docstring's promise, checked against the interpreters."""

    @pytest.mark.parametrize(
        ("language", "source"),
        [
            ("brainfuck", "[[["),
            ("Sophie", "{{{"),
            ("Streetcode", "zzz"),
            ("Grapheme", "abc"),
        ],
    )
    def test_a_malformed_program_is_a_programerror(
        self, language: str, source: str
    ) -> None:
        """They were bare ValueErrors, so the documented base class missed."""
        with pytest.raises(ProgramError) as exc:
            esolangs.run(language, source, timeout=5)
        assert isinstance(exc.value, EsolangError)
        assert str(exc.value)

    def test_every_committed_example_runs_from_its_described_path(self) -> None:
        """describe() handed out paths run() choked on: the file's newline."""
        failures = []
        for name in esolangs.list_languages():
            facts = esolangs.describe(name)
            if facts["parameterized"] or facts["answer_convention"]:
                continue  # needs bits embedded, or answers by terminating
            zero, one = facts["input_encoding"]  # type: ignore[misc]
            for example in facts["examples"]:  # type: ignore[union-attr]
                try:
                    esolangs.run(
                        name,
                        pathlib.Path(ROOT / example),
                        stdin=f"{zero}\n{one}\n",
                        timeout=20,
                    )
                except EsolangError as exc:
                    failures.append(f"{name}: {type(exc).__name__}: {exc}")
        assert failures == []


class TestInstantiateValidates:
    """A wrong call is refused where it is made, not one layer downstream."""

    def test_the_bit_count_must_match_the_slots(self) -> None:
        template = esolangs.generate("Minifuck", XOR)
        with pytest.raises(TemplateError, match="2 input slots, but 1 bit was given"):
            esolangs.instantiate("Minifuck", template, [1])

    def test_a_bit_must_be_a_bit(self) -> None:
        """``2`` was substituted silently into a program that then lied.

        An :class:`ArgumentError` rather than a ``TemplateError``: the
        template is fine, the argument is not, and the same check now backs
        ``encode_inputs`` -- which has no template to complain about.
        """
        template = esolangs.generate("Minifuck", XOR)
        with pytest.raises(esolangs.ArgumentError, match="must each be 0 or 1"):
            esolangs.instantiate("Minifuck", template, [2, 0])


class TestNoTwoNamesDisagree:
    """One question, one answer."""

    def test_width_awareness_has_a_single_spelling(self) -> None:
        """``esolangs.takes_width`` took a function and answered False here."""
        assert not hasattr(esolangs, "takes_width")
        assert esolangs.describe("LaserFuck")["width_aware"] is True

    def test_the_debugger_stop_reason_type_is_exported(self) -> None:
        assert "StopReason" in esolangs.__all__


class TestTheSignaturesAgreeWithThemselves:
    """Two functions taking the same argument should describe it the same.

    Found by reading the public signatures side by side rather than by
    using any one of them, which is the view a caller writing against the
    package gets and no single call ever shows.
    """

    def test_bits_is_annotated_the_same_in_both_places(self) -> None:
        """``encode_inputs`` promised more than it accepts.

        It was annotated ``Sequence[int]`` while ``instantiate`` said
        ``list[int] | tuple[int, ...]``, and *both* refuse anything else at
        runtime -- so a typed caller passing a ``range`` got mypy's
        approval and an ``ArgumentError``.  The narrow one was the true
        one.
        """
        annotations = {
            fn.__name__: inspect.signature(fn).parameters["bits"].annotation
            for fn in (esolangs.encode_inputs, esolangs.instantiate)
        }
        assert len(set(annotations.values())) == 1, annotations

    @pytest.mark.parametrize(
        "call",
        [
            lambda bits: esolangs.encode_inputs("brainfuck", bits),
            lambda bits: esolangs.instantiate(
                "Minifuck", esolangs.generate("Minifuck", "0110"), bits
            ),
        ],
    )
    def test_both_accept_and_refuse_the_same_things(self, call: object) -> None:
        """The annotation is only right while the behaviour matches it."""
        call([1, 0])  # type: ignore[operator]
        call((1, 0))  # type: ignore[operator]
        with pytest.raises(esolangs.ArgumentError, match="list or tuple"):
            call(range(2))  # type: ignore[operator]

    def test_the_default_sentinel_reads_as_a_default(self) -> None:
        """``help`` showed a memory address that changed every run.

        ``timeout: float | esolangs._Default | None = <esolangs._Default
        object at 0x105fa12b0>`` is documentation nobody can use; the
        sentinel means "omit this", so it says so.
        """
        for fn in (esolangs.evaluate, esolangs.verify):
            rendered = str(inspect.signature(fn))
            assert "<default>" in rendered, fn.__name__
            assert "object at 0x" not in rendered, fn.__name__

    def test_language_is_first_everywhere(self) -> None:
        """The one argument every public call shares, in the same place."""
        for name in esolangs.__all__:
            attribute = getattr(esolangs, name)
            if not inspect.isfunction(attribute):
                continue
            first = next(iter(inspect.signature(attribute).parameters), None)
            if first in {None, "output", "truth_table"}:
                continue
            assert first == "language", (name, first)


class TestDescribeHasANameableType:
    """``dict[str, object]`` was accurate and useless.

    Every field access needed a cast, and ``mypy --strict`` over an
    ordinary consumer program reported five errors, all of them this one.
    The docstring already specified every key; ``LanguageInfo`` is that
    specification in a form a type checker can read.
    """

    def test_it_is_exported(self) -> None:
        """A type you cannot name is a type you cannot annotate with."""
        assert "LanguageInfo" in esolangs.__all__
        assert esolangs.LanguageInfo.__doc__

    def test_every_key_is_declared(self) -> None:
        """The TypedDict and the dict must not drift apart."""
        declared = set(esolangs.LanguageInfo.__annotations__)
        assert declared == set(esolangs.describe("brainfuck"))

    def test_every_language_matches_the_declared_types(self) -> None:
        """Declared from a survey of all 69, so it is checked against all 69.

        A TypedDict is not enforced at runtime, so nothing but this notices
        a language whose field is a different shape.
        """
        import typing

        hints = typing.get_type_hints(esolangs.LanguageInfo)
        for name in esolangs.list_languages():
            for key, value in esolangs.describe(name).items():
                expected = hints[key]
                if expected is str:
                    assert isinstance(value, str), (name, key)
                elif expected is bool:
                    assert isinstance(value, bool), (name, key)
                elif expected == list[str]:
                    assert isinstance(value, list), (name, key)
                    assert all(isinstance(v, str) for v in value), (name, key)
                elif expected == tuple[str, str]:
                    assert isinstance(value, tuple), (name, key)
                    assert len(value) == 2, (name, key)
                else:  # the two that may be None
                    assert value is None or isinstance(value, str), (name, key)

    def test_the_four_machine_traits_are_still_carried(self) -> None:
        """They were merged with ``**``, which a TypedDict cannot verify.

        Spelling them out is what let the type land, and it means a
        renamed trait is now a type error rather than a silently missing
        key.
        """
        facts = esolangs.describe("RAM0")
        for key in (
            "self_halts",
            "dumps_on_the_post_halt_step",
            "steppable_to_answer",
            "eof_is_a_value",
        ):
            assert isinstance(facts[key], bool), key  # type: ignore[literal-required]


class TestSpecAbortsRatherThanReturningNothing:
    """``-OO`` strips docstrings, and ``spec`` read one.

    So it returned ``""`` for all 69 languages -- a silent wrong answer
    from the function whose whole promise is that it cannot go stale.
    """

    def test_it_raises_when_there_is_no_docstring(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Simulated by emptying one, since the test run is not under -OO."""
        module = importlib.import_module(
            "esolangs.interpreters."
            + str(esolangs.describe("brainfuck")["interpreter"])
        )
        monkeypatch.setattr(module, "__doc__", None)
        with pytest.raises(esolangs.ProgramError, match="-OO"):
            esolangs.spec("brainfuck")

    def test_it_still_returns_the_text_normally(self) -> None:
        """The abort must not have eaten the ordinary path."""
        assert esolangs.spec("brainfuck").startswith("Interpreter for")


class TestAMissingFileIsAFileNotFoundError:
    """``run`` takes an ``os.PathLike``, so a caller writes the stdlib catch.

    It got a ``ProgramError``, which is a ``ValueError`` and not an
    ``OSError``, so ``except FileNotFoundError`` missed it entirely --
    while ``ExecutionTimeoutError`` had been a ``TimeoutError`` all along.
    """

    def test_it_is_catchable_both_ways(self, tmp_path: Path) -> None:
        """Ours for callers who catch ours, the stdlib's for the rest."""
        missing = tmp_path / "absent.bf"
        with pytest.raises(FileNotFoundError):
            esolangs.run("brainfuck", missing, "", 5)
        with pytest.raises(esolangs.EsolangError):
            esolangs.run("brainfuck", missing, "", 5)
        with pytest.raises(esolangs.ProgramError):
            esolangs.run("brainfuck", missing, "", 5)

    def test_an_unreadable_file_is_still_a_plain_program_error(
        self, tmp_path: Path
    ) -> None:
        """Only *absent* is a FileNotFoundError; the rest keep their class."""
        blocked = tmp_path / "blocked.bf"
        blocked.write_bytes(b"\xff\xfe\x00")
        with pytest.raises(esolangs.ProgramError) as caught:
            esolangs.run("brainfuck", blocked, "", 5)
        assert not isinstance(caught.value, FileNotFoundError)

    def test_version_is_not_star_imported(self) -> None:
        """``from esolangs import *`` injected a dunder into the namespace."""
        assert "__version__" not in esolangs.__all__
        assert esolangs.__version__  # still reachable by name
