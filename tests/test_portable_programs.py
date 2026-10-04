"""Portable source survives disk with its dialect and template conventions."""

import json

import pytest

import esolangs
from esolangs import DialectSettings, Raster
from esolangs.tagged import _Tagged, _Template
from tests.test_public_dialects import CASES


@pytest.mark.medium
@pytest.mark.parametrize(("language", "settings"), CASES)
@pytest.mark.parametrize("balance", [False, True])
def test_disk_round_trip_executes_every_row(tmp_path, language, settings, balance):
    source = esolangs.generate(language, "0110", balance=balance, settings=settings)
    path = tmp_path / "program.json"
    path.write_text(esolangs.dump_program(language, source), encoding="utf-8")
    restored = esolangs.load_program(language, path.read_text(encoding="utf-8"))
    assert restored.settings == settings
    assert type(restored) is type(source)
    if isinstance(source, Raster):
        assert restored.rows == source.rows
    else:
        assert restored == source
    if isinstance(source, _Template):
        assert restored.char == source.char
        assert restored.setters == source.setters
    assert esolangs.evaluate(language, restored, inputs=2) == "0110"


@pytest.mark.medium
@pytest.mark.parametrize("language", ["Alight", "Bitdeque", "Line"])
def test_restored_isolated_execution(language):
    source = esolangs.generate(language, "01", settings=dict(CASES)[language])
    restored = esolangs.load_program(language, esolangs.dump_program(language, source))
    assert esolangs.evaluate(language, restored, inputs=1, isolated=True) == "01"


@pytest.mark.medium
def test_raw_text_preserves_newlines_and_explicit_settings():
    source = "+,.\r\n"
    choices = DialectSettings(eof="unchanged")
    restored = esolangs.load_program(
        "Brainfuck", esolangs.dump_program("Brainfuck", source, settings=choices)
    )
    assert str(restored) == source
    assert restored.settings == choices
    assert esolangs.run("Brainfuck", restored) == "\x01"


@pytest.mark.medium
def test_partial_override_is_saved_and_executes():
    source = _Tagged(
        "+>,+.",
        "brainfuck",
        DialectSettings(cell_modulus=2, tape_size=1, eof="unchanged"),
    )
    restored = esolangs.load_program(
        "Brainfuck",
        esolangs.dump_program(
            "Brainfuck", source, settings=DialectSettings(boundary="wrap")
        ),
    )
    assert restored.settings.options("Brainfuck")["tape_size"] == 1
    assert esolangs.run("Brainfuck", restored) == "\x00"


@pytest.mark.medium
def test_large_integer_round_trip_executes():
    settings = DialectSettings(cell_modulus=1 << 20_000)
    source = _Tagged("+.", "brainfuck", settings)
    document = esolangs.dump_program("Brainfuck", source)
    assert json.loads(document)["settings"]["cell_modulus"] == {
        "integer": hex(1 << 20_000)
    }
    restored = esolangs.load_program("Brainfuck", document)
    assert restored.settings == settings
    assert esolangs.run("Brainfuck", restored) == "\x01"


@pytest.mark.medium
@pytest.mark.parametrize("choices", [None, DialectSettings()])
def test_default_settings_distinction(choices):
    document = esolangs.dump_program("Brainfuck", _Tagged("+.", "brainfuck", choices))
    restored = esolangs.load_program("brainfuck", document)
    assert restored.settings == choices
    assert esolangs.run("Brainfuck", restored) == "\x01"


@pytest.mark.medium
@pytest.mark.parametrize("scale", [1, 2])
def test_raw_png_round_trip_executes(scale):
    settings = DialectSettings(cell_modulus=2, tape_size=2, boundary="wrap")
    source = esolangs.generate("Line", "01", scale=scale, settings=settings)
    raw = Raster.from_png(source.to_png())
    assert raw.settings is None
    restored = esolangs.load_program(
        "Line", esolangs.dump_program("Line", raw, settings=settings)
    )
    assert restored.rows == source.rows
    assert esolangs.evaluate("Line", restored, inputs=1) == "01"


@pytest.mark.medium
def test_filled_template_becomes_portable_text():
    source = esolangs.generate(
        "Bitdeque", "0110", settings=DialectSettings(index_base=1)
    )
    filled = esolangs.instantiate("Bitdeque", source, [1, 0])
    document = esolangs.dump_program("Bitdeque", filled)
    assert json.loads(document)["kind"] == "text"
    assert esolangs.run("Bitdeque", esolangs.load_program("Bitdeque", document)) == "1"


def test_foreign_language_is_rejected():
    source = esolangs.generate(
        "Bitdeque", "0110", settings=DialectSettings(index_base=1)
    )
    with pytest.raises(esolangs.ProgramError):
        esolangs.dump_program("Brainfuck", source)
    with pytest.raises(esolangs.ProgramError, match="program language"):
        esolangs.load_program("Brainfuck", esolangs.dump_program("Bitdeque", source))


@pytest.mark.parametrize(
    "document", ["{", "null", "[]", "{}", '{"format":1,"format":2}']
)
def test_invalid_json(document):
    with pytest.raises(esolangs.ProgramError):
        esolangs.load_program("Brainfuck", document)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("format", "other"),
        ("version", 2),
        ("version", True),
        ("source", 1),
        ("kind", "other"),
        ("kind", []),
        ("settings", []),
        ("settings", {"eof": False}),
        ("settings", {"tape_size": {"integer": 1}}),
        ("settings", {"tape_size": {"integer": "10"}}),
        ("settings", {"tape_size": {"integer": "0x!"}}),
        ("settings", {"tape_size": {"integer": "0x1", "other": 1}}),
        ("settings", {"tape_size": {}}),
        ("settings", {"boundary": "wrap"}),
        ("settings", {"tape_size": {"integer": "-0x1"}}),
        ("extra", None),
    ],
)
def test_invalid_fields(field, value):
    document = json.loads(esolangs.dump_program("Brainfuck", "+."))
    document[field] = value
    with pytest.raises(esolangs.ProgramError):
        esolangs.load_program("Brainfuck", json.dumps(document))


@pytest.mark.parametrize("value", ["!", "abcd", "é"])
def test_invalid_png(value):
    document = json.loads(
        esolangs.dump_program("Line", esolangs.generate("Line", "01"))
    )
    document["source"] = value
    with pytest.raises(esolangs.ProgramError):
        esolangs.load_program("Line", json.dumps(document))


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("char", 1),
        ("char", ""),
        ("char", "$$"),
        ("char", "?"),
        ("setters", None),
        ("setters", [1]),
        ("setters", [["x"]]),
        ("setters", [["x", 1]]),
        ("setters", [["x", "yy"]]),
        ("setters", []),
    ],
)
def test_invalid_template_fields(field, value):
    document = json.loads(
        esolangs.dump_program("Bitdeque", esolangs.generate("Bitdeque", "0110"))
    )
    document[field] = value
    with pytest.raises(esolangs.ProgramError):
        esolangs.load_program("Bitdeque", json.dumps(document))


def test_document_argument_and_invalid_settings():
    with pytest.raises(esolangs.ArgumentError, match="JSON string"):
        esolangs.load_program("Brainfuck", b"{}")
    with pytest.raises(esolangs.ArgumentError):
        esolangs.dump_program("Brainfuck", "+.", settings={})


def test_source_kind_cannot_change_language_contract():
    document = json.loads(
        esolangs.dump_program("Line", esolangs.generate("Line", "01"))
    )
    document["language"] = "brainfuck"
    with pytest.raises(esolangs.ProgramError):
        esolangs.load_program("Brainfuck", json.dumps(document))


def test_template_kind_requires_parameterized_language():
    document = json.loads(esolangs.dump_program("Brainfuck", "+."))
    document.update(kind="template", char="$", setters=[])
    with pytest.raises(esolangs.ProgramError, match="template char does not match"):
        esolangs.load_program("Brainfuck", json.dumps(document))


@pytest.mark.medium
def test_bound_language_round_trip():
    language = esolangs.Language("Bitdeque")
    source = language.generate("0110", settings=DialectSettings(index_base=1))
    document = language.dump_program(source)
    restored = language.load_program(document)
    assert language.evaluate(restored, inputs=2) == "0110"
    filled = language.instantiate(source, [1, 0])
    document = language.dump_program(filled, settings=DialectSettings(index_base=1))
    assert language.run(language.load_program(document)) == "1"
