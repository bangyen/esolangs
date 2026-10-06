"""Contracts the public API owes a caller who has only read the docs."""

import importlib
import inspect
import pathlib
import re
import subprocess
import sys
import threading
from pathlib import Path
from typing import ClassVar

import pytest

import esolangs
import esolangs.debugger as debugger_api
from esolangs import _check_program
from esolangs.exceptions import (
    ArgumentError,
    EsolangError,
    InputExhaustedError,
    ProgramError,
    TemplateError,
    TruthTableError,
    UnknownLanguageError,
)
from esolangs.registry import LANGUAGES
from esolangs.tools.wrap import takes_width
from tests.generator_support import evaluate_generated
from tests.stdin_check import _check_stdin

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


class TestParameterizedTemplates:
    """A template is never mistaken for a runnable program."""

    def test_running_one_unfilled_is_refused(self) -> None:
        """Minifuck ignored its slots and reported a constant as the answer."""
        template = esolangs.generate("Minifuck", XOR)
        with pytest.raises(TemplateError) as exc:
            esolangs.run("Minifuck", template)
        assert "unfilled runs of '$'" in str(exc.value)
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
            (lambda: esolangs.run("zzzz", "+"), UnknownLanguageError),
        ],
    )
    def test_it_derives_from_the_base(self, call: object, expected: type) -> None:
        with pytest.raises(expected) as exc:
            call()  # type: ignore[operator]
        assert isinstance(exc.value, EsolangError)
        assert str(exc.value), "an error with no message cannot be acted on"

    def test_exhausted_input_says_how_much_there_was(self) -> None:
        """A bare ``EOFError()`` reached the caller as the empty string."""
        with pytest.raises(InputExhaustedError, match="1 character supplied"):
            esolangs.run("brainfuck", ",,.", stdin="0")

    def test_it_is_still_an_eoferror(self) -> None:
        """The repo-wide convention every interpreter documents is unchanged."""
        with pytest.raises(EOFError):
            esolangs.run("brainfuck", ",.", stdin="")


class TestDebuggerResume:
    """A stopped debugger can be resumed, and says why it stopped."""

    def _debugger(self) -> debugger_api.Debugger:
        return debugger_api.make_debugger(
            "brainfuck", esolangs.generate("brainfuck", XOR), stdin="10"
        )

    def test_output_breakpoint_does_not_deadlock(self) -> None:
        """Output only accumulates, so the condition is true forever after."""
        dbg = self._debugger()
        dbg.break_on_output("1")
        assert dbg.run(max_steps=100000) == "breakpoint"
        assert dbg.run(max_steps=100000) == "halted"
        assert dbg.halted

    def test_the_stop_reason_separates_all_three(self) -> None:
        dbg = debugger_api.make_debugger("brainfuck", "++>+<.", stdin="")
        assert dbg.run(max_steps=2) == "max_steps"
        assert dbg.run() == "halted"

    def test_a_position_breakpoint_still_fires_before_its_step(self) -> None:
        """The documented contract: ``break_at`` does not execute that ip."""
        dbg = debugger_api.make_debugger("brainfuck", "++>+<.", stdin="")
        dbg.break_at(0)
        assert dbg.run() == "breakpoint"
        assert dbg.ip == 0
        assert dbg.output == ""

    def test_clear_breakpoints_releases_the_run(self) -> None:
        dbg = debugger_api.make_debugger("brainfuck", "++>+<.", stdin="")
        dbg.break_at(0)
        dbg.run()
        dbg.clear_breakpoints()
        assert dbg.run() == "halted"

    def test_timeout_bounds_an_unbounded_run(self) -> None:
        """``run()`` with no budget hangs on a program that never halts."""
        dbg = debugger_api.make_debugger("brainfuck", "+[]", stdin="")
        assert dbg.run(timeout=0.01) == "timeout"
        assert not dbg.halted


class TestDescribe:
    """``describe`` answers what a caller would otherwise read code for."""

    def test_every_language_finds_its_examples(self) -> None:
        """A fifth reported none: the id and the stem are spelled apart."""
        missing = [
            name
            for name in esolangs.list_languages()
            if esolangs.describe(name)["boolean_generator"]
            and not esolangs.describe(name)["examples"]
        ]
        assert missing == []

    def test_width_aware_names_the_generators_that_lay_themselves_out(self) -> None:
        """It answered False for every one: it takes a generator, not a name."""
        aware = {
            name
            for name in esolangs.list_languages()
            if esolangs.describe(name)["width_aware"]
        }
        signature = {
            name
            for name, lang in LANGUAGES.items()
            if (generator := lang.boolean) is not None and takes_width(generator)
        }
        assert aware == signature
        assert aware, "no generator lays itself out; the flag guards nothing"


class TestPackageSurface:
    """What ``dir(esolangs)`` advertises is what the package supports."""

    def test_all_is_exactly_the_public_surface(self) -> None:
        """Adding or removing a public name is a deliberate edit here."""
        assert sorted(esolangs.__all__) == [
            "ArgumentError",
            "DialectSettings",
            "EsolangError",
            "ExecutionTimeoutError",
            "GeneratorCapError",
            "HaltError",
            "InputExhaustedError",
            "InputMismatchWarning",
            "InputSource",
            "InterpreterLimitError",
            "Language",
            "LanguageInfo",
            "MissingDependencyError",
            "Program",
            "ProgramError",
            "ProgramNotFoundError",
            "ProgramSource",
            "Raster",
            "TemplateError",
            "TruthTableError",
            "UnknownLanguageError",
            "describe",
            "dump_program",
            "encode_inputs",
            "generate",
            "instantiate",
            "list_languages",
            "load_program",
            "read_answer",
            "run",
        ]

    @pytest.mark.parametrize("language", ["Minifuck", "brainfuck"])
    def test_check_runnable_refuses_a_non_source(self, language: str) -> None:
        """An int leaked a TypeError for a template language and passed elsewhere."""
        with pytest.raises(esolangs.ProgramError, match="string of source"):
            _check_program(language, 5)  # type: ignore[arg-type]


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

    @pytest.mark.parametrize("name", ["123", "ArrowQueue", "Fargo"])
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

    # Runs every committed example through `run`, which is the `medium`
    # rule exactly.  It sat in the fast band at ~1.07s against its 1s floor,
    # so it passed alone and failed whenever the gate ran a second step
    # beside pytest.
    @pytest.mark.medium
    def test_every_committed_example_runs_from_its_described_path(self) -> None:
        """describe() handed out paths run() choked on: the file's newline."""
        failures = []
        for name in esolangs.list_languages():
            facts = esolangs.describe(name)
            if facts["parameterized"] or facts["answer_convention"]:
                continue  # needs bits embedded, or answers by terminating
            for example in facts["examples"]:  # type: ignore[union-attr]
                try:
                    esolangs.run(
                        name,
                        pathlib.Path(ROOT / example),
                        stdin=esolangs.encode_inputs(name, [0, 1]),
                        timeout=20,
                    )
                except EsolangError as exc:
                    failures.append(f"{name}: {type(exc).__name__}: {exc}")
        assert failures == []


class TestInstantiateValidates:
    """A wrong call is refused where it is made, not one layer downstream."""

    def test_the_bit_count_must_match_the_slots(self) -> None:
        template = esolangs.generate("Minifuck", XOR)
        with pytest.raises(TemplateError, match="2 inputs, but 1 bit was given"):
            esolangs.instantiate("Minifuck", template, [1])

    def test_a_bit_must_be_a_bit(self) -> None:
        """``2`` was substituted silently into a program that then lied."""
        template = esolangs.generate("Minifuck", XOR)
        with pytest.raises(esolangs.ArgumentError, match="must each be 0 or 1"):
            esolangs.instantiate("Minifuck", template, [2, 0])

    def test_a_non_string_template_is_refused_before_provenance(self) -> None:
        """With a table, ``_is_template_for`` called ``.replace`` on the value."""
        with pytest.raises(TemplateError, match="must be the string"):
            esolangs.instantiate("Minifuck", 5, [1], None, XOR)  # type: ignore[arg-type]


class TestTheSignaturesAgreeWithThemselves:
    """Two functions taking the same argument should describe it the same."""

    def test_bits_is_annotated_the_same_in_both_places(self) -> None:
        """``encode_inputs`` promised more than it accepts."""
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


class TestDescribeHasANameableType:
    """``dict[str, object]`` was accurate and useless."""

    def test_it_is_exported(self) -> None:
        """A type you cannot name is a type you cannot annotate with."""
        assert "LanguageInfo" in esolangs.__all__
        assert esolangs.LanguageInfo.__doc__

    def test_every_key_is_declared(self) -> None:
        """The TypedDict and the dict must not drift apart."""
        declared = set(esolangs.LanguageInfo.__annotations__)
        assert declared == set(esolangs.describe("brainfuck"))

    def test_every_language_matches_the_declared_types(self) -> None:
        """Declared from a survey of every one, so it is checked against them all."""
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
                elif typing.get_origin(expected) is dict:
                    assert isinstance(value, dict), (name, key)
                    assert all(isinstance(k, str) for k in value), (name, key)
                    assert all(isinstance(v, dict) for v in value.values()), (name, key)
                elif expected == int | None:
                    assert value is None or type(value) is int, (name, key)
                elif key == "proof_status":
                    assert value is None or isinstance(value, dict), (name, key)
                    if value is not None:
                        declared = next(
                            kind
                            for kind in typing.get_args(expected)
                            if typing.is_typeddict(kind)
                        )
                        assert set(value) == set(declared.__annotations__), (name, key)
                else:  # the two strings that may be None
                    assert value is None or isinstance(value, str), (name, key)

    def test_the_four_machine_traits_are_still_carried(self) -> None:
        """They were merged with ``**``, which a TypedDict cannot verify."""
        facts = esolangs.describe("RAM0")
        for key in (
            "self_halts",
            "dumps_on_the_post_halt_step",
            "steppable_to_answer",
            "eof_is_a_value",
        ):
            assert isinstance(facts[key], bool), key  # type: ignore[literal-required]


class TestSpecAbortsRatherThanReturningNothing:
    """``-OO`` strips docstrings, and ``spec`` read one."""

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
            esolangs.describe("brainfuck")["spec"]

    def test_it_still_returns_the_text_normally(self) -> None:
        """The abort must not have eaten the ordinary path."""
        assert esolangs.describe("brainfuck")["spec"].startswith("Interpreter for")

    def test_a_raster_language_returns_its_own_module_docstring(self) -> None:
        """Piet describes its own interpreter rather than Line's."""
        piet = importlib.import_module("esolangs.interpreters.stack_based.piet")
        line = importlib.import_module("esolangs.interpreters.tape_based.line")
        assert esolangs.describe("Piet")["spec"] == (piet.__doc__ or "").strip()
        assert esolangs.describe("Piet")["spec"] != (line.__doc__ or "").strip()


class TestAMissingFileIsAFileNotFoundError:
    """``run`` takes an ``os.PathLike``, so a caller writes the stdlib catch."""

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

    def test_a_directory_is_an_os_error_not_a_decode_error(
        self, tmp_path: Path
    ) -> None:
        """The third clause: an ``OSError`` that is not ``FileNotFoundError``."""
        with pytest.raises(esolangs.ProgramError) as caught:
            esolangs.run("brainfuck", tmp_path, "", 5)
        assert not isinstance(caught.value, FileNotFoundError)
        assert "cannot read" in str(caught.value)

    def test_a_pathlike_returning_a_non_str_is_a_program_error(self) -> None:
        """``__fspath__`` returning a non-str made ``pathlib`` raise ``TypeError``."""

        class Bad:
            def __fspath__(self) -> int:
                return 5

        with pytest.raises(esolangs.ProgramError) as caught:
            _check_program("brainfuck", Bad())
        assert "cannot read" in str(caught.value)


class TestAMistypedPathIsNotRunAsAProgram:
    """The guard keyed on ``os.path.exists``, so it fired on the mistake
    you would have noticed anyway and missed the one you would not.
    """

    @pytest.mark.parametrize(
        "argument",
        ["/tmp/definitely-not-here.txt", "programs/xor.txt", "nope.txt", r"a\\b.txt"],
    )
    def test_a_path_that_does_not_exist_is_refused(self, argument: str) -> None:
        """Existence is exactly what it must not depend on."""
        assert not pathlib.Path(argument).exists()
        with pytest.raises(esolangs.ProgramError, match="looks like a path"):
            esolangs.run("brainfuck", argument, "", 5)

    def test_a_path_that_does_exist_is_still_refused(
        self, tmp_path: pathlib.Path
    ) -> None:
        """The case that already worked has to keep working."""
        path = tmp_path / "p.txt"
        path.write_text("+++.")
        with pytest.raises(esolangs.ProgramError, match="looks like a path"):
            esolangs.run("brainfuck", str(path), "", 5)

    def test_every_entry_point_agrees(self) -> None:
        """All four take a program, so all four have to refuse the same thing."""
        for call in (
            lambda: esolangs.run("brainfuck", "nope.txt", "", 5),
            lambda: _check_program("brainfuck", "nope.txt", ""),
            lambda: debugger_api.make_vm("brainfuck", "nope.txt", ""),
            lambda: debugger_api.make_debugger("brainfuck", "nope.txt", ""),
        ):
            with pytest.raises(esolangs.ProgramError, match="looks like a path"):
                call()

    def test_a_real_program_is_untouched(self) -> None:
        """A guard that refuses real programs is worse than the bug."""
        assert esolangs.run("brainfuck", "+++.", "", 5) == "\x03"

    def test_no_committed_example_looks_like_a_path(self) -> None:
        """The claim the widened rule rests on, checked rather than asserted."""
        for path in sorted(pathlib.Path("examples").glob("*.txt")):
            text = path.read_text()
            assert not ("\n" not in text and text.endswith(".txt")), path.name

    def test_a_pathlib_path_is_read_in_both_directions(
        self, tmp_path: pathlib.Path
    ) -> None:
        """A Path was always correct, and stays the way to say "this file"."""
        path = tmp_path / "p.txt"
        path.write_text("+++.")
        assert esolangs.run("brainfuck", path, "", 5) == "\x03"
        with pytest.raises(FileNotFoundError):
            esolangs.run("brainfuck", tmp_path / "absent.txt", "", 5)


# 2.2s over 12 tests: runs a diverging program to its bound.
@pytest.mark.medium
class TestTheThreadRefusalNamesAWayThrough:
    """A worker thread had two options and no third."""

    @staticmethod
    def _off_thread(work: object) -> object:
        """Run ``work`` on a worker thread and hand back what it produced."""
        box: dict[str, object] = {}

        def target() -> None:
            try:
                box["value"] = work()  # type: ignore[operator]
            except BaseException as exc:
                box["value"] = exc

        thread = threading.Thread(target=target)
        thread.start()
        thread.join(60)
        assert not thread.is_alive(), "the worker never finished"
        return box["value"]

    def test_the_message_names_the_debugger_route(self) -> None:
        """Naming a route is a claim; the test below runs it."""
        outcome = self._off_thread(lambda: esolangs.run("brainfuck", "+++.", "", 5))
        assert isinstance(outcome, esolangs.ArgumentError)
        message = str(outcome)
        assert "make_debugger" in message

    def test_the_debugger_route_bounds_a_diverging_program(self) -> None:
        """The one that matters: a program that never halts, on a thread."""
        template = esolangs.generate("123", "0110")
        program = esolangs.instantiate("123", template, [0, 1])

        def work() -> object:
            return debugger_api.make_debugger("123", program, "").run(timeout=0.01)

        assert self._off_thread(work) == "timeout"

    def test_the_private_evaluation_route_works_on_a_thread(self) -> None:
        """The private harness settles diverging rows off the main thread."""
        for language in ("123", "ArrowQueue"):
            outcome = self._off_thread(
                lambda language=language: evaluate_generated(  # type: ignore[misc]
                    language, "0110", timeout=None
                )
            )
            assert outcome == "0110", language

    def test_the_main_thread_is_unaffected(self) -> None:
        """The refusal is about threads, not about timeouts."""
        assert esolangs.run("brainfuck", "+++.", "", 5) == "\x03"


# 7.8s over 21 tests: each spawns the CLI to read the version.
@pytest.mark.medium
# 7.8s over 21 tests: each spawns the CLI to read the version.
@pytest.mark.medium
# 7.8s over 21 tests: each spawns the CLI to read the version.
@pytest.mark.medium
class TestTheVersionIsResolvedWhenAsked:
    """``importlib.metadata`` was two fifths of the import for a string."""

    def test_it_still_answers(self) -> None:
        """Lazy is only acceptable while the answer is the same one."""
        assert re.match(r"^\d+\.\d+", esolangs.__version__)

    def test_metadata_is_not_imported_by_importing_us(self) -> None:
        """The measurement, as a check rather than a note in a commit."""
        code = "import sys; import esolangs; print('importlib.metadata' in sys.modules)"
        result = subprocess.run(
            [sys.executable, "-c", code], capture_output=True, text=True, check=True
        )
        assert result.stdout.strip() == "False", result.stdout

    def test_the_cli_reports_it(self) -> None:
        """The one caller that always wants it."""
        result = subprocess.run(
            [sys.executable, "-m", "esolangs", "--version"],
            capture_output=True,
            text=True,
            check=True,
        )
        assert result.stdout.strip() == f"esolangs {esolangs.__version__}"


class TestTheVmPathRefusesLikeRunDoes:
    """``run`` translated an interpreter's exceptions and the VM did not."""

    JUNK = ("]", "}", ")", "ZZZ", "[", "\x00")

    @pytest.mark.parametrize("entry", ["make_vm", "make_debugger"])
    def test_a_malformed_program_is_a_program_error(self, entry: str) -> None:
        """The one-character case, on the language it was reported for."""
        with pytest.raises(esolangs.ProgramError, match="unmatched"):
            getattr(debugger_api, entry)("brainfuck", "]")

    def test_no_language_leaks_anything_else(self) -> None:
        """Every language against six kinds of junk, both entry points."""
        escapes = []
        for name in esolangs.list_languages():
            for junk in self.JUNK:
                for entry in ("make_vm", "make_debugger"):
                    try:
                        getattr(debugger_api, entry)(name, junk)
                    except esolangs.EsolangError:
                        pass
                    except Exception as exc:
                        escapes.append((name, entry, junk, type(exc).__name__))
        assert not escapes, escapes[:5]

    def test_the_two_paths_agree_on_the_class(self) -> None:
        """Not merely "both raise" -- both raise the *same* thing."""
        for entry in (debugger_api.make_vm, debugger_api.make_debugger):
            with pytest.raises(esolangs.ProgramError) as stepped:
                entry("brainfuck", "]")
            with pytest.raises(esolangs.ProgramError) as ran:
                esolangs.run("brainfuck", "]")
            assert str(stepped.value) == str(ran.value)

    def test_a_recursion_limit_is_an_interpreter_limit(self) -> None:
        """Ninety open parens raised a bare ``RecursionError`` from ``step``."""
        vm = debugger_api.make_vm("Algebraic Programming Language", "(" * 90)
        with pytest.raises(esolangs.InterpreterLimitError):
            vm.step()


class TestAnAddressIsNotAllocatedOnTrust:
    """Three interpreters grew a store to whatever the program named."""

    HUGE: ClassVar[list[tuple[str, str]]] = [
        ("S*bleq", "100000000000000000000 0 0"),
        ("S*bleq", "1000000000000000000 0 0"),
        ("Decleq", "1 100000000000000000000"),
    ]

    @pytest.mark.parametrize(("language", "program"), HUGE)
    def test_it_is_refused_cleanly(self, language: str, program: str) -> None:
        """Refused before allocating, so a bigger machine thrashes no worse."""
        with pytest.raises(esolangs.InterpreterLimitError, match="grow its store"):
            esolangs.run(language, program, "", 2)

    def test_an_ordinary_address_still_grows(self) -> None:
        """A cap that refused real programs would be worse than the bug."""
        assert esolangs.run("S*bleq", "20 0 0", "", 5) == ""
        assert evaluate_generated("Decleq", "0110", timeout=30) == "0110"
        assert evaluate_generated("S*bleq", "0110", timeout=30) == "0110"


class TestDecleqNegativeAddressing:
    """A write past the left end escaped as a bare ``IndexError``."""

    def test_it_halts_instead_of_leaking(self) -> None:
        """Four characters, reduced from a 20,000-character random program."""
        with pytest.raises(esolangs.HaltError, match="past the left end"):
            esolangs.run("Decleq", "4 -8", "", 2)

    def test_the_documented_negative_write_is_unchanged(self) -> None:
        """Indexing from the right is deliberate and pinned elsewhere."""
        vm = debugger_api.make_vm("Decleq", "0 -1 3")
        vm.step()
        assert list(vm.memory)[:3] == [0, -1, -1]


class TestThePathGuardKnowsMoreThanTxt:
    """It tested for a literal ``.txt`` and nothing else."""

    @pytest.mark.parametrize(
        "argument",
        [
            "prog.bf",
            "prog.py",
            "prog.TXT",
            "prog.txt",
            "/etc/hosts",
            "~/prog.txt",
            "./prog.b",
            "../x.dat",
            "a/b/c.json",
        ],
    )
    def test_a_path_shaped_string_is_refused(self, argument: str) -> None:
        """Rooted, or ending in a short extension, and only path characters."""
        with pytest.raises(esolangs.ProgramError, match="looks like a path"):
            esolangs.run("brainfuck", argument, "", 5)

    @pytest.mark.parametrize("program", ["+++.", ".", "..", "---.", ">>++<<--."])
    def test_a_real_program_still_runs(self, program: str) -> None:
        """``.`` and ``..`` are legal brainfuck and must not be mistaken."""
        esolangs.run("brainfuck", program, "", 5)

    @pytest.mark.parametrize("program", ["~~", "~*+", ".", "..", "-", "a/b/c"])
    def test_a_hand_written_program_is_not_mistaken(self, program: str) -> None:
        """``~~`` is two ArrowQueue commands and was refused."""
        assert not esolangs._looks_like_a_path(program), program  # noqa: SLF001


class TestAHugeRowIndexIsRefusedNotCrashed:
    """CPython caps int<->str at 4300 digits; both directions leaked it."""

    def test_check_stdin_refuses_a_row_index_past_the_digit_cap(self) -> None:
        """``isdecimal`` passes for 4301 nines; ``int`` is what refuses them."""
        with pytest.raises(ArgumentError):
            _check_stdin("Fargo", "9" * 4301, "01")

    def test_encode_inputs_refuses_a_row_index_past_the_digit_cap(self) -> None:
        """Fargo reads a decimal row index, and 15000 bits name too many digits."""
        with pytest.raises(ArgumentError):
            esolangs.encode_inputs("Fargo", [1] * 15000)


def test_evaluate_refuses_a_timeout_off_the_main_thread() -> None:
    """The termination path drove ``_run`` directly and leaked ``SIGALRM``'s error."""
    box: list[BaseException] = []

    def work() -> None:
        try:
            evaluate_generated("123", "0110")
        except BaseException as exc:
            box.append(exc)

    thread = threading.Thread(target=work)
    thread.start()
    thread.join(30)
    assert not thread.is_alive()
    assert len(box) == 1
    assert isinstance(box[0], ArgumentError)


def test_a_raster_is_not_a_path() -> None:
    """``_looks_like_a_path`` is typed for text; a Raster must answer False."""
    program = esolangs.generate("Piet", "01")
    assert not esolangs._looks_like_a_path(program)  # noqa: SLF001
