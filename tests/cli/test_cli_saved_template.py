"""Fill portable template bindings through generate and execute the result."""

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
