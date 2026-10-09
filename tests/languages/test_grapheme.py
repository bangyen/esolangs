"""Grapheme through the shared API, CLI and machinery."""

import json
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pytest

import esolangs
import esolangs.debugger as debugger_api
from esolangs import DialectSettings
from esolangs._evaluate import _evaluate
from esolangs.cli_debug import _run_tui_session
from esolangs.debugger import make_debugger
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.stack_based.grapheme import _Machine
from esolangs.interpreters.stack_based.grapheme import (
    suggest_corrections as _grapheme_corrections,
)
from esolangs.tagged import _Tagged
from esolangs.tui import History, replay
from esolangs.vm import complete_vm, make_vm
from tests.cli.test_cli import call_main
from tests.cli_support import assert_repair_runs, call_both, repaired
from tests.stdin_check import _check_stdin
from tests.test_dialects import Unreadable
from tests.witness_tables import witnesses


@pytest.mark.medium
def test_portable_choices_and_memory_budget_reach_worker(tmp_path, capsys, monkeypatch):
    command = "run"
    from esolangs import _isolated

    budget = 96 * 1024 * 1024
    source = esolangs.generate(
        "Grapheme",
        "01",
        settings=DialectSettings(integer_conversion="after_each_letter"),
    )
    path = tmp_path / "program.json"
    path.write_text(esolangs.dump_program("Grapheme", source), encoding="utf-8")
    monkeypatch.setattr(_isolated.sys, "platform", "linux")
    calls = []
    runner = vars(esolangs)["_run_isolated"]

    def capture(*args, **kwargs):
        # Check dispatch on every host; the separate Linux test enforces the cap.
        calls.append(kwargs.pop("max_memory"))
        assert kwargs["settings"] == source.settings
        return runner(*args, **kwargs)

    monkeypatch.setattr(esolangs, "_run_isolated", capture)
    options = ["--isolated"]
    output, error = call_both(
        [
            command,
            "--portable",
            *options,
            "--max-memory",
            str(budget),
            "Grapheme",
            str(path),
        ],
        capsys,
        esolangs.encode_inputs("Grapheme", [1]),
    )
    assert (output, error) == ("1", "")
    assert calls == [budget]


@pytest.mark.parametrize(
    ("source", "output"),
    [
        ("EaE", ""),
        ("eabey", "AB"),
    ],
)
def test_grapheme_case_corrections_include_literals(source, output, tmp_path, capsys):
    edits = _grapheme_corrections(source)
    assert repaired(source, edits) == source.upper()
    assert all(edit.after == edit.before.upper() for edit in edits)
    assert esolangs.run("Grapheme", repaired(source, edits), timeout=1) == output
    path = tmp_path / "program"
    path.write_text(source)
    out, err = call_both(["suggest", "Grapheme", str(path)], capsys)
    assert "->" in out
    assert not err
    assert path.read_text() == source


@pytest.mark.filterwarnings("ignore::UserWarning")
class TestGraphemeReadsWhatTheDocsNowSay:
    """The stated mechanism was wrong, and so was its stated direction."""

    def test_only_an_a_line_reads_as_one(self) -> None:
        """'0', '1', 'x' and ' ' are all non-empty and all read as 0."""
        program = esolangs.generate("Grapheme", "01")
        answers = {}
        for line in ("A", "%", "0", "1", "x", " "):
            output = esolangs.run("Grapheme", program, stdin=line + "\n", timeout=10)
            answers[line] = esolangs.read_answer("Grapheme", output)
        assert answers == {
            "A": "1",
            "%": "0",
            "0": "0",
            "1": "0",
            "x": "0",
            " ": "0",
        }

    def test_naive_input_answers_the_all_zeros_row(self) -> None:
        """The true consequence: every bit reads 0, so you get row 0."""
        table = "0001"  # AND: row 0 is 0, row 3 is 1
        program = esolangs.generate("Grapheme", table)
        output = esolangs.run("Grapheme", program, stdin="1\n1\n", timeout=10)
        assert esolangs.read_answer("Grapheme", output) == table[0]


def test_conversion_reaches_debugger_and_bound_language():
    settings = DialectSettings(integer_conversion="after_each_letter")
    language = esolangs.Language("Grapheme")
    assert language.run("FAFY", settings=settings) == "10"
    debugger = make_debugger("Grapheme", "FAFY", settings=settings)
    debugger.run(max_steps=10)
    assert debugger.vm.output == "10"


@pytest.mark.parametrize(
    "isolated", [False, pytest.param(True, marks=pytest.mark.medium)]
)
def test_loaded_text_tag_is_respected(isolated):
    source = _Tagged(
        "FAFY", "Grapheme", DialectSettings(integer_conversion="after_each_letter")
    )
    stream = StringIO()
    stream.read = lambda: source
    assert esolangs.run("Grapheme", stream, isolated=isolated) == "10"
    stream = StringIO()
    stream.read = lambda: source
    assert complete_vm(make_vm("Grapheme", stream), 10) == "10"


def test_evaluation_inherits_loaded_metadata():
    source = esolangs.generate(
        "Grapheme",
        "01",
        settings=DialectSettings(integer_conversion="after_each_letter"),
    )
    stream = StringIO()
    stream.read = lambda: source
    assert _evaluate("Grapheme", stream, inputs=1) == "01"


def test_metadata_is_a_fresh_copy():
    info = esolangs.describe("Grapheme")["dialect_settings"]
    info["integer_conversion"]["default"] = "after_each_letter"
    again = esolangs.describe("Grapheme")["dialect_settings"]
    assert again["integer_conversion"]["default"] == "between_letters"


def test_cli_json_describes_dialect_choices(capsys):
    output, _ = call_both(["describe", "--json", "Grapheme"], capsys)
    schema = json.loads(output)["dialect_settings"]
    assert schema["integer_conversion"]["default"] == "between_letters"
    assert schema["integer_conversion"]["requires"] == {}


def test_unterminated_modes_flush_in_called_frames():
    options = {"integer_conversion": "after_each_letter"}
    machine = _Machine("FA", ScriptedIO(""), **options)
    while not machine.halted:
        machine.step()
    assert machine.stack == [10]
    settings = DialectSettings(**options)
    assert esolangs.run("Grapheme", "HFAHIY", settings=settings) == "10"


# The dialect is machine-wide; one string call and one Z rewind witness it.
@pytest.mark.parametrize("source", ["EFAFYEG", "FZFHFAFYMHZ"])
def test_called_code_uses_selected_conversion(source):
    assert (
        esolangs.run(
            "Grapheme",
            source,
            settings=DialectSettings(integer_conversion="after_each_letter"),
        )
        == "10"
    )


def test_numeric_and_function_conversion_remain_literal():
    assert (
        esolangs.run(
            "Grapheme",
            "FAFJYHABHJY",
            settings=DialectSettings(integer_conversion="after_each_letter"),
        )
        == "102"
    )


def test_string_skip_count_uses_conversion():
    source = "FZFEAEFZFV" + "P" * 9 + "TY"
    settings = DialectSettings(integer_conversion="after_each_letter")
    assert esolangs.run("Grapheme", source, settings=settings) == "0"
    assert esolangs.run("Grapheme", source) == "1"


@pytest.mark.parametrize(("source", "expected"), [("FAFDY", "1"), ("EABEDY", "AB")])
def test_unset_names_read_as_themselves(source, expected):
    assert esolangs.run("Grapheme", source) == expected


@pytest.mark.parametrize(
    "choices", [{"integer_conversion": "bad"}, {"integer_conversion": 1}]
)
def test_invalid_settings_precede_source_reads(choices):
    with pytest.raises(esolangs.ArgumentError):
        esolangs.run("Grapheme", Unreadable(), settings=DialectSettings(**choices))


@pytest.mark.medium
def test_generated_corpus():
    settings = DialectSettings(integer_conversion="after_each_letter")
    for n in range(1, 4):
        for table in witnesses(n):
            for balance in (False, True):
                source = esolangs.generate(
                    "Grapheme", table, settings=settings, balance=balance
                )
                assert _evaluate("Grapheme", source, inputs=n) == table


@pytest.mark.medium
def test_prose_conversion_at_six_inputs():
    table = "".join(str(row.bit_count() & 1) for row in range(64))
    source = esolangs.generate(
        "Grapheme",
        table,
        settings=DialectSettings(integer_conversion="after_each_letter"),
    )
    assert _evaluate("Grapheme", source, inputs=6) == table


@pytest.mark.medium
@pytest.mark.parametrize("isolated", [False, True])
def test_portable_settings_vm_and_override(isolated):
    settings = DialectSettings(integer_conversion="after_each_letter")
    source = _Tagged("FAFY", "Grapheme", settings)
    restored = esolangs.load_program(
        "Grapheme", esolangs.dump_program("Grapheme", source)
    )
    assert esolangs.run("Grapheme", restored, isolated=isolated) == "10"
    assert esolangs.run("Grapheme", restored, max_steps=20) == "10"
    assert complete_vm(make_vm("Grapheme", restored), 20) == "10"
    assert (
        esolangs.run(
            "Grapheme",
            restored,
            settings=DialectSettings(integer_conversion="between_letters"),
        )
        == "1"
    )
    assert source.settings == settings


def test_metadata():
    settings = esolangs.describe("Grapheme")["dialect_settings"]
    assert settings["integer_conversion"]["default"] == "between_letters"
    assert settings["integer_conversion"]["choices"] == (
        "between_letters",
        "after_each_letter",
    )
    assert set(settings) == {"integer_conversion"}


def test_cli_debug_uses_settings(tmp_path: Path, capsys):
    source = tmp_path / "conversion.grapheme"
    source.write_text("FAFY")
    output, _ = call_both(
        [
            "debug",
            "--settings",
            '{"integer_conversion":"after_each_letter"}',
            "Grapheme",
            str(source),
        ],
        capsys,
    )
    assert "halted: yes" in output
    assert "output: '10'" in output


def test_tui_settings_reach_wrapper():
    settings = DialectSettings(integer_conversion="after_each_letter")
    with patch("esolangs.cli_debug.run_tui") as run:
        _run_tui_session("Grapheme", "FAFY", "", {}, None, settings)
    assert run.call_args.kwargs["settings"] is settings


def test_tui_replay_retains_settings():
    settings = DialectSettings(integer_conversion="after_each_letter")
    history = History("Grapheme", "FAFYPPPP", settings=settings)
    history.budget = 1
    assert history.at(8).output == "10"
    assert history.at(4).output == "10"
    assert history.at(2) == replay("Grapheme", "FAFYPPPP", "", 2, settings=settings)


@pytest.mark.medium
def test_raw_text_preserves_newlines_and_explicit_settings():
    source = "FAFY\n"
    choices = DialectSettings(integer_conversion="after_each_letter")
    restored = esolangs.load_program(
        "Grapheme", esolangs.dump_program("Grapheme", source, settings=choices)
    )
    assert str(restored) == source
    assert restored.settings == choices
    assert esolangs.run("Grapheme", restored) == "10"


class TestGrapheme:
    def test_stack_exposed(self) -> None:
        vm = debugger_api.make_vm("Grapheme", "FAFY")
        assert (vm.ip, vm.memory, vm.stack) == ((0,), [], [])
        vm.step()  # F starts int mode
        vm.step()  # A accumulates
        vm.step()  # F ends int mode, pushes 1
        assert vm.stack == [1]
        vm.step()  # Y prints
        assert vm.output == "1"
        assert vm.halted
        assert vm.ip == (len("FAFY"),)  # frames are gone once halted
        assert vm.memory == []

    def test_rejects_non_uppercase(self) -> None:
        with pytest.raises(ValueError, match="uppercase"):
            debugger_api.make_vm("Grapheme", "a")

    def test_ip_exposes_the_call_stack(self) -> None:
        # FAF pushes 1, EKE pushes the string "K"; G calls it as a nested
        # frame (K dups the shared stack's top), so ip grows to (caller pc,
        # callee pc) while that frame is active instead of folding it into
        # one cursor.
        vm = debugger_api.make_vm("Grapheme", "FAFEKEG")
        for _ in range(7):
            vm.step()
        assert vm.ip == (7, 0)  # caller's pc past G, callee's pc at its start
        assert vm.stack == [1]
        vm.step()  # the callee's K command runs, then the frame finishes
        assert vm.halted
        assert vm.ip == (7,)  # the callee frame is gone once it returns
        assert vm.stack == [1, 1]

    def test_caller_resumes_after_the_callee_returns(self) -> None:
        # Y after G still has to run once the callee pops, proving the
        # halted-``ip`` sentinel is the top-level frame's own end position,
        # not an artifact of the callee finishing on the caller's last pc.
        vm = debugger_api.make_vm("Grapheme", "FAFEKEGY")
        for _ in range(9):
            vm.step()
        assert vm.halted
        assert vm.output == "1"  # Y printed the duplicated int 1
        assert vm.ip == (len("FAFEKEGY"),)


class TestStdinIsCheckedAgainstTheDeclaredAlphabet:
    """`encode` refused these bytes all along; `run` answered them."""

    @pytest.mark.parametrize("line", [" 1", "2", "01"])
    def test_plain_run_accepts_a_non_boolean_line(
        self, line: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """General execution does not impose a Boolean input alphabet."""
        path = tmp_path / "p.txt"
        path.write_text(esolangs.generate("brainfuck", "0101"))
        _out, err = call_both(
            ["run", "brainfuck", str(path)], capsys, stdin=f"0\n{line}\n"
        )
        assert "spells its bits" not in err

    def test_a_correct_encoding_is_silent_and_right(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Doing it right must stay quiet, or the check is noise."""
        path = tmp_path / "p.txt"
        path.write_text(esolangs.generate("brainfuck", "0101"))
        out, err = call_both(["run", "brainfuck", str(path)], capsys, stdin="01")
        assert out.strip() == "1"
        assert err == ""

    def test_the_alphabet_check_reads_the_declared_alphabet(self) -> None:
        """Grapheme's own bits are %/A, so 0/1 is what is wrong there."""
        _check_stdin("Grapheme", "%\nA\n")
        # 0/1 is wrong *here*, and the specific message is the one that
        # fires: the general stray-line rule runs last so a language with
        # something better to say keeps saying it.
        with pytest.raises(esolangs.ArgumentError, match="spells its bits"):
            _check_stdin("Grapheme", "0\n1\n")


class TestTheShapeWarningFiresOnlyWhenItShould:
    """The last silent-wrong path: stdin in the shape a reader expects."""

    def test_an_ordinary_language_is_never_warned_about(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The languages that read 0/1 lines must stay silent."""
        path = tmp_path / "bf.txt"
        path.write_text(esolangs.generate("brainfuck", "0110"))
        out, err = call_both(["run", "brainfuck", str(path)], capsys, stdin="10")
        assert out == "1"
        assert err == ""

    def test_the_warning_does_not_change_the_answer(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """It is advice; the run is exactly what it was."""
        path = tmp_path / "g.txt"
        path.write_text(esolangs.generate("Grapheme", "0110"))
        warned = call_main(["run", "Grapheme", str(path)], capsys, stdin="1\n0\n")
        capsys.readouterr()
        stdin = esolangs.encode_inputs("Grapheme", [1, 0])
        right = call_main(["run", "Grapheme", str(path)], capsys, stdin=stdin)
        assert warned == "0"
        assert right == "1"


def test_grapheme_repair_executes(tmp_path, capsys):
    assert_repair_runs("Grapheme", "FAFy", "1", tmp_path, capsys)


def test_grapheme_case_preview_preserves_other_characters():
    source = "Eé1?E\naY"
    assert repaired(source, _grapheme_corrections(source)) == "Eé1?E\nAY"
    assert not _grapheme_corrections("EABEYFAFY")


def test_the_input_alphabet() -> None:
    assert esolangs.describe("Grapheme")["input_encoding"] == ("%", "A")
