"""Fill portable template bindings through generate and execute the result."""

import json
import shlex
from pathlib import Path

import pytest

import esolangs
from tests.support.cli_support import _failure, call_both, call_main
from tests.support.pick import first
from tests.support.reference import REFERENCE


@pytest.fixture(scope="module")
def language() -> esolangs.Language:
    return esolangs.Language(
        first(parameterized=True, answer_mode="output", width_effect="wrap")
    )


def test_saved_template_fills_all_xor_rows(
    language, tmp_path, capsys, monkeypatch
) -> None:
    document = call_main(
        ["generate", "--artifact", "--width=7", language.name, "0110"], capsys
    )
    path = tmp_path / "saved xor.json"
    path.write_text(document, encoding="utf-8")
    template = language.from_json(document)
    assert isinstance(template, esolangs.TemplateArtifact)

    def unused(*_args, **_kwargs):
        pytest.fail("saved bindings started truth-table synthesis")

    monkeypatch.setattr("esolangs.operations.generation._generate_checked", unused)
    for row, answer in zip(("00", "01", "10", "11"), "0110", strict=True):
        filled, diagnostic = call_both(
            [
                "generate",
                "--from-template",
                str(path),
                "--bits",
                row,
                "--artifact",
                language.name,
            ],
            capsys,
        )
        assert diagnostic == ""
        assert language.from_json(filled) == template.fill([int(bit) for bit in row])
        output = call_main(["run", "--artifact", language.name, "-"], capsys, filled)
        assert language.read_answer(output) == answer


def test_saved_template_can_stream_native_source(language, capsys) -> None:
    name = language.name
    document = call_main(["generate", "--artifact", name, "0110"], capsys)
    source = call_main(
        ["generate", "--from-template=-", "--bits=01", "--width=7", name],
        capsys,
        document,
    )
    assert source == call_main(
        ["generate", "--bits=01", "--width=7", name, "0110"], capsys
    )
    assert language.read_answer(call_main(["run", name, "-"], capsys, source)) == "1"


def test_saved_template_can_have_zero_bindings(language, capsys) -> None:
    original = language.generate("11")
    assert isinstance(original, esolangs.TemplateArtifact)
    template = esolangs.TemplateArtifact(
        original.fill([0]).source,
        language.name,
        esolangs.TemplateBindings(char=original.bindings.char),
        spans=(),
    )
    filled = call_main(
        ["generate", "--from-template=-", "--bits=", "--artifact", language.name],
        capsys,
        language.to_json(template),
    )
    output = call_main(["run", "--artifact", language.name, "-"], capsys, filled)
    assert language.read_answer(output) == "1"


def test_fill_reports_a_bom_on_saved_template_stdin(language, capsys):
    document = call_main(["generate", "--artifact", language.name, "0110"], capsys)
    output, error = _failure(
        ["generate", "--from-template=-", "--bits=01", language.name],
        capsys,
        stdin="\ufeff" + document,
    )
    assert output == ""
    assert "stdin: portable JSON starts with a UTF-8 BOM" in error
    assert "remove the UTF-8 BOM" in error


@pytest.mark.parametrize(
    ("options", "message"),
    [
        ([REFERENCE], "--from-template requires --bits"),
        (["--bits=1", "--balance", REFERENCE], "cannot be combined"),
        (["--bits=1", "--scale=1", REFERENCE], "cannot be combined"),
        (["--bits=1", REFERENCE, "01"], "unexpected argument"),
    ],
)
def test_saved_template_preflights_before_reading(
    capsys, monkeypatch, options, message
):
    def unread(*_args, **_kwargs):
        pytest.fail("invalid options reached stdin")

    monkeypatch.setattr("esolangs.cli._bounded_source_stdin", unread)
    output, error = _failure(["generate", "--from-template=-", *options], capsys)
    assert not output
    assert message in error


@pytest.mark.parametrize("option", ["--bits=1", "--width", "--artifact"])
def test_saved_template_requires_its_path_before_other_options(capsys, option) -> None:
    output, error = _failure(["generate", "--from-template", option, REFERENCE], capsys)
    assert not output
    assert "--from-template needs a value" in error


def test_saved_template_rejects_wrong_record_owner_and_row(language, capsys) -> None:
    template = call_main(["generate", "--artifact", language.name, "0110"], capsys)
    program = call_main(
        ["generate", "--artifact", "--bits=01", language.name, "0110"], capsys
    )
    for document, name, message in (
        (program, language.name, "requires an unfilled portable template"),
        (template, REFERENCE, "artifact records"),
        (template, language.name, "pass exactly 2 0/1 digits to --bits"),
        ("not JSON", language.name, "invalid portable template in stdin"),
    ):
        output, error = _failure(
            ["generate", "--from-template=-", "--bits=1", name], capsys, stdin=document
        )
        assert not output
        assert message in error


@pytest.mark.parametrize("from_stdin", [False, True])
def test_invalid_portable_bindings_name_the_source(
    language, tmp_path, capsys, from_stdin
) -> None:
    record = json.loads(
        call_main(["generate", "--artifact", language.name, "0110"], capsys)
    )
    record["spans"] = [[]]
    document = json.dumps(record)
    path = tmp_path / "broken template.json"
    if not from_stdin:
        path.write_text(document, encoding="utf-8")
    operand = "-" if from_stdin else str(path)
    source = "stdin" if from_stdin else str(path)
    stdin = document if from_stdin else ""
    for command in (
        ["run", "--artifact", language.name, operand],
        ["generate", f"--from-template={operand}", "--bits=01", language.name],
    ):
        output, error = _failure(command, capsys, stdin=stdin)
        assert output == ""
        assert error.startswith(f"{source}: invalid portable program:")
        assert "template spans must be pairs of offsets" in error


@pytest.mark.parametrize("path", ["-", "--saved 'width=80'.json"])
def test_saved_template_wrong_owner_suggests_a_runnable_retry(
    language, tmp_path, capsys, monkeypatch, path
) -> None:
    document = call_main(["generate", "--artifact", language.name, "0110"], capsys)
    monkeypatch.chdir(tmp_path)
    if path != "-":
        Path(path).write_text(document, encoding="utf-8")
    stdin = document if path == "-" else ""
    options = [f"--from-template={path}", "--bits=01", "--artifact", "--width=80"]
    output, error = _failure(["generate", *options, REFERENCE], capsys, stdin=stdin)
    assert output == ""
    assert "artifact records" in error
    retry = shlex.split(error.split("for example: ", 1)[1])
    assert retry == ["esolangs", "generate", *options, language.name]
    filled = call_main(retry[1:], capsys, stdin=stdin)
    output = call_main(["run", "--artifact", language.name, "-"], capsys, filled)
    assert language.read_answer(output) == "1"


def test_run_points_directly_to_a_fill_command(language, tmp_path, capsys, monkeypatch):
    document = call_main(["generate", "--artifact", language.name, "0110"], capsys)
    monkeypatch.chdir(tmp_path)
    path = "--saved 'width=80'.json"
    Path(path).write_text(document, encoding="utf-8")
    for flags, owner, filename in (
        ([], language.name, path),
        (["--artifact"], language.name, path),
        (["--artifact"], REFERENCE, path),
        ([], language.name, "-"),
    ):
        stdin = document if filename == "-" else ""
        output, error = _failure(
            ["run", *flags, "--", owner, filename], capsys, stdin=stdin
        )
        assert output == ""
        hint = shlex.split(error.split("for example: ", 1)[1])
        assert hint == [
            "esolangs",
            "generate",
            f"--from-template={filename}",
            "--bits",
            "BITS",
            "--artifact",
            language.name,
        ]
        hint[hint.index("BITS")] = "01"
        filled = call_main(hint[1:], capsys, stdin=stdin)
        output = call_main(["run", "--artifact", language.name, "-"], capsys, filled)
        assert language.read_answer(output) == "1"
