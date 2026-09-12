r"""Contracts the public API owes a caller who has only read the docs."""

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
from esolangs.tools.wrap import takes_width

XOR = "0110"
ROOT = pathlib.Path(__file__).parents[1]


class TestNameResolution:
    r"""A language name is matched however the caller spells it."""

    @pytest.mark.parametrize("spelling", ["brainfuck", "Brainfuck", "BRAINFUCK"])
    def test_case_is_ignored(self, spelling: str) -> None:
        r"""The registry mixes conventions, so a caller cannot guess one."""
        assert esolangs.run(spelling, "+.", timeout=5) == "\x01"

    def test_a_near_miss_is_named(self) -> None:
        r"""A misspelling is a spelling problem; answer it with the spelling."""
        with pytest.raises(UnknownLanguageError) as exc:
            esolangs.generate("Sophi", XOR)
        assert "did you mean Sophie" in str(exc.value)

    def test_a_wild_miss_still_raises_plainly(self) -> None:
        with pytest.raises(UnknownLanguageError, match="unknown language: zzzz"):
            esolangs.generate("zzzz", XOR)

    def test_every_entry_point_resolves(self) -> None:
        r"""One helper backs them all, so none can drift out of step."""
        assert esolangs.describe("BRAINFUCK")["name"] == "brainfuck"
        assert esolangs.make_vm("BRAINFUCK", "+").ip == 0
        assert esolangs.make_debugger("BRAINFUCK", "+").ip == 0


class TestParameterizedTemplates:
    r"""A template is never mistaken for a runnable program."""

    def test_describe_says_so_in_advance(self) -> None:
        facts = esolangs.describe("Minifuck")
        assert facts["parameterized"] is True
        assert facts["reads_input"] is False
        assert esolangs.describe("brainfuck")["parameterized"] is False

    def test_running_one_unfilled_is_refused(self) -> None:
        r"""Minifuck ignored its slots and reported a constant as the answer."""
        template = esolangs.generate("Minifuck", XOR)
        with pytest.raises(TemplateError) as exc:
            esolangs.run("Minifuck", template)
        assert "{X0}" in str(exc.value)
        assert "instantiate" in str(exc.value)

    def test_instantiating_gives_the_right_answer(self) -> None:
        r"""The whole point: all four rows, executed."""
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
        r"""The definition is behavioural, so nothing can quietly leave it."""
        emits = {
            lang.id
            for lang in LANGUAGES.values()
            if lang.boolean is not None and "{X0}" in str(lang.boolean(XOR))
        }
        assert emits == set(parameterized_ids())


class TestErrorsAreCatchable:
    r"""``except EsolangError`` is the one handler a caller needs."""

    @pytest.mark.parametrize(
        ("call", "expected"),
        [
            (lambda: esolangs.run("brainfuck", ",.", stdin=""), InputExhaustedError),
            (lambda: esolangs.generate("brainfuck", "011"), TruthTableError),
            (lambda: esolangs.generate("brainfuck", "0121"), TruthTableError),
            (lambda: esolangs.generate("brainfuck", 6), TruthTableError),
            (lambda: esolangs.run("brainfuck", 42), ProgramError),
            # A bad stdin is an.
            # is not the program.
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
        r"""A bare ``EOFError()`` reached the caller as the empty string."""
        with pytest.raises(InputExhaustedError, match="1 line supplied"):
            esolangs.run("brainfuck", ",,.", stdin="0\n")

    def test_it_is_still_an_eoferror(self) -> None:
        r"""The repo-wide convention every interpreter documents is unchanged."""
        with pytest.raises(EOFError):
            esolangs.run("brainfuck", ",.", stdin="")


class TestRunTakesSource:
    r"""``run`` takes a program, and says so when it is handed a path."""

    def test_a_path_string_is_refused(self) -> None:
        r"""It used to execute the filename and print a null byte."""
        with pytest.raises(ProgramError, match="looks like a path"):
            esolangs.run("brainfuck", "examples/boolean/brainfuck.txt")

    def test_a_path_object_is_read(self) -> None:
        path = ROOT / "examples" / "boolean" / "brainfuck.txt"
        assert esolangs.run("brainfuck", path, stdin="0\n1\n", timeout=30) == "0"

    def test_a_real_program_is_never_mistaken_for_one(self) -> None:
        r"""The guard needs an existing file, so ordinary source is exempt."""
        assert esolangs.run("brainfuck", "+.", timeout=5) == "\x01"


class TestDebuggerResume:
    r"""A stopped debugger can be resumed, and says why it stopped."""

    def _debugger(self) -> esolangs.Debugger:
        return esolangs.make_debugger(
            "brainfuck", esolangs.generate("brainfuck", XOR), stdin="1\n0\n"
        )

    def test_output_breakpoint_does_not_deadlock(self) -> None:
        r"""Output only accumulates, so the condition is true forever after."""
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
        r"""The documented contract: ``break_at`` does not execute that ip."""
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
        r"""``run()`` with no budget hangs on a program that never halts."""
        dbg = esolangs.make_debugger("brainfuck", "+[]", stdin="")
        assert dbg.run(timeout=1) == "timeout"
        assert not dbg.halted


class TestDescribe:
    r"""``describe`` answers what a caller would otherwise read code for."""

    def test_every_language_finds_its_examples(self) -> None:
        r"""19 of 69 reported none: the id and the stem are spelled apart."""
        missing = [
            name
            for name in esolangs.list_languages()
            if not esolangs.describe(name)["examples"]
        ]
        assert missing == []

    def test_width_aware_names_the_generators_that_lay_themselves_out(self) -> None:
        r"""It answered False for all 69: it takes a generator, not a name."""
        aware = {
            name
            for name in esolangs.list_languages()
            if esolangs.describe(name)["width_aware"]
        }
        signature = {
            name
            for name, lang in LANGUAGES.items()
            if lang.boolean is not None and takes_width(lang.boolean)
        }
        assert aware == signature
        assert aware, "no generator lays itself out; the flag guards nothing"


class TestPackageSurface:
    r"""What ``dir(esolangs)`` advertises is what the package supports."""

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
    r"""How to feed a language, and how to read its answer, are askable."""

    def test_grapheme_names_its_input_alphabet(self) -> None:
        r"""Digits are read as truthy, so 0/1 lines answer the wrong row."""
        assert esolangs.describe("Grapheme")["input_encoding"] == ("%", "A")
        assert esolangs.describe("brainfuck")["input_encoding"] == ("0", "1")

    def test_the_named_alphabet_is_the_one_that_works(self) -> None:
        r"""The point of the key: using it reproduces the truth table."""
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
        r"""Termination-as-answer and Fargo's row index are not guessable."""
        assert esolangs.describe(name)["answer_convention"]

    def test_a_plain_printer_needs_no_note(self) -> None:
        assert esolangs.describe("brainfuck")["answer_convention"] is None


class TestEveryDeliberateErrorIsCatchable:
    r"""The package docstring's promise, checked against the interpreters."""

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
        r"""They were bare ValueErrors, so the documented base class missed."""
        with pytest.raises(ProgramError) as exc:
            esolangs.run(language, source, timeout=5)
        assert isinstance(exc.value, EsolangError)
        assert str(exc.value)

    def test_every_committed_example_runs_from_its_described_path(self) -> None:
        r"""describe() handed out paths run() choked on: the file's newline."""
        failures = []
        for name in esolangs.list_languages():
            facts = esolangs.describe(name)
            if facts["parameterized"] or facts["answer_convention"]:
                continue  # needs bits embedded, or.
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
    r"""A wrong call is refused where it is made, not one layer downstream."""

    def test_the_bit_count_must_match_the_slots(self) -> None:
        template = esolangs.generate("Minifuck", XOR)
        with pytest.raises(TemplateError, match="2 input slots, but 1 bit was given"):
            esolangs.instantiate("Minifuck", template, [1])

    def test_a_bit_must_be_a_bit(self) -> None:
        r"""``2`` was substituted silently into a program that then lied."""
        template = esolangs.generate("Minifuck", XOR)
        with pytest.raises(esolangs.ArgumentError, match="must each be 0 or 1"):
            esolangs.instantiate("Minifuck", template, [2, 0])


class TestNoTwoNamesDisagree:
    r"""One question, one answer."""

    def test_width_awareness_has_a_single_spelling(self) -> None:
        r"""``esolangs.takes_width`` took a function and answered False here."""
        assert not hasattr(esolangs, "takes_width")
        assert esolangs.describe("LaserFuck")["width_aware"] is True

    def test_the_debugger_stop_reason_type_is_exported(self) -> None:
        assert "StopReason" in esolangs.__all__


class TestTheSignaturesAgreeWithThemselves:
    r"""Two functions taking the same argument should describe it the same."""

    def test_bits_is_annotated_the_same_in_both_places(self) -> None:
        r"""``encode_inputs`` promised more than it accepts."""
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
        r"""The annotation is only right while the behaviour matches it."""
        call([1, 0])  # type: ignore[operator]
        call((1, 0))  # type: ignore[operator]
        with pytest.raises(esolangs.ArgumentError, match="list or tuple"):
            call(range(2))  # type: ignore[operator]

    def test_the_default_sentinel_reads_as_a_default(self) -> None:
        r"""``help`` showed a memory address that changed every run."""
        for fn in (esolangs.evaluate, esolangs.verify):
            rendered = str(inspect.signature(fn))
            assert "<default>" in rendered, fn.__name__
            assert "object at 0x" not in rendered, fn.__name__

    def test_language_is_first_everywhere(self) -> None:
        r"""The one argument every public call shares, in the same place."""
        for name in esolangs.__all__:
            attribute = getattr(esolangs, name)
            if not inspect.isfunction(attribute):
                continue
            first = next(iter(inspect.signature(attribute).parameters), None)
            if first in {None, "output", "truth_table"}:
                continue
            assert first == "language", (name, first)


class TestDescribeHasANameableType:
    r"""``dict[str, object]`` was accurate and useless."""

    def test_it_is_exported(self) -> None:
        r"""A type you cannot name is a type you cannot annotate with."""
        assert "LanguageInfo" in esolangs.__all__
        assert esolangs.LanguageInfo.__doc__

    def test_every_key_is_declared(self) -> None:
        r"""The TypedDict and the dict must not drift apart."""
        declared = set(esolangs.LanguageInfo.__annotations__)
        assert declared == set(esolangs.describe("brainfuck"))

    def test_every_language_matches_the_declared_types(self) -> None:
        r"""Declared from a survey of all 69, so it is checked against all 69."""
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
                else:  # the two that may be None.
                    assert value is None or isinstance(value, str), (name, key)

    def test_the_four_machine_traits_are_still_carried(self) -> None:
        r"""They were merged with ``**``, which a TypedDict cannot verify."""
        facts = esolangs.describe("RAM0")
        for key in (
            "self_halts",
            "dumps_on_the_post_halt_step",
            "steppable_to_answer",
            "eof_is_a_value",
        ):
            assert isinstance(facts[key], bool), key  # type: ignore[literal-required]


class TestSpecAbortsRatherThanReturningNothing:
    r"""``-OO`` strips docstrings, and ``spec`` read one."""

    def test_it_raises_when_there_is_no_docstring(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        r"""Simulated by emptying one, since the test run is not under -OO."""
        module = importlib.import_module(
            "esolangs.interpreters."
            + str(esolangs.describe("brainfuck")["interpreter"])
        )
        monkeypatch.setattr(module, "__doc__", None)
        with pytest.raises(esolangs.ProgramError, match="-OO"):
            esolangs.spec("brainfuck")

    def test_it_still_returns_the_text_normally(self) -> None:
        r"""The abort must not have eaten the ordinary path."""
        assert esolangs.spec("brainfuck").startswith("Interpreter for")


class TestAMissingFileIsAFileNotFoundError:
    r"""``run`` takes an ``os.PathLike``, so a caller writes the stdlib."""

    def test_it_is_catchable_both_ways(self, tmp_path: Path) -> None:
        r"""Ours for callers who catch ours, the stdlib's for the rest."""
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
        r"""Only *absent* is a FileNotFoundError; the rest keep their class."""
        blocked = tmp_path / "blocked.bf"
        blocked.write_bytes(b"\xff\xfe\x00")
        with pytest.raises(esolangs.ProgramError) as caught:
            esolangs.run("brainfuck", blocked, "", 5)
        assert not isinstance(caught.value, FileNotFoundError)

    def test_version_is_not_star_imported(self) -> None:
        r"""``from esolangs import *`` injected a dunder into the namespace."""
        assert "__version__" not in esolangs.__all__
        assert esolangs.__version__  # still reachable by name.


class TestAMistypedPathIsNotRunAsAProgram:
    r"""The guard keyed on ``os.path.exists``, so it fired on the mistake."""

    @pytest.mark.parametrize(
        "argument",
        ["/tmp/definitely-not-here.txt", "programs/xor.txt", "nope.txt", r"a\\b.txt"],
    )
    def test_a_path_that_does_not_exist_is_refused(self, argument: str) -> None:
        r"""Existence is exactly what it must not depend on."""
        assert not pathlib.Path(argument).exists()
        with pytest.raises(esolangs.ProgramError, match="looks like a path"):
            esolangs.run("brainfuck", argument, "", 5)

    def test_a_path_that_does_exist_is_still_refused(
        self, tmp_path: pathlib.Path
    ) -> None:
        r"""The case that already worked has to keep working."""
        path = tmp_path / "p.txt"
        path.write_text("+++.")
        with pytest.raises(esolangs.ProgramError, match="looks like a path"):
            esolangs.run("brainfuck", str(path), "", 5)

    def test_every_entry_point_agrees(self) -> None:
        r"""All four take a program, so all four have to refuse the same thing."""
        for call in (
            lambda: esolangs.run("brainfuck", "nope.txt", "", 5),
            lambda: esolangs.check_program("brainfuck", "nope.txt", ""),
            lambda: esolangs.make_vm("brainfuck", "nope.txt", ""),
            lambda: esolangs.make_debugger("brainfuck", "nope.txt", ""),
        ):
            with pytest.raises(esolangs.ProgramError, match="looks like a path"):
                call()

    def test_a_real_program_is_untouched(self) -> None:
        r"""A guard that refuses real programs is worse than the bug."""
        assert esolangs.run("brainfuck", "+++.", "", 5) == "\x03"

    def test_no_committed_example_looks_like_a_path(self) -> None:
        r"""The claim the widened rule rests on, checked rather than asserted."""
        for path in sorted(pathlib.Path("examples/boolean").glob("*.txt")):
            text = path.read_text()
            assert not ("\n" not in text and text.endswith(".txt")), path.name

    def test_no_generated_program_looks_like_one_either(self) -> None:
        r"""All 69, three tables each, since a generator could drift into it."""
        for name in esolangs.list_languages():
            for table in ("01", "0110", "10010110"):
                program = esolangs.generate(name, table)
                looks = "\n" not in program and program.endswith(".txt")
                assert not looks, (name, table)

    def test_a_pathlib_path_is_read_in_both_directions(
        self, tmp_path: pathlib.Path
    ) -> None:
        r"""A Path was always correct, and stays the way to say "this file"."""
        path = tmp_path / "p.txt"
        path.write_text("+++.")
        assert esolangs.run("brainfuck", path, "", 5) == "\x03"
        with pytest.raises(FileNotFoundError):
            esolangs.run("brainfuck", tmp_path / "absent.txt", "", 5)


# 2.2s over 12 tests: runs a.
@pytest.mark.medium
# 2.2s over 12 tests: runs a.
@pytest.mark.medium
# 2.2s over 12 tests: runs a.
@pytest.mark.medium
class TestTheThreadRefusalNamesAWayThrough:
    r"""A worker thread had two options and no third."""

    @staticmethod
    def _off_thread(work: object) -> object:
        r"""Run ``work`` on a worker thread and hand back what it produced."""
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

    def test_the_message_names_both_routes(self) -> None:
        r"""Naming a route is a claim; the two tests below run it."""
        outcome = self._off_thread(lambda: esolangs.run("brainfuck", "+++.", "", 5))
        assert isinstance(outcome, esolangs.ArgumentError)
        message = str(outcome)
        assert "make_debugger" in message
        assert "timeout=None" in message

    def test_the_debugger_route_bounds_a_diverging_program(self) -> None:
        r"""The one that matters: a program that never halts, on a thread."""
        template = esolangs.generate("123", "0110")
        program = esolangs.instantiate("123", template, [0, 1])

        def work() -> object:
            return esolangs.make_debugger("123", program, "").run(timeout=2.0)

        assert self._off_thread(work) == "timeout"

    def test_the_evaluate_route_works_on_a_thread(self) -> None:
        r"""``timeout=None`` is unbounded for ``run`` and settled here."""
        for language in ("123", "ArrowQueue", "Point Break"):
            outcome = self._off_thread(
                lambda language=language: esolangs.evaluate(  # type: ignore[misc]
                    language, "0110", timeout=None
                )
            )
            assert outcome == "0110", language

    def test_the_main_thread_is_unaffected(self) -> None:
        r"""The refusal is about threads, not about timeouts."""
        assert esolangs.run("brainfuck", "+++.", "", 5) == "\x03"


# 7.8s over 21 tests: each.
@pytest.mark.medium
# 7.8s over 21 tests: each.
@pytest.mark.medium
# 7.8s over 21 tests: each.
@pytest.mark.medium
class TestTheVersionIsResolvedWhenAsked:
    r"""``importlib.metadata`` was two fifths of the import for a string."""

    def test_it_still_answers(self) -> None:
        r"""Lazy is only acceptable while the answer is the same one."""
        assert re.match(r"^\d+\.\d+", esolangs.__version__)

    def test_it_is_cached_after_the_first_read(self) -> None:
        r"""Otherwise every access pays what the import used to."""
        first = esolangs.__version__
        assert "__version__" in vars(esolangs)
        assert esolangs.__version__ is first

    def test_metadata_is_not_imported_by_importing_us(self) -> None:
        r"""The measurement, as a check rather than a note in a commit."""
        code = "import sys; import esolangs; print('importlib.metadata' in sys.modules)"
        result = subprocess.run(
            [sys.executable, "-c", code], capture_output=True, text=True, check=True
        )
        assert result.stdout.strip() == "False", result.stdout

    def test_reading_it_does_import_metadata(self) -> None:
        r"""The other half: deferred, not removed."""
        code = (
            "import sys; import esolangs; esolangs.__version__; "
            "print('importlib.metadata' in sys.modules)"
        )
        result = subprocess.run(
            [sys.executable, "-c", code], capture_output=True, text=True, check=True
        )
        assert result.stdout.strip() == "True", result.stdout

    def test_an_unknown_attribute_still_fails_normally(self) -> None:
        r"""A module ``__getattr__`` that swallows misses hides typos."""
        with pytest.raises(AttributeError, match="nosuchthing"):
            esolangs.nosuchthing  # type: ignore[attr-defined]  # noqa: B018

    def test_the_namespace_is_unchanged(self) -> None:
        r"""``dir`` must still match ``__all__``, which the hook could break."""
        assert dir(esolangs) == sorted(esolangs.__all__)

    def test_the_cli_reports_it(self) -> None:
        r"""The one caller that always wants it."""
        result = subprocess.run(
            [sys.executable, "-m", "esolangs", "--version"],
            capture_output=True,
            text=True,
            check=True,
        )
        assert result.stdout.strip() == f"esolangs {esolangs.__version__}"


class TestTheVmPathRefusesLikeRunDoes:
    r"""``run`` translated an interpreter's exceptions and the VM did not."""

    JUNK = ("]", "}", ")", "ZZZ", "[", "\x00")

    @pytest.mark.parametrize("entry", ["make_vm", "make_debugger"])
    def test_a_malformed_program_is_a_program_error(self, entry: str) -> None:
        r"""The one-character case, on the language it was reported for."""
        with pytest.raises(esolangs.ProgramError, match="unmatched"):
            getattr(esolangs, entry)("brainfuck", "]")

    def test_no_language_leaks_anything_else(self) -> None:
        r"""All 69 against six kinds of junk, both entry points."""
        escapes = []
        for name in esolangs.list_languages():
            for junk in self.JUNK:
                for entry in ("make_vm", "make_debugger"):
                    try:
                        getattr(esolangs, entry)(name, junk)
                    except esolangs.EsolangError:
                        pass
                    except Exception as exc:
                        escapes.append((name, entry, junk, type(exc).__name__))
        assert not escapes, escapes[:5]

    def test_the_two_paths_agree_on_the_class(self) -> None:
        r"""Not merely "both raise" -- both raise the *same* thing."""
        for entry in (esolangs.make_vm, esolangs.make_debugger):
            with pytest.raises(esolangs.ProgramError) as stepped:
                entry("brainfuck", "]")
            with pytest.raises(esolangs.ProgramError) as ran:
                esolangs.run("brainfuck", "]")
            assert str(stepped.value) == str(ran.value)

    def test_a_recursion_limit_is_an_interpreter_limit(self) -> None:
        r"""Ninety open parens raised a bare ``RecursionError`` from ``step``."""
        vm = esolangs.make_vm("Algebraic Programming Language", "(" * 90)
        with pytest.raises(esolangs.InterpreterLimitError):
            vm.step()


class TestAnAddressIsNotAllocatedOnTrust:
    r"""Three interpreters grew a store to whatever the program named."""

    HUGE: ClassVar[list[tuple[str, str]]] = [
        ("S*bleq", "100000000000000000000 0 0"),
        ("S*bleq", "1000000000000000000 0 0"),
        ("Decleq", "1 100000000000000000000"),
        ("ZTOALC L", "2\nu = [99999999999999999999]"),
    ]

    @pytest.mark.parametrize(("language", "program"), HUGE)
    def test_it_is_refused_cleanly(self, language: str, program: str) -> None:
        r"""Refused before allocating, so a bigger machine thrashes no worse."""
        with pytest.raises(esolangs.InterpreterLimitError, match="grow its store"):
            esolangs.run(language, program, "", 2)

    def test_an_ordinary_address_still_grows(self) -> None:
        r"""A cap that refused real programs would be worse than the bug."""
        assert esolangs.run("S*bleq", "20 0 0", "", 5) == ""
        assert esolangs.evaluate("Decleq", "0110", timeout=30) == "0110"
        assert esolangs.evaluate("S*bleq", "0110", timeout=30) == "0110"
        assert esolangs.evaluate("ZTOALC L", "0110", timeout=30) == "0110"


class TestDecleqNegativeAddressing:
    r"""A write past the left end escaped as a bare ``IndexError``."""

    def test_it_halts_instead_of_leaking(self) -> None:
        r"""Four characters, reduced from a 20,000-character random program."""
        with pytest.raises(esolangs.HaltError, match="past the left end"):
            esolangs.run("Decleq", "4 -8", "", 2)

    def test_the_documented_negative_write_is_unchanged(self) -> None:
        r"""Indexing from the right is deliberate and pinned elsewhere."""
        vm = esolangs.make_vm("Decleq", "0 -1 3")
        vm.step()
        assert list(vm.memory)[:3] == [0, -1, -1]

    def test_the_asymmetry_is_documented(self) -> None:
        r"""A read of -1 is 0 and a write to -1 lands on the last cell."""
        spec = esolangs.spec("Decleq")
        assert "negative" in spec.lower()
        assert "read back" in spec or "cannot read" in spec


class TestThePathGuardKnowsMoreThanTxt:
    r"""It tested for a literal ``.txt`` and nothing else."""

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
        r"""Rooted, or ending in a short extension, and only path characters."""
        with pytest.raises(esolangs.ProgramError, match="looks like a path"):
            esolangs.run("brainfuck", argument, "", 5)

    @pytest.mark.parametrize("program", ["+++.", ".", "..", "---.", ">>++<<--."])
    def test_a_real_program_still_runs(self, program: str) -> None:
        r"""``.`` and ``..`` are legal brainfuck and must not be mistaken."""
        esolangs.run("brainfuck", program, "", 5)

    @pytest.mark.parametrize("program", ["~~", "~*+", ".", "..", "-", "a/b/c"])
    def test_a_hand_written_program_is_not_mistaken(self, program: str) -> None:
        r"""``~~`` is two ArrowQueue commands and was refused."""
        assert not esolangs._looks_like_a_path(program), program  # noqa: SLF001

    def test_no_generated_program_is_mistaken(self) -> None:
        r"""The widened rule is only safe while this holds."""
        mistaken = []
        for name in esolangs.list_languages():
            for table in ("01", "0110"):
                program = esolangs.generate(name, table)
                if esolangs._looks_like_a_path(program):  # noqa: SLF001
                    mistaken.append((name, table))
        assert not mistaken, mistaken
