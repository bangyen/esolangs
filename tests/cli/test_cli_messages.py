"""What the CLI says when something is wrong, and when it stays quiet."""

import io
import shlex
import sys
from dataclasses import replace
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pytest

import esolangs
from esolangs.cli import main
from esolangs.cli.hints import _timeout_text
from esolangs.cli.io import _StdoutEncodingError, _write_output
from esolangs.registry import LANGUAGES, _table
from tests.support.cli_support import _failure, _refused, call_both, call_main
from tests.support.pick import one, one_where
from tests.support.reference import REFERENCE

#: A language whose input bits are not spelled 0 and 1, if one is registered.
_SPELLED = one_where(lambda d: d.input_encoding != ("0", "1"), reads_input=True)
_STREAM = one(input_shape="char_stream")


@pytest.mark.parametrize("bound", [None, "custom_budget", []])
def test_unknown_budget_diagnostics_keep_their_hint(bound, monkeypatch) -> None:
    error = esolangs.ExecutionBudgetError("budget exhausted", hint="check the bound")
    if bound is not None:
        monkeypatch.setattr(error, "bound", bound, raising=False)
    assert _timeout_text(error) == "budget exhausted\nhint: check the bound"


class TestTheHintsStayQuietWhenTheyDoNotApply:
    """Each hint added this round rewrites one message and no others."""

    def test_encode_leaves_an_unrelated_error_alone(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Only the message naming ``instantiate()`` gets rewritten."""
        with pytest.raises(SystemExit) as exc:
            call_main(["encode-inputs", "Nonexistent", "10"], capsys)
        assert exc.value.code == 2
        err = capsys.readouterr().err
        assert "unknown language" in err
        assert "generate --bits" not in err


class TestSmallerReportsFromRoundFifteen:
    """Each one was information that was wrong or hard to find."""

    def test_a_bad_truth_table_echoes_the_argument(self) -> None:
        """It printed ``sorted(set(...))``: "nonsense" came back as "enos"."""
        with pytest.raises(esolangs.TruthTableError, match="got 'nonsense'"):
            esolangs.generate(REFERENCE, "nonsense")

    def test_it_also_names_the_offending_character(self) -> None:
        """So a long table does not have to be diffed by eye."""
        with pytest.raises(esolangs.TruthTableError, match="at position 2"):
            esolangs.generate(REFERENCE, "01x1")

    @pytest.mark.parametrize(
        ("name", "phrase"),
        [
            *(
                (n, "adjacent bit characters")
                for n in one(input_shape="char_stream_cyclic")
            ),
            *((n, "one decimal row index") for n in one(input_shape="row_index")),
            (REFERENCE, "adjacent bit characters"),
        ],
    )
    def test_describe_spells_the_stdin_out(
        self, name: str, phrase: str, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A reader had two fields to compose; templates got a sentence."""
        out = call_main(["describe", name], capsys)
        assert phrase in out


# 1.8s over 45 tests: drives the CLI as a subprocess.
@pytest.mark.medium
class TestRoundSixQol:
    """The CLI no longer sends its users to the Python API for basics."""

    def test_encode_prints_the_stdin_a_language_wants(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """`run --help` used to answer this with a `python -c` incantation."""
        for name in _SPELLED:
            zero, one = esolangs.describe(name).input_encoding
            assert (
                call_main(["encode-inputs", name, "10"], capsys) == f"{one}\n{zero}\n"
            )

    @pytest.mark.parametrize("stream", _STREAM)
    def test_encode_then_run_computes_the_table(
        self, stream: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The pipeline the help now recommends, at an odd arity."""
        path = tmp_path / "tg.txt"
        esolangs.to_file(stream, esolangs.generate(stream, "10010110"), path)
        got = ""
        for row in range(8):
            stdin = call_main(["encode-inputs", stream, f"{row:03b}"], capsys)
            got += call_main(["run", stream, str(path)], capsys, stdin=stdin)[-1:]
        assert got == "10010110"

    def test_version_is_accepted_after_a_subcommand(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The top-level help advertises it without saying where it goes."""
        with pytest.raises(SystemExit) as exc:
            call_main(["list", "--version"], capsys)
        assert exc.value.code == 0
        assert esolangs.__version__ in capsys.readouterr().out

    def test_a_program_that_prints_nothing_says_so_on_a_terminal(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Silence was indistinguishable from piping to the wrong path."""
        empty = tmp_path / "empty.txt"
        empty.write_text("")
        # Not ``call_main``: it drains the capture buffer to return stdout,
        # and the note under test goes to stderr.
        with (
            patch.object(sys, "argv", ["esolangs", "run", REFERENCE, str(empty)]),
            patch.object(sys, "stdin", StringIO("")),
            patch.object(sys.stdout, "isatty", lambda: True),
        ):
            main()
        captured = capsys.readouterr()
        assert captured.out == ""
        assert "printed nothing" in captured.err
        assert "the file is empty" in captured.err

    def test_a_pipe_still_receives_exactly_nothing(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The note is for a terminal; piped output stays byte-exact."""
        empty = tmp_path / "empty.txt"
        empty.write_text("")
        assert call_main(["run", REFERENCE, str(empty)], capsys) == ""


class TestTheLastResortPaths:
    """Refusals a reader only meets when something has already gone wrong."""

    def test_an_oversized_program_is_refused(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A megabyte is far past anything this package generates."""
        path = tmp_path / "huge.bf"
        path.write_text("+" * (1024 * 1024 + 1))
        with pytest.raises(SystemExit) as exc:
            call_main(["run", REFERENCE, str(path)], capsys)
        assert exc.value.code == 2
        assert "larger than" in capsys.readouterr().err

    def test_redirected_stdout_accepts_only_utf8_text(self) -> None:
        buffer = io.BytesIO()
        with (
            io.TextIOWrapper(buffer, encoding="ascii") as stdout,
            patch.object(sys, "stdout", stdout),
        ):
            _write_output("é")
            with pytest.raises(_StdoutEncodingError, match="surrogate at character 1"):
                _write_output("a\ud800")
            assert buffer.getvalue() == "é".encode()


@pytest.mark.parametrize(
    ("bad", "good", "hint"),
    [
        ("0120", "0110", "without spaces or separators"),
        ("010", "0110", "two inputs need four"),
        ("1", "11", "constant with one input"),
    ],
)
def test_truth_table_hint_and_corrected_cli_program(
    bad, good, hint, tmp_path, capsys
) -> None:
    out, err = _failure(["generate", REFERENCE, bad], capsys)
    assert out == ""
    assert err.count("hint:") == 1
    assert hint in err
    program, err = call_both(["generate", REFERENCE, good], capsys)
    assert err == ""
    path = tmp_path / "generated.bf"
    path.write_text(program)
    bits = "01" if len(good) == 4 else "0"
    stdin, err = call_both(["encode-inputs", REFERENCE, bits], capsys)
    assert err == ""
    answer, err = call_both(["run", REFERENCE, str(path)], capsys, stdin)
    assert answer.strip() == "1"
    assert err == ""


def test_reader_template_hint_names_cli_encode(capsys) -> None:
    _, err = _failure(["generate", "--bits", "01", REFERENCE, "0110"], capsys)
    assert "hint: pipe input from esolangs encode-inputs brainfuck <bits>" in err
    assert "stdin=encode_inputs" not in err


@pytest.mark.parametrize("language", one(parameterized=True))
def test_encode_template_refusal_points_to_cli_generation(capsys, language) -> None:
    out, err = _failure(["encode-inputs", language, "01"], capsys)
    assert out == ""
    assert "reads no stdin for its input bits" in err
    assert "instantiate()" not in err
    hint = err.split("embed them in source with: ", 1)[1]
    assert shlex.split(hint) == [
        "esolangs",
        "generate",
        "--bits",
        "<bits>",
        language,
        "<table>",
    ]


@pytest.mark.parametrize(
    "args",
    [
        ["", REFERENCE, "01"],
        ["two", REFERENCE, "01"],
        [REFERENCE, "01"],
        ["--width", "2", REFERENCE, "01"],
    ],
)
def test_bad_bits_are_refused_before_synthesis(capsys, monkeypatch, args) -> None:
    def unused(*_args, **_kwargs):
        pytest.fail("invalid --bits launched generation")

    monkeypatch.setattr(esolangs, "generate", unused)
    out, err = _failure(["generate", "--bits", *args], capsys)
    assert out == ""
    assert "--bits must be a string of 0s and 1s" in err


@pytest.mark.parametrize("language", one(answer_mode="termination"))
def test_read_answer_leaves_a_timed_out_termination_undecided(capsys, language) -> None:
    out, err = _failure(["read-answer", language], capsys)
    assert out == ""
    assert "A timeout leaves the answer undecided." in err


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"answer_pattern": "("}, "invalid answer pattern"),
        (
            {"answer_mode": "termination", "answer_values": ("halts",)},
            "invalid answer encoding",
        ),
        (
            {"answer_mode": "termination", "answer_values": ("diverges", "halts")},
            "answers 0 if it diverges and 1 if it halts",
        ),
    ],
)
def test_read_answer_checks_the_catalog_before_stdin(
    monkeypatch, capsys, changes, message
) -> None:
    original = LANGUAGES[REFERENCE]
    contract = replace(original.contract, **changes)
    scope = esolangs.Catalog([replace(original, contract=contract)])
    monkeypatch.setattr(_table, "CATALOG", scope)

    def unexpected_read(*_args, **_kwargs):
        pytest.fail("read-answer waited for input despite its catalog refusal")

    monkeypatch.setattr("esolangs.cli._read_stdin", unexpected_read)
    out, error = _failure(["read-answer", REFERENCE], capsys)
    assert not out
    assert message in error


def test_read_answer_lets_a_regex_recognize_empty_output(monkeypatch, capsys) -> None:
    original = LANGUAGES[REFERENCE]
    contract = replace(original.contract, answer_pattern="^$", answer_values=("", "1"))
    scope = esolangs.Catalog([replace(original, contract=contract)])
    monkeypatch.setattr(_table, "CATALOG", scope)
    assert scope.bind(REFERENCE).read_answer("") == "0"
    assert call_both(["read-answer", REFERENCE], capsys) == ("0\n", "")


def test_timeout_hint_names_cli_flag_and_correction_runs(tmp_path, capsys) -> None:
    path = tmp_path / "program.bf"
    path.write_text("+.")
    _, err = _failure(["run", "--execution-timeout", "0", REFERENCE, str(path)], capsys)
    assert err.startswith("--execution-timeout must be positive, got 0.0\n")
    assert "hint: set a timeout in seconds, for example --execution-timeout 5.0" in err
    output, err = call_both(
        ["run", "--execution-timeout", "5.0", REFERENCE, str(path)], capsys
    )
    assert output == "\x01"
    assert err == ""
    # The hint said "the bound" for both; it names the flag that raises it.
    path.write_text("+[]")
    _, err = _failure(["run", "--max-steps", "5", REFERENCE, str(path)], capsys, 124)
    assert err.endswith("blocked input before increasing --max-steps\n")


def test_cli_note_translation_preserves_multiline_diagnostic_and_api_notes() -> None:
    from esolangs.cli.hints import _cli_error_text

    error = esolangs.ArgumentError("bad timeout=5.0\nscale=1")
    error.add_note("hint: set timeout=5.0 or scale=1")
    error.add_note("unrelated context")
    assert _cli_error_text(error) == (
        "bad timeout=5.0\nscale=1\nhint: set --execution-timeout 5.0 or --scale 1"
    )
    assert error.__notes__ == ["hint: set timeout=5.0 or scale=1", "unrelated context"]


def test_text_generator_scale_hint_uses_cli_flag(capsys) -> None:
    _, err = _failure(["generate", "--scale", "2", REFERENCE, "0110"], capsys)
    assert "hint: omit --scale for text languages" in err


#: Commands refused with exit code 2, and what stderr must say.
#: ``prog:SRC`` is a file holding SRC; a third item is stdin.
_REFUSALS = {
    "removed_suggest_is_refused": ("suggest", "unknown command: suggest"),
    "encode_refuses_a_language_that_reads_nothing": (
        "encode-inputs ArrowQueue 01",
        "reads no stdin",
    ),
    "a_repeated_option_is_refused": (
        "generate --bits 10 --bits 01 brainfuck 0110",
        "more than once",
    ),
}


@pytest.mark.parametrize("case", _REFUSALS.values(), ids=list(_REFUSALS))
def test_a_bad_command_exits_2_and_says_why(
    case: tuple[str, ...], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    command, message, *stdin = case
    assert message in _refused(command, tmp_path, capsys, *stdin)


#: Refused, but these hints must stay quiet.
_QUIET = {
    "an_unknown_language_is_not_called_a_swapped_argument": (
        "generate Nonexistent 0110",
        "looks like a truth table",
    ),
    "a_non_table_run_of_digits_is_not_called_a_swap": (
        "generate 011 brainfuck",
        "looks like a truth table",
    ),
}


@pytest.mark.parametrize("case", _QUIET.values(), ids=list(_QUIET))
def test_a_bad_command_exits_2_without_the_hint(
    case: tuple[str, ...], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    command, message, *stdin = case
    assert message not in _refused(command, tmp_path, capsys, *stdin)


@pytest.mark.parametrize(
    "language",
    one_where(
        lambda facts: " " in facts.name,
        boolean_generator=True,
        parameterized=False,
        source_kind="text",
        answer_mode="output",
        reads_input=True,
    ),
)
def test_generate_quotes_a_multiword_language(
    language: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _, split = _failure(["generate", *language.split(), "01"], capsys)
    assert shlex.split(split.split("quote it as ", 1)[1]) == [language]

    _, swapped = _failure(["generate", "01", language], capsys)
    command = shlex.split(swapped.split("first: ", 1)[1])
    assert command == ["esolangs", "generate", language, "01"]
    path = tmp_path / "program.txt"
    path.write_text(call_main(command[1:], capsys), encoding="utf-8")
    for bit in (0, 1):
        stdin = esolangs.encode_inputs(language, [bit])
        output = call_main(["run", language, str(path)], capsys, stdin)
        assert esolangs.read_answer(language, output) == str(bit)


@pytest.mark.parametrize("name", ["a; echo x", "--name; echo x"])
def test_generate_swap_suggestion_quotes_metacharacters(
    name: str, capsys: pytest.CaptureFixture[str]
) -> None:
    _, error = _failure(["generate", "--", "01", name], capsys)
    command = error.split("first: ", 1)[1]
    lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    separator = ["--"] if name.startswith("-") else []
    assert list(lexer) == ["esolangs", "generate", *separator, name, "01"]
