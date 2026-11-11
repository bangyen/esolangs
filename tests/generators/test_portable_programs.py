"""Portable source survives disk with its dialect and template conventions."""

import json

import pytest

import esolangs
from esolangs import ProgramArtifact
from tests.support.dialect_support import CASES
from tests.support.evaluation import _evaluate
from tests.support.reference import REFERENCE


@pytest.mark.medium
@pytest.mark.parametrize("language", [name for name, _ in CASES])
def test_restored_isolated_execution(language) -> None:
    choices = dict(CASES)[language]
    source = esolangs.generate(language, "01", settings=choices)
    restored = esolangs.load_program(language, esolangs.dump_program(language, source))
    assert restored.settings == source.settings == choices
    assert _evaluate(language, restored, inputs=1, isolated=True) == "01"


@pytest.mark.medium
@pytest.mark.parametrize("choices", [None, esolangs.Language("brainfuck").settings()])
def test_default_settings_distinction(choices) -> None:
    document = esolangs.dump_program(
        REFERENCE, ProgramArtifact("+.", REFERENCE, choices)
    )
    restored = esolangs.load_program(REFERENCE, document)
    assert restored.settings == choices
    assert esolangs.run("Brainfuck", restored).output == "\x01"
    empty = ProgramArtifact(
        esolangs.CompressedText.from_chunks(("",)), REFERENCE, choices
    )
    document = esolangs.dump_program(REFERENCE, empty)
    restored = esolangs.load_program(REFERENCE, document)
    assert restored == empty
    assert esolangs.run(REFERENCE, restored).output == ""
    missing_limits = json.loads(document)
    del missing_limits["limits"]
    with pytest.raises(esolangs.ProgramError, match="missing fields"):
        esolangs.load_program(REFERENCE, json.dumps(missing_limits))
    damaged = json.loads(document)
    damaged["source"] = ""
    with pytest.raises(esolangs.ProgramError, match="no gzip member"):
        esolangs.load_program(REFERENCE, json.dumps(damaged))


@pytest.mark.parametrize(
    "document", ["{", "null", "[]", "{}", '{"format":1,"format":2}']
)
def test_invalid_json(document) -> None:
    with pytest.raises(esolangs.ProgramError):
        esolangs.load_program("Brainfuck", document)
    for duplicated in ('{"format":1,"format":1}', '{"settings":{"key":1,"key":2}}'):
        with pytest.raises(esolangs.ProgramError, match="duplicate field"):
            esolangs.load_program("Brainfuck", duplicated)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("format", "other"),
        ("version", 2),
        ("source", 1),
        ("kind", "other"),
        ("settings", []),
        ("settings", {"eof": False}),
        ("settings", {"tape_size": {"integer": "0x!"}}),
        ("settings", {"tape_size": {}}),
        ("settings", {"boundary": "wrap"}),
        ("extra", None),
    ],
)
def test_invalid_fields(field, value) -> None:
    document = json.loads(esolangs.dump_program("Brainfuck", "+."))
    document[field] = value
    with pytest.raises(esolangs.ProgramError):
        esolangs.load_program("Brainfuck", json.dumps(document))


def test_document_argument_and_invalid_settings() -> None:
    with pytest.raises(esolangs.ArgumentError, match="JSON string"):
        esolangs.load_program("Brainfuck", b"{}")
    with pytest.raises(esolangs.ArgumentError):
        esolangs.dump_program("Brainfuck", "+.", settings={})

    from tests.support.pick import first

    language = first(source_kind="raster", boolean_generator=True)
    source = esolangs.generate(
        language, "01", settings=esolangs.Language(language).settings()
    )
    document = json.loads(esolangs.dump_program(language, source))
    document["settings"] = None
    with pytest.raises(esolangs.ProgramError, match="conflicting PNG"):
        esolangs.load_program(language, json.dumps(document))


def test_template_kind_requires_parameterized_language() -> None:
    document = json.loads(esolangs.dump_program("Brainfuck", "+."))
    document.update(kind="template", char="$", setters=[], spans=[])
    with pytest.raises(esolangs.ProgramError, match="template char does not match"):
        esolangs.load_program("Brainfuck", json.dumps(document))
