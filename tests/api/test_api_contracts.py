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
from tests.reference import REFERENCE
from tests.support.generator_support import CHECK, evaluate_generated
from tests.support.pick import languages

XOR = "0110"
ROOT = pathlib.Path(__file__).parents[2]


class TestNameResolution:
    """A language name is matched however the caller spells it."""

    def test_case_is_ignored(self) -> None:
        """The registry mixes conventions, so a caller cannot guess one."""
        assert esolangs.run("BRAINFUCK", "+.", timeout=5) == "\x01"

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
            (lambda: esolangs.run(REFERENCE, ",.", stdin=""), InputExhaustedError),
            (lambda: esolangs.generate(REFERENCE, "0121"), TruthTableError),
            (lambda: esolangs.run(REFERENCE, 42), ProgramError),
            # A bad stdin is an ArgumentError, not a ProgramError: the stdin
            # is not the program.  Either way it is an EsolangError, which is
            # what this class is about.
            (lambda: esolangs.run(REFERENCE, ",.", stdin=["0"]), ArgumentError),
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
            if esolangs.describe(name)["boolean_generator"]
            and not esolangs.describe(name)["examples"]
        ]
        assert not missing, f"{missing} report no examples; {CHECK}"

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


#: ``inspect.signature`` of every public callable; identical on 3.12 and 3.14.
#: Required arguments positional, optional ones keyword-only (docs/usage.md).
SIGNATURES = {
    "esolangs.describe": "(language: str) -> esolangs._describe.LanguageInfo",
    "esolangs.dump_program": "(language: 'str', program: 'Program', *, settings: 'DialectSettings | None' = None) -> 'str'",  # noqa: E501
    "esolangs.encode_inputs": "(language: str, bits: list[int] | tuple[int, ...], *, truth_table: str | None = None) -> str",  # noqa: E501
    "esolangs.generate": "(language: str, truth_table: str, *, width: int | None = None, balance: bool = False, scale: int = 1, settings: esolangs.settings.DialectSettings | None = None) -> Program",  # noqa: E501
    "esolangs.instantiate": "(language: str, template: Program, bits: list[int] | tuple[int, ...], *, width: int | None = None, truth_table: str | None = None, settings: esolangs.settings.DialectSettings | None = None) -> str",  # noqa: E501
    "esolangs.list_languages": "() -> list[str]",
    "esolangs.load_program": "(language: 'str', document: 'str') -> 'Program'",
    "esolangs.read_answer": "(language: str, output: str) -> str",
    "esolangs.run": "(language: str, program: ProgramSource, *, stdin: InputSource = '', timeout: float | None = None, seed: int | None = None, isolated: bool = False, max_steps: int | None = None, scale: int | None = None, max_output: int | None = None, max_memory: int | None = None, settings: esolangs.settings.DialectSettings | None = None) -> str",  # noqa: E501
    "esolangs.debugger.make_debugger": "(language: 'str', program: 'ProgramSource', *, stdin: 'InputSource' = '', scale: 'int | None' = None, settings: 'DialectSettings | None' = None) -> 'Debugger'",  # noqa: E501
    "esolangs.debugger.make_vm": "(language: 'str', program: 'ProgramSource', *, stdin: 'InputSource' = '', scale: 'int | None' = None, settings: 'DialectSettings | None' = None) -> 'VM'",  # noqa: E501
    "Language.__init__": "(self, name: str) -> None",
    "Language.describe": "(self) -> esolangs._describe.LanguageInfo",
    "Language.dump_program": "(self, program: Program, *, settings: esolangs.settings.DialectSettings | None = None) -> str",  # noqa: E501
    "Language.encode_inputs": "(self, bits: list[int] | tuple[int, ...], *, truth_table: str | None = None) -> str",  # noqa: E501
    "Language.generate": "(self, truth_table: str, *, width: int | None = None, balance: bool = False, scale: int = 1, settings: esolangs.settings.DialectSettings | None = None) -> Program",  # noqa: E501
    "Language.instantiate": "(self, template: Program, bits: list[int] | tuple[int, ...], *, width: int | None = None, truth_table: str | None = None, settings: esolangs.settings.DialectSettings | None = None) -> str",  # noqa: E501
    "Language.load_program": "(self, document: str) -> Program",
    "Language.read_answer": "(self, output: str) -> str",
    "Language.run": "(self, program: ProgramSource, *, stdin: InputSource = '', timeout: float | None = None, seed: int | None = None, isolated: bool = False, max_steps: int | None = None, max_output: int | None = None, max_memory: int | None = None, settings: esolangs.settings.DialectSettings | None = None, scale: int | None = None) -> str",  # noqa: E501
    "Raster.__init__": "(self, rows: 'Rows', *, language: 'str | None' = None, settings: 'DialectSettings | None' = None, scale: 'int | None' = None) -> 'None'",  # noqa: E501
    "Raster.from_png": "(cls, data: 'bytes') -> 'Raster'",
    "Raster.tagged": "(self, language: 'str', *, settings: 'DialectSettings | None' = None, scale: 'int | None' = None) -> 'Raster'",  # noqa: E501
    "Raster.to_png": "(self) -> 'bytes'",
    "Raster.upscaled": "(self, scale: 'int') -> 'Raster'",
    "DialectSettings.__init__": "(self, **choices: int | str | None) -> None",
    "DialectSettings.options": "(self, language: str) -> dict[str, typing.Any]",
    "Debugger.__init__": "(self, vm: 'VM') -> 'None'",
    "Debugger.break_at": "(self, ip: 'int | tuple[int, ...]') -> 'None'",
    "Debugger.break_on_cell": "(self, index: 'int', value: 'int') -> 'None'",
    "Debugger.break_on_output": "(self, text: 'str') -> 'None'",
    "Debugger.break_on_stack": "(self, slot: 'int', value: 'object') -> 'None'",
    "Debugger.break_when": "(self, predicate: 'Callable[[VM], bool]') -> 'None'",
    "Debugger.clear_breakpoints": "(self) -> 'None'",
    "Debugger.run": "(self, *, max_steps: 'int | None' = None, timeout: 'float | None' = None) -> 'StopReason'",  # noqa: E501
    "Debugger.snapshot": "(self) -> 'object'",
    "Debugger.step": "(self) -> 'None'",
    "Debugger.watch_cell": "(self, index: 'int') -> 'list[int | None]'",
    "Debugger.watch_stack": "(self, slot: 'int') -> 'list[object]'",
}

#: Public (non-underscore) attributes of the public classes, methods included.
PUBLIC_MEMBERS = {
    esolangs.Language: {
        "describe",
        "dump_program",
        "encode_inputs",
        "generate",
        "instantiate",
        "load_program",
        "name",
        "read_answer",
        "run",
    },
    esolangs.Raster: {
        "from_png",
        "language",
        "rows",
        "scale",
        "settings",
        "tagged",
        "to_png",
        "upscaled",
    },
    esolangs.DialectSettings: {"options"},
    debugger_api.Debugger: {
        "break_at",
        "break_on_cell",
        "break_on_output",
        "break_on_stack",
        "break_when",
        "clear_breakpoints",
        "dumps_on_the_post_halt_step",
        "halted",
        "ip",
        "ip_shape",
        "memory",
        "output",
        "ptr",
        "run",
        "self_halts",
        "snapshot",
        "stack",
        "step",
        "steppable_to_answer",
        "views",
        "watch_cell",
        "watch_stack",
    },
}


class TestConventionsAreDiscoverable:
    """How to feed a language, and how to read its answer, are askable."""

    @pytest.mark.parametrize(
        "name",
        languages(answer_mode="termination") + languages(input_shape="row_index"),
    )
    def test_a_language_that_needs_explaining_explains_itself(self, name: str) -> None:
        """Termination-as-answer and Fargo's row index are not guessable."""
        assert esolangs.describe(name)["answer_convention"]

    def test_a_plain_printer_needs_no_note(self) -> None:
        assert esolangs.describe(REFERENCE)["answer_convention"] is None


class TestEveryDeliberateErrorIsCatchable:
    """The package docstring's promise, checked against the interpreters."""

    def test_a_malformed_program_is_a_programerror(self) -> None:
        """They were bare ValueErrors, so the documented base class missed.

        ``assert_rejected_with_hint`` checks each language's own."""
        with pytest.raises(ProgramError) as exc:
            esolangs.run(REFERENCE, "[[[", timeout=5)
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
                        pathlib.Path(str(files("esolangs") / example)),
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
            esolangs.run(REFERENCE, missing, stdin="", timeout=5)
        with pytest.raises(esolangs.EsolangError):
            esolangs.run(REFERENCE, missing, stdin="", timeout=5)
        with pytest.raises(esolangs.ProgramError):
            esolangs.run(REFERENCE, missing, stdin="", timeout=5)

    def test_an_unreadable_file_is_still_a_plain_program_error(
        self, tmp_path: Path
    ) -> None:
        """Only *absent* is a FileNotFoundError; the rest keep their class."""
        blocked = tmp_path / "blocked.bf"
        blocked.write_bytes(b"\xff\xfe\x00")
        with pytest.raises(esolangs.ProgramError) as caught:
            esolangs.run(REFERENCE, blocked, stdin="", timeout=5)
        assert not isinstance(caught.value, FileNotFoundError)

    def test_a_directory_is_an_os_error_not_a_decode_error(
        self, tmp_path: Path
    ) -> None:
        """The third clause: an ``OSError`` that is not ``FileNotFoundError``."""
        with pytest.raises(esolangs.ProgramError) as caught:
            esolangs.run(REFERENCE, tmp_path, stdin="", timeout=5)
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


class TestAMistypedPathIsNotRunAsAProgram:
    """The guard keyed on ``os.path.exists``, so it fired on the mistake
    you would have noticed anyway and missed the one you would not.
    """

    @pytest.mark.parametrize(
        "argument",
        ["/tmp/definitely-not-here.txt", r"a\\b.txt"],
    )
    def test_a_path_that_does_not_exist_is_refused(self, argument: str) -> None:
        """Existence is exactly what it must not depend on."""
        assert not pathlib.Path(argument).exists()
        with pytest.raises(esolangs.ProgramError, match="looks like a path"):
            esolangs.run(REFERENCE, argument, stdin="", timeout=5)

    def test_a_path_that_does_exist_is_still_refused(
        self, tmp_path: pathlib.Path
    ) -> None:
        """The case that already worked has to keep working."""
        path = tmp_path / "p.txt"
        path.write_text("+++.")
        with pytest.raises(esolangs.ProgramError, match="looks like a path"):
            esolangs.run(REFERENCE, str(path), stdin="", timeout=5)

    def test_every_entry_point_agrees(self) -> None:
        """All four take a program, so all four have to refuse the same thing."""
        for call in (
            lambda: esolangs.run(REFERENCE, "nope.txt", stdin="", timeout=5),
            lambda: _check_program(REFERENCE, "nope.txt", ""),
            lambda: debugger_api.make_vm(REFERENCE, "nope.txt", stdin=""),
            lambda: debugger_api.make_debugger(REFERENCE, "nope.txt", stdin=""),
        ):
            with pytest.raises(esolangs.ProgramError, match="looks like a path"):
                call()

    def test_a_real_program_is_untouched(self) -> None:
        """A guard that refuses real programs is worse than the bug."""
        assert esolangs.run(REFERENCE, "+++.", stdin="", timeout=5) == "\x03"

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
        assert esolangs.run(REFERENCE, path, stdin="", timeout=5) == "\x03"
        with pytest.raises(FileNotFoundError):
            esolangs.run(REFERENCE, tmp_path / "absent.txt", stdin="", timeout=5)


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
        outcome = self._off_thread(
            lambda: esolangs.run(REFERENCE, "+++.", stdin="", timeout=5)
        )
        assert isinstance(outcome, esolangs.ArgumentError)
        message = str(outcome)
        assert "make_debugger" in message

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
                lambda language=language: evaluate_generated(  # type: ignore[misc]
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


class TestThePathGuardKnowsMoreThanTxt:
    """It tested for a literal ``.txt`` and nothing else."""

    @pytest.mark.parametrize(
        "argument",
        [
            "prog.bf",
            "prog.TXT",
            "/etc/hosts",
            "a/b/c.json",
        ],
    )
    def test_a_path_shaped_string_is_refused(self, argument: str) -> None:
        """Rooted, or ending in a short extension, and only path characters."""
        with pytest.raises(esolangs.ProgramError, match="looks like a path"):
            esolangs.run(REFERENCE, argument, stdin="", timeout=5)

    @pytest.mark.parametrize("program", [".", ".."])
    def test_a_real_program_still_runs(self, program: str) -> None:
        """``.`` and ``..`` are legal brainfuck and must not be mistaken."""
        esolangs.run(REFERENCE, program, stdin="", timeout=5)

    @pytest.mark.parametrize("program", ["~~", "-", "a/b/c"])
    def test_a_hand_written_program_is_not_mistaken(self, program: str) -> None:
        """``~~`` is two ArrowQueue commands and was refused."""
        assert not esolangs._looks_like_a_path(program), program  # noqa: SLF001
