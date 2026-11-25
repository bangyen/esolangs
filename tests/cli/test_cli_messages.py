"""What the CLI says when something is wrong, and when it stays quiet."""

import io
import json
import os
import shlex
import sys
from ast import literal_eval
from codecs import BOM_UTF8
from dataclasses import replace
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pytest

import esolangs
from esolangs.cli import main
from esolangs.cli.help import help_text
from esolangs.cli.hints import _timeout_text
from esolangs.cli.io import _StdoutEncodingError, _write_output
from esolangs.registry import LANGUAGES, _table
from esolangs.runtime.source_hints import error_text
from tests.support.cli_support import (
    _failure,
    _program,
    _refused,
    call_both,
    call_main,
    run_cli,
)
from tests.support.pick import one, one_where
from tests.support.reference import REFERENCE


@pytest.mark.parametrize(
    "language", [REFERENCE, *one(source_kind="raster", boolean_generator=True)]
)
def test_native_rejection_suggests_running_portable_json(tmp_path, capsys, language):
    api = esolangs.Language(language)
    document = api.to_json(api.generate("01"))
    path = tmp_path / "owner's portable program.json"
    path.write_text(document, encoding="utf-8")
    output, error = _failure(["run", language, str(path)], capsys)
    assert output == ""
    assert "use --artifact to run portable JSON" in error
    command = shlex.split(error.split("for example: ", 1)[1].strip())
    assert command == ["esolangs", "run", "--artifact", language, str(path)]
    for bit in (0, 1):
        output, error = call_both(command[1:], capsys, stdin=api.encode_inputs([bit]))
        assert api.read_answer(output) == str(bit)
        assert error == ""

    if language != REFERENCE:
        value = json.loads(document)
        value["format"] = {"name": value["format"]}
        path.write_text(json.dumps(value), encoding="utf-8")
        _, error = _failure(["run", language, str(path)], capsys)
        assert "--artifact" not in error


@pytest.mark.parametrize("source", ['"+."', '{"example":"+."}'])
def test_artifact_run_suggests_the_native_command_for_json_shaped_source(
    tmp_path, capsys, source
):
    path = tmp_path / "native source.bf"
    path.write_text(source, encoding="utf-8")
    output, error = _failure(["run", "--artifact", REFERENCE, str(path)], capsys)
    assert not output
    assert "remove --artifact" in error
    retry = shlex.split(error.split("for example: ", 1)[1])
    assert retry == ["esolangs", "run", REFERENCE, str(path)]
    assert call_main(retry[1:], capsys) == "\x01"


@pytest.mark.parametrize("duplicate", [False, True])
def test_native_run_keeps_json_with_only_a_similar_format_marker(
    tmp_path, capsys, duplicate
):
    api = esolangs.Language(REFERENCE)
    value = json.loads(api.to_json(api.from_source("+.")))
    path = tmp_path / "native.json"
    document = json.dumps(
        {"format": value["format"] + "_other", "language": value["language"]}
    )
    if duplicate:
        document = document[:-1] + ',"version":1,"version":1}'
    path.write_text(document, encoding="utf-8")
    output, error = call_both(["run", REFERENCE, str(path)], capsys, stdin="AAA")
    assert output == "\x00"
    assert error == ""


@pytest.mark.parametrize(
    ("field", "duplicate"), [("version", "1"), ("format", '"other"')]
)
def test_native_run_refuses_duplicate_fields_in_tagged_artifacts(
    tmp_path, capsys, field, duplicate
) -> None:
    record = esolangs.to_json(REFERENCE, "+.").rstrip()
    if field == "format":
        record = record.replace("esolangs.program", r"esolangs.\u0070rogram")
    path = tmp_path / "duplicate.json"
    path.write_text(
        record[:-1] + f",{json.dumps(field)}:{duplicate}" + "}", encoding="utf-8"
    )
    output, error = _failure(["run", REFERENCE, str(path)], capsys, stdin="AAAAAAAA")
    assert not output
    assert str(path) in error
    assert f"invalid portable program: duplicate field: {field}" in error


@pytest.mark.parametrize("field", ["settings", "language", "source"])
def test_native_run_rejects_a_tagged_artifact_with_missing_fields(
    tmp_path, capsys, field
) -> None:
    record = json.loads(esolangs.to_json(REFERENCE, "+."))
    del record[field]
    path = tmp_path / "incomplete.json"
    path.write_text(json.dumps(record), encoding="utf-8")
    output, error = _failure(["run", REFERENCE, str(path)], capsys, stdin="A")
    assert not output
    assert str(path) in error
    assert "invalid portable program: unexpected or missing fields" in error
    _, explicit = _failure(["run", "--artifact", REFERENCE, str(path)], capsys)
    assert "remove --artifact" not in explicit


@pytest.mark.parametrize(
    "document",
    [
        '{"format":"esolangs.program"',
        '{"settings":{"other":[1]},"format":"esolangs.program","source":',
        r'{"\u0066ormat":"esolangs.\u0070rogram","source":',
    ],
)
def test_native_run_stops_truncated_portable_json(tmp_path, capsys, document):
    path = tmp_path / "truncated.json"
    path.write_text(document, encoding="utf-8")
    output, error = _failure(["run", REFERENCE, str(path)], capsys, stdin="A")
    assert output == ""
    assert f"{path}: invalid portable program:" in error


def test_native_run_ignores_a_truncated_nested_format_tag(tmp_path, capsys):
    path = tmp_path / "native.bf"
    path.write_text('{"other":{"format":"esolangs.program"', encoding="utf-8")
    output, error = call_both(["run", REFERENCE, str(path)], capsys)
    assert (output, error) == ("\x00", "")


@pytest.mark.parametrize("bom_count", [1, 2])
def test_run_reports_a_bom_before_parsing_portable_json(tmp_path, capsys, bom_count):
    path = tmp_path / "portable.json"
    record = esolangs.to_json(REFERENCE, "+.").encode("utf-8")
    path.write_bytes(BOM_UTF8 * bom_count + record)
    for flags in ([], ["--artifact"]):
        output, error = _failure(
            ["run", *flags, REFERENCE, str(path)], capsys, stdin="A"
        )
        assert output == ""
        assert str(path) in error
        assert "remove the UTF-8 BOM" in error
        assert "remove --artifact" not in error
    path.write_bytes(record)
    assert call_main(["run", "--artifact", REFERENCE, str(path)], capsys) == "\x01"


def test_a_bom_prefixed_native_program_keeps_its_source_behavior(tmp_path, capsys):
    path = tmp_path / "native.bf"
    path.write_bytes(BOM_UTF8 + b"{+.}")
    assert call_main(["run", REFERENCE, str(path)], capsys) == "\x01"


@pytest.mark.parametrize("escaped_format", [False, True])
def test_native_run_stops_a_portable_record_for_an_unavailable_language(
    tmp_path, capsys, escaped_format
) -> None:
    record = json.loads(esolangs.to_json(REFERENCE, "+++++."))
    record["language"] = "UnavailableDialect"
    document = json.dumps(record)
    if escaped_format:
        document = document.replace(record["format"], r"esolangs.\u0070rogram")
    path = tmp_path / "unavailable.json"
    path.write_text(document, encoding="utf-8")

    output, error = _failure(["run", REFERENCE, str(path)], capsys, stdin="A")
    assert output == ""
    assert "portable JSON artifact for unavailable language UnavailableDialect" in error


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
        assert "the file contains no source" in captured.err

        alias = "clear\x1b[2J\nlabel"
        declaration = replace(LANGUAGES[REFERENCE], aliases=(alias,))
        scope = esolangs.Catalog([declaration])
        silent = tmp_path / "silent.txt"
        silent.write_text("+")
        with (
            patch.object(_table, "CATALOG", scope),
            patch.object(sys, "argv", ["esolangs", "run", alias, str(silent)]),
            patch.object(sys, "stdin", StringIO("")),
            patch.object(sys.stdout, "isatty", lambda: True),
        ):
            main()
        assert capsys.readouterr() == (
            "",
            r"clear\x1b[2J\nlabel: the program ran and printed nothing" + "\n",
        )
        assert scope.bind(alias).run(silent).output == ""

        renamed = replace(declaration, name=alias, aliases=())
        random = next(lang for lang in LANGUAGES.values() if lang.runtime.random)
        random_name = "draw\x1b[2J\nrandom"
        scope = esolangs.Catalog([renamed, replace(random, name=random_name)])
        with patch.object(_table, "CATALOG", scope):
            output, diagnostic = _failure(
                ["run", "--seed", "1", REFERENCE, str(silent)], capsys
            )
        assert not output
        assert diagnostic.splitlines() == [
            r"clear\x1b[2J\nlabel draws no random values, so a seed has nothing to "
            r"fix; the languages that draw are draw\x1b[2J\nrandom",
            "hint: omit --seed when running a deterministic language",
        ]
        assert scope.resolve(REFERENCE) == alias
        assert scope.resolve(random.id) == random_name

        api = scope.bind(alias)
        assert api.prepare(api.from_json(api.to_json("+."))).run().output == "\x01"
        raster = esolangs.Language(one(source_kind="raster")[0])
        pixels = raster.generate("01").source
        image = tmp_path / "program.png"
        image.write_bytes(pixels.to_png())
        record = json.loads(raster.to_json(pixels))
        record["language"] = alias
        message = r"clear\x1b[2J\nlabel requires text source, but the program is"
        for read in (
            lambda: api.from_source(pixels),
            lambda: api.from_file(image),
            lambda: api.from_json(json.dumps(record)),
        ):
            with pytest.raises(esolangs.ProgramError) as error:
                read()
            assert message in str(error.value)
            assert "\x1b" not in str(error.value)
            assert "\n" not in str(error.value)
        with patch.object(_table, "CATALOG", scope):
            output, diagnostic = _failure(["run", REFERENCE, str(image)], capsys)
        assert not output
        assert diagnostic.splitlines()[0] == f"cannot read {image}: {message} a PNG"

    def test_a_pipe_still_receives_exactly_nothing(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The empty-source note stays on stderr."""
        empty = tmp_path / "empty.txt"
        empty.write_text("")
        output, error = call_both(["run", REFERENCE, str(empty)], capsys)
        assert not output
        assert "contains no source, so there was no program to run" in error

        if os.name == "posix":
            path = tmp_path / "clear\x1b[2J\nsource"
            label = str(tmp_path / r"clear\x1b[2J\nsource")
            args = ["run", REFERENCE, str(path)]
            output, error = _failure(args, capsys)
            assert not output
            assert error.splitlines()[0].startswith(f"cannot read {label}:")
            assert "\x1b" not in error

            api = esolangs.Language(REFERENCE)
            with pytest.raises(esolangs.ProgramNotFoundError) as missing:
                api.from_file(path)
            assert str(missing.value).startswith(f"cannot read {label}:")
            assert missing.value.__cause__.filename == str(path)

            path.write_bytes(b"A\xff")
            outcome = api.execute(path)
            assert outcome.status == "rejected"
            assert isinstance(outcome.error, esolangs.ProgramError)
            message = f"cannot read {label}: not text (invalid UTF-8 at byte 1)"
            assert str(outcome.error) == message
            cause = outcome.error.__cause__
            assert isinstance(cause, UnicodeDecodeError)
            assert cause.object == b"A\xff"
            assert _failure(args, capsys) == (
                "",
                f"{message}\nhint: save the text program as UTF-8 before running it\n",
            )

            path.write_text("+.")
            assert call_both(args, capsys) == ("\x01", "")
            path.write_text("")
            assert call_both(args, capsys) == (
                "",
                f"note: {label} contains no source, so there was no program to run\n",
            )


class TestTheLastResortPaths:
    """Refusals a reader only meets when something has already gone wrong."""

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
    ("args", "reason"),
    [
        (["--bits", "", REFERENCE, "01"], "must be a string of 0s and 1s"),
        (["--bits", "two", REFERENCE, "01"], "must be a string of 0s and 1s"),
        (["--bits", REFERENCE, "01"], "must be a string of 0s and 1s"),
        (["--bits=--width", REFERENCE, "01"], "must be a string of 0s and 1s"),
        (["--bits", "--width", "2", REFERENCE, "01"], "needs a value"),
    ],
)
def test_bad_bits_are_refused_before_synthesis(
    capsys, monkeypatch, args, reason
) -> None:
    from esolangs.operations import generation

    def unused(*_args, **_kwargs):
        pytest.fail("invalid --bits launched generation")

    monkeypatch.setattr(generation, "_generate_checked", unused)
    out, err = _failure(["generate", *args], capsys)
    assert out == ""
    assert err.startswith(f"--bits {reason}")


@pytest.mark.parametrize("language", one(answer_mode="termination"))
def test_read_answer_leaves_a_timed_out_termination_undecided(capsys, language) -> None:
    out, err = _failure(["read-answer", language], capsys)
    assert out == ""
    assert "A timeout leaves the answer undecided." in err


@pytest.mark.medium
def test_read_answer_distinguishes_a_queue_dump_from_a_termination_answer(
    tmp_path: Path,
) -> None:
    generated = run_cli("generate", "--bits", "0", "ArrowQueue", "01")
    assert generated.returncode == 0, generated.stderr
    path = tmp_path / "program.txt"
    path.write_text(generated.stdout, encoding="utf-8")
    execution = run_cli("run", "--max-steps", "100", "ArrowQueue", str(path))
    assert execution.returncode == 0, execution.stderr
    assert execution.stdout

    answer = run_cli("read-answer", "ArrowQueue", stdin=execution.stdout)
    assert answer.returncode == 2
    assert not answer.stdout
    assert "answers 0 if it halts" in answer.stderr
    assert "Program output carries no answer." in answer.stderr
    assert "A timeout leaves the answer undecided." in answer.stderr
    help_page = run_cli("read-answer", "--help")
    assert help_page.returncode == 0
    assert "Program output carries no answer." in help_page.stdout


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
    name = "-Scoped answer"
    scope = esolangs.Catalog(
        [replace(original, name=name, id="scoped_answer", contract=contract)]
    )
    monkeypatch.setattr(_table, "CATALOG", scope)

    def unexpected_read(*_args, **_kwargs):
        pytest.fail("read-answer waited for input despite its catalog refusal")

    monkeypatch.setattr("esolangs.cli._read_stdin", unexpected_read)
    out, error = _failure(["read-answer", "--", name], capsys)
    assert not out
    assert message in error
    metadata = json.loads(call_main(["describe", "--json", "--", name], capsys))
    assert metadata["answer_encoding"] == list(contract.answer_values)
    assert metadata["answer_pattern"] == (contract.answer_pattern or None)
    if contract.answer_values == ("diverges", "halts"):
        assert "--execution-timeout <seconds> scoped_answer <program-file>" in error
        help_page = help_text("read-answer")
        assert f"languages that answer by terminating are {name}." in help_page
        assert "reports what its termination means" in help_page

        description = call_main(["describe", "--", name], capsys)
        assert "termination (diverges for 0, halts for 1)" in description

        unsafe = "clear\x1b[2J\nlabel"
        renamed = replace(scope.languages[name], name=unsafe)
        renamed_scope = esolangs.Catalog([renamed])
        monkeypatch.setattr(_table, "CATALOG", renamed_scope)
        help_page = help_text("read-answer", catalog=renamed_scope)
        assert r"The languages that answer by terminating are clear\x1b[2J\nlabel." in (
            help_page.splitlines()
        )
        assert "\x1b" not in help_page
        with pytest.raises(SystemExit) as exited:
            call_main(["help", "read-answer"], capsys)
        assert exited.value.code == 0
        assert capsys.readouterr() == (help_page, "")
        out, error = _failure(["read-answer", renamed.id], capsys)
        assert not out
        assert error.startswith(r"clear\x1b[2J\nlabel answers 0 if it diverges")
        assert "\x1b" not in error
        metadata = json.loads(call_main(["describe", "--json", renamed.id], capsys))
        assert metadata["name"] == unsafe
    else:
        output, diagnostic = _failure(["describe", "--", name], capsys)
        assert not output
        assert message in diagnostic


def test_read_answer_lets_a_regex_recognize_empty_output(monkeypatch, capsys) -> None:
    original = LANGUAGES[REFERENCE]

    class AnswerValues(tuple):
        def __iter__(self):
            return iter(("other", "incorrect"))

    contract = replace(
        original.contract, answer_pattern="^$", answer_values=AnswerValues(("", "1"))
    )
    scope = esolangs.Catalog([replace(original, contract=contract)])
    monkeypatch.setattr(_table, "CATALOG", scope)
    output = scope.bind(REFERENCE).run("").output
    assert output == ""
    description = call_main(["describe", REFERENCE], capsys)
    assert "printed output ( for 0, 1 for 1)" in description
    assert "incorrect" not in description
    assert scope.bind(REFERENCE).read_answer("") == "0"
    assert call_both(["read-answer", REFERENCE], capsys) == ("0\n", "")

    name = "clear\x1b[2J\nreader"
    label = r"clear\x1b[2J\nreader"
    contract = replace(original.contract, note="first line\nsecond line")
    declaration = replace(original, name=name, contract=contract)
    scope = esolangs.Catalog([declaration])
    monkeypatch.setattr(_table, "CATALOG", scope)
    api = scope.bind(REFERENCE)
    output = api.run("+.").output
    assert output == "\x01"
    with pytest.raises(esolangs.ProgramError) as refused:
        api.read_answer(output)
    assert str(refused.value).startswith(f"{name} produced no answer")
    assert _failure(["read-answer", REFERENCE], capsys, code=1, stdin=output) == (
        "",
        str(refused.value).replace(name, label, 1) + "\n",
    )
    generated = api.generate("01")
    answer = api.run(generated, stdin=api.encode_inputs([1])).output
    assert call_both(["read-answer", REFERENCE], capsys, stdin=answer) == ("1\n", "")
    assert (
        json.loads(call_main(["describe", "--json", REFERENCE], capsys))["name"] == name
    )
    _, diagnostic = _failure(["generate", "--bits", "1", REFERENCE, "01"], capsys)
    assert diagnostic.startswith(f"{label} reads its inputs")

    invalid = replace(declaration, contract=replace(contract, answer_pattern="("))
    monkeypatch.setattr(_table, "CATALOG", esolangs.Catalog([invalid]))
    for command in ("describe", "read-answer"):
        _, diagnostic = _failure([command, REFERENCE], capsys)
        assert diagnostic.startswith(f"{label} has an invalid answer pattern")

    invalid = replace(declaration, contract=replace(contract, alphabet=("0", "0")))
    monkeypatch.setattr(_table, "CATALOG", esolangs.Catalog([invalid]))
    for arguments in (["encode-inputs", REFERENCE, "1"], ["describe", REFERENCE]):
        _, diagnostic = _failure(arguments, capsys)
        assert diagnostic.startswith(f"{label} has an invalid input encoding")


@pytest.mark.parametrize("language", one(source_kind="raster"))
def test_run_checks_saved_metadata_before_stdin(
    language, tmp_path, monkeypatch, capsys
) -> None:
    original = LANGUAGES[language]
    schema = esolangs.DialectSchema(language, {"mode": (1, 2)}, {"mode": 1})
    runtime = replace(
        original.runtime, dialect=lambda mode=1: mode, dialect_schema=schema
    )
    declaration = replace(original, runtime=runtime)
    scope = esolangs.Catalog([declaration])
    bound = scope.bind(language)
    source = esolangs.ProgramArtifact(
        esolangs.Raster((((0, 0, 0),),)),
        language,
        settings=bound.settings(mode=1),
        scale=2,
    )
    path = tmp_path / "source.png"
    bound.to_file(source, path)

    def unexpected_read(*_args, **_kwargs):
        pytest.fail("run waited for input despite invalid source metadata")

    monkeypatch.setattr("esolangs.cli.run._read_stdin", unexpected_read)
    monkeypatch.setattr(_table, "CATALOG", scope)
    with monkeypatch.context() as no_image:
        no_image.setattr("esolangs.raster.png._require_image", unexpected_read)
        out, error = _failure(["run", "--set", "mode=2", language, str(path)], capsys)
        assert not out
        assert "mode=1, not 2" in error

    capabilities = replace(runtime.capabilities, supports_scale=False)
    no_scale = replace(declaration, runtime=replace(runtime, capabilities=capabilities))
    monkeypatch.setattr(_table, "CATALOG", esolangs.Catalog([no_scale]))
    out, error = _failure(["run", language, str(path)], capsys)
    assert not out
    assert "scale is only supported" in error


def test_run_reads_and_executes_in_the_same_catalog(tmp_path, monkeypatch, capsys):
    original = LANGUAGES[REFERENCE]
    name = "Scoped runtime"
    shadow = tmp_path / "shadow"
    shadow.mkdir()

    checks = []
    budget = None

    def validate(**choices):
        checks.append(choices)
        if budget is not None and choices:
            raise budget
        monkeypatch.chdir(shadow)

    schema = esolangs.DialectSchema(name, {"mode": (1,)}, {"mode": 1})
    runtime = replace(original.runtime, dialect=validate, dialect_schema=schema)
    declaration = replace(original, name=name, id="scoped_runtime", runtime=runtime)
    scope = esolangs.Catalog([original, declaration])
    monkeypatch.setattr(_table, "CATALOG", scope)
    path = tmp_path / "source"
    path.write_text(",.")
    (shadow / path.name).write_text("+.")
    command = ["run", "-s", "{}", name]
    for spelling in (str(path), path.name):
        monkeypatch.chdir(tmp_path)
        checks.clear()
        assert call_both([*command, spelling], capsys, stdin="Q") == ("Q", "")
        assert checks == [{}, {"mode": 1}]
        assert Path.cwd() == shadow

    monkeypatch.chdir(tmp_path)
    output, diagnostic = _failure([*command, "missing"], capsys)
    assert not output
    assert diagnostic.splitlines()[0].startswith("cannot read missing:")
    assert diagnostic.splitlines()[0].endswith("'missing'")
    assert str(tmp_path) not in diagnostic
    with pytest.raises(esolangs.ArgumentError) as empty:
        scope.bind(name).from_file("")
    assert _failure([*command, ""], capsys) == ("", f"{empty.value}\n")
    invalid_path = "invalid\0path"
    with pytest.raises(esolangs.ProgramError) as invalid:
        scope.bind(name).from_file(invalid_path)
    output, diagnostic = _failure([*command, invalid_path], capsys)
    assert not output
    assert diagnostic.splitlines() == [
        str(invalid.value).replace("\0", r"\x00"),
        *invalid.value.__notes__,
    ]

    output, diagnostic = _failure(["run", "--set", "mode=2", name, "missing"], capsys)
    assert not output
    assert "mode" in diagnostic
    assert "cannot read" not in diagnostic

    missing = path.with_name("missing")
    expected = scope.bind(name).execute(missing, isolated=True)
    assert expected.status == "rejected"
    assert isinstance(expected.error, esolangs.ArgumentError)
    worker_options = [
        ["--isolated"],
        ["--total-timeout", "1"],
        ["--execution-timeout", "1"],
        ["--preparation-timeout", "1"],
        ["--max-output", "1"],
    ]
    if sys.platform == "linux":
        worker_options.append(["--max-memory", "100000000"])
    for options in worker_options:
        assert _failure(["run", *options, name, str(missing)], capsys) == (
            "",
            f"{expected.error}\n",
        )
    combined = scope.bind(name).execute(missing, isolated=True, scale=2, seed=1)
    assert combined.error is not None
    assert str(combined.error) == str(expected.error)
    assert _failure(
        ["run", "--isolated", "--scale", "2", "--seed", "1", name, str(missing)],
        capsys,
    ) == ("", f"{expected.error}\n")
    assert call_both(
        ["run", "--max-steps", "2", name, str(path)], capsys, stdin="Q"
    ) == ("Q", "")
    assert call_both(
        ["run", "--max-output", "1", REFERENCE, str(path)], capsys, stdin="Q"
    ) == ("Q", "")

    budget = esolangs.ExecutionTimeoutError("dialect validation exceeded its budget")
    budget.bound = "preparation_timeout"
    bound = scope.bind(name)
    checked = esolangs.DialectSettings(schema, mode=1)
    checks.clear()
    rejected = bound.execute(path, stdin="Q", isolated=True, settings=checked)
    assert rejected.error is not None
    assert str(rejected.error) == str(expected.error)
    for flags, diagnostic in (
        (["--set", "mode=1"], f"{expected.error}\n"),
        (["--set", "mode=wrong"], "--set mode needs an integer, got 'wrong'\n"),
    ):
        assert _failure(
            ["run", "--isolated", *flags, name, str(path)], capsys, stdin="Q"
        ) == ("", diagnostic)
    assert checks == []
    for flags, settings in (
        ([], None),
        (["--set", "mode=1"], checked),
    ):
        outcome = bound.execute(path, stdin="Q", settings=settings)
        assert outcome.status == "limit"
        assert outcome.bound == "preparation_timeout"
        assert outcome.error is budget
        assert not outcome.observation.output
        with pytest.raises(esolangs.ExecutionTimeoutError) as refused:
            bound.generate("01", settings=settings)
        assert refused.value is budget
        for command in (
            ["run", *flags, name, str(path)],
            ["generate", *flags, name, "01"],
        ):
            assert _failure(command, capsys, code=124, stdin="Q") == (
                "",
                _timeout_text(budget) + "\n",
            )

    _check_run_validates_runtime_before_reading(path, capsys)
    _check_described_input_samples(monkeypatch, capsys, tmp_path)


def _check_run_validates_runtime_before_reading(path, capsys) -> None:
    original = LANGUAGES[REFERENCE]

    class BrokenInput(StringIO):
        def read(self, *_args):
            pytest.fail("run read stdin before rejecting an unavailable runtime")

    stepped = ["--max-steps", "2"]
    command = ["run", REFERENCE, str(path)]
    limits = esolangs.ExecutionLimits(max_steps=2)
    for runtime, options, budget, missing in (
        (
            replace(original.runtime, completion_entrypoint="absent_completion"),
            [],
            None,
            "absent_completion",
        ),
        (
            replace(original.runtime, interpreter="not_an_installed_runtime"),
            stepped,
            limits,
            "not_an_installed_runtime",
        ),
    ):
        catalog = esolangs.Catalog([replace(original, runtime=runtime)])
        api = catalog.bind(original.name)
        expected = api.execute(path, stdin=BrokenInput("Q"), limits=budget)
        assert isinstance(expected.error, esolangs.ProgramError)
        assert missing in str(expected.error)
        with (
            patch.object(_table, "CATALOG", catalog),
            patch.object(sys, "argv", ["esolangs", *command, *options]),
            patch.object(sys, "stdin", BrokenInput("Q")),
            pytest.raises(SystemExit) as exited,
        ):
            main()
        assert exited.value.code == 2
        assert capsys.readouterr() == ("", error_text(expected.error) + "\n")

    runtime = replace(original.runtime, completion_entrypoint="absent_completion")
    catalog = esolangs.Catalog([replace(original, runtime=runtime)])
    with (
        patch.object(_table, "CATALOG", catalog),
        patch(
            "esolangs.cli.run._unbounded_notice",
            side_effect=AssertionError("a step limit already bounds execution"),
        ),
    ):
        assert call_both([*command, *stepped], capsys, stdin="Q") == ("Q", "")


def _check_described_input_samples(monkeypatch, capsys, tmp_path) -> None:
    name = "Forþ"
    declaration = LANGUAGES[name]
    for shape, alphabet, source, answer in (
        ("line_per_bit", ("", "1"), ",,.", "1"),
        ("row_index", (), ",.", "2"),
    ):
        contract = replace(declaration.contract, input_shape=shape, alphabet=alphabet)
        catalog = esolangs.Catalog([replace(declaration, contract=contract)])
        bound = catalog.bind(name)
        monkeypatch.setattr(_table, "CATALOG", catalog)
        description, notices = call_both(["describe", name], capsys)
        assert not notices
        line = next(
            row for row in description.splitlines() if row.startswith("input: ")
        )
        shown = literal_eval(line.split("e.g. ", 1)[1].removesuffix(" for the bits 10"))
        encoded, notices = call_both(["encode-inputs", name, "10"], capsys)
        assert (encoded, notices) == (bound.encode_inputs([1, 0]), "")
        assert shown == (encoded if shape == "line_per_bit" else "2")
        assert bound.run(source, stdin=shown).output == answer
        path = _program(tmp_path, source)
        assert call_both(["run", name, path], capsys, stdin=shown) == (answer, "")


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

    for table, unknown in (("01", "10"), ("10", "01"), ("01", "Brainfuk")):
        _, error = _failure(["generate", table, unknown], capsys)
        assert f"unknown language: {unknown}" in error
        assert "the language comes first" in error
        assert "first: esolangs generate" not in error


@pytest.mark.parametrize("name", ["a; echo x", "--name; echo x"])
def test_generate_swap_suggestion_quotes_metacharacters(
    name: str, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    declaration = replace(LANGUAGES[REFERENCE], name=name, id="scoped_source")
    scope = esolangs.Catalog([declaration])
    monkeypatch.setattr(_table, "CATALOG", scope)
    _, error = _failure(["generate", "--", "01", name], capsys)
    command = error.split("first: ", 1)[1]
    lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    separator = ["--"] if name.startswith("-") else []
    operand = declaration.id if separator else name
    assert list(lexer) == ["esolangs", "generate", *separator, operand, "01"]

    _, error = _failure(["generate", "--plain", "--balance", "--", "01", name], capsys)
    repair = shlex.split(error.split("first: ", 1)[1])
    assert repair == [
        "esolangs",
        "generate",
        "--balance",
        "--plain",
        *separator,
        operand,
        "01",
    ]
    program = call_main(repair[1:], capsys)
    assert scope.bind(name).run(program, stdin="1").output == "1"
