"""Contracts the public API owes a caller who has only read the docs."""

import pathlib
import re
import subprocess
import sys
import threading
from importlib.resources import files
from pathlib import Path

import pytest

import esolangs
import esolangs.debugger as debugger_api
from esolangs.exceptions import (
    ArgumentError,
    EsolangError,
    InputExhaustedError,
    ProgramError,
    TemplateError,
    TruthTableError,
    UnknownLanguageError,
)
from esolangs.operations.source import _check_program
from esolangs.registry import LANGUAGES
from tests.support.execution import run_observed
from tests.support.generator_support import CHECK, evaluate_generated
from tests.support.pick import languages
from tests.support.reference import REFERENCE
from tests.support.witness_tables import XOR


class TestNameResolution:
    """A language name is matched however the caller spells it."""

    def test_case_is_ignored(self) -> None:
        """The registry mixes conventions, so a caller cannot guess one."""
        assert (
            esolangs.run(
                "BRAINFUCK", "+.", limits=esolangs.ExecutionLimits(execution_timeout=5)
            ).output
            == "\x01"
        )

    def test_a_near_miss_is_named(self) -> None:
        """A misspelling is a spelling problem; answer it with the spelling."""
        name = max(esolangs.list_languages(), key=len)
        with pytest.raises(UnknownLanguageError) as exc:
            esolangs.generate(name[:-1], XOR)
        assert f"did you mean {name}" in str(exc.value)


class TestParameterizedTemplates:
    """A template is never mistaken for a runnable program."""

    def test_a_reader_has_nothing_to_instantiate(self) -> None:
        with pytest.raises(TemplateError, match="reads its inputs"):
            esolangs.instantiate(REFERENCE, esolangs.generate(REFERENCE, XOR), [0])


class TestErrorsAreCatchable:
    """``except EsolangError`` is the one handler a caller needs."""

    @pytest.mark.parametrize(
        ("call", "expected"),
        [
            (
                lambda: esolangs.run(REFERENCE, ",.", stdin="").output,
                InputExhaustedError,
            ),
            (lambda: esolangs.generate(REFERENCE, "0121"), TruthTableError),
            (lambda: esolangs.run(REFERENCE, 42).output, ProgramError),
            # A bad stdin is an ArgumentError, not a ProgramError: the stdin
            # is not the program.  Either way it is an EsolangError, which is
            # what this class is about.
            (lambda: esolangs.run(REFERENCE, ",.", stdin=["0"]).output, ArgumentError),
            (lambda: esolangs.run("zzzz", "+").output, UnknownLanguageError),
        ],
    )
    def test_it_derives_from_the_base(self, call: object, expected: type) -> None:
        with pytest.raises(expected) as exc:
            call()
        assert isinstance(exc.value, EsolangError)
        assert str(exc.value), "an error with no message cannot be acted on"

    def test_exhausted_input_says_how_much_there_was(self) -> None:
        """A bare ``EOFError()`` reached the caller as the empty string."""
        with pytest.raises(InputExhaustedError, match="1 character supplied"):
            esolangs.run(REFERENCE, ",,.", stdin="0")

    def test_it_is_still_an_eoferror(self) -> None:
        """The repo-wide convention every interpreter documents is unchanged."""
        with pytest.raises(EOFError):
            esolangs.run(REFERENCE, ",.", stdin="")


class TestDebuggerResume:
    """A stopped debugger can be resumed, and says why it stopped."""

    def _debugger(self) -> debugger_api.Debugger:
        return debugger_api.make_debugger(
            REFERENCE, esolangs.generate(REFERENCE, XOR), stdin="10"
        )

    def test_output_breakpoint_does_not_deadlock(self) -> None:
        """Output only accumulates, so the condition is true forever after."""
        dbg = self._debugger()
        dbg.break_on_output("1")
        assert dbg.run(max_steps=100000) == "breakpoint"
        assert dbg.run(max_steps=100000) == "halted"
        assert dbg.halted

    def test_the_stop_reason_separates_all_three(self) -> None:
        dbg = debugger_api.make_debugger(REFERENCE, "++>+<.", stdin="")
        assert dbg.run(max_steps=2) == "max_steps"
        assert dbg.run() == "halted"

    def test_a_position_breakpoint_still_fires_before_its_step(self) -> None:
        """The documented contract: ``break_at`` does not execute that ip."""
        dbg = debugger_api.make_debugger(REFERENCE, "++>+<.", stdin="")
        dbg.break_at(0)
        assert dbg.run() == "breakpoint"
        assert dbg.ip == 0
        assert dbg.output == ""

    def test_clear_breakpoints_releases_the_run(self) -> None:
        dbg = debugger_api.make_debugger(REFERENCE, "++>+<.", stdin="")
        dbg.break_at(0)
        dbg.run()
        dbg.clear_breakpoints()
        assert dbg.run() == "halted"

    def test_timeout_bounds_an_unbounded_run(self) -> None:
        """``run()`` with no budget hangs on a program that never halts."""
        dbg = debugger_api.make_debugger(REFERENCE, "+[]", stdin="")
        assert dbg.run(timeout=0.01) == "timeout"
        assert not dbg.halted


class TestDescribe:
    """``describe`` answers what a caller would otherwise read code for."""

    def test_every_language_finds_its_examples(self) -> None:
        """A fifth reported none: the id and the stem are spelled apart."""
        missing = [
            name
            for name in esolangs.list_languages()
            if esolangs.describe(name).boolean_generator
            and not esolangs.describe(name).examples
        ]
        assert not missing, f"{missing} report no examples; {CHECK}"

    def test_layout_names_the_generators_that_lay_themselves_out(self) -> None:
        """It answered False for every one: it takes a generator, not a name."""
        aware = {
            name
            for name in esolangs.list_languages()
            if esolangs.describe(name).width_effect == "layout"
        }
        signature = {
            name
            for name, lang in LANGUAGES.items()
            if lang.backend is not None and lang.backend.layout_width
        }
        assert aware == signature
        assert aware, "no generator lays itself out; the flag guards nothing"


#: ``inspect.signature`` of every public callable; identical on 3.12 and 3.14.
#: Required arguments positional, optional ones keyword-only (docs/usage.md).
#: The table itself is data, not code -- signatures.json beside this file,
#: so its lines are not subject to the line-length rule.

#: Public (non-underscore) attributes of the public classes, methods included.


class TestConventionsAreDiscoverable:
    """How to feed a language, and how to read its answer, are askable."""

    @pytest.mark.parametrize(
        "name",
        languages(answer_mode="termination") + languages(input_shape="row_index"),
    )
    def test_a_language_that_needs_explaining_explains_itself(self, name: str) -> None:
        """Termination-as-answer and integer row indices are not guessable."""
        assert esolangs.describe(name).answer_convention

    def test_a_plain_printer_needs_no_note(self) -> None:
        assert esolangs.describe(REFERENCE).answer_convention is None


class TestEveryDeliberateErrorIsCatchable:
    """The package docstring's promise, checked against the interpreters."""

    def test_a_malformed_program_is_a_programerror(self) -> None:
        """They were bare ValueErrors, so the documented base class missed.

        ``assert_rejected_with_hint`` checks each language's own."""
        with pytest.raises(ProgramError) as exc:
            esolangs.run(
                REFERENCE, "[[[", limits=esolangs.ExecutionLimits(execution_timeout=5)
            )
        assert isinstance(exc.value, EsolangError)
        assert str(exc.value)

    # Runs every committed example through `run`, which is the `medium`
    # rule exactly.  It sat in the fast band at ~1.07s against its 1s floor,
    # so it passed alone and failed whenever the gate ran a second step
    # beside pytest.
    @pytest.mark.medium
    def test_every_committed_example_runs_from_its_described_path(self) -> None:
        """Packaged native examples explicitly use their file newline policy."""
        failures = []
        for name in esolangs.list_languages():
            facts = esolangs.describe(name)
            if facts.parameterized or facts.answer_convention:
                continue  # needs bits embedded, or answers by terminating
            for example in facts.examples:
                try:
                    run_observed(
                        name,
                        esolangs.Language(name).from_file(
                            pathlib.Path(str(files("esolangs") / example)),
                            normalize=True,
                        ),
                        stdin=esolangs.encode_inputs(name, [0, 1]),
                        timeout=20,
                    )
                except EsolangError as exc:
                    failures.append(f"{name}: {type(exc).__name__}: {exc}")
        assert failures == []


class TestAMissingFileIsAFileNotFoundError:
    """``run`` takes an ``os.PathLike``, so a caller writes the stdlib catch."""

    def test_it_is_catchable_both_ways(self, tmp_path: Path) -> None:
        """Ours for callers who catch ours, the stdlib's for the rest."""
        missing = tmp_path / "absent.bf"
        with pytest.raises(FileNotFoundError):
            esolangs.run(
                REFERENCE,
                missing,
                stdin="",
                limits=esolangs.ExecutionLimits(execution_timeout=5),
            )
        with pytest.raises(esolangs.EsolangError):
            esolangs.run(
                REFERENCE,
                missing,
                stdin="",
                limits=esolangs.ExecutionLimits(execution_timeout=5),
            )
        with pytest.raises(esolangs.ProgramError):
            esolangs.run(
                REFERENCE,
                missing,
                stdin="",
                limits=esolangs.ExecutionLimits(execution_timeout=5),
            )

    def test_an_unreadable_file_is_still_a_plain_program_error(
        self, tmp_path: Path
    ) -> None:
        """Only *absent* is a FileNotFoundError; the rest keep their class."""
        blocked = tmp_path / "blocked.bf"
        blocked.write_bytes(b"\xff\xfe\x00")
        with pytest.raises(esolangs.ProgramError) as caught:
            esolangs.run(
                REFERENCE,
                blocked,
                stdin="",
                limits=esolangs.ExecutionLimits(execution_timeout=5),
            )
        assert not isinstance(caught.value, FileNotFoundError)

    def test_a_directory_is_an_os_error_not_a_decode_error(
        self, tmp_path: Path
    ) -> None:
        """The third clause: an ``OSError`` that is not ``FileNotFoundError``."""
        with pytest.raises(esolangs.ProgramError) as caught:
            esolangs.run(
                REFERENCE,
                tmp_path,
                stdin="",
                limits=esolangs.ExecutionLimits(execution_timeout=5),
            )
        assert not isinstance(caught.value, FileNotFoundError)
        assert "cannot read" in str(caught.value)

    def test_a_pathlike_returning_a_non_str_is_a_program_error(self) -> None:
        """``__fspath__`` returning a non-str made ``pathlib`` raise ``TypeError``."""

        class Bad:
            def __fspath__(self) -> int:
                return 5

        with pytest.raises(esolangs.ProgramError) as caught:
            _check_program(REFERENCE, Bad())
        assert "cannot read" in str(caught.value)


class TestSourceAndPathsAreExplicit:
    """Strings remain source regardless of spelling or filesystem contents."""

    @pytest.mark.parametrize("argument", ["/tmp/definitely-not-here.txt", r"a\\b.txt"])
    def test_a_missing_filename_is_literal_source(self, argument: str) -> None:
        api = esolangs.Language(REFERENCE)
        assert api.run(argument) == api.run(api.from_source(argument))

    def test_an_existing_filename_is_still_literal_source(self, tmp_path) -> None:
        path = tmp_path / "p.txt"
        path.write_text("+++.")
        api = esolangs.Language(REFERENCE)
        assert api.run(str(path)) == api.run(api.from_source(str(path)))
        assert api.run(path).output == "\x03"

    def test_every_entry_point_agrees(self) -> None:
        source = "nope.txt"
        assert esolangs.run(REFERENCE, source).output == "\x00"
        assert _check_program(REFERENCE, source).source == source
        from esolangs.vm import complete_vm

        assert complete_vm(debugger_api.make_vm(REFERENCE, source)) == "\x00"
        debugger = debugger_api.make_debugger(REFERENCE, source)
        assert debugger.run(max_steps=100) == "halted"
        assert debugger.output == "\x00"

    def test_a_real_program_is_untouched(self) -> None:
        """A guard that refuses real programs is worse than the bug."""
        assert (
            esolangs.run(
                REFERENCE,
                "+++.",
                stdin="",
                limits=esolangs.ExecutionLimits(execution_timeout=5),
            ).output
            == "\x03"
        )

    def test_file_bytes_are_source_without_spelling_rules(self, tmp_path) -> None:
        path = tmp_path / "source.txt"
        path.write_bytes(b"nope.txt\r\n")
        assert _check_program(REFERENCE, path).source == "nope.txt\r\n"

    def test_a_pathlib_path_is_read_in_both_directions(
        self, tmp_path: pathlib.Path
    ) -> None:
        """A Path was always correct, and stays the way to say "this file"."""
        path = tmp_path / "p.txt"
        path.write_text("+++.")
        assert (
            esolangs.run(
                REFERENCE,
                path,
                stdin="",
                limits=esolangs.ExecutionLimits(execution_timeout=5),
            ).output
            == "\x03"
        )
        with pytest.raises(FileNotFoundError):
            esolangs.run(
                REFERENCE,
                tmp_path / "absent.txt",
                stdin="",
                limits=esolangs.ExecutionLimits(execution_timeout=5),
            )


# 2.2s over 12 tests: runs a diverging program to its bound.
@pytest.mark.medium
class TestThreadExecution:
    """A worker thread had two options and no third."""

    @staticmethod
    def _off_thread(work: object) -> object:
        """Run ``work`` on a worker thread and hand back what it produced."""
        box: dict[str, object] = {}

        def target() -> None:
            try:
                box["value"] = work()
            except BaseException as exc:
                box["value"] = exc

        thread = threading.Thread(target=target)
        thread.start()
        thread.join(60)
        assert not thread.is_alive(), "the worker never finished"
        return box["value"]

    def test_a_timed_run_works_off_thread(self) -> None:
        """The worker deadline works from a caller's thread."""
        outcome = self._off_thread(
            lambda: (
                esolangs.run(
                    REFERENCE,
                    "+++.",
                    stdin="",
                    limits=esolangs.ExecutionLimits(execution_timeout=5),
                ).output
            )
        )
        assert outcome == "\x03"

    def test_the_debugger_route_bounds_a_diverging_program(self) -> None:
        """The one that matters: a program that never halts, on a thread."""
        name = languages(answer_mode="termination", parameterized=True)[0]
        program = esolangs.instantiate(name, esolangs.generate(name, "0110"), [0, 1])

        def work() -> object:
            return debugger_api.make_debugger(name, program, stdin="").run(timeout=0.01)

        assert self._off_thread(work) == "timeout"

    def test_the_private_evaluation_route_works_on_a_thread(self) -> None:
        """The private harness settles diverging rows off the main thread."""
        for language in languages(answer_mode="termination", parameterized=True)[:2]:
            outcome = self._off_thread(
                lambda language=language: evaluate_generated(
                    language, "0110", timeout=None
                )
            )
            assert outcome == "0110", language


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


class TestSourceSpellingDoesNotSelectAContainer:
    """Paths require Path objects, regardless of extensions or commands."""

    @pytest.mark.parametrize(
        "argument",
        [
            "prog.bf",
            "prog.TXT",
            "/etc/hosts",
            "a/b/c.json",
            "foo.7z",
            "data.1",
        ],
    )
    def test_a_path_shaped_string_is_source(self, argument: str) -> None:
        api = esolangs.Language(REFERENCE)
        assert api.run(argument) == api.run(api.from_source(argument))

    @pytest.mark.parametrize("program", [".", ".."])
    def test_a_real_program_still_runs(self, program: str) -> None:
        """``.`` and ``..`` are legal brainfuck and must not be mistaken."""
        esolangs.run(
            REFERENCE,
            program,
            stdin="",
            limits=esolangs.ExecutionLimits(execution_timeout=5),
        )

    @pytest.mark.parametrize("program", ["~~", "-", "a/b/c", "/", "./", "1.5"])
    def test_a_hand_written_program_is_not_mistaken(self, program: str) -> None:
        """Adjacent commands ``~~`` were refused, and Befunge's ``/``."""
        assert _check_program(REFERENCE, program).source == program


class TestTheArgumentBoundaryRefusesCleanly:
    """Wrong arguments the 2.0 audit found escaping as raw or wrong errors."""

    @pytest.mark.parametrize(
        "build",
        [
            lambda: esolangs.CompressedText.from_chunks(["\ud800"]),
            lambda: esolangs.CompressedText.repeated("\ud800", 3),
        ],
    )
    def test_a_lone_surrogate_is_an_argument_error(self, build) -> None:
        """It escaped as ``UnicodeEncodeError`` from ``str.encode``."""
        with pytest.raises(ArgumentError, match="UTF-8"):
            build()

    def test_dump_program_refuses_what_load_program_would(self) -> None:
        """``run`` accepts the surrogate; the dumped document did not load."""
        with pytest.raises(ProgramError, match="UTF-8"):
            esolangs.dump_program(REFERENCE, "\ud800")

    @pytest.mark.parametrize("data", [None, 5, "png"])
    def test_png_data_of_the_wrong_type_says_so(self, data: object) -> None:
        """``None`` read "'NoneType' object is not subscriptable"."""
        with pytest.raises(ArgumentError, match="must be bytes"):
            esolangs.Raster.from_png(data)  # type: ignore[arg-type]

    def test_png_bytes_may_be_any_buffer(self) -> None:
        """A ``memoryview`` hit "unsupported operand type(s) for +"."""
        png = esolangs.Raster((((0, 0, 0),),)).to_png()
        assert esolangs.Raster.from_png(memoryview(png)).rows == ((((0, 0, 0),),))

    def test_png_settings_are_validated_as_a_document_is(self, monkeypatch) -> None:
        """``{"integer": 5}`` said "int() can't convert non-string"."""
        from esolangs.operations.source import read_png_artifact
        from esolangs.raster import png

        bad = {"version": 1, "settings": {"cell_modulus": {"integer": 5}}}
        monkeypatch.setattr(png, "read_metadata", lambda _data: bad)
        data = esolangs.Raster((((0, 0, 0),),)).to_png()
        with pytest.raises(ProgramError, match="hexadecimal"):
            read_png_artifact(REFERENCE, data)

    def test_read_answer_of_a_non_string_is_an_argument_error(self) -> None:
        """Every other wrong-type argument already was."""
        with pytest.raises(ArgumentError, match=r"must be a string, got NoneType$"):
            esolangs.read_answer(REFERENCE, None)  # type: ignore[arg-type]
        result = esolangs.run(REFERENCE, "+.")
        with pytest.raises(ArgumentError, match=r"pass its \.output$"):
            esolangs.read_answer(REFERENCE, result)  # type: ignore[arg-type]

    def test_an_unknown_name_of_any_type_renders(self) -> None:
        """``UnknownLanguageError(5)`` raised ``AttributeError`` on ``.strip``."""
        assert "5" in str(UnknownLanguageError(5))  # type: ignore[arg-type]

    @pytest.mark.parametrize("drive", ["run", "step"])
    def test_a_debugger_fault_keeps_its_partial_output(self, drive: str) -> None:
        """``run(max_steps=)`` filled it and the debugger left it empty."""
        debugger = debugger_api.make_debugger(REFERENCE, "+++.,", stdin="")
        if drive == "step":
            for _ in range(4):
                debugger.step()
        with pytest.raises(InputExhaustedError) as caught:
            getattr(debugger, drive)()
        assert caught.value.partial_output == "\x03"


def test_the_closed_string_sets_match_their_sources() -> None:
    """``describe`` and ``ip_shape`` Literals, against the values they type."""
    from typing import get_args

    from esolangs.registry import _contracts, _describe
    from esolangs.registry._backend import Shape
    from esolangs.runtime._capabilities import IpShape
    from esolangs.runtime._definition import SourceKind

    def labels(alias: object) -> set[str]:
        return set(get_args(alias.__value__))  # type: ignore[attr-defined]

    assert not hasattr(_describe, "LanguageInfo")
    assert labels(_contracts.StateModel) == set(_describe._STATE_MODELS.values())
    assert labels(_contracts.SourceForm) == {kind.value for kind in SourceKind}
    assert labels(_contracts.GeneratorShape) == {shape.value for shape in Shape}
    # Static: an interpreter declares its shape as a class attribute.
    root = Path(esolangs.__file__).parent / "languages"
    shapes = {
        match
        for source in root.rglob("*.py")
        for match in re.findall(r'ip_shape = "(\w+)"', source.read_text())
    }
    assert shapes
    assert shapes <= labels(IpShape), shapes
